Worker Modes
============

Guide to the sync and composite worker modes: what each does, how data source resolution works, and when to combine or separate them.

The Twilight worker is a single Python process (``worker/main.py``) that can run in two concurrent modes: data synchronization (``--sync``) and composite processing (``--worker``). You activate modes with command-line flags and can combine both in a single invocation.

Task Creation
-------------

There is no separate task-generator mode. Tasks are created by the server:

* When a sync record transitions to ``completed`` with ``initiator="sync"``, the server promotes matching ``normal`` pending tasks to ``high`` priority.
* If ``AUTO_CREATE_TASKS_ON_SYNC`` is enabled on the server, it also creates one task for every composite in the server's ``AVAILABLE_COMPOSITES`` list.
* ``AUTO_CREATE_TASKS_ON_SYNC`` defaults to ``false``. Set it to ``true`` on the server, or create individual tasks with ``POST /api/tasks``.

See :doc:`../configuration/server` for server-side settings.

--sync — Data Synchronization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The sync mode downloads raw HSD (Himawari Standard Data) files from the NOAA S3 bucket to your local MinIO instance, enabling faster processing by avoiding repeated remote reads.

**How it works:**

1. Starts from a recent 10-minute interval: the current UTC time rounded down to the nearest 10 minutes, minus 20 minutes.
2. Registers a ``pending`` sync record on the server via ``POST /api/syncs``.
3. Downloads ``.DAT.bz2`` files from ``noaa-himawari9/AHI-L1b-FLDK/`` to ``s3://raw/AHI-L1b-FLDK/`` on local MinIO.
4. Reports ``running`` progress (file count and byte count) while downloading.
5. Marks the sync ``completed`` once at least **160 files** are present and no download failed.
6. Advances to the next 10-minute interval. If the current interval takes longer than **10 minutes**, marks it ``failed`` and moves on; otherwise it retries after 60 seconds.

Sync records are queryable at ``GET /api/syncs/<timestamp>?source=himawari``. Workers consult this endpoint to decide where to read source data from.

--worker — Composite Worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The composite worker polls the task queue, claims tasks, processes satellite composites with SatPy, and uploads Cloud Optimized GeoTIFF (COG) tiles to MinIO for the server to serve.

**How it works:**

1. Calls ``GET /api/tasks/next`` to peek at the next pending task (optionally filtering by ``PRIORITIES`` and ``COMPOSITES``).
2. Calls ``GET /api/syncs/<timestamp>?source=himawari`` to determine the data source.
3. If the source is not ``pending``, claims the task with ``PUT /api/tasks/<task_id>/claim`` and processes it; otherwise it waits and polls again.
4. Loads the HSD files with SatPy, resamples them to the configured bounding box and resolution, and generates the composite.
5. Saves a COG and uploads it to the ``himawari`` MinIO bucket.
6. Updates the task status to ``completed`` (or ``failed`` with an error message) and posts profiler data.

Worker concurrency is determined dynamically: the process measures available RAM and CPU cores, then runs as many parallel Dask workers as the system can safely support given ``MEM_PER_WORKER`` (default 7 GB per worker) and ``SYSTEM_MARGIN`` (default 4 GB reserved). The count is never lower than 1 and never higher than the number of logical CPU cores.

If you run ``python main.py`` without any flags, the worker mode activates automatically. The ``--worker`` flag is only required when combining modes explicitly.

Data Source Resolution
----------------------

Before a worker claims a task, it checks the sync status for that timestamp to decide where to read raw data from.

=======================  ==============================================  ====================================================================
Sync status              Data source                                     Worker behaviour
=======================  ==============================================  ====================================================================
completed                Local MinIO (``s3://raw/…``)                    Claims and processes immediately
running                  Pending — wait                                  Skips the task for now and polls again
pending / not found      Remote NOAA S3 (``s3://noaa-himawari9/…``)      Claims and processes using anonymous remote S3 access
failed                   Remote NOAA S3 (``s3://noaa-himawari9/…``)      Claims and processes using anonymous remote S3 access
=======================  ==============================================  ====================================================================

Reading from local MinIO is faster because it avoids wide-area network latency and NOAA S3 egress. Running ``--sync`` alongside ``--worker`` means most tasks will use local data after the initial sync completes.

Running the Modes
-----------------

**Both modes in one process:**

.. code-block:: bash

   cd worker
   python main.py --sync --worker

**Sync only:**

.. code-block:: bash

   cd worker
   python main.py --sync

**Worker only:**

.. code-block:: bash

   cd worker
   python main.py --worker

**Worker with custom ID:**

.. code-block:: bash

   cd worker
   python main.py --worker --worker-id my-gpu-node-01

Running Modes as Separate Processes
-----------------------------------

You can distribute modes across different machines. A common pattern is:

* One lightweight machine runs ``--sync`` to mirror new data into local MinIO.
* One or more GPU or high-memory machines run ``--worker`` to handle SatPy processing.

All processes communicate through the shared server API and MinIO instance, so they do not need to be co-located.

**Sync machine:**

.. code-block:: bash

   cd worker
   python main.py --sync

**Processing machine (one or more):**

.. code-block:: bash

   cd worker
   python main.py --worker

Pass ``--worker-id`` when running multiple worker processes to distinguish them in server logs and task records. If omitted, the worker ID is generated from the hostname and local IP address.

Worker Filtering
----------------

By default a worker processes every composite and every priority level. You can narrow this with environment variables:

.. code-block:: bash

   # Only process high-priority tasks
   PRIORITIES=high python main.py --worker

   # Only process specific composites
   COMPOSITES=ir_clouds,true_color python main.py --worker

   # Combine both filters
   PRIORITIES=high,normal COMPOSITES=ash python main.py --worker

When running workers through the bundled Docker Compose file, only ``SERVER_URL``, the ``MINIO_*`` settings, and ``CACHE_SIZE_LIMIT`` are forwarded to the processor; ``PRIORITIES`` and ``COMPOSITES`` are not. See :doc:`../deployment/scaling` for how to pass these variables to containers.

Resolution and Bounding Box
---------------------------

The worker resamples each composite to a geographic bounding box and maximum resolution before saving the COG:

.. code-block:: bash

   # Default bounding box: lon 75–160, lat 0–55
   BBOX=75,0,160,55

   # Maximum resolution in meters (typical values: 500, 1000, 2000)
   MAX_RESOLUTION=1000

   # Resampler algorithm used for the final reprojection
   RESAMPLER=nearest

The actual output resolution is the coarser of ``MAX_RESOLUTION`` and the native resolution of the SatPy composite. Pixel dimensions are aligned to 256-pixel tile boundaries for optimal COG performance.
