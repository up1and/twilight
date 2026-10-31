Tiles
=====

Raster tile, TileJSON, and vector tile endpoints.

Serve raster PNG tiles and TileJSON metadata for Himawari composites, vector tiles for overlays, and query latest composite timestamps.

The tile endpoints power the interactive map in Twilight. Raster tiles are generated on-the-fly from Cloud-Optimized GeoTIFFs (COGs) stored in MinIO. Vector tiles for coastlines and flight information regions (FIRs) are served from pre-built MBTiles files. All tile endpoints are publicly accessible.

Successful raster and vector tile responses are cached server-side in Redis for 12 hours. HTTP caching differs by endpoint: PNG and PBF tiles are sent with ``Cache-Control: public, max-age=43200`` (12 hours), while TileJSON is sent with ``Cache-Control: public, max-age=3600`` (1 hour) even though the server keeps its own copy for 12 hours.

.. note::

   Composite names use underscores internally (e.g., ``ir_clouds``) but dashes in URLs (e.g., ``ir-clouds``). The server converts them automatically.

Get Tile
--------

``GET /tiles/{composite}/{timestamp}/{z}/{x}/{y}.png``

Returns a 256x256 PNG tile for the given composite and point in time. Single-band composites (e.g., ``ir-clouds``) are rendered with the ``RdGy`` colormap; multi-band composites (e.g., ``true-color``) are rendered as RGB.

**Cache:** 12 hours server-side; ``Cache-Control: max-age=43200`` to clients

**Path Parameters:**

- ``composite`` - Composite identifier. Use dashes in the URL (e.g., ``ir-clouds``, ``true-color``, ``ash``, ``airmass``, ``day-microphysics``, ``night-microphysics``, ``fog``, ``convection``, ``water-vapor``). Underscores are also accepted.
- ``timestamp`` - Observation time in ISO 8601 format with colons replaced by dashes, e.g., ``2025-04-20T04-00-00Z``. The server normalises the value back to standard ISO 8601 before querying the data store.
- ``z`` - Zoom level
- ``x`` - Tile column
- ``y`` - Tile row

**Response:**

======  ===================================================================
Status  Description
======  ===================================================================
200     PNG image (``image/png``)
400     Invalid timestamp format
404     Composite not found, or tile coordinates are outside the data bounds
======  ===================================================================

**Example:**

.. code-block:: bash

   curl -o tile.png "https://your-server/tiles/ir-clouds/2025-04-20T04-00-00Z/5/25/15.png"

Get TileJSON
------------

``GET /tiles/{composite}/tile.json``

Returns TileJSON 2.x metadata for a composite, including the geographic bounds, zoom range, and a tile URL template. This endpoint reads the latest available COG for the composite to determine the correct bounds.

**Cache:** 12 hours server-side; ``Cache-Control: max-age=3600`` to clients

**Path Parameters:**

- ``composite`` - Composite identifier (dashes or underscores accepted)

**Response (200):**

.. code-block:: json

   {
     "name": "Himawari Ir Clouds",
     "attribution": "© Himawari Ir Clouds",
     "bounds": [85.0, -60.0, 205.0, 60.0],
     "minzoom": 0,
     "maxzoom": 8,
     "tiles": ["/tiles/ir-clouds/{time}/{z}/{x}/{y}.png"]
   }

**Response fields:**

- ``name`` - Human-readable composite name, derived from the composite identifier
- ``attribution`` - Attribution string prefixed with ``©`` for display on the map
- ``bounds`` - Geographic extent as [min_lng, min_lat, max_lng, max_lat] in WGS 84
- ``minzoom`` - Minimum zoom level supported
- ``maxzoom`` - Maximum zoom level supported
- ``tiles`` - Array containing the tile URL template

**Status codes:**

======  =======================================
Status  Description
======  =======================================
200     TileJSON object
404     Composite not found or no data available yet
500     Error reading the source raster
======  =======================================

Get Legend
----------

``GET /tiles/{composite}/legend.json``

Returns the color legend for a composite as an array of ``{"colors": [...], "label": "..."}`` entries. Legends are defined for ``airmass``, ``ash``, ``convection``, ``day-microphysics``, ``night-microphysics``, and ``water-vapor``; any other composite returns an empty array.

No cache headers are added to legend responses.

**Example:**

.. code-block:: bash

   curl "http://localhost:5000/tiles/ash/legend.json"

Composites
----------

``GET /api/composites``

Returns the latest timestamp and availability (day / night / all) for each configured composite that currently has data. Composites with no processed COGs are omitted from the response entirely. Use this to seed the time slider and display availability icons in the UI.

``availability`` is ``day`` for ``true_color``, ``day_microphysics``, and ``convection``; ``night`` for ``fog`` and ``night_microphysics``; and ``all`` for every other composite.

No authentication required.

**Response (200):**

.. code-block:: json

   {
     "ir_clouds": {
       "timestamp": "2025-04-20T04:00:00+00:00",
       "availability": "all"
     },
     "true_color": {
       "timestamp": "2025-04-20T04:00:00+00:00",
       "availability": "day"
     }
   }

The response contains only composites with at least one COG in MinIO. After the server restarts, the timestamp reflects the newest COG found during initialization and then advances as workers finish tasks.

Vector Tiles
------------

``GET /tiles/{map_type}/{z}/{x}/{y}.pbf``

Returns a gzip-compressed Mapbox Vector Tile (MVT) for map overlays. Two datasets are available: Natural Earth land polygons and ICAO Flight Information Region (FIR) boundaries.

**Cache:** 12 hours server-side; ``Cache-Control: max-age=43200`` to clients

**Path Parameters:**

- ``map_type`` - Dataset to serve:

  - ``lands`` — Natural Earth land/coastline polygons
  - ``firs`` — ICAO Flight Information Region boundaries

- ``z`` - Zoom level (0-18)
- ``x`` - Tile column (0 to 2^n - 1 for zoom n)
- ``y`` - Tile row (0 to 2^n - 1 for zoom n)

**Response:**

======  =====================================================================
Status  Description
======  =====================================================================
200     Protobuf vector tile (``application/x-protobuf``, gzip-encoded)
204     Tile exists in range but contains no features
400     Invalid map_type or tile coordinates out of range for the zoom level
404     MBTiles file not found on the server
======  =====================================================================

The response includes ``Access-Control-Allow-Origin: *`` and ``Content-Encoding: gzip`` headers.

**Example:**

.. code-block:: bash

   curl -o overlay.pbf "http://your-server/tiles/firs/4/12/7.pbf"