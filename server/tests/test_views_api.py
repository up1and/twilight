"""
Tests for API views
"""
import datetime
import json

from unittest.mock import Mock


class TestCreateTask:
    """Test POST /api/tasks endpoint"""
    
    def test_create_task_missing_fields(self, client):
        # Missing required fields
        data = {"composite": "ir_clouds"}
        
        response = client.post("/api/tasks",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Missing required fields" in result["message"]
    
    def test_create_task_invalid_priority_defaults_to_normal(self, client):
        data = {
            "composite": "ir_clouds",
            "timestamp": "2025-01-15T12:00:00Z",
            "priority": "invalid_priority"  # Invalid priority should default to normal
        }
        
        response = client.post("/api/tasks",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 201
        result = json.loads(response.data)
        assert "task_id" in result
    
    def test_create_task_invalid_composite(self, client):
        data = {
            "composite": "invalid_composite",
            "timestamp": "2025-01-15T12:00:00Z"
        }
        
        response = client.post("/api/tasks",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid composite" in result["message"]
    
    def test_create_task_invalid_timestamp(self, client):
        data = {
            "composite": "ir_clouds",
            "timestamp": "invalid-timestamp"
        }
        
        response = client.post("/api/tasks",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid timestamp format" in result["message"]
    
    def test_create_task_success(self, client):
        data = {
            "composite": "ir_clouds",
            "timestamp": "2025-01-15T12:00:00Z",
            "priority": "high"
        }
        
        response = client.post("/api/tasks",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 201
        result = json.loads(response.data)
        assert "task_id" in result
        assert result["status"] == "pending"


class TestGetTask:
    """Test GET /api/tasks/<task_id> endpoint"""
    
    def test_get_task_not_found(self, client):
        response = client.get("/api/tasks/nonexistent-task")
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert "not found" in result["message"]
    
    def test_get_task_success(self, client):
        # First create a task
        data = {
            "composite": "ir_clouds",
            "timestamp": "2025-01-15T12:00:00Z"
        }
        
        create_response = client.post("/api/tasks",
                                    data=json.dumps(data),
                                    content_type="application/json")
        
        assert create_response.status_code == 201
        create_result = json.loads(create_response.data)
        task_id = create_result["task_id"]
        
        # Now get the task
        response = client.get(f"/api/tasks/{task_id}")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["task_id"] == task_id
        assert result["composite"] == "ir_clouds"


class TestGetTasks:
    """Test GET /api/tasks endpoint"""
    
    def test_get_tasks_invalid_pagination(self, client):
        response = client.get("/api/tasks?page=invalid")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid page" in result["message"]
    
    def test_get_tasks_success(self, client):
        response = client.get("/api/tasks")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert "tasks" in result
        assert "total" in result
        assert result["page"] == 1
        assert result["per_page"] == 20


class TestPeekNextTask:
    """Test GET /api/tasks/next endpoint"""
    
    def test_peek_next_task_endpoint_exists(self, client):
        response = client.get("/api/tasks/next")
        
        # Should return either 200 with task or 204 with no tasks
        assert response.status_code in [200, 204]
    
    def test_peek_next_task_with_filters(self, client):
        # Test with priority and composite filters
        response = client.get("/api/tasks/next?priority=high,normal&composite=ir_clouds,true_color")
        
        # Should return either 200 with task or 204 with no tasks
        assert response.status_code in [200, 204]
    
    def test_peek_next_task_empty_filters(self, client):
        # Test with empty filter values
        response = client.get("/api/tasks/next?priority=&composite=")
        
        # Should return either 200 with task or 204 with no tasks
        assert response.status_code in [200, 204]


class TestClaimTask:
    """Test PUT /api/tasks/<task_id>/claim endpoint"""
    
    def test_claim_task_missing_worker_id(self, client):
        data = {}
        
        response = client.put("/api/tasks/some-task/claim",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Missing required field: worker_id" in result["message"]
    
    def test_claim_task_not_found(self, client):
        data = {"worker_id": "worker-123"}
        
        response = client.put("/api/tasks/nonexistent-task/claim",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert "not found or already claimed" in result["message"]
    
    def test_claim_task_success(self, client):
        # First create a task
        data = {
            "composite": "ir_clouds",
            "timestamp": "2025-01-15T12:00:00Z"
        }
        
        create_response = client.post("/api/tasks",
                                    data=json.dumps(data),
                                    content_type="application/json")
        
        assert create_response.status_code == 201
        create_result = json.loads(create_response.data)
        task_id = create_result["task_id"]
        
        # Now claim the task
        claim_data = {"worker_id": "worker-123"}
        response = client.put(f"/api/tasks/{task_id}/claim",
                            data=json.dumps(claim_data),
                            content_type="application/json")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["task_id"] == task_id
        assert result["worker_id"] == "worker-123"
        assert result["status"] == "running"


class TestUpdateTaskStatus:
    """Test PUT /api/tasks/<task_id>/status endpoint"""
    
    def test_update_status_missing_status(self, client):
        data = {"message": "Some message"}
        
        response = client.put("/api/tasks/some-task/status",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Missing required field: status" in result["message"]
    
    def test_update_status_invalid_status(self, client):
        data = {"status": "invalid_status"}
        
        response = client.put("/api/tasks/some-task/status",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid status" in result["message"]
    
    def test_update_status_task_not_found(self, client):
        data = {"status": "completed"}
        
        response = client.put("/api/tasks/nonexistent-task/status",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 404
        result = json.loads(response.data)
        assert "not found" in result["message"]
    
    def test_update_status_success(self, client):
        # First create and claim a task
        data = {
            "composite": "ir_clouds",
            "timestamp": "2025-01-15T12:00:00Z"
        }
        
        create_response = client.post("/api/tasks",
                                    data=json.dumps(data),
                                    content_type="application/json")
        
        assert create_response.status_code == 201
        create_result = json.loads(create_response.data)
        task_id = create_result["task_id"]
        
        # Claim the task
        claim_data = {"worker_id": "worker-123"}
        client.put(f"/api/tasks/{task_id}/claim",
                  data=json.dumps(claim_data),
                  content_type="application/json")
        
        # Now update status
        status_data = {"status": "completed", "message": "Task completed successfully"}
        response = client.put(f"/api/tasks/{task_id}/status",
                            data=json.dumps(status_data),
                            content_type="application/json")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert "updated successfully" in result["message"]


class TestManageSync:
    """Test POST/PUT /api/syncs endpoint"""
    
    def test_manage_sync_missing_timestamp(self, client):
        data = {"status": "completed"}
        
        response = client.post("/api/syncs",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Missing required field: timestamp" in result["message"]
    
    def test_manage_sync_invalid_timestamp(self, client):
        data = {"timestamp": "invalid-timestamp"}
        
        response = client.post("/api/syncs",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid timestamp format" in result["message"]
    
    def test_update_sync_no_fields(self, client):
        data = {"timestamp": "2025-01-15T12:00:00Z"}
        
        response = client.put("/api/syncs",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "At least one of status, files, or size must be provided" in result["message"]
    
    def test_update_sync_invalid_status(self, client):
        data = {
            "timestamp": "2025-01-15T12:00:00Z",
            "status": "invalid_status"
        }
        
        response = client.put("/api/syncs",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid status" in result["message"]
    
    def test_create_sync_success(self, client):
        data = {"timestamp": "2025-01-15T12:00:00Z"}
        
        response = client.post("/api/syncs",
                             data=json.dumps(data),
                             content_type="application/json")
        
        assert response.status_code == 201
        result = json.loads(response.data)
        assert "created successfully" in result["message"]
        assert result["status"] == "pending"
    
    def test_update_sync_success(self, client):
        data = {
            "timestamp": "2025-01-15T12:00:00Z",
            "status": "running",  # Use "running" instead of "completed" to avoid promote_tasks call
            "files": 10,
            "size": 1024000
        }
        
        response = client.put("/api/syncs",
                            data=json.dumps(data),
                            content_type="application/json")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert "updated successfully" in result["message"]


class TestGetSync:
    """Test GET /api/syncs/<timestamp> endpoint"""
    
    def test_get_sync_invalid_timestamp(self, client):
        response = client.get("/api/syncs/invalid-timestamp")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid timestamp format" in result["message"]
    
    def test_get_sync_not_found(self, client):
        response = client.get("/api/syncs/2025-01-15T12:00:00Z")
        
        # Should return 404 for non-existent sync or 200 if it exists
        assert response.status_code in [200, 404]


class TestGetSyncs:
    """Test GET /api/syncs endpoint"""
    
    def test_get_syncs_invalid_pagination(self, client):
        response = client.get("/api/syncs?page=invalid")
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert "Invalid page" in result["message"]
    
    def test_get_syncs_success(self, client):
        response = client.get("/api/syncs")
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert "syncs" in result
        assert "total" in result
        assert result["page"] == 1
        assert result["per_page"] == 20


class TestCreateSnapshot:
    """Test POST /api/snapshots endpoint"""

    @staticmethod
    def _payload(**overrides):
        data = {
            "bbox": [100, 20, 140, 50],
            "timestamp": "2025-01-15T12:00:00Z",
            "composite": "ir_clouds",
            "zoom": 6,
        }
        data.update(overrides)
        for key, value in list(data.items()):
            if value is None:
                del data[key]
        return data

    def test_create_snapshot_missing_fields(self, client):
        response = client.post(
            "/api/snapshots",
            data=json.dumps({"bbox": [100, 20, 140, 50]}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "Missing required field" in json.loads(response.data)["message"]

    def test_create_snapshot_requires_zoom(self, client):
        response = client.post(
            "/api/snapshots",
            data=json.dumps(self._payload(zoom=None)),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "zoom" in json.loads(response.data)["message"]

    def test_create_snapshot_invalid_bbox(self, client):
        response = client.post(
            "/api/snapshots",
            data=json.dumps(self._payload(bbox=[100, 20, 140])),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "bbox must be an array of 4 numbers" in json.loads(response.data)["message"]

    def test_create_snapshot_invalid_composite(self, client):
        response = client.post(
            "/api/snapshots",
            data=json.dumps(self._payload(composite="invalid_composite")),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "Invalid composite" in json.loads(response.data)["message"]

    def test_create_snapshot_invalid_timestamp(self, client):
        response = client.post(
            "/api/snapshots",
            data=json.dumps(self._payload(timestamp="invalid-timestamp")),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "Invalid timestamp format" in json.loads(response.data)["message"]

    def test_create_snapshot_invalid_timedelta(self, client):
        response = client.post(
            "/api/snapshots",
            data=json.dumps(self._payload(timedelta=-10)),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "timedelta must be a positive number" in json.loads(response.data)["message"]

    def test_create_snapshot_timedelta_too_large(self, client):
        response = client.post(
            "/api/snapshots",
            data=json.dumps(self._payload(timedelta=2000)),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "Time range cannot exceed 24 hours" in json.loads(response.data)["message"]


class TestAPIErrorHandling:
    """Test error handling in API endpoints"""
    
    def test_create_task_with_invalid_json(self, client):
        # Test with malformed JSON
        response = client.post('/api/tasks',
                             data='{"invalid": json}',
                             content_type='application/json')
        
        # Should handle JSON parsing error gracefully
        assert response.status_code in [400, 500]
    
    def test_create_task_with_no_data(self, client):
        # Test with no JSON data
        response = client.post('/api/tasks',
                             content_type='application/json')
        
        assert response.status_code == 400
    
    def test_update_task_status_with_message(self, client):
        # Test updating task status with message
        data = {
            'status': 'failed',
            'message': 'Test failure message'
        }
        
        response = client.put('/api/tasks/test-task-id/status',
                            data=json.dumps(data),
                            content_type='application/json')
        
        # Should return 404 for non-existent task
        assert response.status_code == 404
    
    def test_get_tasks_with_filters(self, client):
        # Test with various filter parameters
        test_params = [
            '?status=pending',
            '?composite=ir_clouds',
            '?status=completed&composite=true_color',
            '?page=2&per_page=10'
        ]
        
        for params in test_params:
            response = client.get(f'/api/tasks{params}')
            assert response.status_code == 200
            result = json.loads(response.data)
            assert 'tasks' in result
            assert 'total' in result
    
    def test_get_tasks_with_large_per_page(self, client):
        # Test with per_page larger than maximum
        response = client.get('/api/tasks?per_page=200')
        
        assert response.status_code == 200
        result = json.loads(response.data)
        # Should be capped at 100
        assert result['per_page'] <= 100


class TestSyncExtended:
    """Extended tests for sync endpoints"""
    
    def test_create_sync_with_all_fields(self, client):
        data = {
            'timestamp': '2025-01-15T12:00:00Z',
            'status': 'pending',
            'files': 0,
            'size': 0,
            'source': 'himawari'
        }
        
        response = client.post('/api/syncs',
                             data=json.dumps(data),
                             content_type='application/json')
        
        assert response.status_code == 201
        result = json.loads(response.data)
        assert 'created successfully' in result['message']
    
    def test_update_sync_partial_fields(self, client):
        # Test updating with only some fields (avoid 'completed' status to prevent promote_tasks call)
        test_cases = [
            {'timestamp': '2025-01-15T12:00:00Z', 'status': 'running'},
            {'timestamp': '2025-01-15T12:00:00Z', 'files': 5},
            {'timestamp': '2025-01-15T12:00:00Z', 'size': 1024000},
            {'timestamp': '2025-01-15T12:00:00Z', 'status': 'running', 'files': 10, 'size': 2048000}
        ]
        
        for data in test_cases:
            response = client.put('/api/syncs',
                                data=json.dumps(data),
                                content_type='application/json')
            
            assert response.status_code == 200
            result = json.loads(response.data)
            assert 'updated successfully' in result['message']
    
    def test_get_syncs_with_pagination(self, client):
        # Test pagination parameters
        response = client.get('/api/syncs?page=1&per_page=5')
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['page'] == 1
        assert result['per_page'] == 5
        assert 'pages' in result
    
    def test_get_sync_with_various_timestamps(self, client):
        # Test with different timestamp formats
        test_timestamps = [
            '2025-01-15T12:00:00Z',
            '2025-01-15T12:00:00.000Z',
            '2025-01-15T12:00:00+00:00'
        ]
        
        for timestamp in test_timestamps:
            response = client.get(f'/api/syncs/{timestamp}')
            # Should return 200 if exists, 404 if not, but not 400 for valid format
            assert response.status_code in [200, 404]


class TestSnapshotAPIExtended:
    """Extended tests for snapshot API"""

    @staticmethod
    def _payload(**overrides):
        data = {
            "bbox": [100, 20, 140, 50],
            "timestamp": "2025-01-15T12:00:00Z",
            "composite": "ir_clouds",
            "zoom": 6,
        }
        data.update(overrides)
        for key, value in list(data.items()):
            if value is None:
                del data[key]
        return data

    def post(self, client, **overrides):
        return client.post(
            "/api/snapshots",
            data=json.dumps(self._payload(**overrides)),
            content_type="application/json",
        )

    # --- bbox validation ---

    def test_create_snapshot_bbox_validation(self, client):
        invalid_bboxes = [
            [100],
            [100, 20],
            [100, 20, 140],
            [100, 20, 140, 50, 60],
            "100,20,140,50",
            None,
        ]

        for bbox in invalid_bboxes:
            response = self.post(client, bbox=bbox)
            assert response.status_code == 400
            assert "bbox" in json.loads(response.data)["message"]

    def test_create_snapshot_bbox_out_of_range(self, client):
        for bbox in [
            [-181, 20, 140, 50],
            [100, 20, 181, 50],
            [100, -91, 140, 50],
            [100, 20, 140, 91],
            [-180.5, -90, 180, 90],
        ]:
            response = self.post(client, bbox=bbox)
            assert response.status_code == 400
            message = json.loads(response.data)["message"]
            assert "bbox" in message

    def test_create_snapshot_bbox_inverted(self, client):
        for bbox in [
            [140, 20, 100, 50],
            [100, 50, 140, 20],
            [100, 20, 100, 50],
            [100, 20, 140, 20],
        ]:
            response = self.post(client, bbox=bbox)
            assert response.status_code == 400
            assert "bbox" in json.loads(response.data)["message"]

    def test_create_snapshot_bbox_limits_axes(self, client):
        lng = self.post(client, bbox=[-200, 20, 140, 50])
        lat = self.post(client, bbox=[100, -95, 140, 50])

        assert "longitude" in json.loads(lng.data)["message"]
        assert "latitude" in json.loads(lat.data)["message"]

    # --- zoom validation ---

    def test_create_snapshot_zoom_must_be_integer(self, client):
        for zoom in [6.5, "6", [6], True]:
            response = self.post(client, zoom=zoom)
            assert response.status_code == 400
            assert "zoom" in json.loads(response.data)["message"]

    def test_create_snapshot_zoom_out_of_range(self, client):
        for zoom in [-1, 23, 100]:
            response = self.post(client, zoom=zoom)
            assert response.status_code == 400
            assert "zoom must be between" in json.loads(response.data)["message"]

    # --- size guard ---

    def test_create_snapshot_bbox_too_many_pixels(self, client):
        response = self.post(client, bbox=[-180, -90, 180, 90], zoom=10)

        assert response.status_code == 400
        assert "too large" in json.loads(response.data)["message"]

    def test_viewport_sized_bbox_is_accepted(self, client, mock_snapshot_jobs):
        # A realistic viewport export must not trip the pixel guard.
        response = self.post(client, bbox=[100, 20, 110, 25], zoom=6)
        assert response.status_code == 202

    # --- queueing ---

    def test_create_snapshot_returns_202_with_job_id(self, client, mock_snapshot_jobs):
        response = self.post(client)

        assert response.status_code == 202
        result = json.loads(response.data)
        assert result == {"job_id": "test-job-id", "status": "pending"}

        args = mock_snapshot_jobs["enqueue"].call_args[0]
        assert args[0] == "ir_clouds"
        assert args[1] == "2025-01-15T12:00:00Z"
        assert args[2] == [100.0, 20.0, 140.0, 50.0]
        assert args[3] == 6
        assert args[4] is None

    def test_create_snapshot_forwards_timedelta(self, client, mock_snapshot_jobs):
        response = self.post(client, timedelta=60)

        assert response.status_code == 202
        assert mock_snapshot_jobs["enqueue"].call_args[0][4] == 60

    def test_create_snapshot_enqueue_failure(self, client, mock_snapshot_jobs):
        mock_snapshot_jobs["enqueue"].side_effect = RuntimeError("redis down")

        response = self.post(client)

        assert response.status_code == 500
        assert "queue" in json.loads(response.data)["message"].lower()

    # --- missing composites ---

    def test_missing_composite_returns_404(self, client, mock_missing_composites):
        mock_missing_composites.return_value = [
            datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.timezone.utc)
        ]

        response = self.post(client)

        assert response.status_code == 404
        result = json.loads(response.data)
        assert result["error"] == "Not Found"
        assert result["missing"] == ["2025-01-15T12:00:00+00:00"]

    def test_missing_composites_lists_every_gap(self, client, mock_missing_composites):
        mock_missing_composites.return_value = [
            datetime.datetime(2025, 1, 15, 12, 10, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 1, 15, 12, 30, tzinfo=datetime.timezone.utc),
        ]

        response = self.post(client, timedelta=30)

        assert response.status_code == 404
        result = json.loads(response.data)
        assert len(result["missing"]) == 2
        assert "2 composite(s)" in result["message"]

    def test_nothing_is_queued_when_composites_are_missing(
        self, client, mock_snapshot_jobs, mock_missing_composites
    ):
        mock_missing_composites.return_value = [
            datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.timezone.utc)
        ]

        self.post(client)

        mock_snapshot_jobs["enqueue"].assert_not_called()

    # --- polling ---

    def test_get_snapshot_job_not_found(self, client):
        response = client.get("/api/snapshots/unknown")

        assert response.status_code == 404
        assert "not found" in json.loads(response.data)["message"]

    def test_get_snapshot_job_returns_status(self, client, mock_snapshot_jobs):
        mock_call = Mock()
        mock_call.get_status.return_value = "started"
        mock_call.id = "job-1"
        mock_snapshot_jobs["fetch"].return_value = mock_call

        response = client.get("/api/snapshots/job-1")

        assert response.status_code == 200
        assert json.loads(response.data) == {"job_id": "job-1", "status": "running"}


class TestAPIResponseFormats:
    """Test API response formats and consistency"""
    
    def test_error_response_format_consistency(self, client):
        # Test that all error responses have consistent format
        error_endpoints = [
            ('/api/tasks', 'POST', {}),  # Missing fields
            ('/api/tasks/invalid', 'GET', None),  # Not found
            ('/api/tasks/invalid/claim', 'PUT', {}),  # Missing worker_id
            ('/api/syncs', 'POST', {}),  # Missing timestamp
            ('/api/snapshots', 'POST', {}),  # Missing fields
        ]
        
        for endpoint, method, data in error_endpoints:
            if method == 'POST':
                response = client.post(endpoint,
                                     data=json.dumps(data) if data else None,
                                     content_type='application/json')
            elif method == 'PUT':
                response = client.put(endpoint,
                                    data=json.dumps(data) if data else None,
                                    content_type='application/json')
            else:
                response = client.get(endpoint)
            
            # Should return error status
            assert response.status_code >= 400
            
            # Try to parse JSON, but handle cases where it might not be JSON
            try:
                result = json.loads(response.data)
                
                # Should have consistent error format
                assert 'error' in result or 'message' in result
                
                # If both exist, error should be a category and message should be descriptive
                if 'error' in result and 'message' in result:
                    assert isinstance(result['error'], str)
                    assert isinstance(result['message'], str)
                    assert len(result['message']) > 0
            except json.JSONDecodeError:
                # Some error responses might be HTML (like 400 Bad Request from Flask)
                # This is also acceptable
                assert response.status_code >= 400
