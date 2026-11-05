"""
Tests for RQ job helpers in server/tasks.py
"""
import datetime
from unittest.mock import Mock, patch

import pytest
from rq.job import JobStatus

from server.tasks import (
    find_missing_composites,
    get_snapshot_queue,
    render_snapshot,
    serialize_job_status,
)


def make_job(status, result=None, exc_string=None):
    """Build a mock RQ job with the given status and result"""
    job = Mock()
    job.id = "job-123"
    job.get_status.return_value = status
    job.result = result
    latest = Mock()
    latest.exc_string = exc_string
    job.latest_result.return_value = latest
    return job


class TestFindMissingComposites:
    """Up-front COG checks that keep failures out of the render job"""

    def test_single_snapshot_present(self):
        client = Mock()
        start = datetime.datetime(2025, 1, 15, 12, tzinfo=datetime.timezone.utc)
        assert find_missing_composites(client, "ir_clouds", start) == []

    def test_single_snapshot_missing(self):
        client = Mock()
        client.stat_object.side_effect = Exception("missing")
        start = datetime.datetime(2025, 1, 15, 12, tzinfo=datetime.timezone.utc)
        assert find_missing_composites(client, "ir_clouds", start) == [start]

    def test_timelapse_reports_gaps(self):
        client = Mock()

        def stat_object(bucket, name):
            if name.endswith("1210.tif"):
                raise Exception("missing")

        client.stat_object.side_effect = stat_object
        start = datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.timezone.utc)

        result = find_missing_composites(client, "ir_clouds", start, timedelta_minutes=20)

        assert [ts.strftime("%H%M") for ts in result] == ["1210"]

    def test_timelapse_all_present(self):
        client = Mock()
        start = datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.timezone.utc)
        assert find_missing_composites(client, "ir_clouds", start, timedelta_minutes=60) == []


class TestRenderSnapshot:
    """The RQ job body"""

    @patch("server.tasks.create_single_snapshot")
    def test_renders_single_snapshot_at_zoom_size(self, create_single):
        create_single.return_value = {
            "status": "completed",
            "object_name": "image/a.png",
            "filename": "a.png",
        }

        app = Mock()
        app.client = "minio-client"

        with patch("server.tasks.current_app", app):
            result = render_snapshot("ir_clouds", "2025-01-15T12:00:00Z",
                                     [100, 20, 140, 50], 6)

        assert result["download_url"] == "/snapshots/image/a.png"
        kwargs = create_single.call_args.kwargs
        # z6 for a 40x30 degree bbox is 1821x1707
        assert kwargs == {"width": 1821, "height": 1707}

    @patch("server.tasks.create_series_snapshot")
    def test_renders_timelapse_when_timedelta_given(self, create_series):
        create_series.return_value = {
            "status": "completed",
            "object_name": "video/a.mp4",
            "filename": "a.mp4",
        }

        app = Mock()
        app.client = "minio-client"

        with patch("server.tasks.current_app", app):
            result = render_snapshot("true_color", "2025-01-15T12:00:00Z",
                                     [100, 20, 140, 50], 6, timedelta_minutes=60)

        assert result["download_url"] == "/snapshots/video/a.mp4"
        start_time, end_time = create_series.call_args[0][2:4]
        assert (end_time - start_time).total_seconds() == 3600

    @patch("server.tasks.create_single_snapshot")
    def test_failed_render_has_no_download_url(self, create_single):
        create_single.return_value = {
            "status": "failed",
            "message": "Error creating snapshot: boom",
        }

        app = Mock()
        app.client = "minio-client"

        with patch("server.tasks.current_app", app):
            result = render_snapshot("ir_clouds", "2025-01-15T12:00:00Z",
                                     [100, 20, 140, 50], 6)

        assert result["status"] == "failed"
        assert "download_url" not in result


class TestSerializeJobStatus:
    """Polling payload: {job_id, status, download_url?, message?}"""

    def test_pending(self):
        assert serialize_job_status(make_job(JobStatus.QUEUED)) == {
            "job_id": "job-123", "status": "pending",
        }

    def test_started_reports_running(self):
        assert serialize_job_status(make_job(JobStatus.STARTED))["status"] == "running"

    def test_deferred_and_scheduled_stay_pending(self):
        for status in (JobStatus.DEFERRED, JobStatus.SCHEDULED):
            assert serialize_job_status(make_job(status))["status"] == "pending"

    def test_finished_completed(self):
        job = make_job(JobStatus.FINISHED, result={
            "status": "completed",
            "download_url": "/snapshots/image/a.png",
        })

        payload = serialize_job_status(job)

        assert payload == {
            "job_id": "job-123",
            "status": "completed",
            "download_url": "/snapshots/image/a.png",
        }

    def test_finished_with_error_result(self):
        job = make_job(JobStatus.FINISHED, result={
            "status": "failed",
            "message": "Error creating snapshot: boom",
        })

        payload = serialize_job_status(job)

        assert payload["status"] == "failed"
        assert "boom" in payload["message"]

    def test_finished_with_unexpected_result(self):
        payload = serialize_job_status(make_job(JobStatus.FINISHED, result="nope"))

        assert payload["status"] == "failed"
        assert payload["message"]

    @pytest.mark.parametrize("status", [
        JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELED,
    ])
    def test_terminal_failures_surface_the_exception(self, status):
        job = make_job(status, exc_string="RuntimeError: render failed")

        payload = serialize_job_status(job)

        assert payload["status"] == "failed"
        assert payload["message"] == "RuntimeError: render failed"

    def test_payload_has_no_rq_vocabulary(self):
        # Queuing backend details must not leak into the public contract.
        payload = serialize_job_status(make_job(JobStatus.FINISHED, result={
            "status": "completed", "download_url": "/snapshots/image/a.png",
        }))

        assert set(payload) <= {"job_id", "status", "download_url", "message"}


class TestQueueWiring:
    """The worker must actually consume the snapshot queue"""

    def test_queue_name_is_the_function_default(self):
        assert get_snapshot_queue.__defaults__ == ("snapshots",)

    def test_worker_registers_the_queue(self):
        import inspect
        from server import cli

        source = inspect.getsource(cli.worker.callback)
        # 'snapshots' must come first: interactive renders should not queue
        # behind a backlog of maintenance jobs.
        assert "'snapshots', 'default', 'maintenance'" in source

    def test_enqueue_bounds_both_ttls(self):
        import inspect
        from server.tasks import enqueue_snapshot_job

        source = inspect.getsource(enqueue_snapshot_job)
        # RQ defaults failure_ttl to one year, so it must be overridden too.
        assert "result_ttl=3600" in source
        assert "failure_ttl=3600" in source
