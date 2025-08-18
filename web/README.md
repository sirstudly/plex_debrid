# Plex Debrid Web Interface

A modern web dashboard for monitoring and managing Plex Debrid media items. This interface provides real-time monitoring of pending, downloading, and ignored media items with advanced filtering and management capabilities.

## Features

### Core Features
- **Real-time Dashboard**: Monitor pending, downloading, and ignored media items
- **Statistics Overview**: Quick view of item counts across all categories
- **Pagination**: Efficient handling of large datasets
- **Responsive Design**: Works on desktop and mobile devices

### Phase 2 Enhancements
- **Auto-refresh**: Automatic data updates every 15s, 30s, 1m, or 5m
- **Advanced Filtering**: Filter by media type, source, year, and search terms
- **Search Functionality**: Real-time search across titles with debounced input
- **Export Capabilities**: Export filtered data to CSV format
- **Dark Mode**: Toggle between light and dark themes with persistent preference
- **Keyboard Shortcuts**: Quick navigation and actions using keyboard
- **Bulk Actions**: Select multiple items for batch operations (coming soon)
- **Notifications**: Toast notifications for user feedback

## Quick Start

### Prerequisites
- Python 3.8+
- Plex Debrid installation with SQLite database
- Required Python packages (see requirements.txt)

### Installation

1. **Install Dependencies**:
   ```bash
   pip install fastapi uvicorn[standard]
   ```

2. **Start the Web Server**:
   ```bash
   python web_server.py --host 0.0.0.0 --port 8008
   ```

3. **Access the Dashboard**:
   Open your browser and navigate to `http://localhost:8008`

### Alternative Startup Methods

**Using the main CLI**:
```bash
python main.py
# Select "Web Interface" option
```

**Using uvicorn directly**:
```bash
uvicorn web.app:app --host 0.0.0.0 --port 8008 --reload
```

## API Endpoints

### Core Endpoints

#### GET `/api/pending`
Get pending media items with filtering and pagination.

**Parameters**:
- `media_type` (optional): Filter by type (`movie`, `show`, `episode`)
- `source` (optional): Filter by watchlist source (`plex`, `trakt`, `overseerr`)
- `year` (optional): Filter by year (e.g., `2024`)
- `search` (optional): Search in titles
- `sort_by` (optional): Sort by field (`watchlisted_at`, `title`, `year`, `updated_at`)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 200)

**Example**:
```bash
curl "http://localhost:8008/api/pending?media_type=movie&year=2024&page=1&page_size=25"
```

#### GET `/api/pending/movies`
Get pending movies only.

#### GET `/api/pending/shows`
Get pending TV shows only.

#### GET `/api/pending/episodes`
Get pending episodes only.

#### GET `/api/downloading`
Get currently downloading items.

**Parameters**:
- `media_type` (optional): Filter by type (`movie`, `episode`)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 200)

#### GET `/api/ignored`
Get ignored items.

**Parameters**:
- `media_type` (optional): Filter by type (`movie`, `show`, `episode`)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 200)

#### GET `/api/stats`
Get summary statistics.

**Response**:
```json
{
  "pending": {
    "movies": 150,
    "shows": 25,
    "episodes": 300,
    "total": 475
  },
  "downloading": {
    "movies": 5,
    "episodes": 12,
    "total": 17
  },
  "ignored": {
    "movies": 10,
    "shows": 2,
    "episodes": 15,
    "total": 27
  },
  "collected": {
    "movies": 1000,
    "shows": 200,
    "episodes": 2500,
    "total": 3700
  }
}
```

### Utility Endpoints

#### GET `/`
Root endpoint with basic status information.

#### GET `/health`
Health check endpoint.

## User Interface Features

### Auto-Refresh
- Toggle automatic data refresh on/off
- Configurable refresh intervals (15s, 30s, 1m, 5m)
- Visual indicator when auto-refresh is active

### Advanced Filtering
- **Media Type**: Filter by movies, shows, or episodes
- **Source**: Filter by watchlist source (Plex, Trakt, Overseerr)
- **Year**: Filter by release year
- **Search**: Real-time search across titles
- **Sorting**: Sort by watchlisted date, title, year, or updated date
- **Page Size**: Choose how many items to display per page

### Export Functionality
- Export current filtered data to CSV
- Includes all visible columns and data
- Automatic filename with date stamp
- Respects current filters and sorting

### Dark Mode
- Toggle between light and dark themes
- Persistent preference stored in browser
- Optimized color scheme for both modes
- Keyboard shortcut: `Ctrl+D`

### Keyboard Shortcuts
- `R`: Refresh data
- `Ctrl+D`: Toggle dark mode
- `?`: Show keyboard shortcuts help
- `1-3`: Switch tabs (1=Pending, 2=Downloading, 3=Ignored)
- `E`: Export current data

### Notifications
- Success, warning, and error notifications
- Auto-dismiss after 5 seconds
- Manual dismiss option
- Positioned in top-right corner

## Configuration

### Environment Variables
- `HOST`: Server host (default: `0.0.0.0`)
- `PORT`: Server port (default: `8008`)
- `DEBUG`: Enable debug mode (default: `False`)

### Database Configuration
The web interface automatically uses the same SQLite database as your Plex Debrid installation. No additional configuration is required.

## Development

### Project Structure
```
web/
├── __init__.py
├── app.py                 # FastAPI application
├── routes/
│   ├── __init__.py
│   ├── api.py            # API endpoints
│   └── static.py         # Static HTML dashboard
├── static/               # Static assets (CSS, JS, images)
└── README.md            # This file
```

### Running in Development Mode
```bash
python web_server.py --host 0.0.0.0 --port 8008 --reload --debug
```

### Testing
```bash
python test_web_interface.py
```

## Troubleshooting

### Common Issues

**Database Connection Error**:
- Ensure Plex Debrid is properly configured
- Check that the SQLite database file exists
- Verify file permissions

**Port Already in Use**:
- Change the port: `python web_server.py --port 8009`
- Kill existing process: `lsof -ti:8008 | xargs kill`

**Import Errors**:
- Activate the correct virtual environment
- Install required dependencies: `pip install -r requirements.txt`

**Auto-refresh Not Working**:
- Check browser console for JavaScript errors
- Ensure no ad blockers are interfering
- Verify network connectivity

### Debug Mode
Enable debug mode for detailed error messages:
```bash
python web_server.py --debug
```

### Logs
Check the terminal output for detailed logs and error messages.

## Browser Compatibility

- **Chrome/Chromium**: 80+
- **Firefox**: 75+
- **Safari**: 13+
- **Edge**: 80+

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is part of Plex Debrid and follows the same license terms.
