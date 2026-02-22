"""
Database layer for DMless recruitment platform.
Handles all MongoDB Atlas connections and operations.
Collections: users, jobs, applications
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from bson import ObjectId
from typing import Optional, Dict, List, Any

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================
# MongoDB Connection - Your Atlas URI
# ============================

MONGO_URI = "mongodb+srv://DMless:9wnjIAnfyOqkKg2x@cluster0.swqkpo4.mongodb.net/dmless?retryWrites=true&w=majority"
DATABASE_NAME = "dmless"

class MongoDB:
    """
    MongoDB connection manager for DMless application.
    Handles connection to MongoDB Atlas and provides collection access.
    """
    
    def __init__(self):
        """Initialize MongoDB connection using your Atlas URI"""
        self.client = None
        self.db = None
        self.is_connected = False
        
        # Your MongoDB Atlas connection string
        self.connection_string = MONGO_URI
        self.database_name = DATABASE_NAME
        
        # Connection options for Atlas
        self.connection_options = {
            "maxPoolSize": 50,
            "minPoolSize": 10,
            "maxIdleTimeMS": 45000,
            "retryWrites": True,
            "retryReads": True,
            "connectTimeoutMS": 10000,
            "socketTimeoutMS": 45000,
            "serverSelectionTimeoutMS": 5000,
            "ssl": True,
            "tlsAllowInvalidCertificates": True  # Set to False in production
        }
        
        logger.info("🔄 MongoDB Atlas connection configured")
    
    def connect(self):
        """Establish connection to MongoDB Atlas"""
        try:
            # Create MongoDB client with your Atlas URI
            self.client = MongoClient(
                self.connection_string,
                **self.connection_options
            )
            
            # Send a ping to confirm successful connection
            self.client.admin.command('ping')
            
            # Get database
            self.db = self.client[self.database_name]
            self.is_connected = True
            
            # Create indexes
            self._create_indexes()
            
            # Log success
            logger.info("✅ Successfully connected to MongoDB Atlas!")
            logger.info(f"📊 Database: {self.database_name}")
            logger.info(f"📍 Cluster: cluster0.swqkpo4.mongodb.net")
            
            # Test connection by listing collections
            collections = self.db.list_collection_names()
            logger.info(f"📚 Existing collections: {collections if collections else 'None'}")
            
            return True
            
        except ConnectionFailure as e:
            logger.error(f"❌ Failed to connect to MongoDB Atlas: {e}")
            logger.error("💡 Please check your network connection and Atlas whitelist")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
            self.is_connected = False
            return False
    
    def _create_indexes(self):
        """Create necessary indexes for collections"""
        try:
            # Users collection indexes
            self.db.users.create_index("email", unique=True)
            self.db.users.create_index("user_id", unique=True)
            logger.info("✅ Users indexes created")
            
            # Jobs collection indexes
            self.db.jobs.create_index("job_id", unique=True)
            self.db.jobs.create_index("recruiter_id")
            self.db.jobs.create_index("created_at")
            self.db.jobs.create_index([("title", "text"), ("description", "text")])
            logger.info("✅ Jobs indexes created")
            
            # Applications collection indexes
            self.db.applications.create_index("application_id", unique=True)
            self.db.applications.create_index([("job_id", 1), ("candidate_id", 1)], unique=True)
            self.db.applications.create_index("job_id")
            self.db.applications.create_index("candidate_id")
            self.db.applications.create_index("status")
            logger.info("✅ Applications indexes created")
            
        except Exception as e:
            logger.warning(f"⚠️ Index creation warning: {e}")
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("🔌 MongoDB Atlas connection closed")
    
    def get_collection(self, collection_name: str):
        """Get a collection by name"""
        if not self.is_connected:
            self.connect()
        return self.db[collection_name]
    
    def check_connection(self):
        """Check if connection is alive"""
        try:
            self.client.admin.command('ping')
            return True
        except:
            self.is_connected = False
            return False


# Create global database instance
db = MongoDB()

# Automatically connect when module is imported
try:
    connection_success = db.connect()
    if connection_success:
        logger.info("🚀 MongoDB Atlas is ready to use")
    else:
        logger.warning("⚠️ MongoDB Atlas connection failed. Using fallback in-memory?")
except Exception as e:
    logger.error(f"❌ Initial connection failed: {e}")

# ============================
# Helper Functions
# ============================

def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID with optional prefix.
    
    Args:
        prefix: Optional prefix for the ID (e.g., 'user_', 'job_')
    
    Returns:
        Unique ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = str(ObjectId())[-6:]
    return f"{prefix}{timestamp}_{random_suffix}"


def serialize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MongoDB document to JSON-serializable format.
    
    Args:
        doc: MongoDB document with ObjectId
    
    Returns:
        Dictionary with ObjectId converted to string
    """
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ============================
# User Collection Operations
# ============================

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get user by email address.
    
    Args:
        email: User's email address
    
    Returns:
        User document or None if not found
    """
    try:
        users = db.get_collection("users")
        user = users.find_one({"email": email.lower()})
        
        if user:
            user = serialize_document(user)
            logger.info(f"📧 User found: {email}")
        else:
            logger.info(f"📧 User not found: {email}")
        
        return user
        
    except Exception as e:
        logger.error(f"❌ Error getting user by email {email}: {e}")
        return None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user by user ID.
    
    Args:
        user_id: Unique user identifier
    
    Returns:
        User document or None if not found
    """
    try:
        users = db.get_collection("users")
        user = users.find_one({"user_id": user_id})
        
        if user:
            user = serialize_document(user)
            logger.info(f"👤 User found: {user_id}")
        
        return user
        
    except Exception as e:
        logger.error(f"❌ Error getting user by ID {user_id}: {e}")
        return None


def create_user(email: str, name: str, password_hash: str, role: str) -> Optional[Dict[str, Any]]:
    """
    Create a new user in the database.
    
    Args:
        email: User's email address
        name: User's full name
        password_hash: Hashed password
        role: User role (recruiter/candidate)
    
    Returns:
        Created user document or None if creation failed
    """
    try:
        users = db.get_collection("users")
        
        # Generate unique user ID
        user_id = generate_id("user_")
        
        # Create user document
        user_doc = {
            "user_id": user_id,
            "name": name,
            "email": email.lower(),
            "password_hash": password_hash,
            "role": role,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "is_active": True,
            "profile": {
                "title": "",
                "department": "",
                "company": "",
                "phone": "",
                "location": ""
            },
            "settings": {
                "notifications": True,
                "email_updates": True
            }
        }
        
        # Insert into database
        result = users.insert_one(user_doc)
        
        if result.inserted_id:
            logger.info(f"✅ User created successfully: {email} (ID: {user_id})")
            return serialize_document(user_doc)
        else:
            logger.error(f"❌ Failed to create user: {email}")
            return None
            
    except DuplicateKeyError:
        logger.error(f"❌ Duplicate email: {email}")
        return None
    except Exception as e:
        logger.error(f"❌ Error creating user {email}: {e}")
        return None


def update_user(user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update user information.
    
    Args:
        user_id: User ID to update
        update_data: Dictionary of fields to update
    
    Returns:
        Updated user document or None if update failed
    """
    try:
        users = db.get_collection("users")
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.now().isoformat()
        
        # Update user
        result = users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ User updated: {user_id}")
            return get_user_by_id(user_id)
        else:
            logger.warning(f"⚠️ No changes made to user: {user_id}")
            return get_user_by_id(user_id)
            
    except Exception as e:
        logger.error(f"❌ Error updating user {user_id}: {e}")
        return None


# ============================
# Jobs Collection Operations
# ============================

def create_job(recruiter_id: str, title: str, description: str, mcqs: List[Dict], 
               requirements: List[str] = None, salary_range: Dict = None, 
               location: str = None, job_type: str = "full-time") -> Optional[Dict[str, Any]]:
    """
    Create a new job posting.
    
    Args:
        recruiter_id: ID of the recruiter creating the job
        title: Job title
        description: Job description
        mcqs: List of MCQs for knockout screening
        requirements: List of job requirements
        salary_range: Dictionary with min/max salary
        location: Job location
        job_type: Type of job (full-time, part-time, contract)
    
    Returns:
        Created job document or None if creation failed
    """
    try:
        jobs = db.get_collection("jobs")
        
        # Generate unique job ID
        job_id = generate_id("job_")
        
        # Create job document
        job_doc = {
            "job_id": job_id,
            "recruiter_id": recruiter_id,
            "title": title,
            "description": description,
            "mcqs": mcqs,
            "requirements": requirements or [],
            "salary_range": salary_range or {"min": None, "max": None, "currency": "USD"},
            "location": location or "Remote",
            "job_type": job_type,
            "status": "active",
            "applications_count": 0,
            "shortlisted_count": 0,
            "knocked_out_count": 0,
            "hired_count": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "expires_at": None,
            "metadata": {
                "views": 0,
                "applications": 0
            }
        }
        
        # Insert into database
        result = jobs.insert_one(job_doc)
        
        if result.inserted_id:
            logger.info(f"✅ Job created successfully: {job_id} - {title}")
            return serialize_document(job_doc)
        else:
            logger.error(f"❌ Failed to create job: {title}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error creating job: {e}")
        return None


def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get job by job ID.
    
    Args:
        job_id: Unique job identifier
    
    Returns:
        Job document or None if not found
    """
    try:
        jobs = db.get_collection("jobs")
        job = jobs.find_one({"job_id": job_id})
        
        if job:
            job = serialize_document(job)
            logger.info(f"📋 Job found: {job_id}")
        else:
            logger.info(f"📋 Job not found: {job_id}")
        
        return job
        
    except Exception as e:
        logger.error(f"❌ Error getting job by ID {job_id}: {e}")
        return None


def get_jobs_by_recruiter(recruiter_id: str, status: str = None) -> List[Dict[str, Any]]:
    """
    Get all jobs created by a specific recruiter.
    
    Args:
        recruiter_id: Recruiter's user ID
        status: Filter by job status (active, closed, draft)
    
    Returns:
        List of job documents
    """
    try:
        jobs = db.get_collection("jobs")
        
        # Build query
        query = {"recruiter_id": recruiter_id}
        if status:
            query["status"] = status
        
        # Get jobs sorted by creation date (newest first)
        job_list = list(jobs.find(query).sort("created_at", -1))
        
        # Serialize documents
        job_list = [serialize_document(job) for job in job_list]
        
        logger.info(f"📋 Found {len(job_list)} jobs for recruiter: {recruiter_id}")
        return job_list
        
    except Exception as e:
        logger.error(f"❌ Error getting jobs for recruiter {recruiter_id}: {e}")
        return []


def get_all_active_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get all active job postings for candidates.
    
    Args:
        limit: Maximum number of jobs to return
    
    Returns:
        List of active job documents
    """
    try:
        jobs = db.get_collection("jobs")
        
        # Get active jobs, newest first
        job_list = list(jobs.find({"status": "active"})
                       .sort("created_at", -1)
                       .limit(limit))
        
        # Serialize documents
        job_list = [serialize_document(job) for job in job_list]
        
        logger.info(f"📋 Found {len(job_list)} active jobs")
        return job_list
        
    except Exception as e:
        logger.error(f"❌ Error getting active jobs: {e}")
        return []


def update_job(job_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update job information.
    
    Args:
        job_id: Job ID to update
        update_data: Dictionary of fields to update
    
    Returns:
        Updated job document or None if update failed
    """
    try:
        jobs = db.get_collection("jobs")
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.now().isoformat()
        
        # Update job
        result = jobs.update_one(
            {"job_id": job_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Job updated: {job_id}")
            return get_job_by_id(job_id)
        else:
            logger.warning(f"⚠️ No changes made to job: {job_id}")
            return get_job_by_id(job_id)
            
    except Exception as e:
        logger.error(f"❌ Error updating job {job_id}: {e}")
        return None


def delete_job(job_id: str) -> bool:
    """
    Delete a job posting.
    
    Args:
        job_id: Job ID to delete
    
    Returns:
        True if deleted, False otherwise
    """
    try:
        jobs = db.get_collection("jobs")
        
        # Check if job exists
        job = get_job_by_id(job_id)
        if not job:
            logger.warning(f"⚠️ Job not found for deletion: {job_id}")
            return False
        
        # Delete job
        result = jobs.delete_one({"job_id": job_id})
        
        if result.deleted_count > 0:
            logger.info(f"✅ Job deleted: {job_id}")
            
            # Also delete associated applications
            applications = db.get_collection("applications")
            app_result = applications.delete_many({"job_id": job_id})
            logger.info(f"📋 Deleted {app_result.deleted_count} associated applications")
            
            return True
        else:
            logger.warning(f"⚠️ Job not deleted: {job_id}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error deleting job {job_id}: {e}")
        return False


# ============================
# Applications Collection Operations
# ============================

def save_application(job_id: str, candidate_id: str, answers: List[Dict], 
                     status: str = "applied", resume_path: str = None) -> Optional[Dict[str, Any]]:
    """
    Save a job application.
    
    Args:
        job_id: ID of the job being applied for
        candidate_id: ID of the candidate applying
        answers: List of answers to MCQs
        status: Application status (applied, shortlisted, knocked_out, hired)
        resume_path: Path to uploaded resume file
    
    Returns:
        Created application document or None if creation failed
    """
    try:
        applications = db.get_collection("applications")
        
        # Check if already applied
        existing = applications.find_one({
            "job_id": job_id,
            "candidate_id": candidate_id
        })
        
        if existing:
            logger.warning(f"⚠️ Candidate {candidate_id} already applied to job {job_id}")
            return serialize_document(existing)
        
        # Generate unique application ID
        application_id = generate_id("app_")
        
        # Calculate knockout status
        mcq_results = []
        knocked_out = False
        correct_count = 0
        
        for i, answer in enumerate(answers):
            is_correct = answer.get("is_correct", False)
            mcq_results.append({
                "question_number": i + 1,
                "question": answer.get("question", ""),
                "selected_option": answer.get("selected_option", ""),
                "is_correct": is_correct,
                "time_taken": answer.get("time_taken", 0)
            })
            if is_correct:
                correct_count += 1
            else:
                knocked_out = True
        
        # Create application document
        application_doc = {
            "application_id": application_id,
            "job_id": job_id,
            "candidate_id": candidate_id,
            "status": "knocked_out" if knocked_out else "applied",
            "answers": mcq_results,
            "score": correct_count,
            "total_questions": len(answers),
            "resume_path": resume_path,
            "applied_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "notes": "",
            "feedback": "",
            "interview_details": None
        }
        
        # Insert into database
        result = applications.insert_one(application_doc)
        
        if result.inserted_id:
            logger.info(f"✅ Application saved: {application_id} (Status: {application_doc['status']})")
            
            # Update job application count
            update_job_application_count(job_id)
            
            return serialize_document(application_doc)
        else:
            logger.error(f"❌ Failed to save application")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error saving application: {e}")
        return None


def get_applications_by_recruiter(recruiter_id: str) -> List[Dict[str, Any]]:
    """
    Get all applications for jobs created by a recruiter.
    
    Args:
        recruiter_id: Recruiter's user ID
    
    Returns:
        List of application documents with job details
    """
    try:
        applications = db.get_collection("applications")
        jobs = db.get_collection("jobs")
        
        # First get all jobs by this recruiter
        recruiter_jobs = list(jobs.find({"recruiter_id": recruiter_id}))
        job_ids = [job["job_id"] for job in recruiter_jobs]
        
        if not job_ids:
            return []
        
        # Get applications for these jobs
        pipeline = [
            {"$match": {"job_id": {"$in": job_ids}}},
            {"$lookup": {
                "from": "users",
                "localField": "candidate_id",
                "foreignField": "user_id",
                "as": "candidate"
            }},
            {"$lookup": {
                "from": "jobs",
                "localField": "job_id",
                "foreignField": "job_id",
                "as": "job"
            }},
            {"$sort": {"applied_at": -1}}
        ]
        
        app_list = list(applications.aggregate(pipeline))
        
        # Serialize documents
        for app in app_list:
            app = serialize_document(app)
            if "candidate" in app and app["candidate"]:
                app["candidate"] = serialize_document(app["candidate"][0])
            if "job" in app and app["job"]:
                app["job"] = serialize_document(app["job"][0])
        
        logger.info(f"📋 Found {len(app_list)} applications for recruiter: {recruiter_id}")
        return app_list
        
    except Exception as e:
        logger.error(f"❌ Error getting applications for recruiter {recruiter_id}: {e}")
        return []


def get_applications_by_candidate(candidate_id: str) -> List[Dict[str, Any]]:
    """
    Get all applications by a candidate.
    
    Args:
        candidate_id: Candidate's user ID
    
    Returns:
        List of application documents with job details
    """
    try:
        applications = db.get_collection("applications")
        
        pipeline = [
            {"$match": {"candidate_id": candidate_id}},
            {"$lookup": {
                "from": "jobs",
                "localField": "job_id",
                "foreignField": "job_id",
                "as": "job"
            }},
            {"$sort": {"applied_at": -1}}
        ]
        
        app_list = list(applications.aggregate(pipeline))
        
        # Serialize documents
        for app in app_list:
            app = serialize_document(app)
            if "job" in app and app["job"]:
                app["job"] = serialize_document(app["job"][0])
        
        logger.info(f"📋 Found {len(app_list)} applications for candidate: {candidate_id}")
        return app_list
        
    except Exception as e:
        logger.error(f"❌ Error getting applications for candidate {candidate_id}: {e}")
        return []


def get_application_by_id(application_id: str) -> Optional[Dict[str, Any]]:
    """
    Get application by application ID.
    
    Args:
        application_id: Unique application identifier
    
    Returns:
        Application document or None if not found
    """
    try:
        applications = db.get_collection("applications")
        application = applications.find_one({"application_id": application_id})
        
        if application:
            application = serialize_document(application)
            logger.info(f"📋 Application found: {application_id}")
        
        return application
        
    except Exception as e:
        logger.error(f"❌ Error getting application by ID {application_id}: {e}")
        return None


def update_application_status(application_id: str, status: str, notes: str = "", feedback: str = "") -> Optional[Dict[str, Any]]:
    """
    Update application status.
    
    Args:
        application_id: Application ID to update
        status: New status (shortlisted, knocked_out, hired, etc.)
        notes: Additional notes
        feedback: Feedback for candidate
    
    Returns:
        Updated application document or None if update failed
    """
    try:
        applications = db.get_collection("applications")
        
        update_data = {
            "status": status,
            "updated_at": datetime.now().isoformat()
        }
        
        if notes:
            update_data["notes"] = notes
        
        if feedback:
            update_data["feedback"] = feedback
        
        # Update application
        result = applications.update_one(
            {"application_id": application_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Application status updated: {application_id} -> {status}")
            
            # Get job ID for counter update
            app = get_application_by_id(application_id)
            if app:
                update_job_application_status_count(app["job_id"])
            
            return get_application_by_id(application_id)
        else:
            logger.warning(f"⚠️ No changes made to application: {application_id}")
            return get_application_by_id(application_id)
            
    except Exception as e:
        logger.error(f"❌ Error updating application {application_id}: {e}")
        return None


def update_job_application_count(job_id: str) -> None:
    """
    Update the application count for a job.
    
    Args:
        job_id: Job ID to update
    """
    try:
        jobs = db.get_collection("jobs")
        applications = db.get_collection("applications")
        
        # Count applications for this job
        count = applications.count_documents({"job_id": job_id})
        
        # Update job
        jobs.update_one(
            {"job_id": job_id},
            {"$set": {"applications_count": count, "updated_at": datetime.now().isoformat()}}
        )
        
        logger.info(f"📊 Updated application count for job {job_id}: {count}")
        
    except Exception as e:
        logger.error(f"❌ Error updating job application count: {e}")


def update_job_application_status_count(job_id: str) -> None:
    """
    Update status counts (shortlisted, knocked_out) for a job.
    
    Args:
        job_id: Job ID to update
    """
    try:
        jobs = db.get_collection("jobs")
        applications = db.get_collection("applications")
        
        # Count by status
        shortlisted = applications.count_documents({"job_id": job_id, "status": "shortlisted"})
        knocked_out = applications.count_documents({"job_id": job_id, "status": "knocked_out"})
        hired = applications.count_documents({"job_id": job_id, "status": "hired"})
        
        # Update job
        jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "shortlisted_count": shortlisted,
                "knocked_out_count": knocked_out,
                "hired_count": hired,
                "updated_at": datetime.now().isoformat()
            }}
        )
        
        logger.info(f"📊 Updated status counts for job {job_id}")
        
    except Exception as e:
        logger.error(f"❌ Error updating job status counts: {e}")


# ============================
# Dashboard Statistics
# ============================

def get_recruiter_dashboard_stats(recruiter_id: str) -> Dict[str, Any]:
    """
    Get dashboard statistics for a recruiter.
    
    Args:
        recruiter_id: Recruiter's user ID
    
    Returns:
        Dictionary with dashboard statistics
    """
    try:
        jobs = db.get_collection("jobs")
        applications = db.get_collection("applications")
        
        # Get all jobs by recruiter
        recruiter_jobs = list(jobs.find({"recruiter_id": recruiter_id}))
        job_ids = [job["job_id"] for job in recruiter_jobs]
        
        if not job_ids:
            return {
                "total_jobs": 0,
                "active_jobs": 0,
                "total_applications": 0,
                "shortlisted": 0,
                "knocked_out": 0,
                "hired": 0,
                "jobs": []
            }
        
        # Count applications for these jobs
        total_applications = applications.count_documents({"job_id": {"$in": job_ids}})
        shortlisted = applications.count_documents({"job_id": {"$in": job_ids}, "status": "shortlisted"})
        knocked_out = applications.count_documents({"job_id": {"$in": job_ids}, "status": "knocked_out"})
        hired = applications.count_documents({"job_id": {"$in": job_ids}, "status": "hired"})
        
        # Get active jobs count
        active_jobs = len([j for j in recruiter_jobs if j.get("status") == "active"])
        
        # Prepare job summaries
        job_summaries = []
        for job in recruiter_jobs:
            job_apps = applications.count_documents({"job_id": job["job_id"]})
            job_shortlisted = applications.count_documents({"job_id": job["job_id"], "status": "shortlisted"})
            job_knocked = applications.count_documents({"job_id": job["job_id"], "status": "knocked_out"})
            
            job_summaries.append({
                "job_id": job["job_id"],
                "title": job["title"],
                "status": job["status"],
                "applications": job_apps,
                "shortlisted": job_shortlisted,
                "knocked_out": job_knocked,
                "created_at": job["created_at"]
            })
        
        stats = {
            "total_jobs": len(recruiter_jobs),
            "active_jobs": active_jobs,
            "total_applications": total_applications,
            "shortlisted": shortlisted,
            "knocked_out": knocked_out,
            "hired": hired,
            "jobs": job_summaries
        }
        
        logger.info(f"📊 Dashboard stats for recruiter {recruiter_id}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error getting dashboard stats: {e}")
        return {
            "total_jobs": 0,
            "active_jobs": 0,
            "total_applications": 0,
            "shortlisted": 0,
            "knocked_out": 0,
            "hired": 0,
            "jobs": []
        }


def get_candidate_dashboard_stats(candidate_id: str) -> Dict[str, Any]:
    """
    Get dashboard statistics for a candidate.
    
    Args:
        candidate_id: Candidate's user ID
    
    Returns:
        Dictionary with candidate statistics
    """
    try:
        applications = db.get_collection("applications")
        
        # Get all applications by candidate
        candidate_apps = list(applications.find({"candidate_id": candidate_id}))
        
        # Count by status
        total_applications = len(candidate_apps)
        shortlisted = len([a for a in candidate_apps if a.get("status") == "shortlisted"])
        knocked_out = len([a for a in candidate_apps if a.get("status") == "knocked_out"])
        pending = len([a for a in candidate_apps if a.get("status") == "applied"])
        hired = len([a for a in candidate_apps if a.get("status") == "hired"])
        
        stats = {
            "total_applications": total_applications,
            "shortlisted": shortlisted,
            "knocked_out": knocked_out,
            "pending": pending,
            "hired": hired
        }
        
        logger.info(f"📊 Dashboard stats for candidate {candidate_id}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error getting candidate dashboard stats: {e}")
        return {
            "total_applications": 0,
            "shortlisted": 0,
            "knocked_out": 0,
            "pending": 0,
            "hired": 0
        }


# ============================
# Connection Test
# ============================

def test_connection():
    """Test the MongoDB Atlas connection"""
    try:
        # Try to connect
        if db.connect():
            # List all collections
            collections = db.db.list_collection_names()
            print("\n" + "="*50)
            print("✅ MongoDB Atlas Connection Successful!")
            print("="*50)
            print(f"📊 Database: {DATABASE_NAME}")
            print(f"📍 Cluster: cluster0.swqkpo4.mongodb.net")
            print(f"📚 Collections: {collections if collections else 'None yet'}")
            
            # Show counts
            for collection in ['users', 'jobs', 'applications']:
                if collection in collections:
                    count = db.db[collection].count_documents({})
                    print(f"   - {collection}: {count} documents")
            
            print("="*50 + "\n")
            return True
        else:
            print("\n" + "="*50)
            print("❌ MongoDB Atlas Connection Failed!")
            print("="*50)
            print("Please check:")
            print("1. Your internet connection")
            print("2. Atlas whitelist (add your IP)")
            print("3. Username and password are correct")
            print("="*50 + "\n")
            return False
    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        return False


# Run test if script is executed directly
if __name__ == "__main__":
    test_connection()