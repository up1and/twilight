Introduction
============

Twilight is a real-time Himawari-8/9 satellite data visualization system for meteorologists, researchers, and weather enthusiasts.

Twilight turns raw Himawari-8/9 satellite data into interactive, time-navigable map tiles you can explore in a browser. It continuously monitors NOAA S3 for new imagery every ten minutes, processes the data into multiple scientific composites, and serves it through a tile API backed by MinIO object storage. The result is a live, multi-composite satellite viewer with side-by-side comparison and time-range navigation.

Components
----------

Twilight is split into three cooperating components. Each runs independently and communicates over a shared Redis task queue and MinIO tile store.

Client
~~~~~~

A React and TypeScript web application built with Vite. Renders satellite tiles on an interactive Leaflet map with time-range navigation, composite selection, and a side-by-side split-screen comparison tool.

Server
~~~~~~

A Flask REST API that serves map tiles from MinIO, provides TileJSON metadata for the client, manages the distributed task queue in Redis, and tracks raw data sync status.

Worker
~~~~~~

Python processes that monitor NOAA S3 for new HSD files, synchronize raw data to local MinIO, generate composite GeoTIFFs using SatPy, convert them to Cloud Optimized GeoTIFF tiles, and upload the results for the server to serve.

What Problems It Solves
-----------------------

Himawari-8/9 data is publicly available on NOAA S3, but consuming it directly requires downloading large HSD format files, running spectral band math to produce composites, and reprojecting the output into web-compatible tiles — all on a ten-minute update cycle. Twilight automates this entire pipeline and exposes the results through a standard tile API that any Leaflet-based client can consume.

Available Composites
--------------------

Twilight supports ten satellite composites out of the box. The set is configurable through the ``AVAILABLE_COMPOSITES`` environment variable on both the server and the worker.

===================  ===========================================================================
Composite            Description
===================  ===========================================================================
true_color           Natural-color view using visible red, green, and blue bands
ir_clouds            Infrared cloud-top temperature
ash                  Volcanic ash detection using thermal infrared differences
airmass              Upper-tropospheric air mass analysis
day_microphysics     Daytime cloud microphysics (particle size and phase)
night_microphysics   Nighttime cloud microphysics using infrared bands
fog                  Low-level fog and stratus detection
convection           Deep convection and overshooting tops
vapor                Differential  water vapor
===================  ===========================================================================

What You Need to Run It
-----------------------

* **Python 3.11+** — for the server and worker processes
* **Node.js 18+** — for the client development server and build tooling
* **Docker and Docker Compose** — to run Redis (task queue) and MinIO (tile and raw data storage)
* **Outbound internet access** — the worker fetches raw HSD files from ``noaa-himawari8/9`` on AWS S3 anonymously

The worker reads approximately 160 files per ten-minute observation interval from NOAA S3. Make sure your network and disk have enough headroom for continuous ingestion.