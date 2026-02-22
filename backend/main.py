"""
DMless Recruitment Platform - Main Entry Point
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import os
import logging
from pathlib import Path
from datetime import datetime

# Import routers
from backend.auth import router as auth_router
from backend.dashboard import router as dashboard_router
from backend.jobs import router as jobs_router
from backend.applications import router as applications_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DMless Recruitment Platform",
    description="AI-Powered Recruitment with Knockout Screening",
    version="1.0.0"
)

# ============================
# CORS Middleware
# ============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# Static Files Configuration
# ============================
current_dir = Path(__file__).parent.absolute()
frontend_path = current_dir.parent / "frontend"

logger.info(f"📁 Frontend directory: {frontend_path}")

if not frontend_path.exists():
    logger.error(f"❌ Frontend directory not found at: {frontend_path}")
    frontend_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"✅ Created frontend directory at: {frontend_path}")

app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
logger.info("✅ Static files mounted at /static")

# ============================
# Include All Routers
# ============================
app.include_router(auth_router)        # /auth/*
app.include_router(dashboard_router)   # /dashboard/*
app.include_router(jobs_router)        # /jobs/*
app.include_router(applications_router)  # /applications/*

logger.info("✅ Auth router mounted at /auth")
logger.info("✅ Dashboard router mounted at /dashboard")
logger.info("✅ Jobs router mounted at /jobs")
logger.info("✅ Applications router mounted at /applications")

# ============================
# Root endpoint - Serve landing page
# ============================
@app.get("/")
async def root():
    """Serve the landing page (index.html)"""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        logger.info("Serving index.html (landing page)")
        return FileResponse(index_path)
    
    # Fallback to login.html if index doesn't exist
    login_path = frontend_path / "login.html"
    if login_path.exists():
        logger.warning("index.html not found, serving login.html as fallback")
        return FileResponse(login_path)
    
    return JSONResponse(
        status_code=404,
        content={"message": "index.html not found"}
    )

# ============================
# Health check
# ============================
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "DMless API is running",
        "timestamp": datetime.now().isoformat()
    }

# ============================
# API test endpoint
# ============================
@app.get("/api/test")
async def api_test():
    return {
        "status": "success",
        "message": "API is working",
        "endpoints": {
            "auth": "/auth/test, /auth/login, /auth/signup",
            "dashboard": "/dashboard/test, /dashboard/{recruiter_id}",
            "jobs": "/jobs/test, /jobs/create, /jobs, /jobs/activate-all",
            "applications": "/applications/test, /applications/submit/{job_id}, /applications/upload-resume/{candidate_id}"
        }
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 DMless Recruitment Platform")
    print("="*60)
    print(f"\n📁 Frontend path: {frontend_path}")
    print(f"\n🌐 URLs:")
    print(f"   • Landing Page: http://localhost:8000")
    print(f"   • Login: http://localhost:8000/static/login.html")
    print(f"   • Signup: http://localhost:8000/static/signup.html")
    print(f"   • Jobs (Candidate): http://localhost:8000/static/jobs.html")
    print(f"   • Dashboard (Recruiter): http://localhost:8000/static/dashboard.html")
    print(f"   • API Test: http://localhost:8000/api/test")
    print(f"   • Auth Test: http://localhost:8000/auth/test")
    print(f"   • Dashboard Test: http://localhost:8000/dashboard/test")
    print(f"   • Jobs Test: http://localhost:8000/jobs/test")
    print(f"   • Jobs API: http://localhost:8000/jobs")
    print("\n" + "="*60)
    print("✨ Server starting... Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"

    )
