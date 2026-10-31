Docker Compose
==============

Deploy Twilight's Flask server, satellite processing workers, MinIO object store, Redis, and Nginx on a single host using Docker Compose.

Docker Compose is the recommended way to run a complete Twilight instance. The setup uses two Compose files: ``docker-compose.yml`` for the core infrastructure (Redis, MinIO, Flask server, RQ maintenance worker/cron, and Nginx), and ``docker-compose.workers.yml`` for the two worker roles that download and process satellite data.

Services Overview
-----------------

The core stack defines six services:

=============  ====================  ==========================  ===========================================
Service        Image                 Port(s)                     Role
=============  ====================  ==========================  ===========================================
redis          redis:alpine          127.0.0.1:6379              Task queue and state management
minio          minio/minio           9000, 9001                  Object storage for raw and processed tiles
server         twilight-server       5000 (internal)             Flask API and tile server
rq-worker      twilight-server       —                           Executes scheduled maintenance jobs (prune)
rq-cron        twilight-server       —                           Enqueues daily maintenance jobs on a schedule
nginx          twilight-client       80                          Static frontend and reverse proxy
=============  ====================  ==========================  ===========================================

Two named volumes are created automatically:

* ``redis_data`` — persists the Redis dataset across restarts
* ``minio_data`` — persists all MinIO objects across restarts

MBTiles vector basemaps (``natural_earth.mbtiles``, ``firs.mbtiles``) are read from the ``data/`` directory next to the server package; they are not covered by a named volume.

The worker Compose file adds two additional services that both use the ``twilight-worker:latest`` image:

* ``worker-sync`` — syncs raw HSD files from NOAA S3 to local MinIO
* ``worker-processor`` — pulls tasks from the queue and generates composite tiles

The server creates processing tasks when a sync completes, but only if ``AUTO_CREATE_TASKS_ON_SYNC=true``; it defaults to ``false``. The bundled ``docker-compose.yml`` does not forward this variable, so add it to the ``server`` service's ``environment`` list to enable automatic task creation in Compose.

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

Build the server and client images, then start Redis, MinIO, the Flask server, the RQ maintenance services, and Nginx:

.. code-block:: bash

   docker compose up -d redis minio server rq-worker rq-cron nginx

Starting only the named services ensures the images are built before the workers try to use them. ``rq-worker`` executes the scheduled prune jobs and ``rq-cron`` enqueues them; without them, expired tasks and syncs are never cleaned up. MinIO's web console is available at ``http://localhost:9001`` once the container is healthy.

Step 4: Start the workers
~~~~~~~~~~~~~~~~~~~~~~~~~

Start both worker roles using the separate Compose file:

.. code-block:: bash

   docker compose -f docker-compose.workers.yml up -d

Each worker role runs a different command against the same image:

=======================  ===========================
Worker                   Command
=======================  ===========================
worker-sync              python main.py --sync
worker-processor         python main.py --worker
=======================  ===========================

``worker-sync`` is typically run as a single instance. ``worker-processor`` can be scaled horizontally.

Step 5: Access the application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Open your browser and navigate to ``http://localhost``. The map and tile endpoints are public, so imagery loads without signing in. To use the dashboard and task management, open ``http://localhost/login`` and enter the ``AUTH_KEY`` from your ``.env``; a successful sign-in redirects to ``/dashboard``.

Nginx serves the React frontend on port ``80`` and proxies API and tile requests to the Flask server at ``http://server:5000``.

The Nginx configuration mounts ``./docker/nginx/nginx.conf`` into the container. It routes ``/api/``, ``/tiles/``, and ``/snapshots/`` to the server and serves the compiled React SPA from ``/usr/share/nginx/html`` for all other paths.

Worker Environment Variables
----------------------------

``worker-processor`` accepts an additional variable:

==================  =========  ====================================================================================
Variable            Default    Description
==================  =========  ====================================================================================
CACHE_SIZE_LIMIT    200        Maximum size of the local satellite data cache in GB, mounted at /tmp/satpy_cache
==================  =========  ====================================================================================

Tune ``CACHE_SIZE_LIMIT`` based on the available disk space on your Docker host. Each 10-minute Himawari observation set is approximately 1–2 GB of raw HSD data before processing.

``docker-compose.workers.yml`` only forwards ``SERVER_URL``, ``MINIO_ENDPOINT``, ``MINIO_ACCESS_KEY``, ``MINIO_SECRET_KEY``, ``MINIO_SECURE``, and ``CACHE_SIZE_LIMIT``. The worker also reads ``PRIORITIES``, ``COMPOSITES``, ``MAX_RESOLUTION``, ``BBOX``, ``RESAMPLER``, ``MEM_PER_WORKER``, and ``SYSTEM_MARGIN``, but Compose will not pass them through from ``.env`` unless you add them to the service's ``environment`` list. Likewise, ``AUTH_KEY`` is not forwarded and falls back to the worker default, so change both defaults or add the variable explicitly when using a custom key.

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
