# Plex Debrid Web Interface

A web-based dashboard for monitoring pending media items in Plex Debrid.

## Features

- **Real-time Dashboard**: Monitor pending, downloading, and ignored media items
- **Statistics Overview**: View counts of items by status and media type
- **Filtering**: Filter items by media type (movies, shows, episodes) and source
- **RESTful API**: Full API for programmatic access to media status
- **Responsive Design**: Works on desktop and mobile devices

## Quick Start

### Option 1: Standalone Web Server

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the web server:
   ```bash
   python web_server.py
   ```

3. Open your browser to: http://127.0.0.1:8008/dashboard

### Option 2: From Main Application

1. Run the main Plex Debrid application:
   ```bash
   python main.py
   ```

2. Select "Web Interface" from the main menu

3. Follow the instructions to start the web server

## API Endpoints

### Core Endpoints

- `GET /api/pending` - Get all pending media items
- `GET /api/pending/movies` - Get pending movies only
- `GET /api/pending/shows` - Get pending TV shows only
- `GET /api/pending/episodes` - Get pending episodes only
- `GET /api/downloading` - Get currently downloading items
- `GET /api/ignored` - Get ignored items
- `GET /api/stats` - Get summary statistics

### Query Parameters

- `media_type`: Filter by type (movie, show, episode)
- `source`: Filter by watchlist source (plex, trakt, overseerr)
- `limit`: Maximum number of items to return (default: 100)

### Examples

```bash
# Get all pending movies from Plex
curl "http://127.0.0.1:8008/api/pending/movies?source=plex"

# Get statistics
curl "http://127.0.0.1:8008/api/stats"

# Get first 10 pending items
curl "http://127.0.0.1:8008/api/pending?limit=10"
```

## Configuration

The web server uses the same configuration as the main Plex Debrid application. The database connection is automatically configured based on your existing settings.

### Server Options

- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 8008)
- `--reload`: Enable auto-reload for development
- `--debug`: Enable debug mode

### Example

```bash
python web_server.py --host 0.0.0.0 --port 9000 --debug
```

## Development

### Project Structure

```
web/
├── __init__.py          # Package initialization
├── app.py              # FastAPI application
├── routes/
│   ├── __init__.py     # Routes package
│   ├── api.py          # API endpoints
│   └── static.py       # Static file serving
└── static/             # Static files (CSS, JS, etc.)
```

### Adding New Endpoints

1. Add new routes to `web/routes/api.py`
2. Update the dashboard in `web/routes/static.py` if needed
3. Test the API using the interactive docs at `/docs`

### Database Integration

The web interface uses the existing SQLite database and media tracking system. All data is read-only to ensure system stability.

## Troubleshooting

### Common Issues

1. **Database Connection Error**: Ensure the main application has been run at least once to initialize the database
2. **Port Already in Use**: Change the port using `--port` parameter
3. **Import Errors**: Make sure all dependencies are installed with `pip install -r requirements.txt`

### Logs

The web server logs are displayed in the console. For debugging, use the `--debug` flag for more verbose output.

## Security Notes

- The web interface is designed for local network use
- No authentication is implemented in this basic version
- Consider using a reverse proxy (nginx) for production deployments
- The API provides read-only access to media status data
