"""
Applications module for DMless recruitment platform.
Handles job applications, MCQ submissions, knockout logic, and resume uploads.
"""

from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
import shutil
from pathlib import Path

# Import database functions
from backend.database import (
    get_user_by_id,
    get_job_by_id,
    save_application,
    update_application_status,
    db
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/applications", tags=["applications"])

# ============================
# Pydantic Models
# ============================

class Answer(BaseModel):
    question_id: int
    question: str
    selected_option: str
    is_correct: bool

class ApplicationSubmit(BaseModel):
    candidate_id: str
    answers: List[Answer]
    score: int
    total_questions: int

class ApplicationResponse(BaseModel):
    success: bool
    message: str
    application_id: Optional[str] = None
    status: Optional[str] = None
    knocked_out: Optional[bool] = None

# ============================
# Helper function to update job application count
# ============================
def update_job_application_count(job_id: str):
    """Update the application count for a job"""
    try:
        jobs_collection = db.get_collection("jobs")
        applications_collection = db.get_collection("applications")
        
        # Count applications for this job
        count = applications_collection.count_documents({"job_id": job_id})
        
        # Update job
        jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": {"applications_count": count, "updated_at": datetime.now().isoformat()}}
        )
        
        logger.info(f"📊 Updated application count for job {job_id}: {count}")
        
    except Exception as e:
        logger.error(f"Error updating job application count: {e}")

# ============================
# Test endpoint
# ============================
@router.get("/test")
async def test_applications():
    """Test endpoint for applications router"""
    return {
        "success": True,
        "message": "Applications API is running",
        "endpoints": [
            "/applications/submit/{job_id}",
            "/applications/{application_id}",
            "/applications/candidate/{candidate_id}",
            "/applications/job/{job_id}",
            "/applications/{application_id}/status",
            "/applications/upload-resume/{candidate_id}"
        ]
    }

# ============================
# Submit application (MCQ answers) - UPDATED WITH AUTO-SHORTLIST
# ============================
@router.post("/submit/{job_id}", response_model=ApplicationResponse)
async def submit_application(job_id: str, application: ApplicationSubmit):
    """
    Submit MCQ answers for a job application.
    Implements knockout logic - wrong answer = knocked out.
    AUTO-SHORTLIST if all answers are correct!
    """
    logger.info(f"📝 Application submitted for job: {job_id} by candidate: {application.candidate_id}")
    logger.info(f"Score: {application.score}/{application.total_questions}")
    
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
        
        # Verify job exists
        job = get_job_by_id(job_id)
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Job not found"
                }
            )
        
        # Verify candidate exists
        candidate = get_user_by_id(application.candidate_id)
        if not candidate:
            logger.warning(f"Candidate not found: {application.candidate_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Candidate not found"
                }
            )
        
        # Check if any answer was wrong (knockout logic)
        knocked_out = False
        all_correct = True
        for answer in application.answers:
            if not answer.is_correct:
                knocked_out = True
                all_correct = False
                break
        
        # AUTO-SHORTLIST if all answers are correct!
        if all_correct and application.score == application.total_questions:
            status = "shortlisted"
            logger.info(f"✨ Candidate {application.candidate_id} PASSED all questions! Auto-shortlisting...")
        elif knocked_out:
            status = "knocked_out"
            logger.info(f"❌ Candidate {application.candidate_id} FAILED - Knocked out")
        else:
            status = "applied"
            logger.info(f"📝 Candidate {application.candidate_id} applied")
        
        # Save application to database
        result = save_application(
            job_id=job_id,
            candidate_id=application.candidate_id,
            answers=[a.dict() for a in application.answers],
            status=status  # This will be "shortlisted" for candidates who pass!
        )
        
        if result:
            logger.info(f"✅ Application saved with status: {status}")
            
            return {
                "success": True,
                "message": "Application submitted successfully",
                "application_id": result.get("application_id"),
                "status": status,
                "knocked_out": knocked_out
            }
        else:
            logger.error("Failed to save application")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Failed to save application"
                }
            )
            
    except Exception as e:
        logger.error(f"❌ Application submission error: {str(e)}")
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
# Upload Resume endpoint
# ============================
@router.post("/upload-resume/{candidate_id}")
async def upload_resume(
    candidate_id: str,
    job_id: str = Form(...),
    resume: UploadFile = File(...)
):
    """
    Upload resume for a job application
    """
    logger.info(f"📄 Resume upload for candidate: {candidate_id}, job: {job_id}")
    
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
        
        # Verify candidate exists
        candidate = get_user_by_id(candidate_id)
        if not candidate:
            logger.warning(f"Candidate not found: {candidate_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Candidate not found"
                }
            )
        
        # Verify job exists
        job = get_job_by_id(job_id)
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Job not found"
                }
            )
        
        # Validate file type
        valid_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if resume.content_type not in valid_types:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Invalid file type. Please upload PDF or Word documents only."
                }
            )
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Create candidate directory
        candidate_dir = upload_dir / candidate_id
        candidate_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = resume.filename.split('.')[-1]
        safe_filename = f"resume_{job_id}_{timestamp}.{file_extension}"
        file_path = candidate_dir / safe_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
        
        logger.info(f"✅ File saved: {file_path}")
        
        # Update application status in database
        applications_collection = db.get_collection("applications")
        
        # Find the application for this candidate and job
        application = applications_collection.find_one({
            "candidate_id": candidate_id,
            "job_id": job_id
        })
        
        if application:
            # Update existing application with resume path
            applications_collection.update_one(
                {"_id": application["_id"]},
                {"$set": {
                    "resume_path": str(file_path),
                    "updated_at": datetime.now().isoformat()
                }}
            )
            
            logger.info(f"✅ Updated application {application.get('application_id')} with resume")
            
        else:
            # Create new application if doesn't exist
            from database import generate_id
            application_id = generate_id("app_")
            
            application_doc = {
                "application_id": application_id,
                "job_id": job_id,
                "candidate_id": candidate_id,
                "resume_path": str(file_path),
                "status": "applied",
                "applied_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "score": application.score if hasattr(application, 'score') else 5,
                "total_questions": application.total_questions if hasattr(application, 'total_questions') else 5,
                "answers": []
            }
            
            applications_collection.insert_one(application_doc)
            logger.info(f"✅ Created new application {application_id} with resume")
        
        # Update job application count
        update_job_application_count(job_id)
        
        return {
            "success": True,
            "message": "Resume uploaded successfully! Your application has been submitted.",
            "filename": safe_filename
        }
            
    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Upload failed: {str(e)}"
            }
        )


# ============================
# Get application by ID
# ============================
@router.get("/{application_id}")
async def get_application(application_id: str):
    """Get application details by ID"""
    try:
        applications_collection = db.get_collection("applications")
        application = applications_collection.find_one({"application_id": application_id})
        
        if not application:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Application not found"
                }
            )
        
        # Convert ObjectId to string
        application["_id"] = str(application["_id"])
        
        return {
            "success": True,
            "application": application
        }
        
    except Exception as e:
        logger.error(f"Error fetching application: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }
        )


# ============================
# Get all applications for a candidate
# ============================
@router.get("/candidate/{candidate_id}")
async def get_candidate_applications(candidate_id: str):
    """Get all applications for a candidate"""
    try:
        applications_collection = db.get_collection("applications")
        jobs_collection = db.get_collection("jobs")
        
        # Get applications
        applications = list(applications_collection.find({"candidate_id": candidate_id}))
        
        # Enrich with job details
        result = []
        for app in applications:
            app["_id"] = str(app["_id"])
            job = jobs_collection.find_one({"job_id": app.get("job_id")})
            
            result.append({
                "application_id": app.get("application_id"),
                "job_id": app.get("job_id"),
                "job_title": job.get("title") if job else "Unknown Job",
                "status": app.get("status"),
                "score": app.get("score", 0),
                "total_questions": app.get("total_questions", 5),
                "applied_at": app.get("applied_at"),
                "resume_path": app.get("resume_path"),
                "knocked_out": app.get("status") == "knocked_out",
                "is_shortlisted": app.get("status") == "shortlisted"
            })
        
        return {
            "success": True,
            "count": len(result),
            "applications": result
        }
        
    except Exception as e:
        logger.error(f"Error fetching candidate applications: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }
        )


# ============================
# Get all applications for a job (recruiter view)
# ============================
@router.get("/job/{job_id}")
async def get_job_applications(job_id: str):
    """Get all applications for a specific job"""
    try:
        applications_collection = db.get_collection("applications")
        users_collection = db.get_collection("users")
        
        # Get applications
        applications = list(applications_collection.find({"job_id": job_id}))
        
        # Enrich with candidate details
        result = []
        for app in applications:
            app["_id"] = str(app["_id"])
            candidate = users_collection.find_one({"user_id": app.get("candidate_id")})
            
            result.append({
                "application_id": app.get("application_id"),
                "candidate_id": app.get("candidate_id"),
                "candidate_name": candidate.get("name") if candidate else "Unknown",
                "candidate_email": candidate.get("email") if candidate else "Unknown",
                "status": app.get("status"),
                "score": app.get("score", 0),
                "total_questions": app.get("total_questions", 5),
                "applied_at": app.get("applied_at"),
                "resume_path": app.get("resume_path"),
                "knocked_out": app.get("status") == "knocked_out",
                "is_shortlisted": app.get("status") == "shortlisted"
            })
        
        return {
            "success": True,
            "count": len(result),
            "applications": result
        }
        
    except Exception as e:
        logger.error(f"Error fetching job applications: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }
        )


# ============================
# Update application status (shortlist/knockout/hire)
# ============================
@router.post("/{application_id}/status")
async def update_status(application_id: str, status: str, notes: str = ""):
    """Update application status (shortlist, knockout, hire)"""
    try:
        # Validate status
        valid_statuses = ["shortlisted", "knocked_out", "hired", "reviewing"]
        if status not in valid_statuses:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Invalid status. Must be one of: {valid_statuses}"
                }
            )
        
        # Update status
        result = update_application_status(application_id, status, notes)
        
        if result:
            return {
                "success": True,
                "message": f"Application status updated to {status}",
                "application": result
            }
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Application not found"
                }
            )
            
    except Exception as e:
        logger.error(f"Error updating application status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error"
            }

        )
