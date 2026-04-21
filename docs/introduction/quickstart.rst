Quickstart
==========

Install and run Twilight on one machine.

This guide walks you through starting every component of Twilight on a single machine using the default local configuration. By the end you will have Redis and MinIO running in Docker, the Flask tile server accepting requests, workers downloading and processing satellite data, and the React client open in your browser.

Step 1: Clone the repository
----------------------------

.. code-block:: bash

   git clone https://github.com/up1and/twilight.git
   cd twilight

Step 2: Start infrastructure services
-------------------------------------

Use the main ``docker-compose.yml`` to start Redis and MinIO. Redis drives the task queue; MinIO stores both raw HSD files and processed tiles.

.. code-block:: bash

   docker compose up -d redis minio

MinIO starts on port ``9000`` (API) and ``9001`` (web console). Redis starts on port ``6379``. Both use the default credentials ``minioadmin`` / ``minioadmin`` unless you override them with environment variables.

You can verify MinIO is running by opening ``http://localhost:9001`` in your browser and logging in with ``minioadmin`` / ``minioadmin``.

Step 3: Start the Flask server
------------------------------

Install the server dependencies using ``uv`` and start the Flask tile server.

.. code-block:: bash

   uv sync
   cd server
   python app.py

Or pass environment variables explicitly to override the defaults:

.. code-block:: bash

   MINIO_ENDPOINT=127.0.0.1:9000 \
   MINIO_ACCESS_KEY=minioadmin \
   MINIO_SECRET_KEY=minioadmin \
   REDIS_URL=redis://127.0.0.1:6379/0 \
   AUTH_KEY=twilight-secret \
   python app.py

The server listens on ``http://0.0.0.0:5000``. The ``AUTH_KEY`` value is the bearer token workers and the client use to authenticate against the API.

All environment variables have defaults. If you are running Redis and MinIO with the Docker Compose defaults, you can start the server with just ``python app.py`` and it will connect automatically.

Step 4: Start the worker modes
------------------------------

Install the worker dependencies using ``uv``, then start all three modes together with a single command.

.. code-block:: bash

   uv sync
   cd worker
   python main.py --task --sync --worker

The three flags activate the three worker modes:

=============  ==========================================================================
Flag           Role
=============  ==========================================================================
``--task``     Monitors NOAA S3 for new data and creates processing tasks in the queue
``--sync``     Downloads raw HSD files from NOAA S3 to local MinIO
``--worker``   Picks tasks from the queue, generates composites, and uploads tiles to MinIO
=============  ==========================================================================

Each mode runs as a separate thread inside the same process. You can also run them as separate processes on different machines.

Step 5: Start the client
------------------------

In a new terminal, install Node dependencies and start the Vite development server.

.. code-block:: bash

   cd client
   npm install
   npm run dev

The client starts at ``http://localhost:5173``.

Step 6: Open the browser and configure the API endpoint
-------------------------------------------------------

Open ``http://localhost:5173`` in your browser. Before satellite tiles appear you need to tell the client where the server is and provide the authentication token.

1. Click the **Settings** button in the interface.
2. Set the **API endpoint** to ``http://localhost:5000``.
3. Set the **token** to the value you used for ``AUTH_KEY`` (default: ``twilight-secret``).
4. Save the settings.

Select a composite from the dropdown and use the time selector to navigate through available imagery.

.. note::

   The first time you start the workers, no tiles are immediately available. The sync worker needs to download 160 HSD files for each ten-minute observation interval before the composite worker can generate tiles. This typically takes several minutes per interval. The client will show tiles as soon as the first composite finishes processing.
