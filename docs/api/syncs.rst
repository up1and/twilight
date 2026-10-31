Syncs
=====

Create and update sync records for raw Himawari HSD file ingestion from NOAA S3, and query download progress by timestamp and source.

The sync API tracks raw satellite data download operations. Each sync record represents one 10-minute observation slot being ingested from a source (by default ``himawari``). Sync records expire 30 days after their observation timestamp by default (configurable via ``SYNC_EXPIRE_DAYS``); the scheduled prune job removes the record and deletes the corresponding raw files from the MinIO ``raw`` bucket. All endpoints require authentication.

.. note::

   Authenticate every request by setting ``Authorization: Bearer <token>``, where ``<token>`` is the value of the ``AUTH_KEY`` environment variable on the server (default: ``twilight-secret``).

Sync Lifecycle
--------------

A sync record transitions through the following states::

   pending → running → completed
                 ↘ failed

=============  ========================================
State          Meaning
=============  ========================================
pending        Download is queued but not yet started
running        Download is in progress
completed      All files were downloaded successfully
failed         Download encountered an error
=============  ========================================

The server does not decide when a download is complete; the sync worker reports ``completed`` once at least 160 files are present and no file failed. When a sync transitions to ``completed`` through an update marked ``initiator: "sync"``, the server promotes matching pending ``normal`` tasks to ``high``. If ``AUTO_CREATE_TASKS_ON_SYNC`` is enabled, it also creates a task for every composite in ``AVAILABLE_COMPOSITES``. Promotions and creations are skipped when the status was already ``completed`` or when the update does not claim ``initiator: "sync"``.

Create Sync
-----------

``POST /api/syncs``

Creates a new sync record in ``pending`` state. If a record for the same source and timestamp already exists, this call is a no-op.

**Request Body:**

- ``timestamp`` (required) - Observation time in ISO 8601 format, e.g., ``2025-04-20T04:00:00Z``.
- ``source`` (optional) - Data source identifier. Default: ``himawari``.

**Response (201):**

.. code-block:: json

   {
     "message": "Himawari sync created successfully",
     "timestamp": "2025-04-20T04:00:00+00:00",
     "source": "himawari",
     "status": "pending"
   }

Update Sync
-----------

``PUT /api/syncs``

Updates an existing sync record with progress information. You can update any combination of ``status``, ``files``, and ``size`` in a single call; at least one field must be present.

.. note::

   If the record does not exist, a new one is created before applying the update.

**Request Body:**

- ``timestamp`` (required) - Observation time in ISO 8601 format identifying the sync record to update.
- ``source`` (optional) - Data source identifier. Default: ``himawari``.
- ``status`` (optional) - New status. One of ``pending``, ``running``, ``completed``, ``failed``. Setting ``running`` records the start time if not already set.
- ``files`` (optional) - Total number of files downloaded so far.
- ``size`` (optional) - Total bytes downloaded so far.
- ``initiator`` (optional) - Who is reporting the update. Set to ``sync`` (as the bundled worker does) so that a transition to ``completed`` can promote tasks and, when enabled, create new ones.

**Response (200):**

.. code-block:: json

   {
     "message": "Himawari sync updated successfully (status=completed, files=160, size=524288000)",
     "timestamp": "2025-04-20T04:00:00+00:00",
     "source": "himawari"
   }

Get Sync
--------

``GET /api/syncs/{timestamp}``

Returns the sync record for a specific observation time and source.

**Path Parameters:**

- ``timestamp`` - Observation time in ISO 8601 format, e.g., ``2025-04-20T04:00:00Z``.

**Query Parameters:**

- ``source`` - Data source to query. Default: ``himawari``.

**Response (200):**

.. code-block:: json

   {
     "timestamp": "2025-04-20T04:00:00+00:00",
     "source": "himawari",
     "initiator": null,
     "status": "completed",
     "files": 160,
     "size": 524288000,
     "started": "2025-04-20T04:00:10+00:00",
     "ended": "2025-04-20T04:02:30+00:00",
     "duration": 140,
     "speed": 3744,
     "created": "2025-04-20T04:00:00+00:00"
   }

``initiator`` records who created the sync record. The bundled worker currently leaves it ``null``: it creates the record with a plain ``POST`` and then sends ``initiator: "sync"`` on progress updates, which is what triggers promotion and task creation.

**Status codes:**

======  ==========================================
Status  Description
======  ==========================================
200     Sync record returned
400     Invalid timestamp format
404     No sync found for the given timestamp and source
======  ==========================================

Delete Sync
-----------

``DELETE /api/syncs/{timestamp}``

Deletes a sync record and the raw HSD files for that observation slot from the MinIO ``raw`` bucket.

**Query Parameters:**

- ``source`` - Data source of the record to delete. Default: ``himawari``.

**Response (200):**

.. code-block:: json

   {"message": "Himawari sync for 2025-04-20T04:00:00Z deleted successfully"}

If some raw objects could not be removed, the response also contains a ``warnings`` array describing the failures. Returns ``404`` when no matching record exists and ``400`` for an invalid timestamp.

List Syncs
----------

``GET /api/syncs``

Returns a paginated list of sync records ordered by observation time descending.

**Query Parameters:**

- ``page`` - Page number (1-indexed). Default: 1.
- ``per_page`` - Results per page. Maximum 100. Default: 20.
- ``source`` - Filter by source identifier. Omit to return records from all sources.

**Response (200):**

.. code-block:: none

   {
     "syncs": [...],
     "total": 100,
     "page": 1,
     "per_page": 20,
     "pages": 5
   }
