from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os

from .controllers.story_controller import router as story_router
from .controllers.admin_controller import router as admin_router
from ...database.db_utils import init_db

# Initialize the database
init_db()

# Create FastAPI app
app = FastAPI(
    title="Interactive Fairy Tale API",
    description="API for generating interactive fairy tales with LLMs",
    version="1.0.0"
)

# Configure CORS
origins = [
        "https://edudash.vidsoft.net",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(story_router, prefix="/api", tags=["Stories"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])

@app.get("/api/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

# Run the application with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)