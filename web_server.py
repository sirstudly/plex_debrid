#!/usr/bin/env python3
"""
Plex Debrid Web Server
A standalone web server for the Plex Debrid web interface.
"""

import uvicorn
import argparse
import os
import sys

# Add the current directory to the path so we can import from the main project
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web.app import app

def main():
    parser = argparse.ArgumentParser(description="Plex Debrid Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8008, help="Port to bind to (default: 8008)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    print(f"Starting Plex Debrid Web Server on http://{args.host}:{args.port}")
    print(f"Dashboard available at: http://{args.host}:{args.port}/dashboard")
    print(f"API documentation available at: http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info"
    )

if __name__ == "__main__":
    main()
