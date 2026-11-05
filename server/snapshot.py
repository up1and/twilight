import math
import hashlib
import datetime

from io import BytesIO
from PIL import Image
from pycoast import ContourWriterAGG
from rio_tiler.io import Reader
from rio_tiler.colormap import cmap

from config import get_pycoast_dir


def validate_bbox(bbox):
    """
    Validate a geographic bounding box.

    Args:
        bbox: Candidate [min_lng, min_lat, max_lng, max_lat]

    Returns:
        str | None: An error message, or None when the bbox is valid.
    """
    message = "bbox must be an array of 4 numbers [min_lng, min_lat, max_lng, max_lat]"

    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return message

    for value in bbox:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return message
        if not math.isfinite(value):
            return "bbox values must be finite numbers"

    min_lng, min_lat, max_lng, max_lat = bbox

    if not (-180.0 <= min_lng < max_lng <= 180.0):
        return "bbox longitudes must satisfy -180 <= min_lng < max_lng <= 180"

    if not (-90.0 <= min_lat < max_lat <= 90.0):
        return "bbox latitudes must satisfy -90 <= min_lat < max_lat <= 90"

    return None


def estimate_snapshot_size(bbox, zoom, tile_size=256):
    """
    Pixel size of bbox at a Web Mercator zoom level.

    This is the same sampling the map tiles use, so a snapshot rendered at the
    current zoom matches what the user sees on screen: the output size stays
    roughly constant as the user zooms, because a wider viewport is rendered
    at a correspondingly coarser resolution.

    Args:
        bbox: [min_lng, min_lat, max_lng, max_lat]
        zoom: Map zoom level
        tile_size: Tile edge in pixels (Web Mercator default is 256)

    Returns:
        tuple[int, int]: (width, height) in pixels.
    """
    min_lng, min_lat, max_lng, max_lat = bbox

    def mercator_y(lat):
        # Web Mercator cuts off at ~85.05 degrees, so clamp before projecting.
        lat = max(min(lat, 85.05112878), -85.05112878)
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    world_px = tile_size * (2 ** zoom)

    width = (max_lng - min_lng) / 360.0 * world_px
    height = (mercator_y(max_lat) - mercator_y(min_lat)) / (2 * math.pi) * world_px

    return max(math.ceil(width), 1), max(math.ceil(height), 1)


def validate_zoom(zoom, min_zoom=0, max_zoom=22):
    """
    Validate a requested zoom level.

    Returns:
        str | None: An error message, or None when valid.
    """
    if isinstance(zoom, bool) or not isinstance(zoom, (int, float)):
        return "zoom must be a number"

    if not math.isfinite(zoom) or zoom != int(zoom):
        return "zoom must be an integer"

    if not (min_zoom <= zoom <= max_zoom):
        return f"zoom must be between {min_zoom} and {max_zoom}"

    return None


def validate_snapshot_limits(bbox, zoom, max_pixels=16_000_000):
    """
    Check that a bbox renders within the pixel budget at the given zoom.

    Zoom alone normally keeps the output bounded near the viewport size; this
    guard catches pathological input (an absurd zoom, or a bbox far larger than
    the viewport it was read from) before a worker is asked to render it.

    Args:
        bbox: [min_lng, min_lat, max_lng, max_lat]
        zoom: Map zoom level
        max_pixels: Maximum width * height

    Returns:
        str | None: An error message, or None when within limits.
    """
    width, height = estimate_snapshot_size(bbox, zoom)
    pixels = width * height

    if pixels > max_pixels:
        return (
            f"bbox is too large to render at zoom {zoom}: {width}x{height} px "
            f"({pixels} pixels), the limit is {max_pixels} pixels."
        )

    return None


def generate_bbox_hash(bbox):
    """Generate a short hash from bbox coordinates"""
    bbox_str = f"{bbox[0]:.6f},{bbox[1]:.6f},{bbox[2]:.6f},{bbox[3]:.6f}"
    return hashlib.md5(bbox_str.encode()).hexdigest()[:8]

def generate_filename(composite, timestamp, bbox, file_type="image", end_timestamp=None):
    """Generate filename for snapshot image or video with prefix"""
    bbox_hash = generate_bbox_hash(bbox)
    time_str = timestamp.strftime("%Y%m%d_%H%M")

    if file_type == "video" and end_timestamp:
        end_str = end_timestamp.strftime("%Y%m%d_%H%M")
        return f"video/snapshot_{composite}_{time_str}_to_{end_str}_{bbox_hash}.mp4"
    else:
        return f"image/snapshot_{composite}_{time_str}_{bbox_hash}.png"

def create_snapshot_image(presigned_url, bbox, width=None, height=None):
    """
    Render bbox from a COG, draw coastlines on top, and return it as PNG.

    The read is bounded by bbox. Without width/height rio-tiler returns the
    COG's native grid; with them it reprojects to that size, upsampling when
    the request is finer than the source, which matches how the map renders
    past its native zoom.

    Args:
        presigned_url: Presigned URL of the source COG
        bbox: Bounding box [min_lng, min_lat, max_lng, max_lat]
        width: Optional output width in pixels
        height: Optional output height in pixels

    Returns:
        BytesIO: PNG bytes.
    """
    read_kwargs = {"width": width, "height": height} if width and height else {}

    with Reader(presigned_url) as cog:
        img = cog.part(bbox, **read_kwargs)
        bounds = img.bounds
        crs = cog.crs

    # Single-channel data needs a colormap to render as RGB
    colormap = cmap.get("rdgy") if img.data.shape[0] == 1 else None
    buffer = img.render(colormap=colormap)
    image = Image.open(BytesIO(buffer))

    # pycoast accepts area_def as a (proj4_string, area_extent) tuple
    proj_str = crs.to_proj4() if crs else "+proj=latlong +datum=WGS84"
    # pycoast supports area_def as a tuple: (proj4_string, area_extent)
    area_def = (proj_str, (bounds[0], bounds[1], bounds[2], bounds[3]))

    cw = ContourWriterAGG(get_pycoast_dir())
    # Add coastlines using pycoast
    # resolution 'h' for high quality, or 'i' for intermediate, 'l' for low
    cw.add_coastlines(image, area_def, resolution="i",
                      outline=(130, 130, 130), width=1)

    buffer = BytesIO()
    image.save(buffer, format="png")
    buffer.seek(0)
    return buffer

def upload_to_minio(client, data, filename):
    """
    Upload file (image buffer or video file) to MinIO
    """
    try:
        # Ensure snapshot bucket exists
        if not client.bucket_exists("snapshot"):
            client.make_bucket("snapshot")

        # Determine content type based on file extension
        if filename.endswith(".mp4"):
            content_type = "video/mp4"
        elif filename.endswith(".png"):
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"

        # Upload based on data type
        if isinstance(data, str):
            # File path for video
            client.fput_object(
                bucket_name="snapshot",
                object_name=filename,
                file_path=data,
                content_type=content_type
            )
        else:
            # Buffer for image
            client.put_object(
                bucket_name="snapshot",
                object_name=filename,
                data=data,
                length=data.getbuffer().nbytes,
                content_type=content_type
            )

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


def generate_composite_object_name(composite, timestamp):
    """
    Generate the object name for a composite
    """
    filename = f"himawari_{composite}_{timestamp.strftime('%Y%m%d_%H%M')}.tif"
    object_name = f"{composite}/{timestamp.strftime('%Y/%m/%d')}/{filename}"
    return object_name


def create_video_from_images(image_buffers, fps=4):
    """
    Create MP4 video from image buffers using imageio, encoded in memory.

    Args:
        image_buffers: List of BytesIO buffers containing PNG images
        fps: Frames per second (default: 4, matching the 10-minute scan cadence)

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

        # Create video in memory using BytesIO
        video_buffer = BytesIO()

        # Append frames one at a time so peak memory stays at a single frame
        # instead of holding every frame as a numpy array at once.
        with imageio.get_writer(video_buffer, format="mp4", fps=fps, codec="libx264", quality=8) as writer:
            for buffer in image_buffers:
                buffer.seek(0)
                with Image.open(buffer) as pil_image:
                    writer.append_data(np.array(pil_image))

        # Reset buffer position to beginning
        video_buffer.seek(0)

        print(f"Video created successfully in memory with {len(image_buffers)} frames at {fps:.2f} fps")
        return video_buffer

    except Exception as e:
        print(f"Error creating video with imageio: {str(e)}")
        return None

def cog_exists(client, composite, timestamp):
    """Return True when the composite COG for this timestamp exists in MinIO"""
    object_name = generate_composite_object_name(composite, timestamp)
    try:
        client.stat_object("himawari", object_name)
        return True
    except Exception:
        return False


def create_single_snapshot(client, composite, timestamp, bbox, width=None, height=None):
    """
    Create a single snapshot image from an existing COG.

    The COG must already exist: this function never waits for or triggers
    composite processing, so a render job always finishes quickly.

    Args:
        client: MinIO client
        composite: Composite name
        timestamp: Datetime object
        bbox: Bounding box [min_lng, min_lat, max_lng, max_lat]
        width: Output width in pixels
        height: Output height in pixels

    Returns:
        dict: Response with status, object_name, filename, etc.
    """
    try:
        object_name = generate_composite_object_name(composite, timestamp)

        # Generate filename
        filename = generate_filename(composite, timestamp, bbox, "image")

        # Get presigned URL for COG
        presigned_url = client.presigned_get_object(
            bucket_name="himawari",
            object_name=object_name,
            expires=datetime.timedelta(hours=24)
        )

        # Create the snapshot image at the requested size
        image_buffer = create_snapshot_image(
            presigned_url, bbox, width=width, height=height
        )

        # Upload to minio and get object name
        upload_to_minio(client, image_buffer, filename)

        return {
            "status": "completed",
            "object_name": filename,
        }

    except Exception as e:
        print(f"Error creating snapshot: {str(e)}")
        return {
            "status": "failed",
            "message": f"Error creating snapshot: {str(e)}"
        }


def missing_cogs(client, composite, start_time, end_time):
    """
    Return the timestamps in [start_time, end_time] with no composite COG.

    Timelapse rendering needs every frame, so callers check this up front
    instead of rendering a partial video.
    """
    return [
        timestamp
        for timestamp in generate_time_range(start_time, end_time)
        if not cog_exists(client, composite, timestamp)
    ]


def create_series_snapshot(client, composite, start_time, end_time, bbox, width=None, height=None):
    """
    Create a timelapse video from existing COGs over a time range.

    Every frame's COG must already exist; use ``missing_cogs`` first to check.
    Frames are rendered straight into the encoder and never uploaded
    individually, so a 24-hour export leaves no orphaned PNGs behind.

    Args:
        client: MinIO client
        composite: Composite name
        start_time: Start datetime
        end_time: End datetime
        bbox: Bounding box [min_lng, min_lat, max_lng, max_lat]
        width: Frame width in pixels
        height: Frame height in pixels

    Returns:
        dict: Response with status, object_name, filename, etc.
    """
    try:
        # Generate time range
        time_intervals = generate_time_range(start_time, end_time)

        if not time_intervals:
            return {
                "status": "failed",
                "message": "No valid time intervals found"
            }

        print(f"Generating video for {len(time_intervals)} time intervals")

        # Render each frame straight to a PNG buffer in memory.
        image_buffers = []

        for timestamp in time_intervals:
            object_name = generate_composite_object_name(composite, timestamp)
            try:
                presigned_url = client.presigned_get_object(
                    bucket_name="himawari",
                    object_name=object_name,
                    expires=datetime.timedelta(hours=24)
                )
                image_buffers.append(
                    create_snapshot_image(
                        presigned_url, bbox, width=width, height=height
                    )
                )
            except Exception as e:
                return {
                    "status": "failed",
                    "message": f"Failed to render {timestamp}: {str(e)}"
                }

        print(f"Successfully generated {len(image_buffers)} images")

        # Generate video filename
        filename = generate_filename(composite, start_time, bbox, "video", end_time)

        # Encode in memory: 250ms per frame = 4 fps
        video_buffer = create_video_from_images(image_buffers)

        if not video_buffer:
            return {
                "status": "failed",
                "message": "Failed to create video with imageio"
            }

        # Upload video to MinIO
        upload_to_minio(client, video_buffer, filename)

        return {
            "status": "completed",
            "object_name": filename,
        }

    except Exception as e:
        print(f"Error creating series snapshot: {str(e)}")
        return {
            "status": "failed",
            "message": f"Error creating video: {str(e)}"
        }


if __name__ == "__main__":
    # values = calculate_image_dimensions([100, 20, 140, 50], 7)
    url = "http://127.0.0.1:9000/himawari/true_color/2025/05/24/himawari_true_color_20250524_0340.tif?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20250528%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250528T071643Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=e2a0394f9c5b3cf20d48598cbe4d46571b803db296ca1f9d5567cdc2e2f7d177"
    bbox = [119.28955078125001, 13.678013256725489, 123.83789062500001, 20.2725032501349]
    create_snapshot_image(url, bbox)
