Overview
========

Twilight API overview, base URLs, and endpoint groups.

The Twilight API serves map tiles, manages processing tasks, tracks data sync status, and generates geographic snapshots of satellite imagery.

Base URL
--------

::

   http://your-server:5000

Replace ``your-server`` with the hostname or IP address where your Twilight server is running. There is no versioning prefix — the base URL is the server root.

Authentication
--------------

Some endpoint groups require a Bearer token. See :doc:`authentication` for details on which endpoints are protected and how to pass your token.

Endpoint Groups
---------------

Tile Serving
~~~~~~~~~~~~

Fetch raster PNG tiles for any composite and timestamp, or retrieve TileJSON metadata for map clients.

See: :doc:`tiles`

Composite State
~~~~~~~~~~~~~~~

Query the latest available timestamp for each satellite composite. Public — no auth required.

See: :doc:`tiles`

Task Management
~~~~~~~~~~~~~~~

Create, list, claim, and update processing tasks. All task endpoints require authentication.

See: :doc:`tasks`

Sync Management
~~~~~~~~~~~~~~~

Create and update raw data sync records, and query sync status by timestamp. Requires authentication.

See: :doc:`syncs`

Snapshots
~~~~~~~~~

Generate and download static PNG or MP4 snapshots of satellite imagery within a geographic bounding box. No auth required.

See: :doc:`snapshots`

Authentication
~~~~~~~~~~~~~~

Verify a Bearer token against the server's configured ``AUTH_KEY``.

See: :doc:`authentication`

Vector Tiles
~~~~~~~~~~~~

Serve Mapbox Vector Tile (PBF) layers for land boundaries and flight information regions.

See: :doc:`tiles`

Response Formats
----------------

**JSON** — All ``/api/*`` endpoints return ``application/json``. Error responses include ``error`` and ``message`` fields.

**PNG** — Raster tile endpoints (``/tiles/…/{z}/{x}/{y}.png``) return ``image/png`` binary data.

**PBF** — Vector tile endpoints (``/tiles/…/{z}/{x}/{y}.pbf``) return ``application/x-protobuf``, gzip-encoded.

**Video/image** — Snapshot download endpoints return ``image/png`` or ``video/mp4`` depending on the requested output.

HTTP Caching
------------

Successful tile responses are cached server-side:

====================================================  ==============
Endpoint                                              Cache duration
====================================================  ==============
``/tiles/{composite}/{timestamp}/{z}/{x}/{y}.png``    12 hours
``/tiles/{composite}/tile.json``                      12 hours
``/tiles/{map_type}/{z}/{x}/{y}.pbf``                 12 hours
====================================================  ==============

.. note::

   Only HTTP 200 responses are cached. Error responses (404, 400, 500) are never cached and will be re-evaluated on the next request.
