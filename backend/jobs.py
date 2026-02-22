"""
Jobs module for DMless recruitment platform.
Handles job creation and management.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

# Import database functions
from database import (
    get_user_by_id,
    db
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/jobs", tags=["jobs"])

# ============================
# Pydantic Models
# ============================

class Option(BaseModel):
    option: str
    text: str

class MCQ(BaseModel):
    question: str
    options: List[Option]
    correct_answer: str

class JobCreate(BaseModel):
    recruiter_id: str
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    job_type: str = "full-time"
    location: str = "Remote"
    mcqs: List[MCQ] = Field(..., min_items=5, max_items=5)

class JobResponse(BaseModel):
    success: bool
    message: str
    job_id: Optional[str] = None

# ============================
# Helper Functions
# ============================

def generate_job_id() -> str:
    """Generate a unique job ID"""
    from database import generate_id
    return generate_id("job_")

# ============================
# Test endpoint
# ============================
@router.get("/test")
async def test_jobs():
    """Test endpoint for jobs router"""
    logger.info("Jobs test endpoint called")
    return {
        "success": True,
        "message": "Jobs API is running",
        "database": "connected" if db.is_connected else "disconnected",
        "endpoints": [
            "/jobs/create", 
            "/jobs/{job_id}", 
            "/jobs/recruiter/{recruiter_id}",
            "/jobs/recruiter/all",
            "/jobs/debug/all",
            "/jobs/activate-all",
            "/jobs"  # NEW PUBLIC ENDPOINT
        ]
    }

# ============================
# PUBLIC API: Get all active jobs for candidates
# ============================
@router.get("")
async def get_active_jobs():
    """Get all active jobs for candidates to browse (PUBLIC API)"""
    try:
        logger.info("🔍 Fetching active jobs for candidates")
        jobs_collection = db.get_collection("jobs")
        
        # Get ONLY jobs with status = "active"
        jobs = list(jobs_collection.find({"status": "active"}).sort("created_at", -1))
        
        logger.info(f"📊 Found {len(jobs)} active jobs")
        
        # Convert ObjectId to string and remove correct answers
        result_jobs = []
        for job in jobs:
            job["_id"] = str(job["_id"])
            # Remove correct answers from MCQs so candidates can't see them
            if "mcqs" in job:
                for mcq in job["mcqs"]:
                    if "correct_answer" in mcq:
                        del mcq["correct_answer"]
            result_jobs.append(job)
        
        return {
            "success": True,
            "count": len(result_jobs),
            "jobs": result_jobs
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching active jobs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }
        )

# ============================
# Create Job endpoint
# ============================
@router.post("/create", response_model=JobResponse)
async def create_job(job_data: JobCreate):
    """
    Create a new job posting with MCQs.
    """
    logger.info(f"📝 Job creation attempt for recruiter: {job_data.recruiter_id}")
    logger.info(f"Job title: {job_data.title}")
    
    try:
        # Check database connection
        if not db.is_connected:
            logger.error("Database is not connected")
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "Database connection error"
                }
            )
        
        # Verify recruiter exists
        logger.info(f"Checking recruiter: {job_data.recruiter_id}")
        recruiter = get_user_by_id(job_data.recruiter_id)
        
        if not recruiter:
            logger.warning(f"Recruiter not found: {job_data.recruiter_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Recruiter not found"
                }
            )
        
        if recruiter.get("role") != "recruiter":
            logger.warning(f"User {job_data.recruiter_id} is not a recruiter")
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": "Only recruiters can create jobs"
                }
            )
        
        # Get jobs collection
        jobs_collection = db.get_collection("jobs")
        
        # Generate job ID
        job_id = generate_job_id()
        logger.info(f"Generated job ID: {job_id}")
        
        # Prepare job document with status = "active"
        job_doc = {
            "job_id": job_id,
            "recruiter_id": job_data.recruiter_id,
            "title": job_data.title,
            "description": job_data.description,
            "job_type": job_data.job_type,
            "location": job_data.location,
            "mcqs": [mcq.dict() for mcq in job_data.mcqs],
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "applications_count": 0,
            "shortlisted_count": 0,
            "knocked_out_count": 0,
            "hired_count": 0
        }
        
        # Insert into database
        logger.info("Inserting job into database...")
        result = jobs_collection.insert_one(job_doc)
        
        if result.inserted_id:
            logger.info(f"✅ Job created successfully: {job_id} - {job_data.title}")
            
            return {
                "success": True,
                "message": "Job created successfully",
                "job_id": job_id
            }
        else:
            logger.error("Failed to insert job into database - no inserted_id returned")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Failed to create job in database"
                }
            )
            
    except Exception as e:
        logger.error(f"❌ Job creation error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"An error occurred: {str(e)}"
            }
        )


# ============================
# Get job by ID
# ============================
@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get job details by ID"""
    try:
        logger.info(f"Fetching job: {job_id}")
        jobs_collection = db.get_collection("jobs")
        job = jobs_collection.find_one({"job_id": job_id})
        
        if not job:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Job not found"
                }
            )
        
        # Convert ObjectId to string
        job["_id"] = str(job["_id"])
        
        return {
            "success": True,
            "job": job
        }
        
    except Exception as e:
        logger.error(f"Error fetching job: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }
        )


# ============================
# Get all jobs for a recruiter
# ============================
@router.get("/recruiter/{recruiter_id}")
async def get_recruiter_jobs(recruiter_id: str):
    """Get all jobs for a recruiter"""
    try:
        logger.info(f"Fetching jobs for recruiter: {recruiter_id}")
        jobs_collection = db.get_collection("jobs")
        jobs = list(jobs_collection.find({"recruiter_id": recruiter_id}))
        
        # Convert ObjectId to string for each job
        for job in jobs:
            job["_id"] = str(job["_id"])
        
        return {
            "success": True,
            "count": len(jobs),
            "jobs": jobs
        }
        
    except Exception as e:
        logger.error(f"Error fetching recruiter jobs: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }
        )


# ============================
# Get ALL active jobs for candidates (OLD ENDPOINT)
# ============================
@router.get("/recruiter/all")
async def get_all_jobs():
    """Get all active jobs for candidates to browse"""
    try:
        logger.info("🔍 Fetching all active jobs for candidates")
        jobs_collection = db.get_collection("jobs")
        
        # Get ONLY jobs with status = "active"
        jobs = list(jobs_collection.find({"status": "active"}).sort("created_at", -1))
        
        logger.info(f"📊 Found {len(jobs)} active jobs")
        
        # If no active jobs, log it
        if len(jobs) == 0:
            logger.warning("⚠️ No active jobs found in database")
            total_jobs = jobs_collection.count_documents({})
            logger.info(f"📊 Total jobs in database (any status): {total_jobs}")
        
        # Convert ObjectId to string and remove sensitive data
        result_jobs = []
        for job in jobs:
            job["_id"] = str(job["_id"])
            if "mcqs" in job:
                for mcq in job["mcqs"]:
                    if "correct_answer" in mcq:
                        pass
            result_jobs.append(job)
        
        return {
            "success": True,
            "count": len(result_jobs),
            "jobs": result_jobs
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching all jobs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }
        )


# ============================
# DEBUG: See ALL jobs in database (including inactive)
# ============================
@router.get("/debug/all")
async def debug_all_jobs():
    """See ALL jobs in database regardless of status"""
    try:
        jobs_collection = db.get_collection("jobs")
        jobs = list(jobs_collection.find({}))
        
        for job in jobs:
            job["_id"] = str(job["_id"])
        
        logger.info(f"🔍 Debug: Found {len(jobs)} total jobs in database")
        
        return {
            "success": True,
            "count": len(jobs),
            "jobs": jobs
        }
    except Exception as e:
        return {"error": str(e)}


# ============================
# Force activate all jobs
# ============================
@router.get("/activate-all")
async def activate_all_jobs():
    """Force all jobs to become active"""
    try:
        jobs_collection = db.get_collection("jobs")
        
        # Update all jobs to active
        result = jobs_collection.update_many(
            {},  # Match all jobs
            {"$set": {"status": "active"}}
        )
        
        logger.info(f"✅ Activated {result.modified_count} jobs")
        
        return {
            "success": True,
            "message": f"Updated {result.modified_count} jobs to active",
            "modified_count": result.modified_count
        }
    except Exception as e:
        return {"success": False, "error": str(e)}