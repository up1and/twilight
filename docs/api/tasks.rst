Tasks
===============

Create, query, claim, and track COG tile processing tasks in the Twilight worker queue.

The task API manages the queue of Cloud-Optimized GeoTIFF (COG) generation jobs. Workers poll this API to discover pending work, claim individual tasks, and report back status updates. All endpoints require authentication.

.. note::

   Authenticate every request by setting ``Authorization: Bearer <token>``, where ``<token>`` is the value of the ``AUTH_KEY`` environment variable on the server (default: ``twilight-secret``).

Tasks expire after a configurable number of days (default 7, controlled by ``TASK_EXPIRE_DAYS``). Creating a task for a composite/timestamp pair that already has a pending or running task returns the existing task rather than creating a duplicate.

Create Task
-----------

``POST /api/tasks``

Creates a new COG processing task. If an identical task (same composite and timestamp) is already pending or running, the existing task is returned.

**Request Body:**

- ``composite`` (required) - Composite to process. Must be one of the configured composites on the server (e.g., ``ir_clouds``, ``true_color``, ``ash``). Use underscore format.
- ``timestamp`` (required) - Observation time in ISO 8601 format, e.g., ``2025-04-20T04:00:00Z``.
- ``priority`` (optional) - Task priority. One of ``low``, ``normal``, or ``high``. Invalid values are silently coerced to ``normal``. Default: ``normal``.

**Response (201):**

.. code-block:: json

   {
     "task_id": "ir_clouds_20250420_040000_a1b2c3d4",
     "status": "pending",
     "created": "2025-04-20T04:01:12.345678+00:00"
   }

List Tasks
----------

``GET /api/tasks``

Returns a paginated list of tasks with optional filtering.

**Query Parameters:**

- ``status`` - Filter by status. One of ``pending``, ``processing``, ``completed``, ``failed``.
- ``composite`` - Filter by composite name (underscore format).
- ``priority`` - Filter by priority. One of ``low``, ``normal``, ``high``.
- ``page`` - Page number (1-indexed). Default: 1.
- ``per_page`` - Results per page. Maximum 100. Default: 20.

**Response (200):**

.. code-block:: none

   {
     "tasks": [...],
     "total": 100,
     "page": 1,
     "per_page": 20,
     "pages": 5
   }

Peek Next Task
--------------

``GET /api/tasks/next``

Peeks at the next pending task in the queue without claiming it. Workers use this to decide whether to call ``PUT /api/tasks/{task_id}/claim`` for a specific task.

.. warning::

   This endpoint only peeks — it does not remove or lock the task. Another worker may claim the same task before you do. Always follow up with a claim request.

**Query Parameters:**

- ``priority`` - Comma-separated list of priorities to consider, e.g., ``high,normal``. Omit to match all priorities.
- ``composite`` - Comma-separated list of composite names to consider, e.g., ``ir_clouds,true_color``. Omit to match all composites.

**Response:**

======  ====================================
Status  Description
======  ====================================
200     Next pending task found
204     No pending tasks matching the filters
======  ====================================

Get Task
--------

``GET /api/tasks/{task_id}``

Returns the full task object for a given task ID.

**Task Object Fields:**

.. code-block:: json

   {
     "task_id": "ir_clouds_20250420_040000_a1b2c3d4",
     "composite": "ir_clouds",
     "timestamp": "2025-04-20T04:00:00+00:00",
     "priority": "normal",
     "status": "pending",
     "created": "2025-04-20T04:00:00+00:00",
     "started": null,
     "ended": null,
     "duration": null,
     "worker_id": null,
     "message": null
   }

Claim Task
----------

``PUT /api/tasks/{task_id}/claim``

Atomically claims a pending task for a specific worker, marking its status as ``running``. Once claimed, the task is removed from the priority queue so other workers cannot claim it.

**Request Body:**

- ``worker_id`` (required) - Identifier for the worker claiming the task, e.g., ``worker-1`` or a hostname.

**Response (200):**

.. code-block:: json

   {
     "task_id": "ir_clouds_20250420_040000_a1b2c3d4",
     "composite": "ir_clouds",
     "timestamp": "2025-04-20T04:00:00+00:00",
     "status": "running",
     "worker_id": "worker-1"
   }

Update Task Status
------------------

``PUT /api/tasks/{task_id}/status``

Updates the status of a task. When a task transitions to ``completed``, the server also updates the composite state so that tile requests for that timestamp are immediately served.

**Request Body:**

- ``status`` (required) - New status. One of ``pending``, ``processing``, ``completed``, ``failed``.
- ``message`` (optional) - Optional human-readable message, e.g., an error description when setting ``failed``.

**Response (200):**

.. code-block:: json

   {"message": "Task status updated successfully"}

Task Profiling
--------------

``POST /api/tasks/{task_id}/profile``

Saves profiling data captured during task execution, such as per-subtask timings and resource utilisation metrics.

**Request Body:**

- ``tasks`` - Array of per-subtask timing records captured by the profiler.
- ``resources`` - Array of resource utilisation samples (CPU, memory, etc.) captured during processing.

**Response (201):**

.. code-block:: json

   {"message": "Profile saved"}

``GET /api/tasks/{task_id}/profile``

Retrieves previously saved profiling data for a task.

**Response (200):**

.. code-block:: none

   {
     "task_id": "ir_clouds_20250420_040000_a1b2c3d4",
     "tasks": [...],
     "resources": [...]
   }

**Status codes:**

======  =============================================
Status  Description
======  =============================================
200     Profile data returned
404     No profile data found for the task
======  =============================================