"""
Himawari-9 Data Synchronization Script
Syncs latest AHI-L1b-FLDK data from NOAA S3 to local MinIO
"""
import sys
import time
import requests

import s3fs

from io import BytesIO

from utils import logger
from client import get_minio_client

# Configuration
noaa_bucket = 'noaa-himawari9'
local_bucket = 'raw'


class SyncClient:
    """Client for communicating with the himawari sync server"""

    def __init__(self, server_url):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()

    def get_sync(self, target_time):
        """Get current himawari sync progress from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/raws/{target_time.isoformat()}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'files': data.get('files', 0),
                    'size': data.get('size', 0),
                    'status': data.get('status', 'pending')
                }
            elif response.status_code == 404:
                # No existing record, return defaults
                return {'files': 0, 'size': 0, 'status': 'pending'}
            else:
                logger.warning(f"Failed to get himawari sync progress: {response.status_code} {response.text}")
                return {'files': 0, 'size': 0, 'status': 'pending'}
                
        except Exception as e:
            logger.error(f"Error getting himawari sync progress: {e}")
            return {'files': 0, 'size': 0, 'status': 'pending'}

    def update_sync(self, target_time, status=None, files=None, size=None):
        """Update himawari sync progress to server"""
        try:
            # Validate that at least one field is provided
            if status is None and files is None and size is None:
                raise ValueError("At least one of status, files, or size must be provided")
            
            # Build data payload with only non-None values
            data = {'timestamp': target_time.isoformat()}
            
            if status is not None:
                data['status'] = status
            if files is not None:
                data['files'] = files
            if size is not None:
                data['size'] = size
                
            response = self.session.put(
                f"{self.server_url}/api/raws",
                json=data,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to report himawari sync progress: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"Error reporting himawari sync progress: {e}")

    def create_sync(self, target_time):
        """Create a pending himawari sync record"""
        try:
            data = {
                'timestamp': target_time.isoformat()
            }
            
            response = self.session.post(
                f"{self.server_url}/api/raws",
                json=data,
                timeout=10
            )
            
            if response.status_code != 201:
                logger.warning(f"Failed to create pending himawari sync: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"Error creating pending himawari sync: {e}")


class ProgressBar:
    """Custom progress bar with specified format"""

    def __init__(self, filename, total_size):
        self.filename = filename
        self.total_size = total_size
        self.downloaded = 0
        self.start_time = time.time()
        self.bar_width = 25

    def update(self, chunk_size):
        self.downloaded += chunk_size
        self._display()

    def _display(self):
        # Calculate percentage
        percentage = int((self.downloaded / self.total_size) * 100)

        # Calculate progress bar
        filled_length = int(self.bar_width * self.downloaded // self.total_size)
        bar = '#' * filled_length + ' ' * (self.bar_width - filled_length)

        # Calculate speed and ETA
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            speed = self.downloaded / elapsed_time
            speed_mb = speed / (1024 * 1024)

            if speed > 0:
                eta_seconds = (self.total_size - self.downloaded) / speed
                eta_minutes = int(eta_seconds // 60)
                eta_seconds = int(eta_seconds % 60)
                eta = f"{eta_minutes:02d}:{eta_seconds:02d}"
            else:
                eta = "--:--"
        else:
            speed_mb = 0
            eta = "--:--"

        # Format size
        size_mb = self.downloaded / (1024 * 1024)

        # Display progress
        progress_line = f"\r{self.filename} {percentage}% [{bar}] {size_mb:.0f}MB {speed_mb:.1f}MB/s ETA: {eta}"
        sys.stdout.write(progress_line)
        sys.stdout.flush()

    def close(self):
        sys.stdout.write('\n')
        sys.stdout.flush()


class SyncProcessor:
    """Synchronizes Himawari-9 data from NOAA S3 to local MinIO"""

    def __init__(self, sync_client: SyncClient):
        # Initialize NOAA S3 filesystem (anonymous access)
        self.noaa_fs = s3fs.S3FileSystem(anon=True)

        # Initialize local MinIO client
        self.client = get_minio_client()

        self.sync_client = sync_client

        # Ensure local bucket exists
        if not self.client.bucket_exists(local_bucket):
            self.client.make_bucket(local_bucket)

    def count_local_files(self, time_folder):
        """Count files in local bucket for given time folder"""
        try:
            files = self.list_files(self.client, local_bucket, time_folder)
            return len(files)
        except Exception as e:
            logger.error(f"Error counting local files in {time_folder}: {e}")
            return 0

    def list_files(self, client, bucket, time_prefix):
        """List files in a bucket with given prefix and extension"""
        try:
            files = []

            # Check if it's s3fs or minio client
            if isinstance(client, s3fs.S3FileSystem):
                # s3fs client
                path = f"{bucket}/{time_prefix}"
                try:
                    file_list = client.ls(path, detail=False)
                    for file_path in file_list:
                        if file_path.endswith('.DAT.bz2'):
                            # Remove bucket name from path to get object key
                            object_key = file_path.replace(f"{bucket}/", "")
                            files.append(object_key)
                except FileNotFoundError:
                    # Directory doesn't exist
                    pass
            else:
                # minio client
                objects = client.list_objects(bucket, prefix=time_prefix, recursive=True)
                for obj in objects:
                    if obj.object_name.endswith('.DAT.bz2'):
                        files.append(obj.object_name)

            return files

        except Exception as e:
            logger.error(f"Error listing files in {bucket}: {e}")
            return []

    def sync_file(self, object_name):
        """Copy file from NOAA S3 to local MinIO with progress tracking"""
        try:
            # Get file info from s3fs
            s3_path = f"{noaa_bucket}/{object_name}"
            file_info = self.noaa_fs.info(s3_path)
            file_size = file_info['size']

            filename = object_name.split('/')[-1]

            # Create progress bar
            progress_bar = ProgressBar(filename, file_size)

            # Create BytesIO stream for streaming upload
            stream = BytesIO()

            # Download from NOAA S3 in chunks and write to stream
            chunk_size = 1024 * 1024  # 1MB chunks

            with self.noaa_fs.open(s3_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    stream.write(chunk)
                    progress_bar.update(len(chunk))

            progress_bar.close()

            # Reset stream position for upload
            stream.seek(0)

            # Upload to local MinIO using streaming
            self.client.put_object(
                bucket_name=local_bucket,
                object_name=object_name,
                data=stream,
                length=file_size,
                part_size=10*1024*1024  # 10MB parts
            )

            stream.close()

            return file_size

        except Exception as e:
            logger.error(f"Error syncing {object_name}: {e}")
            return 0
    
    def sync(self, target_time):
        """Sync specific time folder"""
        # Build time folder path
        time_folder = f"AHI-L1b-FLDK/{target_time.strftime('%Y/%m/%d/%H%M')}"

        # Get current progress from server to maintain cumulative data
        current_progress = self.sync_client.get_sync(target_time)
        total_size = current_progress['size']
        status = 'pending'

        # List files in NOAA S3
        noaa_files = self.list_files(self.noaa_fs, noaa_bucket, time_folder)
        if not noaa_files:
            logger.warning(f"No files found in NOAA S3 for {time_folder}")
            return status

        existing_files = set(self.list_files(self.client, local_bucket, time_folder))
        file_count = len(existing_files)

        # Find files that need to be synced
        files_to_sync = [f for f in noaa_files if f not in existing_files]

        if files_to_sync:
            logger.info(f"Need to sync {len(files_to_sync)} files for {time_folder}")
            # Sync missing files
            for i, object_name in enumerate(files_to_sync):
                file_size = self.sync_file(object_name)
                total_size += file_size
                file_count += 1
                status = 'running'
                self.sync_client.update_sync(target_time, status=status, files=file_count, size=total_size)

        if file_count >= 160:
            status = 'done'
            
        self.sync_client.update_sync(target_time, status=status)
        return status
