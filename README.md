# Twilight - Himawari Satellite Data Visualization System

A real-time satellite data visualization system that processes and displays Himawari-8/9 satellite imagery through an interactive web interface. The system consists of three main components: a React-based frontend application, a Flask backend server, and Python worker processes for satellite data processing.

![twilight](docs/images/twilight.png)

## Project Overview

This system provides real-time visualization of Himawari-8/9 satellite data with the following capabilities:

- **Real-time Data Processing**: Automatically downloads and processes Himawari-8/9 satellite data from NOAA S3 buckets
- **Interactive Web Interface**: React-based frontend with Leaflet maps for satellite imagery visualization
- **Multiple Composite Types**: Support for various satellite composites (True Color, IR Clouds, Ash, Night Microphysics, etc.)
- **Time-based Navigation**: Browse satellite imagery across different time periods
- **Side-by-side Comparison**: Compare two different satellite composites simultaneously
- **Task-based Architecture**: Distributed processing system with priority-based task management
- **Data Synchronization**: Automatic synchronization of raw satellite data to local storage

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   Client        │◄──►│   Server        │◄──►│   Worker        │
│   (React/TS)    │    │   (Flask)       │    │   (Python)      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   MinIO/S3      │    │   NOAA S3       │
│ (User Interface)│    │   (Tile Storage)│    │   (Raw Data)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Project Structure

### `/client` - Frontend Application

React-based web application built with TypeScript and Vite.

**Key Features:**

- Interactive map interface using Leaflet and React-Leaflet
- Real-time satellite imagery display with time-based navigation
- Multi-composite selection and side-by-side comparison
- Responsive design for desktop and mobile devices
- Settings management for API configuration
- Coordinate display and snapshot functionality

**Main Components:**

- `app.tsx` - Main application component with map container
- `components/` - Reusable UI components
  - `time-range-selector.tsx` - Time navigation controls
  - `multi-select-composite.tsx` - Composite type selector
  - `side-by-side.tsx` - Split-screen comparison tool
  - `settings-button.tsx` - Configuration interface
  - `coordinates-display.tsx` - Coordinate display
  - `snapshot-button.tsx` - Snapshot functionality
- `utils/api-client.ts` - API communication layer
- `utils/types.ts` - TypeScript type definitions

**Technologies:**

- React 18 with TypeScript
- Leaflet for interactive maps
- Vite for build tooling
- Day.js for time manipulation
- Ky for HTTP requests

### `/server` - Backend Server

Flask-based REST API server that serves satellite tile data and manages processing tasks.

**Key Features:**

- Time-based tile server (`/{composite}/tiles/{time}/{z}/{x}/{y}.png`)
- TileJSON endpoint for map configuration
- Task management API for distributed processing
- Flask-Caching for performance optimization
- MinIO integration for tile storage
- Raw data synchronization status management

**Main Components:**

- `app.py` - Main Flask application with tile serving and task management
- `config.py` - Configuration settings for MinIO and other services
- `services.py` - Business logic services (TaskManager, HimawariRawManager)
- `models.py` - Data models (TaskModel, HimawariRawModel)
- `extensions.py` - Flask extensions initialization
- `utils.py` - Utility functions
- `views/` - View layer
  - `api.py` - API routes
  - `main.py` - Main routes

**API Endpoints:**

- `GET /{composite}/tiles/{time}/{z}/{x}/{y}.png` - Tile serving with ISO 8601 time format
- `GET /{composite}.tilejson` - TileJSON metadata for map configuration
- `GET /composites/latest` - Latest available timestamps for all composites
- `POST /api/tasks` - Create new processing tasks
- `GET /api/tasks` - List and filter tasks
- `PUT /api/tasks/{task_id}` - Update task status
- `POST /api/raws` - Create raw data sync records
- `GET /api/raws/{timestamp}` - Get raw data sync status
- `PUT /api/raws` - Update raw data sync progress

**Technologies:**

- Flask web framework
- Flask-Caching for memory-based caching
- Rio-Tiler for raster tile generation
- MinIO client for object storage
- Redis for task queue and state management

### `/worker` - Satellite Data Processor

Python worker system for downloading, processing, and uploading Himawari satellite data.

**Key Features:**

- Automatic monitoring of NOAA Himawari S3 buckets
- Multi-composite processing (True Color, IR Clouds, Ash, Night Microphysics, etc.)
- Task-based architecture with priority management
- Distributed processing across multiple machines
- Real-time status reporting to backend server
- Raw data synchronization to local MinIO

**Main Components:**

- `main.py` - Entry point with task generator and worker process management
- `himawari_processor.py` - Core satellite data processing logic
- `task.py` - Task queue management and server communication
- `sync.py` - Raw data synchronization processing
- `utils.py` - Utility functions and logging configuration
- `client.py` - Local file checking utilities

**Processing Pipeline:**

1. **Data Monitoring**: Continuously checks NOAA S3 for new Himawari data (160 files per 10-minute interval)
2. **Data Synchronization**: Syncs raw HSD format files from NOAA S3 to local MinIO
3. **Task Generation**: Creates processing tasks when complete datasets are available
4. **Composite Generation**: Uses SatPy to generate various satellite composites
5. **Tile Generation**: Converts composites to Cloud Optimized GeoTIFF (COG) format
6. **Upload**: Stores processed tiles in MinIO for serving by the backend

**Operation Modes:**

- `--task` - Enable task generator (monitors data availability and creates tasks)
- `--sync` - Enable Himawari data synchronization (from NOAA S3 to local MinIO)
- `--worker` - Enable composite worker (processes tasks from the queue)

**Technologies:**

- SatPy for satellite data processing
- S3FS for AWS S3 access
- Rasterio for raster data manipulation
- MinIO client for tile storage
- Threading for concurrent processing
- Boto3 for S3 operations

## Installation and Setup

### Prerequisites

- Python 3.12
- Node.js 18+
- MinIO server (for tile storage)
- Redis server (for task queue)

### Backend Setup

```bash
# Install Python dependencies using PDM
pdm install

# Copy and configure settings
cp server/config.sample.py server/config.py
# Edit config.py with your MinIO and Redis credentials

# Run the server
cd server && python app.py
```

### Client Setup

```bash
# Install Node.js dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### Worker Setup

```bash
# Install Python dependencies using PDM
pdm install

# Copy and configure settings
cp worker/config.sample.py worker/config.py
# Edit config.py with your MinIO and server settings

# Run task generator + data sync + worker
cd worker && python main.py --task --sync --worker

# Or run different components separately
python main.py --task      # Task generator only
python main.py --sync      # Data sync only
python main.py --worker    # Worker only
```

## Configuration

### MinIO Setup

The system requires MinIO for tile storage. Configure the connection in both `server/config.py` and `worker/config.py`:

```python
endpoint = "your-minio-endpoint:9000"
access_key = "your-access-key"
secret_key = "your-secret-key"
```

### Redis Setup

The system requires Redis for task queue and state management. Configure in `server/config.py`:

```python
redis_host = "localhost"
redis_port = 6379
redis_db = 0
```

### Client Configuration

The client can be configured through the settings interface or by modifying localStorage:

```javascript
localStorage.setItem("endpoint", "http://localhost:5000");
localStorage.setItem("token", "your-api-token");
```

### Worker Configuration

Configure processing profile in `worker/config.py`:

```python
processing_profile = {
    'priorities': ['high', 'normal'],  # Task priorities to process
    'composites': ['true_color', 'ir_clouds']  # Composite types to process
}
```

## Usage

### Starting the System

1. Start MinIO server
2. Start Redis server
3. Start the Flask backend server
4. Start one or more worker processes
5. Start the client development server or serve the built application

### Accessing the Interface

- Open your web browser to `http://localhost:5173` (development) or your deployed URL
- Select satellite composites from the dropdown menu
- Use the time selector to navigate through available imagery
- Enable side-by-side comparison by selecting two composites

### Processing Modes

The worker supports multiple operational modes:

- **Task Generation Mode** (`--task`): Monitors for new data and creates tasks
- **Sync Mode** (`--sync`): Synchronizes raw data from NOAA S3 to local MinIO
- **Worker Mode** (`--worker`): Only processes existing tasks from the queue

## API Reference

### Tile Endpoints

- `GET /{composite}/tiles/{time}/{z}/{x}/{y}.png`
  - Returns PNG tile for specified composite, time, and tile coordinates
  - Time format: ISO 8601 (e.g., `2025-01-20T04:00:00`)

### Data Endpoints

- `GET /composites/latest` - Returns latest timestamps for all composites
- `GET /{composite}.tilejson` - Returns TileJSON metadata

### Task Management

- `POST /api/tasks` - Create new processing task
- `GET /api/tasks` - List tasks with optional filtering
- `PUT /api/tasks/{task_id}` - Update task status

### Raw Data Management

- `POST /api/raws` - Create raw data sync records
- `GET /api/raws/{timestamp}` - Get raw data sync status
- `PUT /api/raws` - Update raw data sync progress

## Development

### Client Development

```bash
npm run dev     # Start development server
npm run build   # Build for production
npm run lint    # Run ESLint
```

### Backend Development

```bash
cd server && python app.py   # Start Flask development server
```

### Worker Development

```bash
cd worker && python main.py --task --sync --worker  # Start in development mode
```

### Testing

```bash
# Run all tests
pdm run test

# Run tests with coverage report
pdm run test-cov

# Run verbose tests
pdm run test-verbose
```

## Available Composite Types

- `true_color` - True Color composite
- `ir_clouds` - Infrared Clouds
- `ash` - Volcanic Ash detection
- `night_microphysics` - Night Microphysics

## Data Flow

1. **Data Monitoring**: Worker processes monitor NOAA S3 for new Himawari data
2. **Data Synchronization**: Raw data is synced from NOAA S3 to local MinIO
3. **Task Creation**: Processing tasks are created when data is complete
4. **Task Processing**: Workers process tasks, generating composite images and tiles
5. **Data Serving**: Backend server serves tile data through HTTP API
6. **User Interface**: Frontend application displays interactive maps and satellite imagery

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
