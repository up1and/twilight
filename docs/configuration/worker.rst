Worker
======

Configure Twilight workers: MinIO and server connections, task filtering, resolution, bounding box, cache, resampling, and memory scaling.

Workers are stateless processes that connect to the shared MinIO store and the Flask server. Each worker mode — sync (``--sync``) and processor (``--worker``) — reads the same environment variables but uses only the subset relevant to its function. You can run workers on the same host as the server or on separate machines by pointing ``SERVER_URL`` and ``MINIO_ENDPOINT`` at the master node.

Connection Settings
-------------------

``MINIO_ENDPOINT``
~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``127.0.0.1:9000``

Host and port of the MinIO API. On a remote worker node, set this to the IP address of the master node: ``<MASTER_IP>:9000``.

``MINIO_ACCESS_KEY``
~~~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``minioadmin``

Access key for MinIO. Must match the value configured on the MinIO server.

``MINIO_SECRET_KEY``
~~~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``minioadmin``

Secret key for MinIO. Must match the value configured on the MinIO server.

``MINIO_SECURE``
~~~~~~~~~~~~~~~~

- **Type:** boolean (``true`` / ``false``)
- **Default:** ``false``

Whether to use HTTPS when connecting to MinIO. Must match the server's setting.

``SERVER_URL``
~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``http://127.0.0.1:5000``

Full base URL of the Twilight Flask API. Remote workers should set this to ``http://<MASTER_IP>:5000``. In a local Docker Compose setup, use ``http://server:5000``.

``AUTH_KEY``
~~~~~~~~~~~~

- **Type:** string
- **Default:** ``twilight-secret``

Shared secret sent as a Bearer token with every API request to the server. This value must match ``AUTH_KEY`` on the server.

Task Filtering
--------------

These variables apply to the processor worker (``--worker`` mode) and let you dedicate specific workers to subsets of the work queue.

``PRIORITIES``
~~~~~~~~~~~~~~

- **Type:** string
- **Default:** (empty - all priorities)

Comma-separated list of priority levels this worker will accept. Accepted values: ``high``, ``normal``, ``low``. Leave empty to process tasks of all priorities.

.. code-block:: bash

   PRIORITIES=high,normal

``COMPOSITES``
~~~~~~~~~~~~~~

- **Type:** string
- **Default:** (empty - all composites)

Comma-separated list of composite types this worker will process. Leave empty to process all composite types. Accepted values: ``ir_clouds``, ``true_color``, ``ash``, ``airmass``, ``day_microphysics``, ``night_microphysics``, ``fog``, ``convection``, ``water_vapor``.

.. code-block:: bash

   COMPOSITES=ir_clouds,true_color

.. note::

   The bundled ``docker-compose.workers.yml`` only forwards ``SERVER_URL``, the ``MINIO_*`` settings, and ``CACHE_SIZE_LIMIT``. Variables such as ``PRIORITIES``, ``COMPOSITES``, ``MAX_RESOLUTION``, ``BBOX``, ``RESAMPLER``, ``MEM_PER_WORKER``, and ``SYSTEM_MARGIN`` must be added to the relevant service's ``environment`` list before they take effect in Compose.

Image Processing
----------------

``MAX_RESOLUTION``
~~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``1000``

Maximum pixel resolution in metres per pixel. A smaller value produces higher-resolution output. Accepted values: ``500``, ``1000``, ``2000``.

``BBOX``
~~~~~~~~

- **Type:** string
- **Default:** ``75,0,160,55``

Geographic bounding box for processed output, as four comma-separated decimal values: ``lon_min,lat_min,lon_max,lat_max``. The default covers the Himawari full-disk region from 75°E to 160°E and 0°N to 55°N.

.. code-block:: bash

   # Southeast Asia only
   BBOX=95,0,145,35

``RESAMPLER``
~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``nearest``

Resampler passed to SatPy when reprojecting the scene onto the target bounding box. ``nearest`` is fastest; ``bilinear`` produces smoother output at the cost of extra CPU time. Any SatPy resampler name works if its optional dependencies are installed. The worker always performs a native resample first, then applies this resampler for the final target area.

Cache
-----

``CACHE_SIZE_LIMIT``
~~~~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``200``

Maximum size of the local satellite data cache in gigabytes. When the cache exceeds this limit, older files are evicted. Used by the processor worker.

Memory Management
-----------------

The processor worker auto-scales its Dask parallelism based on available system RAM. Two variables control this behaviour.

``MEM_PER_WORKER``
~~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``7.0``

Estimated peak RAM consumption per parallel processing task in gigabytes. The worker uses this value together with ``SYSTEM_MARGIN`` to calculate how many Dask workers to run concurrently.

``SYSTEM_MARGIN``
~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``4.0``

Amount of RAM in gigabytes to keep free for the operating system and other processes. At startup the worker measures currently available RAM, computes ``floor((available_ram - SYSTEM_MARGIN) / MEM_PER_WORKER)``, and clamps the result to at least 1 and at most the number of logical CPU cores available to the process.

For example, on a 32 GB host with 12 GB already in use and the default settings, ``available_ram`` is 20 GB and the worker allocates ``floor((20 - 4) / 7) = 2`` Dask workers. Because the calculation uses live available memory rather than total memory, the count can differ between restarts on a busy host. Reduce ``MEM_PER_WORKER`` only if your workload consistently uses less memory; setting it too low will cause out-of-memory errors.

Sample Configuration
--------------------

**Local worker (.env):**

.. code-block:: bash

   # Connect to local server and MinIO
   SERVER_URL=http://server:5000
   MINIO_ENDPOINT=minio:9000
   MINIO_ACCESS_KEY=minioadmin
   MINIO_SECRET_KEY=minioadmin
   MINIO_SECURE=false
   AUTH_KEY=change-me-before-deploying

   # Process all composites and priorities (defaults)
   # PRIORITIES=
   # COMPOSITES=

   # Processing options
   MAX_RESOLUTION=1000
   BBOX=75,0,160,55
   RESAMPLER=nearest

   # Memory
   MEM_PER_WORKER=7.0
   SYSTEM_MARGIN=4.0

   # Cache
   CACHE_SIZE_LIMIT=200

**Remote worker (.env):**

.. code-block:: bash

   # Remote worker pointing at master node
   SERVER_URL=http://192.168.1.100:5000
   MINIO_ENDPOINT=192.168.1.100:9000
   MINIO_ACCESS_KEY=your-access-key
   MINIO_SECRET_KEY=your-secret-key
   AUTH_KEY=your-strong-secret-key

   # Dedicate this worker to high-priority true_color only
   PRIORITIES=high
   COMPOSITES=true_color

   MAX_RESOLUTION=500
   BBOX=100,10,150,50
   RESAMPLER=bilinear
   CACHE_SIZE_LIMIT=100