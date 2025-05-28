import hashlib
import datetime

from io import BytesIO

from rio_tiler.io import Reader


def generate_bbox_hash(bbox):
    """Generate a short hash from bbox coordinates"""
    bbox_str = f"{bbox[0]:.6f},{bbox[1]:.6f},{bbox[2]:.6f},{bbox[3]:.6f}"
    return hashlib.md5(bbox_str.encode()).hexdigest()[:8]

def generate_snapshot_filename(composite, timestamp, bbox):
    """Generate snapshot filename"""
    bbox_hash = generate_bbox_hash(bbox)
    time_str = timestamp.strftime('%Y%m%d_%H%M')
    return f"snapshot_{composite}_{time_str}_{bbox_hash}.png"

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

def upload_snapshot_to_minio(client, image_buffer, filename):
    """
    Upload snapshot image to MinIO
    Returns presigned URL for download
    """
    try:
        # Ensure snapshot bucket exists
        if not client.bucket_exists('snapshot'):
            client.make_bucket('snapshot')

        # Upload to minio from buffer
        client.put_object(
            bucket_name='snapshot',
            object_name=filename,
            data=image_buffer,
            length=image_buffer.getbuffer().nbytes,
            content_type='image/png'
        )

        # Generate presigned URL for download
        presigned_url = client.presigned_get_object(
            bucket_name='snapshot',
            object_name=filename,
            expires=datetime.timedelta(hours=24)
        )

        return presigned_url

    except Exception as e:
        print(f"Error uploading snapshot to MinIO: {str(e)}")
        raise







if __name__ == '__main__':
    # values = calculate_image_dimensions([100, 20, 140, 50], 7)
    url = 'http://127.0.0.1:9000/himawari/true_color/2025/05/24/himawari_true_color_20250524_0340.tif?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20250528%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250528T071643Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=e2a0394f9c5b3cf20d48598cbe4d46571b803db296ca1f9d5567cdc2e2f7d177'
    bbox = [119.28955078125001, 13.678013256725489, 123.83789062500001, 20.2725032501349]
    create_snapshot_image(url, bbox)
