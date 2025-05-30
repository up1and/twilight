import os
import hashlib
import datetime

from io import BytesIO

from rio_tiler.io import Reader


def generate_bbox_hash(bbox):
    """Generate a short hash from bbox coordinates"""
    bbox_str = f"{bbox[0]:.6f},{bbox[1]:.6f},{bbox[2]:.6f},{bbox[3]:.6f}"
    return hashlib.md5(bbox_str.encode()).hexdigest()[:8]

def generate_filename(composite, timestamp, bbox, file_type='image', end_timestamp=None):
    """Generate filename for snapshot image or video with prefix"""
    bbox_hash = generate_bbox_hash(bbox)
    time_str = timestamp.strftime('%Y%m%d_%H%M')

    if file_type == 'video' and end_timestamp:
        end_str = end_timestamp.strftime('%Y%m%d_%H%M')
        return f"video/snapshot_{composite}_{time_str}_to_{end_str}_{bbox_hash}.mp4"
    else:
        return f"image/snapshot_{composite}_{time_str}_{bbox_hash}.png"

def create_snapshot_image(presigned_url, bbox):
    """
    Read raster data from COG, create cartopy figure with raster data and coastlines
    Returns BytesIO buffer with PNG image
    """
    import matplotlib
    matplotlib.use('Agg')
    import cartopy.crs as ccrs
    import matplotlib.pyplot as plt

    with Reader(presigned_url) as cog:
        img = cog.part(bbox)
        data = img.data
        bounds = img.bounds

    data = data.transpose(1, 2, 0)
    extent = [bounds[0], bounds[2], bounds[1], bounds[3]]

    # Calculate figure size based on data dimensions to maintain original size
    height, width = data.shape[:2]
    dpi = 100
    fig_width = width / dpi
    fig_height = height / dpi

    fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
    ax = fig.add_subplot(projection=ccrs.PlateCarree())

    # Remove all margins and padding
    ax.set_position([0, 0, 1, 1])

    # Disable axis and spines to prevent any border artifacts
    ax.axis('off')
    ax.set_frame_on(False)

    if data.shape[-1] == 1:
        ax.imshow(
            data[:, :, 0],
            extent=extent,
            origin='upper',
            cmap='RdGy',
            transform=ccrs.PlateCarree()
        )
    else:
        ax.imshow(
            data,
            extent=extent,
            origin='upper',
            transform=ccrs.PlateCarree()
        )

    # Add coastlines using cartopy
    ax.coastlines(resolution='10m', color='#828282', linewidth=1)
    ax.set_extent([bounds[0], bounds[2], bounds[1], bounds[3]], crs=ccrs.PlateCarree())

    # Save to BytesIO buffer with exact dimensions
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=dpi, pad_inches=0,
               facecolor='none', edgecolor='none')
    plt.close()
    buffer.seek(0)

    return buffer

def upload_to_minio(client, data, filename):
    """
    Upload file (image buffer or video file) to MinIO
    Returns presigned URL for download
    """
    try:
        # Ensure snapshot bucket exists
        if not client.bucket_exists('snapshot'):
            client.make_bucket('snapshot')

        # Determine content type based on file extension
        if filename.endswith('.mp4'):
            content_type = 'video/mp4'
        elif filename.endswith('.png'):
            content_type = 'image/png'
        else:
            content_type = 'application/octet-stream'

        # Upload based on data type
        if isinstance(data, str):
            # File path for video
            client.fput_object(
                bucket_name='snapshot',
                object_name=filename,
                file_path=data,
                content_type=content_type
            )
        else:
            # Buffer for image
            client.put_object(
                bucket_name='snapshot',
                object_name=filename,
                data=data,
                length=data.getbuffer().nbytes,
                content_type=content_type
            )

        # Generate presigned URL for download
        presigned_url = client.presigned_get_object(
            bucket_name='snapshot',
            object_name=filename,
            expires=datetime.timedelta(hours=24)
        )

        return presigned_url

    except Exception as e:
        print(f"Error uploading to MinIO: {str(e)}")
        raise


def generate_time_range(start_time, end_time):
    """
    Generate time intervals between start_time and end_time with 10-minute intervals

    Args:
        start_time: datetime object
        end_time: datetime object

    Returns:
        list: List of datetime objects at 10-minute intervals
    """
    times = []
    current_time = start_time

    # Round start time to nearest 10-minute interval
    minutes = current_time.minute
    rounded_minutes = (minutes // 10) * 10
    current_time = current_time.replace(minute=rounded_minutes, second=0, microsecond=0)

    while current_time <= end_time:
        times.append(current_time)
        current_time += datetime.timedelta(minutes=10)

    return times


def find_composite_object(composite, timestamp):
    """
    Find the object name for a composite, either for a specific time or the latest
    """
    if timestamp is None:
        timestamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)

    filename = 'himawari_{}_{}.tif'.format(composite, timestamp.strftime('%Y%m%d_%H%M'))
    object_name = '{}/{}/{}'.format(
        composite, timestamp.strftime('%Y/%m/%d'), filename
    )
    return object_name


def create_video_from_images(image_buffers, fps=4):
    """
    Create MP4 video from image buffers using imageio in memory

    Args:
        image_buffers: List of BytesIO buffers containing PNG images
        fps: Frames per second (default: 4)

    Returns:
        BytesIO: Video buffer if successful, None if failed
    """
    try:
        import imageio
        from PIL import Image
        import numpy as np

        if not image_buffers:
            print("No images to create video")
            return None

        # Read images from buffers
        images = []
        for buffer in image_buffers:
            buffer.seek(0)
            # Use PIL to read the image from buffer
            pil_image = Image.open(buffer)
            # Convert to numpy array
            image_array = np.array(pil_image)
            images.append(image_array)

        # Create video in memory using BytesIO
        video_buffer = BytesIO()

        # Create video using imageio with in-memory buffer
        with imageio.get_writer(video_buffer, format='mp4', fps=fps, codec='libx264', quality=8) as writer:
            for image in images:
                writer.append_data(image)

        # Reset buffer position to beginning
        video_buffer.seek(0)

        print(f"Video created successfully in memory with {len(images)} frames at {fps:.2f} fps")
        return video_buffer

    except Exception as e:
        print(f"Error creating video with imageio: {str(e)}")
        return None

def create_single_snapshot(client, composite, timestamp, bbox, task_manager=None):
    """
    Create a single snapshot image

    Args:
        client: MinIO client
        composite: Composite name
        timestamp: Datetime object
        bbox: Bounding box [min_lng, min_lat, max_lng, max_lat]
        task_manager: Optional task manager for creating tasks when COG doesn't exist

    Returns:
        dict: Response with status, download_url, filename, etc.
    """
    try:
        # Check if COG exists
        object_name = find_composite_object(composite, timestamp)
        try:
            client.stat_object('himawari', object_name)
        except Exception:
            if task_manager:
                # Create a low priority task for COG generation
                task = task_manager.create_task(composite, timestamp, 'low')
                return {
                    'status': 'processing',
                    'message': 'COG file not found. Task created for processing.',
                    'task_id': task.task_id
                }
            else:
                return {
                    'status': 'error',
                    'message': f'COG file not found for {timestamp}'
                }

        # Generate filename
        filename = generate_filename(composite, timestamp, bbox, 'image')

        # Get presigned URL for COG
        presigned_url = client.presigned_get_object(
            bucket_name='himawari',
            object_name=object_name,
            expires=datetime.timedelta(hours=24)
        )

        # Create the snapshot image
        image_buffer = create_snapshot_image(presigned_url, bbox)

        # Upload to minio and get download URL
        download_url = upload_to_minio(client, image_buffer, filename)

        return {
            'status': 'completed',
            'download_url': download_url,
            'filename': os.path.basename(filename)
        }

    except Exception as e:
        print(f"Error creating snapshot: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error creating snapshot: {str(e)}'
        }


def create_series_snapshot(client, composite, start_time, end_time, bbox, task_manager=None):
    """
    Create a video from snapshots over a time range
    Only processes if ALL COGs exist, otherwise returns error

    Args:
        client: MinIO client
        composite: Composite name
        start_time: Start datetime
        end_time: End datetime
        bbox: Bounding box [min_lng, min_lat, max_lng, max_lat]
        task_manager: Optional task manager for creating tasks when COGs don't exist

    Returns:
        dict: Response with status, download_url, filename, etc.
    """
    try:
        # Generate time range
        time_intervals = generate_time_range(start_time, end_time)

        if not time_intervals:
            return {
                'status': 'error',
                'message': 'No valid time intervals found'
            }

        print(f"Checking COGs for {len(time_intervals)} time intervals")

        # First pass: check if ALL COGs exist
        missing_cogs = []
        for timestamp in time_intervals:
            object_name = find_composite_object(composite, timestamp)
            try:
                client.stat_object('himawari', object_name)
            except Exception:
                missing_cogs.append(timestamp)

        if missing_cogs and task_manager:
            # Create tasks for missing COGs
            created_tasks = []
            for timestamp in missing_cogs:
                task = task_manager.create_task(composite, timestamp, 'low')
                created_tasks.append(task.task_id)

            return {
                'status': 'processing',
                'message': f'Missing {len(missing_cogs)} files. Tasks created for processing.',
                'missing_count': len(missing_cogs),
                'total_count': len(time_intervals),
                'task_ids': created_tasks
            }

        print(f"All COGs exist, generating video for {len(time_intervals)} time intervals")

        # Second pass: generate all snapshots
        image_buffers = []

        for timestamp in time_intervals:
            result = create_single_snapshot(client, composite, timestamp, bbox)
            if result['status'] == 'completed':
                # Download the image to get buffer
                import requests
                response = requests.get(result['download_url'])
                if response.status_code == 200:
                    from io import BytesIO
                    image_buffer = BytesIO(response.content)
                    image_buffers.append(image_buffer)
                else:
                    return {
                        'status': 'error',
                        'message': f'Failed to download image for {timestamp}'
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'Failed to create snapshot for {timestamp}: {result.get("message", "Unknown error")}'
                }

        print(f"Successfully generated {len(image_buffers)} images")

        # Generate video filename
        filename = generate_filename(composite, start_time, bbox, 'video', end_time)

        # Create video in memory (250ms per frame = 4 fps)
        video_buffer = create_video_from_images(image_buffers, fps=4)

        if not video_buffer:
            return {
                'status': 'error',
                'message': 'Failed to create video with imageio'
            }

        # Upload video to MinIO
        download_url = upload_to_minio(client, video_buffer, filename)

        return {
            'status': 'completed',
            'download_url': download_url,
            'filename': os.path.basename(filename),
            'frame_count': len(image_buffers),
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            }
        }

    except Exception as e:
        print(f"Error creating series snapshot: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error creating video: {str(e)}'
        }


if __name__ == '__main__':
    # values = calculate_image_dimensions([100, 20, 140, 50], 7)
    url = 'http://127.0.0.1:9000/himawari/true_color/2025/05/24/himawari_true_color_20250524_0340.tif?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20250528%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250528T071643Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=e2a0394f9c5b3cf20d48598cbe4d46571b803db296ca1f9d5567cdc2e2f7d177'
    bbox = [119.28955078125001, 13.678013256725489, 123.83789062500001, 20.2725032501349]
    create_snapshot_image(url, bbox)
