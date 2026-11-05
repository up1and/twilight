"""
Tests for snapshot module
"""
import math
import pytest
import datetime
from unittest.mock import Mock, patch
from io import BytesIO
from server.snapshot import (
    generate_bbox_hash, generate_filename, create_snapshot_image,
    upload_to_minio, generate_time_range, generate_composite_object_name,
    create_video_from_images, create_single_snapshot, create_series_snapshot,
    validate_bbox, validate_snapshot_limits, estimate_snapshot_size,
    cog_exists, missing_cogs
)


class TestValidateBbox:
    """Test bounding box validation"""

    def test_valid_bboxes(self):
        valid = [
            [100, 20, 140, 50],
            [-180, -90, 180, 90],
            [0, 0, 1, 1],
            [-122.5, 37.5, -122.0, 38.0],
            (100, 20, 140, 50),  # tuple is accepted too
        ]

        for bbox in valid:
            assert validate_bbox(bbox) is None

    def test_rejects_non_four_value_arrays(self):
        for bbox in [[100], [100, 20], [100, 20, 140], [100, 20, 140, 50, 60],
                     "100,20,140,50", None, {}, 123]:
            message = validate_bbox(bbox)
            assert message is not None
            assert "bbox" in message

    def test_rejects_non_numeric_values(self):
        for bbox in [[100, 20, 140, "50"], [None, 20, 140, 50],
                     [True, 20, 140, 50], [100, 20, 140, [50]]]:
            message = validate_bbox(bbox)
            assert message is not None
            assert "bbox" in message

    def test_rejects_non_finite_values(self):
        for bbox in [[float("nan"), 20, 140, 50],
                     [100, 20, float("inf"), 50]]:
            message = validate_bbox(bbox)
            assert message is not None
            assert "finite" in message

    def test_rejects_longitude_out_of_range(self):
        for bbox in [[-180.1, 20, 140, 50], [100, 20, 180.1, 50],
                     [-200, 20, 140, 50]]:
            message = validate_bbox(bbox)
            assert message is not None
            assert "longitude" in message

    def test_rejects_latitude_out_of_range(self):
        for bbox in [[100, -90.1, 140, 50], [100, 20, 140, 90.1],
                     [100, -95, 140, 50]]:
            message = validate_bbox(bbox)
            assert message is not None
            assert "latitude" in message

    def test_rejects_inverted_or_empty_bbox(self):
        for bbox in [[140, 20, 100, 50], [100, 50, 140, 20],
                     [100, 20, 100, 50], [100, 20, 140, 20]]:
            message = validate_bbox(bbox)
            assert message is not None
            assert "bbox" in message


class TestZoomSizing:
    """Output size is derived from the map zoom the user captured"""

    def test_size_follows_web_mercator(self):
        # 256 * 2^z world pixels; a 40-degree span at z6 is 40/360 of it
        width, height = estimate_snapshot_size([100, 20, 140, 50], 6)
        assert width == math.ceil(40 / 360 * 256 * 2**6)
        assert height > 0

    def test_output_size_is_stable_across_zooms(self):
        # A viewport-sized bbox stays near the screen size at every zoom,
        # because a wider view is rendered at a coarser resolution.
        sizes = []
        for zoom in (5, 6, 7, 8, 9, 10):
            span = 360 / 2**zoom * 7.5      # 1920px wide viewport
            lat_span = span * 1080 / 1920
            bbox = [117.5 - span / 2, 27.5 - lat_span / 2,
                    117.5 + span / 2, 27.5 + lat_span / 2]
            width, height = estimate_snapshot_size(bbox, zoom)
            sizes.append(width * height)

        assert max(sizes) / min(sizes) < 1.1
        assert all(2_000_000 < p < 3_000_000 for p in sizes)

    def test_accepts_viewport_sized_bbox(self):
        assert validate_snapshot_limits([100, 20, 110, 25], 6) is None

    def test_rejects_world_bbox_at_high_zoom(self):
        message = validate_snapshot_limits([-180, -90, 180, 90], 10)
        assert message is not None
        assert "too large" in message

    def test_limit_is_a_parameter_default(self):
        # Not a deployment knob: viewport exports never approach it.
        assert validate_snapshot_limits([100, 20, 102, 21], 6,
                                        max_pixels=10_000_000) is None
        assert validate_snapshot_limits([100, 20, 102, 21], 6,
                                        max_pixels=100) is not None


class TestCreateSnapshotImageSizing:
    """create_snapshot_image reads bbox, and takes size only when asked"""

    @staticmethod
    def _render(width=None, height=None):
        import numpy as np

        with patch("server.snapshot.Reader") as mock_reader, \
                patch("server.snapshot.ContourWriterAGG") as mock_cw, \
                patch("server.snapshot.get_pycoast_dir", return_value="/tmp"), \
                patch("server.snapshot.Image.open"):
            mock_cog = Mock()
            mock_cog.crs = None
            mock_reader.return_value.__enter__.return_value = mock_cog

            mock_img = Mock()
            mock_img.data = np.zeros((3, 10, 10), dtype=np.uint8)
            mock_img.bounds = (100, 20, 101, 21)
            mock_img.render.return_value = b"mock_png"
            mock_cog.part.return_value = mock_img

            if width is None:
                create_snapshot_image("http://mock-url", [100, 20, 101, 21])
            else:
                create_snapshot_image("http://mock-url", [100, 20, 101, 21],
                                      width, height)

            return mock_cog.part.call_args.kwargs, mock_cw

    def test_bbox_alone_uses_the_native_grid(self):
        kwargs, _ = self._render()
        assert kwargs == {}

    def test_size_is_forwarded_unchanged(self):
        kwargs, _ = self._render(40, 30)
        assert kwargs == {"width": 40, "height": 30}

    def test_deep_zoom_upsamples_rather_than_clamping(self):
        # Interpolating past the source resolution is intentional: the map
        # itself does the same past its native zoom.
        kwargs, _ = self._render(4000, 4000)
        assert kwargs == {"width": 4000, "height": 4000}

    def test_coastlines_are_drawn_once(self):
        _, mock_cw = self._render(40, 30)
        assert mock_cw.call_count == 1
        assert mock_cw.return_value.add_coastlines.call_count == 1

    def test_coastlines_are_drawn_once_without_size_too(self):
        _, mock_cw = self._render()
        assert mock_cw.call_count == 1
        assert mock_cw.return_value.add_coastlines.call_count == 1


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

    @patch('server.snapshot.Reader')
    @patch('server.snapshot.ContourWriterAGG')
    @patch('server.snapshot.get_pycoast_dir')
    @patch('PIL.Image.open')
    def test_create_snapshot_image_success(self, mock_image_open, mock_get_pycoast, mock_cw, mock_reader):
        mock_get_pycoast.return_value = "/tmp/pycoast"
        
        # Mock rio-tiler Reader
        mock_cog = Mock()
        mock_reader.return_value.__enter__.return_value = mock_cog
        
        # Mock image
        import numpy as np
        mock_img = Mock()
        mock_img.data = np.zeros((3, 10, 10), dtype=np.uint8)
        mock_img.bounds = (100, 20, 110, 30)
        mock_img.render.return_value = b"mock_png"
        mock_cog.part.return_value = mock_img
        # No CRS on the mock COG, so the code falls back to latlong
        mock_cog.crs = None
        
        # Mock PIL Image
        mock_pil = Mock()
        mock_image_open.return_value.convert.return_value = mock_pil
        
        from server.snapshot import create_snapshot_image
        result = create_snapshot_image("http://mock-url", [100, 20, 110, 30])
        
        assert isinstance(result, BytesIO)
        mock_cw.assert_called_once_with("/tmp/pycoast")
        mock_cw.return_value.add_coastlines.assert_called_once()
        # Verify area_def passed to add_coastlines is a tuple
        args = mock_cw.return_value.add_coastlines.call_args[0]
        assert isinstance(args[1], tuple)
        assert args[1][0] == "+proj=latlong +datum=WGS84"
        assert args[1][1] == (100, 20, 110, 30)
    



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


class TestGenerateCompositeObjectName:
    """Test composite object finding"""
    
    def test_generate_composite_object_name(self):
        timestamp = datetime.datetime(2025, 1, 15, 12, 30, 0, tzinfo=datetime.timezone.utc)
        
        object_name = generate_composite_object_name('ir_clouds', timestamp)
        
        expected = 'ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1230.tif'
        assert object_name == expected


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
    @patch('server.snapshot.Image.open')
    def test_create_video_from_images_success(self, mock_image_open, mock_get_writer):
        import numpy as np

        # Real numpy arrays, since the encoder consumes frames one at a time
        image_buffers = [BytesIO(b'image1'), BytesIO(b'image2')]

        mock_pil_image = Mock()
        mock_pil_image.__enter__ = Mock(return_value=mock_pil_image)
        mock_pil_image.__exit__ = Mock(return_value=False)
        mock_image_open.return_value = mock_pil_image

        with patch('numpy.array', return_value=np.zeros((4, 4, 3), np.uint8)):
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
    @patch('server.snapshot.generate_composite_object_name')
    def test_create_single_snapshot_success(self, mock_find_object, mock_upload, mock_create_image):
        mock_client = Mock()
        mock_client.presigned_get_object.return_value = 'http://mock-url'

        mock_find_object.return_value = 'test-object.tif'
        mock_create_image.return_value = BytesIO(b'mock_image')

        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]

        result = create_single_snapshot(mock_client, 'ir_clouds', timestamp, bbox)

        assert result['status'] == 'completed'
        assert 'object_name' in result
        # The caller builds download_url from object_name; no filename field.
        assert set(result) == {'status', 'object_name'}
        mock_upload.assert_called_once()

    @patch('server.snapshot.create_snapshot_image')
    @patch('server.snapshot.upload_to_minio')
    @patch('server.snapshot.generate_composite_object_name')
    def test_create_single_snapshot_forwards_requested_size(
        self, mock_find_object, mock_upload, mock_create_image
    ):
        mock_client = Mock()
        mock_client.presigned_get_object.return_value = 'http://mock-url'
        mock_find_object.return_value = 'test-object.tif'
        mock_create_image.return_value = BytesIO(b'mock_image')

        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

        create_single_snapshot(
            mock_client, 'ir_clouds', timestamp, [100, 20, 140, 50],
            width=1821, height=1707,
        )

        assert mock_create_image.call_args.kwargs == {
            'width': 1821, 'height': 1707
        }

    @patch('server.snapshot.create_snapshot_image')
    @patch('server.snapshot.generate_composite_object_name')
    def test_create_single_snapshot_error_handling(self, mock_find_object, mock_create_image):
        mock_client = Mock()
        mock_client.presigned_get_object.return_value = 'http://mock-url'

        mock_find_object.return_value = 'test-object.tif'
        mock_create_image.side_effect = Exception("Image creation failed")

        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        bbox = [100, 20, 140, 50]

        result = create_single_snapshot(mock_client, 'ir_clouds', timestamp, bbox)

        assert result['status'] == 'failed'
        assert 'Error creating snapshot' in result['message']


class TestCreateSeriesSnapshot:
    """Test timelapse rendering"""

    @patch('server.snapshot.create_video_from_images')
    @patch('server.snapshot.upload_to_minio')
    @patch('server.snapshot.create_snapshot_image')
    def test_create_series_snapshot_success(
        self, mock_create_image, mock_upload, mock_make_video
    ):
        mock_client = Mock()
        mock_client.presigned_get_object.return_value = 'http://mock-url'
        mock_create_image.return_value = BytesIO(b'frame')
        mock_make_video.return_value = BytesIO(b'mp4')

        start = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2025, 1, 15, 13, 0, 0, tzinfo=datetime.timezone.utc)

        result = create_series_snapshot(
            mock_client, 'true_color', start, end, [100, 20, 140, 50]
        )

        assert result['status'] == 'completed'
        assert result['object_name'].startswith('video/')
        # 7 frames rendered, one video uploaded
        assert mock_create_image.call_count == 7
        mock_upload.assert_called_once()

    @patch('server.snapshot.upload_to_minio')
    @patch('server.snapshot.create_snapshot_image')
    def test_frames_are_never_uploaded_individually(
        self, mock_create_image, mock_upload
    ):
        # The old flow wrote every frame to MinIO and leaked them; frames now
        # stay in memory and only the encoded video is stored.
        mock_client = Mock()
        mock_client.presigned_get_object.return_value = 'http://mock-url'
        mock_create_image.return_value = BytesIO(b'frame')

        with patch('server.snapshot.create_video_from_images',
                   return_value=BytesIO(b'mp4')):
            start = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
            end = datetime.datetime(2025, 1, 15, 13, 0, 0, tzinfo=datetime.timezone.utc)
            create_series_snapshot(
                mock_client, 'true_color', start, end, [100, 20, 140, 50]
            )

        # upload_to_minio(client, data, filename): only the video is written
        uploaded = [c.args[2] for c in mock_upload.call_args_list]
        assert len(uploaded) == 1
        assert uploaded[0].startswith('video/')
        assert not any(name.startswith('image/') for name in uploaded)

    @patch('server.snapshot.create_snapshot_image')
    def test_frames_use_the_requested_size(self, mock_create_image):
        mock_client = Mock()
        mock_client.presigned_get_object.return_value = 'http://mock-url'
        mock_create_image.return_value = BytesIO(b'frame')

        with patch('server.snapshot.create_video_from_images',
                   return_value=BytesIO(b'mp4')), \
             patch('server.snapshot.upload_to_minio'):
            start = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
            end = datetime.datetime(2025, 1, 15, 13, 0, 0, tzinfo=datetime.timezone.utc)
            create_series_snapshot(
                mock_client, 'true_color', start, end, [100, 20, 140, 50],
                width=800, height=600,
            )

        assert mock_create_image.call_args.kwargs == {'width': 800, 'height': 600}

    def test_create_series_snapshot_no_time_intervals(self):
        mock_client = Mock()
        start = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

        with patch('server.snapshot.generate_time_range', return_value=[]):
            result = create_series_snapshot(
                mock_client, 'true_color', start, start, [100, 20, 140, 50]
            )

        assert result['status'] == 'failed'
        assert 'No valid time intervals' in result['message']

    @patch('server.snapshot.create_snapshot_image')
    def test_create_series_snapshot_frame_error(self, mock_create_image):
        mock_client = Mock()
        mock_client.presigned_get_object.side_effect = Exception("COG vanished")

        start = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2025, 1, 15, 13, 0, 0, tzinfo=datetime.timezone.utc)

        result = create_series_snapshot(
            mock_client, 'true_color', start, end, [100, 20, 140, 50]
        )

        assert result['status'] == 'failed'
        assert 'Failed to render' in result['message']

    @patch('server.snapshot.create_snapshot_image')
    @patch('server.snapshot.upload_to_minio')
    def test_create_series_snapshot_video_creation_failed(
        self, mock_upload, mock_create_image
    ):
        mock_client = Mock()
        mock_client.presigned_get_object.return_value = 'http://mock-url'
        mock_create_image.return_value = BytesIO(b'frame')

        start = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2025, 1, 15, 13, 0, 0, tzinfo=datetime.timezone.utc)

        with patch('server.snapshot.create_video_from_images', return_value=None):
            result = create_series_snapshot(
                mock_client, 'true_color', start, end, [100, 20, 140, 50]
            )

        assert result['status'] == 'failed'
        assert 'imageio' in result['message']
        mock_upload.assert_not_called()


class TestMissingCogs:
    """COG presence checks used for the up-front 404"""

    def test_cog_exists_true(self):
        client = Mock()
        assert cog_exists(client, 'ir_clouds', datetime.datetime(2025, 1, 15, 12, tzinfo=datetime.timezone.utc))

    def test_cog_exists_false(self):
        client = Mock()
        client.stat_object.side_effect = Exception("missing")
        assert not cog_exists(client, 'ir_clouds', datetime.datetime(2025, 1, 15, 12, tzinfo=datetime.timezone.utc))

    def test_missing_cogs_reports_every_gap(self):
        client = Mock()
        start = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2025, 1, 15, 12, 30, 0, tzinfo=datetime.timezone.utc)

        # 12:00 ok, 12:10 missing, 12:20 ok, 12:30 missing
        def stat_object(bucket, name):
            if name.endswith('1210.tif') or name.endswith('1230.tif'):
                raise Exception("missing")

        client.stat_object.side_effect = stat_object
        result = missing_cogs(client, 'ir_clouds', start, end)

        assert [ts.strftime('%H%M') for ts in result] == ['1210', '1230']


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
    
    def test_generate_composite_object_name(self):
        from server.snapshot import generate_composite_object_name
        import datetime
        
        timestamp = datetime.datetime(2025, 1, 15, 12, 0, 0)
        object_name = generate_composite_object_name('ir_clouds', timestamp)
        
        expected = 'ir_clouds/2025/01/15/himawari_ir_clouds_20250115_1200.tif'
        assert object_name == expected


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
