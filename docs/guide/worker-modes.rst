Worker Modes
============

Guide to the task generator, sync, and composite worker modes: what each does, how data source resolution works, and when to combine or separate them.

The Twilight worker is a single Python process (``worker/main.py``) that can run in up to three concurrent modes, each responsible for a distinct stage of the processing pipeline. You activate modes with command-line flags and can combine any subset of them in a single invocation.

Modes
-----

--task — Task Generator
~~~~~~~~~~~~~~~~~~~~~~~

The task generator monitors the NOAA Himawari-9 S3 bucket for new data and creates processing tasks on the server.

**How it works:**

1. Computes the latest available 10-minute interval from the current UTC time.
2. Lists files under ``noaa-himawari9/AHI-L1b-FLDK/<YYYY/MM/DD/HHMM>/`` using anonymous S3 access.
3. When at least **160 files** are present for a given interval, it posts one task to ``/api/tasks`` for every composite in ``AVAILABLE_COMPOSITES``.
4. Advances to the next 10-minute interval and waits **60 seconds** before checking again.
5. If the current interval falls more than 20 minutes behind the latest available time, it fast-forwards by one 10-minute step to catch up.

Himawari-8/9 delivers one full-disk scan every 10 minutes, producing approximately 160 HSD files per interval. The task generator uses this file count as the availability signal.

--sync — Data Synchronization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The sync mode downloads raw HSD (Himawari Standard Data) files from the NOAA S3 bucket to your local MinIO instance, enabling faster processing by avoiding repeated remote reads.

**How it works:**

1. Starts from the latest available 10-minute interval.
2. Registers a ``pending`` sync record on the server via ``/api/syncs``.
3. Downloads files from ``noaa-himawari9/AHI-L1b-FLDK/`` to ``s3://raw/AHI-L1b-FLDK/`` on local MinIO.
4. Updates the sync record to ``completed`` when all files are downloaded.
5. Advances to the next 10-minute interval.
6. If a sync takes longer than **10 minutes**, marks it ``failed`` and moves on.

Sync records are queryable at ``GET /api/syncs/<timestamp>?source=himawari``. Workers consult this endpoint to decide where to read source data from.

--worker — Composite Worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The composite worker polls the task queue, claims tasks, processes satellite composites with SatPy, and uploads Cloud Optimized GeoTIFF (COG) tiles to MinIO for the server to serve.

**How it works:**

1. Calls ``GET /api/tasks/next`` to peek at the next pending task (optionally filtering by ``PRIORITIES`` and ``COMPOSITES``).
2. Calls ``GET /api/syncs/<timestamp>`` to determine the data source.
3. If the source is not ``pending``, claims the task with ``PUT /api/tasks/<task_id>/claim`` and processes it.
4. Passes the composite name and data source to SatPy, which reads AHI HSD files, generates the composite, resamples to the configured bounding box and resolution, and saves a COG file.
5. Uploads the COG to the ``himawari`` MinIO bucket.
6. Updates the task status to ``completed`` via ``PUT /api/tasks/<task_id>/status``.

Worker concurrency is determined dynamically: the process measures available RAM and CPU cores, then launches as many Dask threads as the system can safely support given ``MEM_PER_WORKER`` (default 7 GB per worker) and ``SYSTEM_MARGIN`` (default 4 GB reserved).

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
=======================  ==============================================  ====================================================================

Reading from local MinIO is faster because it avoids wide-area network latency and NOAA S3 egress. Running ``--sync`` alongside ``--worker`` means most tasks will use local data after the initial sync completes.

Running the Modes
-----------------

**All modes in one process:**

.. code-block:: bash

   cd worker
   python main.py --task --sync --worker

**Task generator only:**

.. code-block:: bash

   cd worker
   python main.py --task

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

* One lightweight machine runs ``--task`` and ``--sync`` to handle scheduling and data mirroring.
* One or more GPU or high-memory machines run ``--worker`` to handle SatPy processing.

All processes communicate through the shared server API and MinIO instance, so they do not need to be co-located.

**Scheduler machine:**

.. code-block:: bash

   cd worker
   python main.py --task --sync

**Processing machine (one or more):**

.. code-block:: bash

   cd worker
   python main.py --worker

Pass ``--worker-id`` when running multiple worker processes to distinguish them in server logs and task records. If omitted, a random ID is generated at startup.

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

Resolution and Bounding Box
---------------------------

The worker resamples each composite to a geographic bounding box and maximum resolution before saving the COG:

.. code-block:: bash

   # Default bounding box: lon 75–160, lat 0–55
   BBOX=75,0,160,55

   # Maximum resolution in meters (500, 1000, or 2000)
   MAX_RESOLUTION=1000

   # Resampler algorithm
   RESAMPLER=nearest

The actual output resolution is the coarser of ``MAX_RESOLUTION`` and the native resolution of the SatPy composite. Pixel dimensions are aligned to 256-pixel tile boundaries for optimal COG performance.
