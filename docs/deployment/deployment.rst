Docker Compose
==============

Deploy Twilight's Flask server, satellite processing workers, MinIO object store, Redis, and Nginx on a single host using Docker Compose.

Docker Compose is the recommended way to run a complete Twilight instance. The setup uses two Compose files: ``docker-compose.yml`` for the core infrastructure (Redis, MinIO, Flask server, and Nginx), and ``docker-compose.workers.yml`` for the three worker roles that download and process satellite data.

Services Overview
-----------------

The core stack defines four services:

=============  ====================  ==========================  ===========================================
Service        Image                 Port(s)                     Role
=============  ====================  ==========================  ===========================================
redis          redis:alpine          6379                        Task queue and state management
minio          minio/minio           9000, 9001                  Object storage for raw and processed tiles
server         twilight-server       5000 (internal)             Flask API and tile server
nginx          twilight-client       80                          Static frontend and reverse proxy
=============  ====================  ==========================  ===========================================

Two named volumes are created automatically:

* ``minio_data`` — persists all MinIO objects across restarts
* ``mbtiles_data`` — persists MBTiles files served by the Flask server

The worker Compose file adds three additional services that all use the ``twilight-worker:latest`` image:

* ``worker-sync`` — syncs raw HSD files from NOAA S3 to local MinIO
* ``worker-task`` — monitors data availability and generates processing tasks
* ``worker-processor`` — pulls tasks from the queue and generates composite tiles

Step-by-step Deployment
-----------------------

Step 1: Clone the repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/up1and/twilight.git
   cd twilight

Step 2: Configure environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copy the sample environment file and edit it with your credentials:

.. code-block:: bash

   cp .env.sample .env

At minimum, set the following values in ``.env``:

==================  ======================  =============================================
Variable            Default                 Description
==================  ======================  =============================================
MINIO_ACCESS_KEY    minioadmin              MinIO root username
MINIO_SECRET_KEY    minioadmin              MinIO root password
AUTH_KEY            twilight-secret         Shared secret for worker-to-server API requests
REDIS_URL           redis://redis:6379/0    Redis connection string (server only)
CACHE_SIZE_LIMIT    200                     Maximum on-disk cache per worker-processor, in GB
==================  ======================  =============================================

.. warning::

   Change ``MINIO_ACCESS_KEY``, ``MINIO_SECRET_KEY``, and ``AUTH_KEY`` before deploying to any environment reachable from the internet. The defaults are well-known and must not be used in production.

Step 3: Build and start the core services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build the server and client images, then start Redis, MinIO, the Flask server, and Nginx:

.. code-block:: bash

   docker compose up -d redis minio server nginx

Starting only the named services ensures the images are built before the workers try to use them. MinIO's web console is available at ``http://localhost:9001`` once the container is healthy.

Step 4: Start the workers
~~~~~~~~~~~~~~~~~~~~~~~~~

Start all three worker roles using the separate Compose file:

.. code-block:: bash

   docker compose -f docker-compose.workers.yml up -d

Each worker role runs a different command against the same image:

=======================  ===========================
Worker                   Command
=======================  ===========================
worker-sync              python main.py --sync
worker-task              python main.py --task
worker-processor         python main.py --worker
=======================  ===========================

``worker-sync`` and ``worker-task`` are typically run as single instances. ``worker-processor`` can be scaled horizontally.

Step 5: Access the application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Open your browser and navigate to ``http://localhost``. Nginx serves the React frontend on port ``80`` and proxies API and tile requests to the Flask server at ``http://server:5000``.

The Nginx configuration mounts ``./docker/nginx/nginx.conf`` into the container. It routes ``/api/`` and ``/tiles/`` to the server and serves the compiled React SPA from ``/usr/share/nginx/html`` for all other paths.

Worker Environment Variables
----------------------------

``worker-processor`` accepts an additional variable:

==================  =========  ====================================================================================
Variable            Default    Description
==================  =========  ====================================================================================
CACHE_SIZE_LIMIT    200        Maximum size of the local satellite data cache in GB, mounted at /tmp/himawari_cache
==================  =========  ====================================================================================

Tune ``CACHE_SIZE_LIMIT`` based on the available disk space on your Docker host. Each 10-minute Himawari observation set is approximately 1–2 GB of raw HSD data before processing.

Viewing Logs
------------

.. code-block:: bash

   # All core services
   docker compose logs -f

   # A specific worker role
   docker compose -f docker-compose.workers.yml logs -f worker-processor

Stopping the Stack
------------------

.. code-block:: bash

   # Stop core services (data volumes are preserved)
   docker compose down

   # Stop workers
   docker compose -f docker-compose.workers.yml down
