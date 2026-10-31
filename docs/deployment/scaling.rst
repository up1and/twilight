Scale Worker
============

Scale Twilight's processing pipeline by tuning worker replicas, RAM allocation per worker, composite type filters, and geographic scope.

Twilight's processing pipeline is designed for horizontal scaling. The ``worker-processor`` role is the compute-intensive stage—it pulls tasks from the queue and uses SatPy to render composite tiles from raw Himawari data. You can run as many processor instances as your hardware supports, while ``worker-sync`` is typically kept as a single instance because it performs a coordination role.

How Worker Count is Determined Automatically
--------------------------------------------

Each ``worker-processor`` instance internally calculates how many parallel Dask workers to use based on the memory available at startup:

.. code-block:: python

   mem_per_worker = float(os.getenv("MEM_PER_WORKER", 7.0))  # GB per task
   system_margin  = float(os.getenv("SYSTEM_MARGIN", 4.0))   # GB reserved for OS

The number of workers is derived from::

   available_ram = RAM currently available to the process
   workers = max(1, min(floor((available_RAM - SYSTEM_MARGIN) / MEM_PER_WORKER), logical_cores))

For example, on a 32 GB host with 12 GB already in use, the defaults yield ``floor((20 - 4) / 7) = 2`` parallel workers per container instance. The calculation uses live available memory, so a busy host may allocate fewer workers than a freshly booted one.

On memory-constrained hosts, reduce ``MEM_PER_WORKER`` only if you are confident each composite stays within that budget. Underestimating causes OOM kills during peak processing.

Scaling worker-processor with Docker Compose
--------------------------------------------

Use the ``--scale`` flag to run multiple ``worker-processor`` containers from a single Compose command:

.. code-block:: bash

   docker compose -f docker-compose.workers.yml up -d --scale worker-processor=4

Each container independently requests the next task from the server API, and the server hands out work atomically, so adding containers increases throughput without any configuration changes to the server or other workers.

``worker-sync`` does not benefit from scaling. Run it as a single instance. Only ``worker-processor`` should be scaled.

To adjust the replica count on a running stack without recreating existing containers:

.. code-block:: bash

   docker compose -f docker-compose.workers.yml up -d --scale worker-processor=8 --no-recreate

Passing Variables Through Compose
---------------------------------

The worker services list their environment explicitly in ``docker-compose.workers.yml``, so variables set only in your shell or ``.env`` are not forwarded to the containers. Put worker tuning variables in an override file and load it together with the worker Compose file:

.. code-block:: yaml

   # docker-compose.override.yml
   services:
     worker-processor:
       environment:
         - COMPOSITES=true_color,ir_clouds
         - PRIORITIES=high,normal
         - MAX_RESOLUTION=500
         - BBOX=75,0,160,55

.. code-block:: bash

   docker compose -f docker-compose.workers.yml -f docker-compose.override.yml up -d

The examples below assume this override file, and every variable listed there must be added to the service's ``environment`` list to take effect.

Filtering by Composite Type
---------------------------

By default a ``worker-processor`` handles all composite types. Set ``COMPOSITES`` to restrict a container to a specific subset:

.. code-block:: yaml

   services:
     worker-processor:
       environment:
         - COMPOSITES=true_color,ir_clouds

Valid composite identifiers::

   ir_clouds, true_color, ash, airmass,
   night_microphysics, day_microphysics,
   fog, convection, water_vapor

This lets you dedicate faster machines to high-demand composites (e.g., ``true_color``) and route less critical composites to smaller instances.

Filtering by Task Priority
--------------------------

Workers can be restricted to specific priority tiers using the ``PRIORITIES`` variable:

.. code-block:: yaml

   services:
     worker-processor:
       environment:
         - PRIORITIES=high,normal

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

.. code-block:: yaml

   services:
     worker-processor:
       environment:
         - MAX_RESOLUTION=500

Setting ``MAX_RESOLUTION=500`` significantly increases memory usage per task. Increase ``MEM_PER_WORKER`` accordingly to prevent OOM errors.

Limiting Geographic Scope with BBOX
-----------------------------------

Use the ``BBOX`` variable to restrict processing to a specific region, which reduces both CPU and storage load. The value is a bounding box in decimal degrees: ``lon_min,lat_min,lon_max,lat_max``.

.. code-block:: yaml

   services:
     worker-processor:
       environment:
         - BBOX=75,0,160,55

The default bounding box covers the primary Himawari-8/9 full-disk footprint (``75,0,160,55``). Narrow it further if you only need a sub-region.