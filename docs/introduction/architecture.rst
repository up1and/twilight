Architecture
============

How the Twilight client, server, and worker components fit together, and how data flows from NOAA S3 to your browser as interactive map tiles.

Twilight is a three-tier pipeline. Raw Himawari-8/9 sensor data enters from NOAA S3, workers transform it into web-compatible tiles, the Flask server exposes those tiles through a standard HTTP API, and the React client renders them on an interactive map. Redis connects the server and workers via a task queue; MinIO stores both raw data and finished tiles.

Component Diagram
-----------------

::

   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │                 │    │                 │    │                 │
   │   Client        │◄──►│   Server        │◄──►│   Worker        │
   │   (React/TS)    │    │   (Flask)       │    │   (Python)      │
   │                 │    │                 │    │                 │
   └─────────────────┘    └─────────────────┘    └─────────────────┘
           │                       │                       │
           │                       │                       │
           ▼                       ▼                       ▼
   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │   Web Browser   │    │   MinIO/S3      │    │   NOAA S3       │
   │ (User Interface)│    │   (Tile Storage)│    │   (Raw Data)    │
   └─────────────────┘    └─────────────────┘    └─────────────────┘

Data Flow
---------

Each ten-minute observation cycle follows six stages from raw sensor data to browser tile.

1. **Data monitoring** — The task-generator worker thread polls ``noaa-himawari9/AHI-L1b-FLDK`` on AWS S3 and waits until at least 160 files are present for a given ten-minute interval. This threshold confirms that the full-disk scan is complete.

2. **Data synchronization** — The sync worker downloads the HSD format files from NOAA S3 and stores them in the local MinIO instance. The server tracks sync status per timestamp (``/api/syncs/{timestamp}``) so workers can check whether to read from local MinIO or fall back to NOAA S3 directly.

3. **Task creation** — Once a complete dataset is confirmed, the task generator creates one processing task per enabled composite type by calling ``POST /api/tasks`` on the server. Tasks are stored in Redis and include the composite name, timestamp, and priority.

4. **Composite generation** — Worker threads poll ``GET /api/tasks`` for pending tasks, claim them atomically via ``PUT /api/tasks/{task_id}/claim``, then load the HSD files with SatPy to generate composite GeoTIFFs. SatPy applies the appropriate spectral band math for each composite type.

5. **Tile generation and upload** — The composite GeoTIFF is converted to Cloud Optimized GeoTIFF (COG) format using Rasterio, then uploaded to MinIO in a bucket keyed by composite name and timestamp.

6. **Tile serving** — The Flask server reads tiles from MinIO on demand in response to ``GET /tiles/{composite}/{timestamp}/{z}/{x}/{y}.png`` requests. PNG tiles are cached for twelve hours; TileJSON metadata is cached for twelve hours.

Components in Detail
--------------------

Client (React / TypeScript)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The client is a single-page application built with Vite. It renders satellite tiles on a Leaflet map using the TileJSON endpoint for layer configuration. The user can:

* Navigate through available timestamps with the time-range selector
* Select one or two composites from the multi-select dropdown
* Enable side-by-side split-screen comparison of two composites
* Configure the API endpoint and bearer token through the settings panel

The API endpoint and token are stored in ``localStorage`` and sent as a ``Bearer`` token on every request to the server.

Server (Flask)
~~~~~~~~~~~~~~

The Flask server has two responsibilities: tile serving and task orchestration.

**Tile API**

=======================================================================  =========================================================================
Endpoint                                                                 Description
=======================================================================  =========================================================================
``GET /tiles/{composite}/{timestamp}/{z}/{x}/{y}.png``                   Returns a PNG tile. Timestamp in ISO 8601 format with dashes
``GET /tiles/{composite}/tile.json``                                     Returns TileJSON metadata for the Leaflet layer
``GET /api/composites/latest``                                           Returns the latest available timestamp for each composite
=======================================================================  =========================================================================

**Task and sync API**

====================================  ============================================================
Endpoint                              Description
====================================  ============================================================
``POST /api/tasks``                   Creates a new processing task
``GET /api/tasks``                    Lists tasks with optional priority and composite filters
``PUT /api/tasks/{task_id}/status``   Updates task status (completed, failed, etc.)
``POST /api/syncs``                   Creates a raw data sync record for a timestamp
``GET /api/syncs/{timestamp}``        Returns sync status: pending, running, or completed
``PUT /api/syncs``                    Updates sync progress
====================================  ============================================================

All task and sync endpoints require a ``Bearer`` token matching the server's ``AUTH_KEY``.

Worker (Python)
~~~~~~~~~~~~~~~

The worker runs up to three concurrent threads, each handling a distinct role in the pipeline. You can run all three in one process or distribute them across machines.

Task generator (``--task``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Polls NOAA S3 every 60 seconds. When 160 files are available for a ten-minute interval, it creates one task per composite and advances to the next interval.

Sync worker (``--sync``)
^^^^^^^^^^^^^^^^^^^^^^^^

Downloads raw HSD files from NOAA S3 to local MinIO. Reports status to the server so composite workers know when local data is ready. Moves to the next interval on completion or after a ten-minute timeout.

Composite worker (``--worker``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Peeks at the next available task, waits if sync is still running, claims the task atomically, runs SatPy to generate a composite, converts to COG tiles, and uploads to MinIO.

Infrastructure Services
-----------------------

Redis
~~~~~

Redis serves as both the task queue and the state store for composite availability. The server writes task records and sync state to Redis; workers read from it to claim tasks and check data readiness. The default connection is ``redis://127.0.0.1:6379/0``, configurable via ``REDIS_URL``.

MinIO
~~~~~

MinIO provides S3-compatible object storage for two data types:

* **Raw HSD files** — Downloaded from NOAA S3 by the sync worker and kept locally to avoid repeated downloads.
* **Processed tiles** — COG tiles generated by the composite worker and served on demand by the Flask server.

The default connection is ``127.0.0.1:9000`` with credentials ``minioadmin`` / ``minioadmin``, all configurable through ``MINIO_ENDPOINT``, ``MINIO_ACCESS_KEY``, and ``MINIO_SECRET_KEY``.
