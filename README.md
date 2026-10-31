# Twilight - A Himawari Satellite Data Visualization System

A real-time satellite data visualization system that processes and displays Himawari-8/9 satellite imagery through an interactive web interface.

![twilight](docs/images/twilight.png)

## Documentation

For detailed installation guides, configuration, and API reference, please see our [Full Documentation](docs/index.rst).

- [Architecture](docs/introduction/architecture.rst)
- [Deployment](docs/deployment/deployment.rst)
- [Satellite Composites](docs/guide/composites.rst)
- [API Reference](docs/api/overview.rst)

## Available Composite Types

Twilight supports nine satellite composites out of the box:

- `true_color` - Natural-color view using visible red, green, and blue bands.
- `ir_clouds` - Infrared cloud-top temperature.
- `ash` - Volcanic ash detection using thermal infrared differences.
- `airmass` - Upper-tropospheric air mass analysis.
- `day_microphysics` - Daytime cloud microphysics (particle size and phase).
- `night_microphysics` - Nighttime cloud microphysics using infrared bands.
- `fog` - Low-level fog and stratus detection.
- `convection` - Deep convection and overshooting tops.
- `water_vapor` - Differential water vapor analysis distinguishing between upper and mid-level humidity layers.

## Quick Start

1. **Configure environment**:

   ```bash
   cp .env.sample .env
   ```

2. **Start core services** (Infrastructure, API & Frontend):

   ```bash
   docker compose up -d
   ```

3. **Start processing workers**:

   ```bash
   docker compose -f docker-compose.workers.yml up -d
   ```

4. **Access the interface**:
   Open `http://localhost/` for the public map. To use the dashboard and task management, sign in at `http://localhost/login` with the `AUTH_KEY` value from `.env` (default `twilight-secret`).

> **Note:** The server only enqueues composite tasks automatically when `AUTO_CREATE_TASKS_ON_SYNC=true`. The bundled `docker-compose.yml` does not forward this variable, so add it to the `server` service's `environment` list (or create tasks through `POST /api/tasks`).

## Processing Modes

The worker system supports multiple operational modes via command-line flags (configured in the Docker Compose environment):

- **Data Synchronization** (`--sync`): Downloads raw HSD files from NOAA S3 to local MinIO storage.
- **Composite Worker** (`--worker`): Picks tasks from the queue, generates composites, and uploads tiles.

## Project Structure

Twilight is composed of three primary services:

- **[`/client`](client/)**: React-based frontend application built with TypeScript and Vite.
- **[`/server`](server/)**: Flask-based REST API serving satellite tiles, managing tasks, and generating snapshots.
- **[`/worker`](worker/)**: Python processes that sync raw data from S3 and generate composites.
- **[`/docs`](docs/)**: Sphinx-based documentation source files.

## Development

If you wish to run components individually for development:

### Backend & Infrastructure

```bash
# Start Redis and MinIO only
docker compose up -d redis minio

# Run Flask server (from the repository root)
uv run --package server server/app.py
```

### Frontend

```bash
cd client && npm install && npm run dev
```

### Worker

```bash
# From the repository root
uv run --package worker worker/main.py --sync --worker
```

## Testing

```bash
# Run all tests
uv run --with pytest pytest

# Build documentation
just docs
```

## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.
