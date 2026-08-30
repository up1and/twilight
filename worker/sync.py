"""
Himawari-9 Data Synchronization Script
Syncs latest AHI-L1b-FLDK data from NOAA S3 to local MinIO
"""
import sys
import time

import boto3
import botocore
import requests

from io import BytesIO

from utils import logger
from config import endpoint, access_key, secret_key, secure

# Configuration
noaa_bucket = "noaa-himawari9"
local_bucket = "raw"


class SyncClient:
    """Client for communicating with the himawari sync server"""

    def __init__(self, server_url, auth_key=None):
        self.server_url = server_url.rstrip("/")
        self.auth_key = auth_key
        self.session = requests.Session()

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.auth_key}"} if self.auth_key else {}

    def get_sync(self, target_time):
        """Get current sync progress from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/syncs/{target_time.isoformat()}",
                params={"source": "himawari"},
                headers=self._auth_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "files": data.get("files", 0),
                    "size": data.get("size", 0),
                    "status": data.get("status", "pending")
                }
            elif response.status_code == 404:
                # No existing record, return defaults
                return {"files": 0, "size": 0, "status": "pending"}
            else:
                logger.warning(f"Failed to get sync progress: {response.status_code} {response.text}")
                return {"files": 0, "size": 0, "status": "pending"}
                
        except Exception as e:
            logger.error(f"Error getting sync progress: {e}")
            return {"files": 0, "size": 0, "status": "pending"}

    def update_sync(self, target_time, status=None, files=None, size=None):
        """Update sync progress to server"""
        try:
            # Validate that at least one field is provided
            if status is None and files is None and size is None:
                raise ValueError("At least one of status, files, or size must be provided")
            
            # Build data payload with only non-None values
            data = {
                "timestamp": target_time.isoformat(),
                "source": "himawari",
                "initiator": "sync"
            }
            
            if status is not None:
                data["status"] = status
            if files is not None:
                data["files"] = files
            if size is not None:
                data["size"] = size
                
            response = self.session.put(
                f"{self.server_url}/api/syncs",
                json=data,
                headers=self._auth_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to report sync progress: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"Error reporting sync progress: {e}")

    def create_sync(self, target_time):
        """Create a pending sync record"""
        try:
            data = {
                "timestamp": target_time.isoformat(),
                "source": "himawari",
                "initiator": "worker"
            }
            
            response = self.session.post(
                f"{self.server_url}/api/syncs",
                json=data,
                headers=self._auth_headers(),
                timeout=10
            )
            
            if response.status_code != 201:
                logger.warning(f"Failed to create pending sync: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"Error creating pending sync: {e}")


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
        bar = "#" * filled_length + " " * (self.bar_width - filled_length)

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
        sys.stdout.write("\n")
        sys.stdout.flush()


class SyncProcessor:
    """Synchronizes Himawari-9 data from NOAA S3 to local MinIO"""

    def __init__(self, sync_client: SyncClient):
        # Initialize NOAA S3 client (anonymous access)
        self.noaa_s3 = boto3.client(
            "s3",
            config=botocore.config.Config(signature_version=botocore.UNSIGNED)
        )

        # Initialize local MinIO client using boto3
        protocol = "https" if secure else "http"
        self.minio_s3 = boto3.client(
            "s3",
            endpoint_url=f"{protocol}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1"  # MinIO requires a region
        )

        self.sync_client = sync_client

        # Ensure local bucket exists
        try:
            self.minio_s3.head_bucket(Bucket=local_bucket)
        except:
            self.minio_s3.create_bucket(Bucket=local_bucket)

    def list_files(self, s3_client, bucket, time_prefix):
        """List files in a bucket with given prefix and extension"""
        try:
            files = []
            paginator = s3_client.get_paginator("list_objects_v2")
            
            page_iterator = paginator.paginate(
                Bucket=bucket,
                Prefix=time_prefix
            )
            
            for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        if obj["Key"].endswith(".DAT.bz2"):
                            files.append(obj["Key"])

            return files

        except Exception as e:
            logger.error(f"Error listing files in {bucket}: {e}")
            return []

    def sync_file(self, object_name):
        """Copy file from NOAA S3 to local MinIO with progress tracking.

        Returns the synced file size, raises if the transfer fails.
        """
        # Get file info from NOAA S3
        response = self.noaa_s3.head_object(Bucket=noaa_bucket, Key=object_name)
        file_size = response["ContentLength"]

        filename = object_name.split("/")[-1]

        # Create progress bar
        progress_bar = ProgressBar(filename, file_size)

        # Create BytesIO stream for streaming upload
        stream = BytesIO()

        try:
            # Download from NOAA S3 in chunks and write to stream
            chunk_size = 1024 * 1024  # 1MB chunks

            response = self.noaa_s3.get_object(Bucket=noaa_bucket, Key=object_name)

            with response["Body"] as body:
                while True:
                    chunk = body.read(chunk_size)
                    if not chunk:
                        break

                    stream.write(chunk)
                    progress_bar.update(len(chunk))

            progress_bar.close()

            # Reset stream position for upload
            stream.seek(0)

            # Upload to local MinIO
            self.minio_s3.put_object(
                Bucket=local_bucket,
                Key=object_name,
                Body=stream,
                ContentLength=file_size
            )

            return file_size
        finally:
            stream.close()
    
    def sync(self, target_time):
        """Sync specific time folder"""
        # Build time folder path
        time_folder = f"AHI-L1b-FLDK/{target_time.strftime('%Y/%m/%d/%H%M')}"

        # Get current progress from server to maintain cumulative data
        current_progress = self.sync_client.get_sync(target_time)
        total_size = current_progress["size"]
        status = "pending"

        # List files in NOAA S3
        noaa_files = self.list_files(self.noaa_s3, noaa_bucket, time_folder)
        if not noaa_files:
            logger.warning(f"No files found in NOAA S3 for {time_folder}")
            return status

        existing_files = set(self.list_files(self.minio_s3, local_bucket, time_folder))
        file_count = len(existing_files)
        failed_files = []

        # Find files that need to be synced
        files_to_sync = [f for f in noaa_files if f not in existing_files]

        if files_to_sync:
            logger.info(f"Need to sync {len(files_to_sync)} files for {time_folder}")
            status = "running"

            # Sync missing files; failed ones are left out of the counts and
            # retried by the next sync run for this time slot
            for object_name in files_to_sync:
                try:
                    file_size = self.sync_file(object_name)
                except Exception as e:
                    logger.error(f"Error syncing {object_name}: {e}")
                    failed_files.append(object_name)
                    continue

                total_size += file_size
                file_count += 1
                self.sync_client.update_sync(target_time, status=status, files=file_count, size=total_size)

            if failed_files:
                logger.warning(
                    f"{len(failed_files)}/{len(files_to_sync)} files failed to sync for {time_folder}"
                )

        if file_count >= 160 and not failed_files:
            status = "completed"

        self.sync_client.update_sync(target_time, status=status)
        return status
