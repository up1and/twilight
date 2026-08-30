Scale Worker
============

Scale Twilight's processing pipeline by tuning worker replicas, RAM allocation per worker, composite type filters, and geographic scope.

Twilight's processing pipeline is designed for horizontal scaling. The ``worker-processor`` role is the compute-intensive stage—it pulls tasks from the queue and uses SatPy to render composite tiles from raw Himawari data. You can run as many processor instances as your hardware supports, while ``worker-sync`` is typically kept as a single instance because it performs a coordination role.

How Worker Count is Determined Automatically
--------------------------------------------

Each ``worker-processor`` instance internally calculates how many parallel processing threads to spawn based on available system memory:

.. code-block:: python

   mem_per_worker = float(os.getenv("MEM_PER_WORKER", 7.0))  # GB per thread
   system_margin  = float(os.getenv("SYSTEM_MARGIN", 4.0))   # GB reserved for OS

The number of threads is derived from::

   threads = floor((total_RAM - SYSTEM_MARGIN) / MEM_PER_WORKER)

For example, on a host with 32 GB of RAM, the defaults yield ``floor((32 - 4) / 7) = 4`` parallel threads per container instance.

On memory-constrained hosts, reduce ``MEM_PER_WORKER`` only if you are confident each composite stays within that budget. Underestimating causes OOM kills during peak processing.

Scaling worker-processor with Docker Compose
--------------------------------------------

Use the ``--scale`` flag to run multiple ``worker-processor`` containers from a single Compose command:

.. code-block:: bash

   docker compose -f docker-compose.workers.yml up -d --scale worker-processor=4

Each container independently polls the Redis task queue, so adding containers increases throughput without any configuration changes to the server or other workers.

``worker-sync`` does not benefit from scaling. Run it as a single instance. Only ``worker-processor`` should be scaled.

To adjust the replica count on a running stack without restarting other services:

.. code-block:: bash

   docker compose -f docker-compose.workers.yml up -d --scale worker-processor=8 --no-recreate worker-sync

Filtering by Composite Type
---------------------------

By default a ``worker-processor`` handles all composite types. Set the ``COMPOSITES`` environment variable to restrict a container to a specific subset:

.. code-block:: bash

   COMPOSITES=true_color,ir_clouds docker compose -f docker-compose.workers.yml up -d

Valid composite identifiers::

   ir_clouds, true_color, ash, airmass,
   night_microphysics, day_microphysics,
   fog, convection, vapor

This lets you dedicate faster machines to high-demand composites (e.g., ``true_color``) and route less critical composites to smaller instances.

Filtering by Task Priority
--------------------------

Workers can be restricted to specific priority tiers using the ``PRIORITIES`` variable:

.. code-block:: bash

   PRIORITIES=high,normal docker compose -f docker-compose.workers.yml up -d

An empty or unset ``PRIORITIES`` value means the worker accepts tasks at any priority level.

Separating Worker Roles Across Hosts
------------------------------------

For larger deployments, run each worker role on a separate machine. On each remote worker host:

1. Copy ``.env`` from the master node.
2. Set ``SERVER_URL`` to the master node's API address and ``MINIO_ENDPOINT`` to its MinIO address:

.. code-block:: bash

   SERVER_URL=http://<MASTER_IP>:5000
   MINIO_ENDPOINT=<MASTER_IP>:9000

3. Start only the worker-processor role:

.. code-block:: bash

   docker compose -f docker-compose.workers.yml up -d worker-processor

The master node continues to run ``worker-sync`` and the core stack (``docker-compose.yml``).

Tuning Resolution vs. Speed
---------------------------

The ``MAX_RESOLUTION`` variable controls the output resolution in meters. Lower values produce higher-quality tiles at the cost of more processing time and memory:

==============  ===========  ==========  ==========================================
MAX_RESOLUTION  Quality      Speed       Typical use
==============  ===========  ==========  ==========================================
500             Highest      Slowest     Archive or research deployments
1000            Balanced     Moderate    Default; recommended for most setups
2000            Lowest       Fastest     Resource-constrained or preview use
==============  ===========  ==========  ==========================================

.. code-block:: bash

   MAX_RESOLUTION=500 docker compose -f docker-compose.workers.yml up -d worker-processor

Setting ``MAX_RESOLUTION=500`` significantly increases memory usage per task. Increase ``MEM_PER_WORKER`` accordingly to prevent OOM errors.

Limiting Geographic Scope with BBOX
-----------------------------------

Use the ``BBOX`` variable to restrict processing to a specific region, which reduces both CPU and storage load. The value is a bounding box in decimal degrees: ``lon_min,lat_min,lon_max,lat_max``.

.. code-block:: bash

   # East Asia and Australia
   BBOX=75,0,160,55 docker compose -f docker-compose.workers.yml up -d worker-processor

The default bounding box covers the primary Himawari-8/9 full-disk footprint (``75,0,160,55``). Narrow it further if you only need a sub-region.