"""
RQ tasks for scheduled maintenance jobs
"""
import logging
from flask import current_app
from extensions import rq
from utils import delete_minio_objects

logger = logging.getLogger(__name__)


def _run_prune(manager, client, bucket, label):
    """Generic helper to prune expired items from Redis and MinIO"""
    stats = {"deleted": 0, "errors": 0}
    try:
        expired_items = manager.get_expired()
        for item in expired_items:
            try:
                # Delete file from MinIO
                errors = delete_minio_objects(client, bucket, item.filepath)
                if errors:
                    logger.warning(f"[{label}] MinIO deletion warnings for {item.filepath}: {errors}")
                
                # Delete from Redis
                if hasattr(manager, 'delete_task'):
                    manager.delete_task(item.task_id)
                else:
                    manager.delete_sync(item.source, item.timestamp)
                stats["deleted"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[{label}] Failed to prune {item.filepath}: {e}")
                
        logger.info(f"[{label}] Finished. Success: {stats['deleted']}, Errors: {stats['errors']}")
    except Exception as e:
        logger.exception(f"[{label}] Critical failure during prune job: {e}")
    
    return stats

@rq.job
def prune_tasks():
    """Prune expired tasks and their composite TIFF files"""
    return _run_prune(current_app.task_manager, current_app.client, "himawari", "tasks")

@rq.job
def prune_syncs():
    """Prune expired sync records and their raw HSD files"""
    return _run_prune(current_app.sync_manager, current_app.client, "raw", "syncs")
