Snapshots
=========

Export a PNG snapshot or MP4 timelapse of any Himawari composite at a specific time or time range of up to 24 hours, via the UI or API.

Twilight can export satellite imagery as static PNG images or MP4 timelapse videos. A snapshot captures a composite at a single point in time; a timelapse stitches together a sequence of 10-minute frames across a time range. Both are generated server-side from Cloud Optimized GeoTIFF (COG) tiles stored in MinIO, with coastlines rendered using pycoast.

Using the Snapshot Button in the Web UI
---------------------------------------

The **Snapshot** button is in the map toolbar. Its icon changes depending on the keyboard state:

* **Camera icon** — click to export a single PNG snapshot of the current view and time.
* **Video icon** — hold **Ctrl** while clicking to export an MP4 timelapse. The timelapse spans the ``timedelta`` configured for the current view.

**To export a snapshot:**

1. **Frame the area you want to capture** — Pan and zoom the map to the region of interest. The snapshot bounding box is derived from the current map viewport.

2. **Select a composite and time** — Use the composite selector and time slider to choose what you want to capture. The snapshot uses the currently selected composite and timestamp.

3. **Click the Snapshot button** — Click the **Camera** button to export a PNG. The button shows a spinner while the server is generating the image.

4. **Download the file** — When the server returns a completed response, the browser automatically downloads the file. PNG snapshots follow the pattern ``snapshot_{composite}_{YYYYMMDD_HHMM}_{bbox_hash}.png`` and MP4 files follow ``snapshot_{composite}_{start}_to_{end}_{bbox_hash}.mp4``.

Hold **Ctrl** before clicking the Snapshot button to switch to video mode. The icon changes to a video camera to confirm the mode is active.

If the COG for the requested time does not yet exist, the server creates a processing task automatically and returns a ``202 Accepted`` response. Retry the request once the task completes.

Snapshot API
------------

Snapshots are created with a single ``POST /api/snapshots`` request. The server responds synchronously: if the COG is available it generates and returns the file immediately; if it is not, it queues a task and responds with ``202``.

Request Format
~~~~~~~~~~~~~~

.. code-block:: javascript

   {
     "bbox": [min_lng, min_lat, max_lng, max_lat],
     "timestamp": "2025-05-24T03:40:00+0000",
     "composite": "true_color"
   }

**Required fields:**

=========  ============  =============================================
Field      Type          Description
=========  ============  =============================================
bbox       array of 4    Geographic bounding box: [min_lng, min_lat, max_lng, max_lat]
timestamp  string        ISO 8601 datetime for the snapshot frame
composite  string        One of the available composite identifiers
=========  ============  =============================================

**Optional fields:**

==========  ======  ================================================
Field       Type    Description
==========  ======  ================================================
timedelta   number  Duration in minutes for a timelapse
==========  ======  ================================================

Single Snapshot
~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -X POST http://localhost:5000/api/snapshots \
     -H "Content-Type: application/json" \
     -d '{
       "bbox": [119.0, 13.5, 124.0, 20.5],
       "timestamp": "2025-05-24T03:40:00+0000",
       "composite": "true_color"
     }'

**201 Created** — image is ready:

.. code-block:: json

   {
     "status": "completed",
     "download_url": "/snapshots/image/snapshot_true_color_20250524_0340_a1b2c3d4.png",
     "filename": "snapshot_true_color_20250524_0340_a1b2c3d4.png"
   }

**202 Accepted** — COG not found, task queued:

.. code-block:: json

   {
     "status": "pending",
     "message": "COG file not found. Task created for processing.",
     "task_id": "true_color_20250524_034000_a1b2c3d4"
   }

Timelapse (Series Snapshot)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``timedelta`` to create an MP4 from a sequence of 10-minute frames:

.. code-block:: bash

   curl -X POST http://localhost:5000/api/snapshots \
     -H "Content-Type: application/json" \
     -d '{
       "bbox": [119.0, 13.5, 124.0, 20.5],
       "timestamp": "2025-05-24T00:00:00Z",
       "composite": "true_color",
       "timedelta": 180
     }'

**201 Created** — video is ready:

.. code-block:: json

   {
     "status": "completed",
     "download_url": "/snapshots/video/snapshot_true_color_20250524_0000_to_20250524_0300_a1b2c3d4.mp4",
     "filename": "snapshot_true_color_20250524_0000_to_20250524_0300_a1b2c3d4.mp4",
     "frame_count": 18,
     "time_range": {
       "start": "2025-05-24T00:00:00",
       "end": "2025-05-24T03:00:00"
     }
   }

**202 Accepted** — one or more COGs are missing, tasks queued:

.. code-block:: json

   {
     "status": "pending",
     "message": "Missing 3 files. Tasks created for processing.",
     "missing_count": 3,
     "total_count": 18,
     "task_ids": ["true_color_20250524_000000_a1b2c3d4", "true_color_20250524_001000_a1b2c3d4"]
   }

The maximum ``timedelta`` is **1440 minutes (24 hours)**. Requests with a larger value are rejected with a ``400 Bad Request`` error. Timelapse generation requires all COGs in the time range to exist; if any are missing the server queues tasks instead of producing a partial video.

Downloading a Snapshot
----------------------

Once you have a ``download_url`` from the completed response, fetch the file directly:

.. code-block:: bash

   curl -O "http://localhost:5000/snapshots/image/snapshot_true_color_20250524_0340_a1b2c3d4.png"

The URL pattern is ``GET /snapshots/{object_name}`` where ``object_name`` is the path returned in ``download_url``, including the ``image/`` or ``video/`` prefix.

How Frames Are Timed
--------------------

For series snapshots, the server rounds the ``timestamp`` down to the nearest 10-minute boundary and then steps forward in 10-minute increments until it reaches ``timestamp + timedelta``. This aligns with Himawari's 10-minute scan cadence.

For example, a ``timestamp`` of ``2025-05-24T00:07:00Z`` with ``timedelta: 30`` produces frames at ``00:00``, ``00:10``, ``00:20``, and ``00:30``.

The resulting MP4 is encoded at **4 frames per second** using libx264.