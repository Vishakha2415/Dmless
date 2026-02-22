"""
Dashboard module for DMless recruitment platform.
Handles recruiter dashboard metrics and statistics.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import re

# Import database functions
from database import (
    get_user_by_id,
    db
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# ============================
# Test endpoint
# ============================
@router.get("/test")
async def test_dashboard():
    """Test endpoint to verify dashboard router is working"""
    return {
        "success": True,
        "message": "Dashboard API is running",
        "timestamp": datetime.now().isoformat()
    }

# ============================
# Helper function for searching jobs
# ============================
def search_jobs_in_list(jobs: List[Dict], search_term: str) -> List[Dict]:
    """
    Search jobs by title, description, or status
    """
    if not search_term or search_term == "":
        return jobs
    
    search_term = search_term.lower().strip()
    filtered_jobs = []
    
    for job in jobs:
        # Search in title
        if search_term in job.get("title", "").lower():
            filtered_jobs.append(job)
            continue
            
        # Search in description
        if search_term in job.get("description", "").lower():
            filtered_jobs.append(job)
            continue
            
        # Search in status
        if search_term in job.get("status", "").lower():
            filtered_jobs.append(job)
            continue
            
        # Search in job type
        if search_term in job.get("job_type", "").lower():
            filtered_jobs.append(job)
            continue
            
        # Search in location
        if search_term in job.get("location", "").lower():
            filtered_jobs.append(job)
            continue
    
    return filtered_jobs

# ============================
# Helper function for filtering jobs by status
# ============================
def filter_jobs_by_status(jobs: List[Dict], status: str) -> List[Dict]:
    """
    Filter jobs by status (active, closed, draft, all)
    """
    if not status or status == "all":
        return jobs
    
    return [job for job in jobs if job.get("status", "").lower() == status.lower()]

# ============================
# Helper function for sorting jobs
# ============================
def sort_jobs(jobs: List[Dict], sort_by: str) -> List[Dict]:
    """
    Sort jobs by various criteria
    """
    if not jobs:
        return jobs
    
    if sort_by == "newest":
        # Newest first
        return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)
    elif sort_by == "oldest":
        # Oldest first
        return sorted(jobs, key=lambda x: x.get("created_at", ""))
    elif sort_by == "title":
        # Alphabetical by title
        return sorted(jobs, key=lambda x: x.get("title", "").lower())
    elif sort_by == "applications":
        # Most applications first
        return sorted(jobs, key=lambda x: x.get("applications", 0), reverse=True)
    else:
        # Default to newest
        return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)

# ============================
# Get REAL dashboard data from database with search/filter/sort
# ============================
@router.get("/{recruiter_id}")
async def get_dashboard(
    recruiter_id: str,
    search: Optional[str] = Query(None, description="Search term for jobs"),
    status: Optional[str] = Query("all", description="Filter by status: active, closed, draft, all"),
    sort: Optional[str] = Query("newest", description="Sort by: newest, oldest, title, applications")
):
    """
    Get REAL dashboard metrics for a recruiter from database.
    Supports search, filter by status, and sorting.
    """
    logger.info(f"📊 Dashboard requested for recruiter: {recruiter_id}")
    logger.info(f"   Search: '{search}', Status: {status}, Sort: {sort}")
    
    try:
        # Check if recruiter exists
        recruiter = get_user_by_id(recruiter_id)
        
        if not recruiter:
            logger.warning(f"Recruiter not found: {recruiter_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Recruiter not found"
                }
            )
        
        # Get jobs collection
        jobs_collection = db.get_collection("jobs")
        applications_collection = db.get_collection("applications")
        
        # Get ALL jobs for this recruiter from database
        recruiter_jobs = list(jobs_collection.find({"recruiter_id": recruiter_id}))
        
        logger.info(f"Found {len(recruiter_jobs)} jobs in database for recruiter {recruiter_id}")
        
        # Convert ObjectId to string for each job
        for job in recruiter_jobs:
            job["_id"] = str(job["_id"])
        
        if not recruiter_jobs:
            # No jobs yet - return empty data
            return {
                "success": True,
                "data": {
                    "total_jobs": 0,
                    "active_jobs": 0,
                    "total_applications": 0,
                    "shortlisted": 0,
                    "knocked_out": 0,
                    "hired": 0,
                    "pending": 0,
                    "jobs": [],
                    "filtered_count": 0,
                    "search_term": search,
                    "status_filter": status,
                    "sort_by": sort
                },
                "recruiter": {
                    "name": recruiter.get("name", "Recruiter"),
                    "email": recruiter.get("email", "")
                }
            }
        
        # Get all job IDs
        job_ids = [job["job_id"] for job in recruiter_jobs]
        
        # Get applications for these jobs
        all_applications = list(applications_collection.find({"job_id": {"$in": job_ids}}))
        
        # Calculate overall metrics (before filtering)
        total_applications_all = len(all_applications)
        shortlisted_all = len([a for a in all_applications if a.get("status") == "shortlisted"])
        knocked_out_all = len([a for a in all_applications if a.get("status") == "knocked_out"])
        hired_all = len([a for a in all_applications if a.get("status") == "hired"])
        pending_all = total_applications_all - (shortlisted_all + knocked_out_all + hired_all)
        
        # Get active jobs count (before filtering)
        active_jobs_all = len([j for j in recruiter_jobs if j.get("status") == "active"])
        
        # Prepare job summaries with their application counts (for ALL jobs)
        all_job_summaries = []
        for job in recruiter_jobs:
            job_apps = [a for a in all_applications if a.get("job_id") == job["job_id"]]
            
            all_job_summaries.append({
                "job_id": job["job_id"],
                "title": job.get("title", "Untitled"),
                "description": job.get("description", "")[:100] + "..." if job.get("description") else "",
                "status": job.get("status", "active"),
                "job_type": job.get("job_type", "full-time"),
                "location": job.get("location", "Remote"),
                "created_at": job.get("created_at"),
                "applications": len(job_apps),
                "shortlisted": len([a for a in job_apps if a.get("status") == "shortlisted"]),
                "knocked_out": len([a for a in job_apps if a.get("status") == "knocked_out"]),
                "hired": len([a for a in job_apps if a.get("status") == "hired"])
            })
        
        # APPLY SEARCH FILTER
        if search:
            filtered_jobs = search_jobs_in_list(all_job_summaries, search)
            logger.info(f"Search '{search}' found {len(filtered_jobs)} jobs")
        else:
            filtered_jobs = all_job_summaries
        
        # APPLY STATUS FILTER
        if status and status != "all":
            filtered_jobs = filter_jobs_by_status(filtered_jobs, status)
            logger.info(f"Status filter '{status}' reduced to {len(filtered_jobs)} jobs")
        
        # APPLY SORTING
        filtered_jobs = sort_jobs(filtered_jobs, sort)
        
        # Calculate metrics for FILTERED jobs only
        filtered_job_ids = [job["job_id"] for job in filtered_jobs]
        filtered_applications = [a for a in all_applications if a.get("job_id") in filtered_job_ids]
        
        total_applications_filtered = len(filtered_applications)
        shortlisted_filtered = len([a for a in filtered_applications if a.get("status") == "shortlisted"])
        knocked_out_filtered = len([a for a in filtered_applications if a.get("status") == "knocked_out"])
        hired_filtered = len([a for a in filtered_applications if a.get("status") == "hired"])
        pending_filtered = total_applications_filtered - (shortlisted_filtered + knocked_out_filtered + hired_filtered)
        
        active_jobs_filtered = len([j for j in filtered_jobs if j.get("status") == "active"])
        
        # Return data with search/filter/sort info
        return {
            "success": True,
            "data": {
                # Overall metrics (all jobs)
                "total_jobs_all": len(recruiter_jobs),
                "active_jobs_all": active_jobs_all,
                "total_applications_all": total_applications_all,
                "shortlisted_all": shortlisted_all,
                "knocked_out_all": knocked_out_all,
                "hired_all": hired_all,
                "pending_all": pending_all,
                
                # Filtered metrics (current view)
                "total_jobs": len(filtered_jobs),
                "active_jobs": active_jobs_filtered,
                "total_applications": total_applications_filtered,
                "shortlisted": shortlisted_filtered,
                "knocked_out": knocked_out_filtered,
                "hired": hired_filtered,
                "pending": pending_filtered,
                "jobs": filtered_jobs,
                
                # Search/filter metadata
                "filtered_count": len(filtered_jobs),
                "total_count": len(recruiter_jobs),
                "search_term": search,
                "status_filter": status,
                "sort_by": sort
            },
            "recruiter": {
                "name": recruiter.get("name", "Recruiter"),
                "email": recruiter.get("email", "")
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Dashboard error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Internal server error: {str(e)}"
            }
        )


# ============================
# Search endpoint specifically for jobs
# ============================
@router.get("/{recruiter_id}/search")
async def search_recruiter_jobs(
    recruiter_id: str,
    q: str = Query(..., description="Search query"),
    status: Optional[str] = Query("all", description="Filter by status")
):
    """
    Dedicated search endpoint for recruiter jobs
    """
    try:
        jobs_collection = db.get_collection("jobs")
        
        # Build search query
        query = {"recruiter_id": recruiter_id}
        
        if status and status != "all":
            query["status"] = status
        
        # Get jobs
        jobs = list(jobs_collection.find(query))
        
        # Convert ObjectId
        for job in jobs:
            job["_id"] = str(job["_id"])
        
        # Search in memory
        results = search_jobs_in_list(jobs, q)
        
        return {
            "success": True,
            "query": q,
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Search failed"}
        )


# ============================
# Get specific job details
# ============================
@router.get("/{recruiter_id}/jobs/{job_id}")
async def get_job_details(recruiter_id: str, job_id: str):
    """Get details for a specific job"""
    try:
        jobs_collection = db.get_collection("jobs")
        applications_collection = db.get_collection("applications")
        users_collection = db.get_collection("users")
        
        # Get job
        job = jobs_collection.find_one({"job_id": job_id, "recruiter_id": recruiter_id})
        
        if not job:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Job not found"}
            )
        
        # Convert ObjectId
        job["_id"] = str(job["_id"])
        
        # Get applications for this job
        applications = list(applications_collection.find({"job_id": job_id}))
        
        # Get candidate details for each application
        detailed_apps = []
        for app in applications:
            app["_id"] = str(app["_id"])
            candidate = users_collection.find_one({"user_id": app.get("candidate_id")})
            
            detailed_apps.append({
                "application_id": app.get("application_id"),
                "status": app.get("status"),
                "applied_at": app.get("applied_at"),
                "score": app.get("score"),
                "total_questions": app.get("total_questions"),
                "candidate": {
                    "name": candidate.get("name") if candidate else "Unknown",
                    "email": candidate.get("email") if candidate else "Unknown"
                } if candidate else None
            })
        
        return {
            "success": True,
            "job": {
                "job_id": job.get("job_id"),
                "title": job.get("title"),
                "description": job.get("description"),
                "status": job.get("status"),
                "created_at": job.get("created_at"),
                "applications": detailed_apps,
                "statistics": {
                    "total": len(applications),
                    "shortlisted": len([a for a in applications if a.get("status") == "shortlisted"]),
                    "knocked_out": len([a for a in applications if a.get("status") == "knocked_out"]),
                    "hired": len([a for a in applications if a.get("status") == "hired"])
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching job details: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error"}
        )