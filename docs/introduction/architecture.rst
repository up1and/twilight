Architecture
============

How the Twilight client, server, and worker components fit together, and how data flows from NOAA S3 to your browser as interactive map tiles.

Twilight is a three-tier pipeline. Raw Himawari-8/9 sensor data enters from NOAA S3, workers transform it into web-compatible tiles, the Flask server exposes those tiles through a standard HTTP API, and the React client renders them on an interactive map. The server tracks tasks and sync state in Redis, workers claim work through the server API, and MinIO stores both raw data and finished composites.

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

1. **Availability check** — The sync worker lists ``noaa-himawari9/AHI-L1b-FLDK/{YYYY}/{MM}/{DD}/{HHMM}`` on NOAA S3 and waits until at least 160 ``.DAT.bz2`` files are present for the ten-minute interval. This threshold confirms that the full-disk scan is complete.

2. **Data synchronization** — The sync worker downloads the HSD files into the local MinIO ``raw`` bucket under the same prefix, and reports progress to the server through the sync record (``/api/syncs/{timestamp}``). A sync starts ``pending``, becomes ``running``, and ends ``completed`` (at least 160 files, no failures) or ``failed``. Workers and the server use this state to decide whether to read from local MinIO or fall back to NOAA S3.

3. **Task creation** — When a sync completes, the server creates one processing task per composite listed in ``AVAILABLE_COMPOSITES``. This only happens if ``AUTO_CREATE_TASKS_ON_SYNC`` is enabled and the sync was started by a worker (``initiator="sync"``); the server also promotes existing ``normal`` pending tasks to ``high``. Tasks are stored in Redis and include the composite name, timestamp, and priority. Clients can still create tasks explicitly with ``POST /api/tasks``.

4. **Composite generation** — Worker threads peek at the next available task with ``GET /api/tasks/next``, check the sync status (waiting while it is still ``running``), claim the task atomically via ``PUT /api/tasks/{task_id}/claim``, then load the HSD files with SatPy to generate composite GeoTIFFs. SatPy applies the appropriate spectral band math for each composite type. Because the worker does not poll for new data itself, a worker with only ``--worker`` needs tasks to be created by a ``--sync`` worker or by an API client.

5. **Tile generation and upload** — The composite GeoTIFF is converted to Cloud Optimized GeoTIFF (COG) format using Rasterio, then uploaded to the MinIO ``himawari`` bucket at ``{composite}/{YYYY}/{MM}/{DD}/himawari_{composite}_{YYYYMMDD_HHMM}.tif``.

6. **Tile serving** — The Flask server reads the COG from MinIO on demand in response to ``GET /tiles/{composite}/{timestamp}/{z}/{x}/{y}.png`` requests. Tile responses are cached server-side in Redis for twelve hours, and sent with a twelve-hour HTTP ``Cache-Control`` header; TileJSON is cached server-side for twelve hours but gets a one-hour HTTP ``Cache-Control`` header.

Components in Detail
--------------------

Client (React / TypeScript)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The client is a single-page application built with Vite. It renders satellite tiles on a Leaflet map using the TileJSON endpoint for layer configuration. The user can:

* Navigate through available timestamps with the time-range selector
* Select one or two composites from the multi-select dropdown
* Enable side-by-side split-screen comparison of two composites
* Sign in with a shared Authorization Key on the login page

The Authorization Key is stored in ``localStorage`` (``auth-token``) and sent as a ``Bearer`` token on every request to the server. The API endpoint is fixed at build time via ``VITE_API_BASE_URL`` and defaults to same-origin (Nginx proxies ``/api/``, ``/tiles/``, and ``/snapshots/``).

Server (Flask)
~~~~~~~~~~~~~~

The Flask server has three responsibilities: tile serving, task orchestration, and snapshot generation.

**Tile API**

=======================================================================  =========================================================================
Endpoint                                                                 Description
=======================================================================  =========================================================================
``GET /tiles/{composite}/{timestamp}/{z}/{x}/{y}.png``                   Returns a PNG tile. Timestamp in ISO 8601 format with dashes
``GET /tiles/{composite}/tile.json``                                     Returns TileJSON metadata for the Leaflet layer
``GET /tiles/{composite}/legend.json``                                   Returns the color legend for the composite
``GET /tiles/{map_type}/{z}/{x}/{y}.pbf``                                Returns vector tiles for map overlays
``GET /api/composites``                                                  Returns the latest timestamp for each composite with data
``POST /api/snapshots``                                                  Generates an image or MP4 snapshot from tiles
``GET /snapshots/{object_name}``                                         Serves a generated snapshot file
=======================================================================  =========================================================================

**Task and sync API**

==============================================  ============================================================
Endpoint                                        Description
==============================================  ============================================================
``POST /api/tasks``                             Creates a new processing task
``GET /api/tasks``                              Lists tasks with optional priority and composite filters
``GET /api/tasks/next``                         Peeks at the next pending task without claiming it
``GET /api/tasks/{task_id}``                    Returns one task
``DELETE /api/tasks/{task_id}``                 Deletes a task
``PUT /api/tasks/{task_id}/claim``              Atomically claims a pending task
``PUT /api/tasks/{task_id}/status``             Updates task status (completed, failed, etc.)
``POST /api/tasks/{task_id}/profile``           Stores a processing profile for a task
``GET /api/tasks/{task_id}/profile``            Returns a task's processing profile
``POST /api/syncs``                             Creates a raw data sync record for a timestamp
``PUT /api/syncs``                              Updates sync progress
``GET /api/syncs``                              Lists sync records
``GET /api/syncs/{timestamp}``                  Returns sync status: pending, running, completed, or failed
``DELETE /api/syncs/{timestamp}``               Deletes a sync record and its raw files
==============================================  ============================================================

All task and sync endpoints require a ``Bearer`` token matching the server's ``AUTH_KEY``.

Worker (Python)
~~~~~~~~~~~~~~~

The worker runs up to two concurrent threads, each handling a distinct role in the pipeline. You can run both in one process or distribute them across machines. Neither mode creates tasks for new data: the server does that when a sync completes (see step 3 above).

Sync worker (``--sync``)
^^^^^^^^^^^^^^^^^^^^^^^^

Downloads raw HSD files from NOAA S3 to the local MinIO ``raw`` bucket and reports status to the server so composite workers know when local data is ready. The timestamp starts at the current UTC time rounded down by the processing delay (20 minutes), then advances to the next interval on completion or after a ten-minute timeout.

Composite worker (``--worker``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Peeks at the next available task with ``GET /api/tasks/next``, waits if the sync for that timestamp is still running, claims the task atomically, runs SatPy to generate a composite, converts it to a COG, and uploads it to MinIO.

Infrastructure Services
-----------------------

Redis
~~~~~

Redis serves as both the task queue and the state store for composite availability. The server writes task records and sync state to Redis; workers interact with that state through the server's ``/api/tasks`` and ``/api/syncs`` endpoints rather than connecting to Redis directly. The default connection is ``redis://127.0.0.1:6379/0``, configurable via ``REDIS_URL``. The response cache uses a separate URL, configurable via ``CACHE_REDIS_URL``.

MinIO
~~~~~

MinIO provides S3-compatible object storage for two data types:

* **Raw HSD files** — Downloaded from NOAA S3 by the sync worker into the ``raw`` bucket and kept locally to avoid repeated downloads.
* **Processed composites** — COG files generated by the composite worker, stored in the ``himawari`` bucket, and read on demand by the Flask server.

The default connection is ``127.0.0.1:9000`` with credentials ``minioadmin`` / ``minioadmin``, all configurable through ``MINIO_ENDPOINT``, ``MINIO_ACCESS_KEY``, ``MINIO_SECRET_KEY``, and ``MINIO_SECURE``.
