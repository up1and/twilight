"""
Himawari-9 Data Synchronization Script
Syncs latest AHI-L1b-FLDK data from NOAA S3 to local MinIO
"""
from minio import Minio
from utils import logger
from client import get_minio_client

# Configuration
noaa_bucket = 'noaa-himawari9'
local_bucket = 'raw'

class HimawariDataSync:
    """Synchronizes Himawari-9 data from NOAA S3 to local MinIO"""

    def __init__(self):
        # Initialize NOAA S3 client (anonymous access)
        self.noaa = Minio(
            's3.amazonaws.com',
            secure=True
        )

        # Initialize local MinIO client
        self.client = get_minio_client()

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
            objects = client.list_objects(bucket, prefix=time_prefix, recursive=True)

            for obj in objects:
                if obj.object_name.endswith('.DAT.bz2'):
                    files.append(obj.object_name)

            return files

        except Exception as e:
            logger.error(f"Error listing files in {bucket}: {e}")
            return []

    def sync_file(self, file_key):
        """Copy file from NOAA S3 to local MinIO"""
        try:
            # Download from NOAA and upload to local
            # Get object from NOAA
            response = self.noaa.get_object(noaa_bucket, file_key)

            # Upload to local MinIO
            self.client.put_object(
                bucket_name=local_bucket,
                object_name=file_key,
                data=response,
                length=-1,  # Unknown length, let MinIO handle it
                part_size=10*1024*1024  # 10MB parts
            )

            logger.info(f"Successfully synced: {file_key}")
            return True

        except Exception as e:
            logger.error(f"Error syncing {file_key}: {e}")
            return False
    
    def sync(self, target_time):
        """Sync specific time folder"""
        # Build time folder path
        time_folder = f"AHI-L1b-FLDK/{target_time.strftime('%Y/%m/%d/%H%M')}"

        # List files in NOAA S3 and local MinIO
        noaa_files = self.list_files(self.noaa, noaa_bucket, time_folder)
        if not noaa_files:
            logger.warning(f"No files found in {time_folder}")
            return False

        existing_files = set(self.list_files(self.client, local_bucket, time_folder))

        # Find files that need to be synced
        files_to_sync = [f for f in noaa_files if f not in existing_files]

        if files_to_sync:
            logger.info(f"Need to sync {len(files_to_sync)} files for {time_folder}")
            # Sync missing files
            success_count = 0
            for file_key in files_to_sync:
                if self.sync_file(file_key):
                    success_count += 1

            logger.info(f"Sync completed: {success_count}/{len(files_to_sync)} files for {time_folder}")

        # Check if we have 160 files locally
        local_count = self.count_local_files(time_folder)
        logger.info(f"Local file count for {time_folder}: {local_count}")

        return local_count >= 160
