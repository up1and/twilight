Server
======

Configure the Twilight Flask server: MinIO object storage, Redis, API authentication, composite types, and data retention settings.

The server reads all configuration from environment variables at startup. You can set these in a ``.env`` file at the project root or pass them directly to your container environment. The defaults are suitable for a local Docker Compose setup — change them for any production or multi-node deployment.

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

``REDIS_URL``
~~~~~~~~~~~~~

- **Type:** string
- **Default:** ``redis://127.0.0.1:6379/0``

Full connection URL for Redis. Redis is used as the message queue for task coordination. In Docker Compose, use ``redis://redis:6379/0``.

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

Comma-separated list of composite types the server accepts and advertises. Workers will only enqueue tasks for composites that appear in this list. Remove entries here to disable specific products system-wide.

``TASK_EXPIRE_DAYS``
~~~~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``7``

Number of days before completed or failed task records are removed from the database. Set to ``0`` to disable expiration and retain all task history indefinitely.

``SYNC_EXPIRE_DAYS``
~~~~~~~~~~~~~~~~~~~~

- **Type:** number
- **Default:** ``30``

Number of days before sync records are removed from the database. Set to ``0`` to disable expiration and retain all sync history indefinitely.

Sample Configuration
--------------------

**Local development (.env):**

.. code-block:: bash

   # MinIO — internal Docker Compose service names
   MINIO_ENDPOINT=minio:9000
   MINIO_ACCESS_KEY=minioadmin
   MINIO_SECRET_KEY=minioadmin

   # Redis — internal Docker Compose service name
   REDIS_URL=redis://redis:6379/0

   # Authentication
   AUTH_KEY=change-me-before-deploying

   # Composites (default: all ten types)
   # AVAILABLE_COMPOSITES=ir_clouds,true_color,ash,airmass,day_microphysics,night_microphysics,fog,convection,water_vapor

   # Data retention
   # TASK_EXPIRE_DAYS=7
   # SYNC_EXPIRE_DAYS=30

**Remote server (.env):**

.. code-block:: bash

   # MinIO — accessible from worker nodes on the network
   MINIO_ENDPOINT=0.0.0.0:9000
   MINIO_ACCESS_KEY=your-access-key
   MINIO_SECRET_KEY=your-secret-key

   # Redis
   REDIS_URL=redis://127.0.0.1:6379/0

   # Authentication — use the same key on all workers
   AUTH_KEY=your-strong-secret-key

   # Limit to a subset of composites
   AVAILABLE_COMPOSITES=ir_clouds,true_color,ash

.. tip::

   In Docker Compose, service hostnames (such as ``minio`` and ``redis``) resolve automatically within the same Compose network. Use ``127.0.0.1`` only when running the server outside of Docker.