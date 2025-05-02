import os

from minio import Minio
from minio.error import S3Error
from minio.commonconfig import Tags

from utils import logger
from config import endpoint, access_key, secret_key


def upload(bucket_name, object_name, file, composite_name):
    client = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False
    )

    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)


    tags = Tags(for_object=True)
    tags['composite'] = composite_name

    _, ext = os.path.splitext(object_name)
    mime_map = {
        '.tif': 'image/tiff',
        '.tiff': 'image/tiff',
        '.jpg': 'image/jpeg',
        '.png': 'image/png'
    }
    content_type = mime_map.get(ext, 'application/octet-stream')

    result = client.fput_object(
        bucket_name, object_name, file,
        content_type=content_type,
        metadata={'Composite': composite_name},
        tags=tags
    )

    logger.info(
        'created {0} object; bucket: {1}, etag: {2}, version-id: {3}'.format(
            result.object_name, result.bucket_name, result.etag, result.version_id,
        )
    )

    return result


if __name__ == '__main__':
    try:
        upload('himawari', '/bands/2025/05/09/himawari_B13_20250509_0140.tif', 'himawari_ahi_B13_202505090750.tif', 'B13')
    except S3Error as exc:
        print('error occurred.', exc)