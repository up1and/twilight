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

1. **Frame the area you want to capture** — Pan and zoom the map to the region of interest. The snapshot bounding box is the current map viewport, and the map zoom becomes the render resolution.

2. **Select a composite and time** — Use the composite selector and time slider to choose what you want to capture. If one composite is selected, you get one file. If two composites are selected for side-by-side mode, the client sends one request per composite and you receive one file for each.

3. **Click the Snapshot button** — The server queues a render job and the client polls it, showing a spinner until the job finishes.

4. **Download the file** — When the job reports a completed result, the browser automatically downloads the file. PNG snapshots follow the pattern ``snapshot_{composite}_{YYYYMMDD_HHMM}_{bbox_hash}.png`` and MP4 files follow ``snapshot_{composite}_{start}_to_{end}_{bbox_hash}.mp4``.

Hold **Ctrl** before clicking the Snapshot button to switch to video mode. The icon changes to a video camera to confirm the mode is active.

Snapshot API
------------

Rendering is **asynchronous**. A single ``POST /api/snapshots`` request validates the parameters, checks that the requested composites already exist, enqueues a render job on the ``snapshots`` RQ queue, and responds with ``202 Accepted`` and a ``job_id``. The client then polls ``GET /api/snapshots/{job_id}`` until the job finishes.

Only already-processed timestamps can be exported. A render never waits for, or triggers, composite processing; a missing composite is rejected up front with ``404``.

The queueing and polling endpoints are open, matching the tile endpoints; the rendered file itself is served from ``GET /snapshots/{object_name}``.

Request Format
~~~~~~~~~~~~~~

.. code-block:: javascript

   {
     "bbox": [min_lng, min_lat, max_lng, max_lat],
     "timestamp": "2025-05-24T03:40:00+0000",
     "composite": "true_color",
     "zoom": 6
   }

**Required fields:**

=========  ============  =============================================
Field      Type          Description
=========  ============  =============================================
bbox       array of 4    Geographic bounding box: [min_lng, min_lat, max_lng, max_lat]
timestamp  string        ISO 8601 datetime for the snapshot frame
composite  string        One of the available composite identifiers
zoom       integer       Map zoom level the bbox was captured at
=========  ============  =============================================

**Optional fields:**

==========  ======  ================================================
Field       Type    Description
==========  ======  ================================================
timedelta   number  Duration in minutes for a timelapse
==========  ======  ================================================

Render Resolution
~~~~~~~~~~~~~~~~~

``zoom`` sets the output resolution using the same Web Mercator grid the map
tiles use: ``256 * 2^zoom`` pixels span the world, so the snapshot matches what
the user sees on screen. Because a wider viewport is rendered at a coarser
resolution, the output size stays roughly constant as the user zooms — about
2.4 megapixels for a 1080p viewport regardless of zoom level.

The output is rendered at exactly the requested size. Zooming past the source
COG's own resolution upsamples it, which matches how the map itself renders at
deep zoom levels, so the snapshot always looks like what is on screen.

Bounding Box and Zoom Validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``bbox`` and ``zoom`` are validated before a job is queued:

* Longitude must satisfy ``-180 <= min_lng < max_lng <= 180``.
* Latitude must satisfy ``-90 <= min_lat < max_lat <= 90``.
* Both bounds must be finite numbers; ``min`` must be strictly less than ``max`` on both axes.
* ``zoom`` must be an integer between ``0`` and ``22``.
* The rendered pixel area must not exceed 16 megapixels. A viewport-sized export stays far below this, so it only rejects crafted requests such as a world-sized bbox at zoom 10.

Any violation returns ``400 Bad Request`` with a message naming the failed rule, and no job is created.

Queueing a Snapshot
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -X POST http://localhost:5000/api/snapshots \
     -H "Content-Type: application/json" \
     -d '{
       "bbox": [119.0, 13.5, 124.0, 20.5],
       "timestamp": "2025-05-24T03:40:00+0000",
       "composite": "true_color",
       "zoom": 6
     }'

**202 Accepted** — the render job is queued:

.. code-block:: json

   {
     "job_id": "0f4a2c9e8b1d4c6fa3e5d7b9c1a2f3e4",
     "status": "pending"
   }

**404 Not Found** — the composite for that timestamp does not exist yet:

.. code-block:: json

   {
     "error": "Not Found",
     "message": "1 composite(s) in the requested range have not been processed yet; only existing ones can be exported.",
     "missing": ["2025-05-24T03:40:00+00:00"]
   }

``missing`` lists every absent timestamp in the requested range, so a timelapse
request reports exactly which frames are gaps. Composite files are pruned after
``TASK_EXPIRE_DAYS``, so a range older than that can never be rendered — the
list tells you which, rather than leaving you to guess.

Polling the Job
~~~~~~~~~~~~~~~

.. code-block:: bash

   curl http://localhost:5000/api/snapshots/0f4a2c9e8b1d4c6fa3e5d7b9c1a2f3e4

A job is a resource, so its state is reported in the body and the HTTP status
stays ``200``; only an unknown ``job_id`` returns ``404``.

**200 OK** — still working:

.. code-block:: json

   {
     "job_id": "0f4a2c9e8b1d4c6fa3e5d7b9c1a2f3e4",
     "status": "pending"
   }

``status`` is ``pending`` before a worker picks the job up and ``running`` while
it renders. Both mean "keep polling".

**200 OK** — file is ready:

.. code-block:: json

   {
     "job_id": "0f4a2c9e8b1d4c6fa3e5d7b9c1a2f3e4",
     "status": "completed",
     "download_url": "/snapshots/image/snapshot_true_color_20250524_0340_a1b2c3d4.png"
   }

**200 OK** — the render failed:

.. code-block:: json

   {
     "job_id": "0f4a2c9e8b1d4c6fa3e5d7b9c1a2f3e4",
     "status": "failed",
     "message": "Error creating snapshot: ..."
   }

The payload carries at most four fields: ``job_id``, ``status``, and then
``download_url`` or ``message`` depending on the outcome. ``status`` is one of
``pending``, ``running``, ``completed``, or ``failed``, the same
vocabulary the task and sync endpoints use.

Finished job records are kept for one hour before RQ drops them; after that the
``job_id`` returns ``404``. The rendered file itself stays in MinIO.

Timelapse (Series Snapshot)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``timedelta`` to create an MP4 from a sequence of 10-minute frames. The
request is queued exactly like a single snapshot, and every frame's COG must
already exist:

.. code-block:: bash

   curl -X POST http://localhost:5000/api/snapshots \
     -H "Content-Type: application/json" \
     -d '{
       "bbox": [119.0, 13.5, 124.0, 20.5],
       "timestamp": "2025-05-24T00:00:00Z",
       "composite": "true_color",
       "zoom": 6,
       "timedelta": 180
     }'

If frames are missing the request is rejected before anything is queued:

.. code-block:: json

   {
     "error": "Not Found",
     "message": "3 composite(s) in the requested range have not been processed yet; only existing ones can be exported.",
     "missing": [
       "2025-05-24T00:10:00+00:00",
       "2025-05-24T01:20:00+00:00",
       "2025-05-24T02:30:00+00:00"
     ]
   }

The maximum ``timedelta`` is **1440 minutes (24 hours)**. Frames are rendered
straight into the encoder and never stored individually, so an export does not
leave intermediate images behind.

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

Both ends of the range are inclusive, so a 180-minute request from ``00:00`` yields 19 frames at ``00:00`` through ``03:00``. The MP4 filename uses the requested timestamps, not the rounded-down start, so it may not match the first frame when the request is not aligned to a 10-minute boundary.

The resulting MP4 is encoded at **4 frames per second** using libx264.
