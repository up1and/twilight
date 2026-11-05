"""
RQ jobs: every function that runs on a worker, in one place.

Two groups live here:

* **Scheduled maintenance** — ``prune_tasks`` / ``prune_syncs``, registered on
  the ``maintenance`` queue by ``flask rq cron``.
* **Snapshot rendering** — ``render_snapshot`` plus its queue helpers, driven
  by ``POST /api/snapshots`` on the ``snapshots`` queue.

Job functions must stay importable from a worker process, so keep module-level
imports to things that are safe outside a request context.
"""
import datetime
import logging
import uuid

from flask import current_app
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus

from extensions import rq
from snapshot import (
    cog_exists,
    create_series_snapshot,
    create_single_snapshot,
    estimate_snapshot_size,
    missing_cogs,
)
from utils import delete_minio_objects, parse_iso_timestamp

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


def get_snapshot_queue(name="snapshots"):
    """Return the RQ queue used for snapshot rendering"""
    return Queue(name, connection=rq.connection)


def find_missing_composites(client, composite, start_time, timedelta_minutes=None):
    """
    Timestamps in the requested range whose composite COG does not exist yet.

    Composite files are pruned after TASK_EXPIRE_DAYS, so a range older than
    that can never be rendered. Checking up front keeps that failure out of the
    render job, where it would otherwise only surface after a long wait.

    Args:
        client: MinIO client
        composite: Composite name
        start_time: Start datetime
        timedelta_minutes: Optional timelapse duration in minutes

    Returns:
        list[datetime.datetime]: Missing timestamps, oldest first.
    """
    if not timedelta_minutes:
        return [] if cog_exists(client, composite, start_time) else [start_time]

    end_time = start_time + datetime.timedelta(minutes=timedelta_minutes)
    return missing_cogs(client, composite, start_time, end_time)


def render_snapshot(composite, timestamp, bbox, zoom, timedelta_minutes=None):
    """
    Render a snapshot (or timelapse) at the user's map zoom level.

    Runs inside an RQ worker, which supplies the Flask app context. Every
    frame's COG must already exist: the caller checks this before queueing, so
    the job never waits on composite processing.

    Args:
        composite: Composite name
        timestamp: ISO 8601 timestamp
        bbox: [min_lng, min_lat, max_lng, max_lat]
        zoom: Map zoom level the bbox was captured at
        timedelta_minutes: Optional duration in minutes for a timelapse

    Returns:
        dict: Render result, with download_url once the file exists.
    """
    width, height = estimate_snapshot_size(bbox, zoom=zoom)
    start_time = parse_iso_timestamp(timestamp)
    client = current_app.client

    if timedelta_minutes:
        end_time = start_time + datetime.timedelta(minutes=timedelta_minutes)
        result = create_series_snapshot(
            client, composite, start_time, end_time, bbox,
            width=width, height=height,
        )
    else:
        result = create_single_snapshot(
            client, composite, start_time, bbox,
            width=width, height=height,
        )

    if not isinstance(result, dict):
        return result

    result = dict(result)
    object_name = result.pop("object_name", None)
    if object_name:
        result["download_url"] = f"/snapshots/{object_name}"
    return result


def enqueue_snapshot_job(composite, timestamp, bbox, zoom, timedelta_minutes=None):
    """
    Queue a snapshot render and return the RQ job.

    Returns:
        rq.job.Job: The enqueued job.
    """
    description = f"snapshot {composite} @ {timestamp} z{zoom}"
    if timedelta_minutes:
        description += f" (+{timedelta_minutes}m)"

    return get_snapshot_queue().enqueue(
        render_snapshot,
        composite,
        timestamp,
        bbox,
        zoom,
        timedelta_minutes,
        job_id=uuid.uuid4().hex,
        description=description,
        # Keep finished jobs pollable for an hour. Both TTLs are set
        # explicitly because RQ's failure_ttl default is one year, which
        # would leave failed renders sitting in Redis indefinitely.
        result_ttl=3600,
        failure_ttl=3600,
    )


def get_snapshot_job(job_id):
    """
    Fetch a snapshot job by id.

    Returns:
        rq.job.Job | None: The job, or None when it does not exist.
    """
    try:
        return Job.fetch(job_id, connection=rq.connection)
    except NoSuchJobError:
        return None


def serialize_job_status(job):
    """
    Build the API payload for a snapshot job.

    A job is a resource, so its status is reported in the body and the HTTP
    status stays 200; only a missing job id is a 404.

    Args:
        job: rq.job.Job

    Returns:
        dict: ``{job_id, status, download_url?, message?}``
    """
    status = job.get_status(refresh=True)

    if status in (JobStatus.FINISHED, JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELED):
        if status == JobStatus.FINISHED:
            result = job.result
            if not isinstance(result, dict):
                return {
                    "job_id": job.id,
                    "status": "failed",
                    "message": "Snapshot job returned an unexpected result",
                }
            return {"job_id": job.id, **result}

        latest = job.latest_result()
        return {
            "job_id": job.id,
            "status": "failed",
            "message": (latest.exc_string if latest else None) or f"Snapshot job {status}",
        }

    # Anything RQ has not settled yet is still pollable. Only STARTED is
    # reported separately; every other unfinished status reads as pending.
    if status == JobStatus.STARTED:
        return {"job_id": job.id, "status": "running"}
    return {"job_id": job.id, "status": "pending"}
