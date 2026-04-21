Authentication
==============

Twilight uses Bearer token authentication. Learn how to set your AUTH_KEY, attach the token to requests, and verify it with the auth endpoint.

Twilight protects its task management and sync management endpoints with Bearer token authentication. You pass your token in an ``Authorization`` header on every request to a protected endpoint. Public endpoints — including tile serving and composite state — do not require a token.

How Authentication Works
------------------------

The server reads a secret key from the ``AUTH_KEY`` environment variable when it starts. Every request to a protected endpoint must include that key as a Bearer token. If the token is missing or incorrect, the server responds with ``401 Unauthorized``.

Setting Your AUTH_KEY
---------------------

Set the ``AUTH_KEY`` environment variable before starting the server:

.. code-block:: bash

   export AUTH_KEY="your-secret-token"
   python app.py

If ``AUTH_KEY`` is not set, the server uses the default value ``twilight-secret``. Change this before deploying to a shared or public environment.

.. warning::

   The default value ``twilight-secret`` is publicly known. Always set a strong, unique ``AUTH_KEY`` in production deployments.

Passing the Token
-----------------

Include your token in the ``Authorization`` header using the ``Bearer`` scheme::

   Authorization: Bearer <your-token>

**Example curl requests:**

.. code-block:: bash

   # List processing tasks
   curl http://your-server:5000/api/tasks \
     -H "Authorization: Bearer your-secret-token"

.. code-block:: bash

   # Create a new processing task
   curl -X POST http://your-server:5000/api/tasks \
     -H "Authorization: Bearer your-secret-token" \
     -H "Content-Type: application/json" \
     -d '{"composite": "true_color", "timestamp": "2025-04-20T04:00:00Z"}'

.. code-block:: bash

   # Create a sync record
   curl -X POST http://your-server:5000/api/syncs \
     -H "Authorization: Bearer your-secret-token" \
     -H "Content-Type: application/json" \
     -d '{"timestamp": "2025-04-20T04:00:00Z", "source": "himawari"}'

Which Endpoints Require Authentication
--------------------------------------

============================================  =============
Endpoint group                                Auth required
============================================  =============
``Task management (/api/tasks/*)``            Yes
``Sync management (/api/syncs/*)``            Yes
``Tile serving (/tiles/*)``                   No
``Composite state (/api/composites/latest)``  No
``Snapshots (/api/snapshots, /snapshots/*)``  No
``Token verification (/api/auth/verify)``     No
``Vector tiles (/tiles/*.pbf)``               No
============================================  =============

Tile serving, composite state, snapshot generation and download, and vector tiles are all public endpoints. No ``Authorization`` header is needed to access them.

Verifying a Token
-----------------

Use ``POST /api/auth/verify`` to check whether a token is valid without making a real API call. This endpoint does not require authentication itself.

.. code-block:: bash

   curl -X POST http://your-server:5000/api/auth/verify \
     -H "Content-Type: application/json" \
     -d '{"token": "your-secret-token"}'

A valid token returns:

.. code-block:: json

   {"valid": true}

An invalid token also returns HTTP 200 with:

.. code-block:: json

   {"valid": false}

If you omit the ``token`` field entirely, the endpoint returns HTTP 400.

Authentication Failure Responses
--------------------------------

When a protected endpoint receives a missing or invalid token, it responds with HTTP ``401`` and a JSON body:

**Missing or malformed Authorization header:**

.. code-block:: json

   {
     "title": "Authentication Required",
     "description": "Please provide a Bearer token in the Authorization header."
   }

**Wrong token value:**

.. code-block:: json

   {
     "title": "Invalid Token",
     "description": "The provided auth token is invalid. Please verify your credentials and try again."
   }

The server also sends a ``WWW-Authenticate: Bearer realm="api"`` response header with every 401.
