Server
======

Configure the Twilight Flask server: MinIO object storage, Redis, API authentication, composite types, and data retention settings.

The server reads all configuration from environment variables at startup. You can set these in a ``.env`` file at the project root or pass them directly to your container environment. The defaults are suitable for a local Docker Compose setup — change them for any production or multi-node deployment.

.. note::

   The bundled ``docker-compose.yml`` forwards only ``REDIS_URL``, ``MINIO_ENDPOINT``, ``MINIO_ACCESS_KEY``, ``MINIO_SECRET_KEY``, ``MINIO_SECURE``, and ``AUTH_KEY`` to the server service. Settings such as ``CACHE_REDIS_URL``, ``AVAILABLE_COMPOSITES``, ``AUTO_CREATE_TASKS_ON_SYNC``, ``PYCOAST_DATA_ROOT``, ``TASK_EXPIRE_DAYS``, and ``SYNC_EXPIRE_DAYS`` must be added to that service's ``environment`` list before they take effect in Compose.

Storage and Messaging
---------------------

``MINIO_ENDPOINT``
~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``127.0.0.1:9000``

Host and port of the MinIO S3-compatible object store. In a Docker Compose deployment, set this to ``minio:9000`` to use the internal service name.

``MINIO_ACCESS_KEY``
~~~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``minioadmin``

Access key (username) for MinIO authentication. Must match the value used when starting MinIO.

``MINIO_SECRET_KEY``
~~~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``minioadmin``

Secret key (password) for MinIO authentication. Must match the value used when starting MinIO.

``MINIO_SECURE``
~~~~~~~~~~~~~~~~

- **Type:** boolean (``true`` / ``false``)
- **Default:** ``false``

Whether to use HTTPS when connecting to MinIO. Set to ``true`` behind a TLS-terminating proxy or when MinIO itself serves TLS.

``REDIS_URL``
~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``redis://127.0.0.1:6379/0``

Full connection URL for Redis. Redis stores the task queue, sync records, and composite availability state, and also backs RQ maintenance jobs. In Docker Compose, use ``redis://redis:6379/0``.

``CACHE_REDIS_URL``
~~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``REDIS_URL`` with the database index changed from ``/0`` to ``/1``

Redis URL used by Flask-Caching for the tile, TileJSON, and vector-tile response cache. Point it at a separate database or instance to keep cached responses from competing with queue data.

Authentication
--------------

``AUTH_KEY``
~~~~~~~~~~~~

- **Type:** string
- **Default:** ``twilight-secret``

Shared secret used to authenticate worker-to-server API requests. Workers must supply this value as a Bearer token in the ``Authorization`` header. Change this to a strong, unique value in any deployment accessible over a network.

.. warning::

   The default ``AUTH_KEY`` value is public. Always set a strong, unique key before exposing the server to any network outside localhost.

Composites and Data Retention
-----------------------------

``AVAILABLE_COMPOSITES``
~~~~~~~~~~~~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``ir_clouds,true_color,ash,airmass,day_microphysics,night_microphysics,fog,convection,water_vapor``

Comma-separated list of composite types the server accepts and advertises. It controls which composites appear in ``/api/composites``, which ``/tiles/{composite}`` requests succeed, and which tasks the server creates automatically when a sync completes. Remove entries here to disable specific products system-wide.

``AUTO_CREATE_TASKS_ON_SYNC``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Type:** boolean (``true`` / ``false``)
- **Default:** ``false``

When enabled, the server creates one task per composite in ``AVAILABLE_COMPOSITES`` each time a sync started by a worker (``initiator="sync"``) reaches ``completed``, and promotes pending ``normal`` tasks for that timestamp to ``high``. Leave it disabled to create tasks explicitly through ``POST /api/tasks`` instead.

.. note::

   The bundled ``docker-compose.yml`` does not forward this variable to the server container. Add it to the ``server`` service's ``environment`` list when enabling it in Compose.

``PYCOAST_DATA_ROOT``
~~~~~~~~~~~~~~~~~~~~~

- **Type:** string (directory path)
- **Default:** the platform user data directory for ``pycoast`` (for example ``~/.local/share/pycoast`` on Linux)

Directory containing the GSHHS and WDBII shapefiles used to draw coastlines and borders in snapshots. The value is used only if the directory exists; otherwise pycoast's default data directory is used. The official server image sets this to ``/usr/local/share/pycoast``.

``TASK_EXPIRE_DAYS``
~~~~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``7``

Age in days after which a task record is pruned, measured from its creation time regardless of status. Pruning removes the task from Redis and deletes its composite from the MinIO ``himawari`` bucket. Set to ``0`` to disable expiration and retain all task history indefinitely.

``SYNC_EXPIRE_DAYS``
~~~~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``30``

Age in days after which a sync record is pruned, measured from the observation timestamp. Pruning removes the sync record from Redis and deletes the associated raw HSD files from the MinIO ``raw`` bucket. Set to ``0`` to disable expiration and retain all sync history indefinitely.

Sample Configuration
--------------------

**Local development (.env):**

.. code-block:: bash

   # MinIO — internal Docker Compose service names
   MINIO_ENDPOINT=minio:9000
   MINIO_ACCESS_KEY=minioadmin
   MINIO_SECRET_KEY=minioadmin
   MINIO_SECURE=false

   # Redis — internal Docker Compose service name
   REDIS_URL=redis://redis:6379/0
   # CACHE_REDIS_URL=redis://redis:6379/1

   # Authentication
   AUTH_KEY=change-me-before-deploying

   # Composites (default: all nine types)
   # AVAILABLE_COMPOSITES=ir_clouds,true_color,ash,airmass,day_microphysics,night_microphysics,fog,convection,water_vapor

   # Automatically create tasks when a worker sync completes
   # AUTO_CREATE_TASKS_ON_SYNC=true

   # Coastline shapefiles for snapshots (defaults to the pycoast data directory)
   # PYCOAST_DATA_ROOT=/usr/local/share/pycoast

   # Data retention
   # TASK_EXPIRE_DAYS=7
   # SYNC_EXPIRE_DAYS=30

**Remote server (.env):**

.. code-block:: bash

   # MinIO — an address reachable from worker nodes on the network
   MINIO_ENDPOINT=192.0.2.10:9000
   MINIO_ACCESS_KEY=your-access-key
   MINIO_SECRET_KEY=your-secret-key
   MINIO_SECURE=false

   # Redis
   REDIS_URL=redis://127.0.0.1:6379/0

   # Authentication — use the same key on all workers
   AUTH_KEY=your-strong-secret-key

   # Limit to a subset of composites
   AVAILABLE_COMPOSITES=ir_clouds,true_color,ash

   # Enable automatic task creation on completed syncs
   AUTO_CREATE_TASKS_ON_SYNC=true

.. tip::

   In Docker Compose, service hostnames (such as ``minio`` and ``redis``) resolve automatically within the same Compose network. Use ``127.0.0.1`` only when running the server outside of Docker.