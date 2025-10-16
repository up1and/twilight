"""
Tests for snapshot module
"""
import pytest
import datetime
from unittest.mock import Mock, patch
from io import BytesIO
from server.snapshot import (
    generate_bbox_hash, generate_filename, create_snapshot_image,
    upload_to_minio, generate_time_range, find_composite_object,
    create_video_from_images, create_single_snapshot, create_series_snapshot
)


class TestGenerateBboxHash:
    """Test bbox hash generation"""
    
    def test_generate_bbox_hash(self):
        bbox = [100.0, 20.0, 140.0, 50.0]
        hash_result = generate_bbox_hash(bbox)
        
        assert isinstance(hash_result, str)
        assert len(hash_result) == 8
        
        # Same bbox should generate same hash
        hash_result2 = generate_bbox_hash(bbox)
        assert hash_result == hash_result2
        
        # Different bbox should generate different hash
        different_bbox = [101.0, 21.0, 141.0, 51.0]
        different_hash = generate_bbox_hash(different_bbox)
        assert hash_result != different_hash


class TestGenerateFilename:
    """Test filename generation"""
    
    def test_generate_filename_image(self):
        timestamp = datetime.datetime(2025, 1, 15, 12, 30, 0, tzinfo=datetime.timezone.utc)
        bbox = [100.0, 20.0, 140.0, 50.0]
        
        filename = generate_filename('ir_clouds', timestamp, bbox, 'image')
        
        assert filename.startswith('image/snapshot_ir_clouds_20250115_1230_')
        assert filename.endswith('.png')
    
    def test_generate_filename_video(self):
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 13, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100.0, 20.0, 140.0, 50.0]
        
        filename = generate_filename('true_color', start_time, bbox, 'video', end_time)
        
        assert filename.startswith('video/snapshot_true_color_20250115_1200_to_20250115_1300_')
        assert filename.endswith('.mp4')


class TestCreateSnapshotImage:
    """Test snapshot image creation"""
    
    def test_create_snapshot_image_function_exists(self):
        # Just test that the function exists and can be imported
        from server.snapshot import create_snapshot_image
        assert callable(create_snapshot_image)
    



class TestUploadToMinio:
    """Test MinIO upload functionality"""
    
    def test_upload_image_to_minio(self):
        mock_client = Mock()
        mock_client.bucket_exists.return_value = True
        
        buffer = BytesIO(b'mock_image_data')
        filename = 'image/test.png'
        
        upload_to_minio(mock_client, buffer, filename)
        
        mock_client.put_object.assert_called_once_with(
            bucket_name='snapshot',
            object_name=filename,
            data=buffer,
            length=buffer.getbuffer().nbytes,
            content_type="image/png"
        )
    
    def test_upload_video_to_minio(self):
        mock_client = Mock()
        mock_client.bucket_exists.return_value = True
        
        filename = 'video/test.mp4'
        file_path = '/path/to/video.mp4'
        
        upload_to_minio(mock_client, file_path, filename)
        
        mock_client.fput_object.assert_called_once_with(
            bucket_name='snapshot',
            object_name=filename,
            file_path=file_path,
            content_type="video/mp4"
        )
    
    def test_upload_create_bucket_if_not_exists(self):
        mock_client = Mock()
        mock_client.bucket_exists.return_value = False
        
        buffer = BytesIO(b'mock_data')
        filename = 'test.png'
        
        upload_to_minio(mock_client, buffer, filename)
        
        mock_client.make_bucket.assert_called_once_with("snapshot")
    
    def test_upload_unknown_file_type(self):
        mock_client = Mock()
        mock_client.bucket_exists.return_value = True
        
        buffer = BytesIO(b'mock_data')
        filename = 'test.unknown'
        
        upload_to_minio(mock_client, buffer, filename)
        
        mock_client.put_object.assert_called_once_with(
            bucket_name='snapshot',
            object_name=filename,
            data=buffer,
            length=buffer.getbuffer().nbytes,
            content_type="application/octet-stream"
        )
    
    def test_upload_error_handling(self):
        mock_client = Mock()
        mock_client.bucket_exists.return_value = True
        mock_client.put_object.side_effect = Exception("Upload failed")
        
        buffer = BytesIO(b'mock_data')
        filename = 'test.png'
        
        with pytest.raises(Exception):
            upload_to_minio(mock_client, buffer, filename)


class TestGenerateTimeRange:
    """Test time range generation"""
    
    def test_generate_time_range(self):
        start_time = datetime.datetime(2025, 1, 15, 12, 5, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 35, 0, tzinfo=datetime.timezone.utc)
        
        times = generate_time_range(start_time, end_time)
        
        # Should round to 10-minute intervals
        assert len(times) == 4  # 12:00, 12:10, 12:20, 12:30
        assert times[0].minute == 0
        assert times[1].minute == 10
        assert times[2].minute == 20
        assert times[3].minute == 30
    
    def test_generate_time_range_exact_intervals(self):
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 20, 0, tzinfo=datetime.timezone.utc)
        
        times = generate_time_range(start_time, end_time)
        
        assert len(times) == 3  # 12:00, 12:10, 12:20
        assert all(t.minute % 10 == 0 for t in times)


class TestFindCompositeObject:
    """Test composite object finding"""
    
    def test_find_composite_object_with_timestamp(self):
        timestamp = datetime.datetime(2025, 1, 15, 12, 30, 0, tzinfo=datetime.timezone.utc)
        
        object_name = find_composite_object('ir_clouds', timestamp)
        
        expected = 'ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1230.tif'
        assert object_name == expected
    
    def test_find_composite_object_without_timestamp(self):
        with patch('server.snapshot.datetime') as mock_datetime:
            mock_now = datetime.datetime(2025, 1, 15, 12, 30, 0, tzinfo=datetime.timezone.utc)
            mock_datetime.datetime.now.return_value = mock_now
            mock_datetime.timedelta = datetime.timedelta
            mock_datetime.timezone = datetime.timezone
            
            object_name = find_composite_object('true_color', None)
            
            # Should use current time minus 30 minutes
            expected_time = mock_now - datetime.timedelta(minutes=30)
            expected = f'true_color/2025/01/15/himawari_true_color_{expected_time.strftime("%Y%m%d_%H%M")}.tif'
            assert 'true_color/2025/01/15/himawari_true_color_' in object_name


class TestCreateVideoFromImages:
    """Test video creation from images"""
    
    def test_create_video_from_images_empty_list(self):
        result = create_video_from_images([])
        
        assert result is None
    
    def test_create_video_from_images_function_exists(self):
        # Just test that the function exists and can be imported
        from server.snapshot import create_video_from_images
        assert callable(create_video_from_images)
    
    @patch('imageio.get_writer')
    @patch('PIL.Image.open')
    @patch('numpy.array')
    def test_create_video_from_images_success(self, mock_np_array, mock_image_open, mock_get_writer):
        # Mock image buffers
        image_buffers = [BytesIO(b'image1'), BytesIO(b'image2')]
        
        # Mock PIL Image
        mock_pil_image = Mock()
        mock_image_open.return_value = mock_pil_image
        
        # Mock numpy array
        mock_array = Mock()
        mock_np_array.return_value = mock_array
        
        # Mock imageio writer
        mock_writer = Mock()
        mock_get_writer.return_value.__enter__.return_value = mock_writer
        
        result = create_video_from_images(image_buffers, fps=4)
        
        assert isinstance(result, BytesIO)
        assert mock_writer.append_data.call_count == 2
    
    @patch('imageio.get_writer')
    def test_create_video_from_images_error(self, mock_get_writer):
        mock_get_writer.side_effect = Exception("Video creation failed")
        
        image_buffers = [BytesIO(b'image1')]
        result = create_video_from_images(image_buffers)
        
        assert result is None


class TestCreateSingleSnapshot:
    """Test single snapshot creation"""
    
    @patch('server.snapshot.create_snapshot_image')
    @patch('server.snapshot.upload_to_minio')
    @patch('server.snapshot.find_composite_object')
    def test_create_single_snapshot_success(self, mock_find_object, mock_upload, mock_create_image):
        mock_client = Mock()
        mock_client.stat_object.return_value = True  # COG exists
        mock_client.presigned_get_object.return_value = 'http://mock-url'
        
        mock_find_object.return_value = 'test-object.tif'
        mock_create_image.return_value = BytesIO(b'mock_image')
        
        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_single_snapshot(mock_client, 'ir_clouds', timestamp, bbox)
        
        assert result['status'] == 'completed'
        assert 'object_name' in result
        assert 'filename' in result
        mock_upload.assert_called_once()
    
    @patch('server.snapshot.find_composite_object')
    def test_create_single_snapshot_cog_not_found_with_task_manager(self, mock_find_object):
        mock_client = Mock()
        mock_client.stat_object.side_effect = Exception("COG not found")
        
        mock_task_manager = Mock()
        mock_task = Mock()
        mock_task.task_id = 'test-task-id'
        mock_task_manager.create_task.return_value = mock_task
        
        mock_find_object.return_value = 'test-object.tif'
        
        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_single_snapshot(mock_client, 'ir_clouds', timestamp, bbox, mock_task_manager)
        
        assert result['status'] == 'pending'
        assert result['task_id'] == 'test-task-id'
        mock_task_manager.create_task.assert_called_once_with('ir_clouds', timestamp, 'low')
    
    @patch('server.snapshot.find_composite_object')
    def test_create_single_snapshot_cog_not_found_without_task_manager(self, mock_find_object):
        mock_client = Mock()
        mock_client.stat_object.side_effect = Exception("COG not found")
        
        mock_find_object.return_value = 'test-object.tif'
        
        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_single_snapshot(mock_client, 'ir_clouds', timestamp, bbox)
        
        assert result['status'] == 'error'
        assert 'COG file not found' in result['message']
    
    @patch('server.snapshot.create_snapshot_image')
    @patch('server.snapshot.upload_to_minio')
    @patch('server.snapshot.find_composite_object')
    def test_create_single_snapshot_error_handling(self, mock_find_object, mock_upload, mock_create_image):
        mock_client = Mock()
        mock_client.stat_object.return_value = True  # COG exists
        mock_client.presigned_get_object.return_value = 'http://mock-url'
        
        mock_find_object.return_value = 'test-object.tif'
        mock_create_image.side_effect = Exception("Image creation failed")
        
        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_single_snapshot(mock_client, 'ir_clouds', timestamp, bbox)
        
        assert result['status'] == 'error'
        assert 'Error creating snapshot' in result['message']


class TestCreateSeriesSnapshot:
    """Test series snapshot creation"""
    
    @patch('server.snapshot.create_video_from_images')
    @patch('server.snapshot.upload_to_minio')
    @patch('server.snapshot.create_single_snapshot')
    @patch('server.snapshot.generate_time_range')
    @patch('server.snapshot.find_composite_object')
    def test_create_series_snapshot_success(self, mock_find_object, mock_time_range, 
                                          mock_create_single, mock_upload, mock_create_video):
        mock_client = Mock()
        mock_client.stat_object.return_value = True  # All COGs exist
        
        # Mock time range
        timestamps = [
            datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        ]
        mock_time_range.return_value = timestamps
        
        # Mock single snapshot creation
        mock_create_single.return_value = {
            'status': 'completed',
            'object_name': 'test-image.png'
        }
        
        # Mock MinIO get_object for images
        mock_response = Mock()
        mock_response.read.return_value = b'mock_image_data'
        mock_client.get_object.return_value = mock_response
        
        # Mock video creation
        mock_create_video.return_value = BytesIO(b'mock_video_data')
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_series_snapshot(mock_client, 'ir_clouds', start_time, end_time, bbox)
        
        assert result['status'] == 'completed'
        assert 'object_name' in result
        assert 'filename' in result
        assert result['frame_count'] == 2
        mock_upload.assert_called_once()
    
    @patch('server.snapshot.generate_time_range')
    @patch('server.snapshot.find_composite_object')
    def test_create_series_snapshot_missing_cogs_with_task_manager(self, mock_find_object, mock_time_range):
        mock_client = Mock()
        # First COG exists, second doesn't
        mock_client.stat_object.side_effect = [True, Exception("COG not found")]
        
        mock_task_manager = Mock()
        mock_task = Mock()
        mock_task.task_id = 'test-task-id'
        mock_task_manager.create_task.return_value = mock_task
        
        timestamps = [
            datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        ]
        mock_time_range.return_value = timestamps
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_series_snapshot(mock_client, 'ir_clouds', start_time, end_time, bbox, mock_task_manager)
        
        assert result['status'] == 'pending'
        assert result['missing_count'] == 1
        assert result['total_count'] == 2
        assert 'test-task-id' in result['task_ids']
    
    @patch('server.snapshot.generate_time_range')
    def test_create_series_snapshot_no_time_intervals(self, mock_time_range):
        mock_client = Mock()
        mock_time_range.return_value = []
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_series_snapshot(mock_client, 'ir_clouds', start_time, end_time, bbox)
        
        assert result['status'] == 'error'
        assert 'No valid time intervals' in result['message']
    
    @patch('server.snapshot.create_single_snapshot')
    @patch('server.snapshot.generate_time_range')
    @patch('server.snapshot.find_composite_object')
    def test_create_series_snapshot_failed_single_snapshot(self, mock_find_object, mock_time_range, mock_create_single):
        mock_client = Mock()
        mock_client.stat_object.return_value = True  # All COGs exist
        
        # Mock time range
        timestamps = [
            datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        ]
        mock_time_range.return_value = timestamps
        
        # Mock failed single snapshot creation
        mock_create_single.return_value = {
            'status': 'error',
            'message': 'Failed to create snapshot'
        }
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_series_snapshot(mock_client, 'ir_clouds', start_time, end_time, bbox)
        
        assert result['status'] == 'error'
        assert 'Failed to create snapshot' in result['message']
    
    @patch('server.snapshot.create_single_snapshot')
    @patch('server.snapshot.generate_time_range')
    @patch('server.snapshot.find_composite_object')
    def test_create_series_snapshot_minio_get_error(self, mock_find_object, mock_time_range, mock_create_single):
        mock_client = Mock()
        mock_client.stat_object.return_value = True  # All COGs exist
        
        # Mock time range
        timestamps = [
            datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        ]
        mock_time_range.return_value = timestamps
        
        # Mock successful single snapshot creation
        mock_create_single.return_value = {
            'status': 'completed',
            'object_name': 'test-image.png'
        }
        
        # Mock MinIO get_object error
        mock_client.get_object.side_effect = Exception("MinIO error")
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_series_snapshot(mock_client, 'ir_clouds', start_time, end_time, bbox)
        
        assert result['status'] == 'error'
        assert 'Failed to get image' in result['message']
    
    @patch('server.snapshot.create_video_from_images')
    @patch('server.snapshot.create_single_snapshot')
    @patch('server.snapshot.generate_time_range')
    @patch('server.snapshot.find_composite_object')
    def test_create_series_snapshot_video_creation_failed(self, mock_find_object, mock_time_range, 
                                                         mock_create_single, mock_create_video):
        mock_client = Mock()
        mock_client.stat_object.return_value = True  # All COGs exist
        
        # Mock time range
        timestamps = [
            datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        ]
        mock_time_range.return_value = timestamps
        
        # Mock successful single snapshot creation
        mock_create_single.return_value = {
            'status': 'completed',
            'object_name': 'test-image.png'
        }
        
        # Mock MinIO get_object for images
        mock_response = Mock()
        mock_response.read.return_value = b'mock_image_data'
        mock_client.get_object.return_value = mock_response
        
        # Mock video creation failure
        mock_create_video.return_value = None
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_series_snapshot(mock_client, 'ir_clouds', start_time, end_time, bbox)
        
        assert result['status'] == 'error'
        assert 'Failed to create video' in result['message']
    
    @patch('server.snapshot.generate_time_range')
    def test_create_series_snapshot_general_error(self, mock_time_range):
        mock_client = Mock()
        # Mock exception in generate_time_range
        mock_time_range.side_effect = Exception("General error")
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2025, 1, 15, 12, 10, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]
        
        result = create_series_snapshot(mock_client, 'ir_clouds', start_time, end_time, bbox)
        
        assert result['status'] == 'error'
        assert 'Error creating video' in result['message']


class TestSnapshotUtilityFunctions:
    """Test utility functions in snapshot module"""
    
    def test_generate_bbox_hash(self):
        from server.snapshot import generate_bbox_hash
        
        bbox = [100.123456, 20.654321, 140.987654, 50.123456]
        hash1 = generate_bbox_hash(bbox)
        hash2 = generate_bbox_hash(bbox)
        
        # Same bbox should generate same hash
        assert hash1 == hash2
        assert len(hash1) == 8  # Should be 8 characters
        
        # Different bbox should generate different hash
        different_bbox = [100.123457, 20.654321, 140.987654, 50.123456]
        hash3 = generate_bbox_hash(different_bbox)
        assert hash1 != hash3
    
    def test_generate_filename_image(self):
        from server.snapshot import generate_filename
        import datetime
        
        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0)
        bbox = [100, 20, 140, 50]
        
        filename = generate_filename('ir_clouds', timestamp, bbox, 'image')
        
        assert filename.startswith('image/snapshot_ir_clouds_20250115_1200_')
        assert filename.endswith('.png')
    
    def test_generate_filename_video(self):
        from server.snapshot import generate_filename
        import datetime
        
        start_time = datetime.datetime(2025, 1, 15, 12, 0, 0)
        end_time = datetime.datetime(2025, 1, 15, 13, 0, 0)
        bbox = [100, 20, 140, 50]
        
        filename = generate_filename('ir_clouds', start_time, bbox, 'video', end_time)
        
        assert filename.startswith('video/snapshot_ir_clouds_20250115_1200_to_20250115_1300_')
        assert filename.endswith('.mp4')
    
    def test_generate_time_range(self):
        from server.snapshot import generate_time_range
        import datetime
        
        start_time = datetime.datetime(2025, 1, 15, 12, 5, 30)  # 12:05:30
        end_time = datetime.datetime(2025, 1, 15, 12, 35, 45)   # 12:35:45
        
        times = generate_time_range(start_time, end_time)
        
        # Should round to 10-minute intervals
        assert len(times) == 4  # 12:00, 12:10, 12:20, 12:30
        assert times[0].minute == 0
        assert times[1].minute == 10
        assert times[2].minute == 20
        assert times[3].minute == 30
    
    def test_find_composite_object(self):
        from server.snapshot import find_composite_object
        import datetime
        
        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0)
        object_name = find_composite_object('ir_clouds', timestamp)
        
        expected = 'ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1200.tif'
        assert object_name == expected
    
    def test_find_composite_object_none_timestamp(self):
        from server.snapshot import find_composite_object
        
        # Should use current time minus 30 minutes when timestamp is None
        object_name = find_composite_object('ir_clouds', None)
        
        # Should contain the composite name and follow the pattern
        assert 'ir_clouds' in object_name
        assert object_name.endswith('.tif')
        assert 'himawari_ir_clouds_' in object_name


class TestUploadToMinioBasic:
    """Basic tests for upload_to_minio function"""
    
    def test_upload_to_minio_content_types(self):
        from server.snapshot import upload_to_minio
        
        mock_client = Mock()
        mock_client.bucket_exists.return_value = True
        mock_buffer = Mock()
        mock_buffer.getbuffer.return_value.nbytes = 1024
        
        # Test PNG content type
        upload_to_minio(mock_client, mock_buffer, 'test.png')
        call_args = mock_client.put_object.call_args
        assert call_args[1]['content_type'] == 'image/png'
        
        mock_client.reset_mock()
        
        # Test MP4 content type
        upload_to_minio(mock_client, '/path/to/video.mp4', 'test.mp4')
        call_args = mock_client.fput_object.call_args
        assert call_args[1]['content_type'] == 'video/mp4'
        
        mock_client.reset_mock()
        
        # Test unknown content type
        upload_to_minio(mock_client, mock_buffer, 'test.unknown')
        call_args = mock_client.put_object.call_args
        assert call_args[1]['content_type'] == 'application/octet-stream'


class TestCreateVideoFromImagesBasic:
    """Basic tests for create_video_from_images function"""
    
    def test_create_video_from_images_empty_list(self):
        from server.snapshot import create_video_from_images
        
        result = create_video_from_images([], fps=4)
        assert result is None
    
    def test_create_video_from_images_with_exception(self):
        from server.snapshot import create_video_from_images
        
        # Test with mock buffers that will cause an exception
        mock_buffer = Mock()
        mock_buffer.seek.side_effect = Exception("Test error")
        
        result = create_video_from_images([mock_buffer], fps=4)
        assert result is None
