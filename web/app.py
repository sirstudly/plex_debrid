from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sys

# Add the parent directory to the path so we can import from the main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.routes import api
from web.routes import static

app = FastAPI(
    title="Plex Debrid Web Interface",
    description="Web interface for monitoring pending media items in Plex Debrid",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api.router, prefix="/api", tags=["api"])

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Include static routes (for serving the main page)
app.include_router(static.router, tags=["static"])

@app.get("/")
async def root():
    """Root endpoint that redirects to the web interface"""
    return {"message": "Plex Debrid Web Interface", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
