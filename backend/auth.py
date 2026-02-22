"""
Authentication module for DMless recruitment platform.
Handles user registration, login, and password hashing.
"""

from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import re
import logging

# Import database functions - updated for MongoDB
from database import (
    get_user_by_email,
    create_user,
    db
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================
# Pydantic Models
# ============================

class UserCreate(BaseModel):
    """Model for user registration request"""
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    email: EmailStr = Field(..., description="Work email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    role: str = Field(..., pattern="^(recruiter|candidate)$", description="User role")

class UserLogin(BaseModel):
    """Model for user login request"""
    email: EmailStr = Field(..., description="Work email address")
    password: str = Field(..., description="User password")

class UserResponse(BaseModel):
    """Model for user data response"""
    user_id: str
    name: str
    email: str
    role: str
    created_at: Optional[str] = None

class AuthResponse(BaseModel):
    """Model for authentication response"""
    success: bool
    message: str
    role: Optional[str] = None
    user: Optional[UserResponse] = None
    token: Optional[str] = None

# ============================
# Helper Functions
# ============================

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength requirements.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    
    return True, ""

# ============================
# API Endpoints
# ============================

@router.post("/signup", response_model=AuthResponse)
async def signup(user_data: UserCreate):
    """
    Register a new user in the system.
    """
    logger.info(f"Signup attempt for email: {user_data.email}")
    
    try:
        # Step 1: Check if user already exists in MongoDB
        existing_user = get_user_by_email(user_data.email)
        
        if existing_user:
            logger.warning(f"Signup failed - email already exists: {user_data.email}")
            return AuthResponse(
                success=False,
                message="Email already registered. Please use a different email or login.",
                role=None,
                user=None
            )
        
        # Step 2: Validate password strength
        is_valid_password, password_error = validate_password_strength(user_data.password)
        if not is_valid_password:
            logger.warning(f"Signup failed - weak password for: {user_data.email}")
            return AuthResponse(
                success=False,
                message=password_error,
                role=None,
                user=None
            )
        
        # Step 3: Hash password and create user
        password_hash = hash_password(user_data.password)
        
        # Create user in MongoDB
        user = create_user(
            email=user_data.email,
            name=user_data.name,
            password_hash=password_hash,
            role=user_data.role
        )
        
        if not user:
            logger.error(f"Failed to create user in database: {user_data.email}")
            return AuthResponse(
                success=False,
                message="Failed to create user. Please try again.",
                role=None,
                user=None
            )
        
        logger.info(f"User created successfully: {user_data.email} (Role: {user_data.role})")
        
        # Step 4: Return success response
        return AuthResponse(
            success=True,
            message="Account created successfully! Please login.",
            role=user["role"],
            user=UserResponse(
                user_id=user["user_id"],
                name=user["name"],
                email=user["email"],
                role=user["role"],
                created_at=user.get("created_at")
            )
        )
        
    except Exception as e:
        logger.error(f"Signup error for {user_data.email}: {str(e)}")
        return AuthResponse(
            success=False,
            message=f"An error occurred during signup: {str(e)}",
            role=None,
            user=None
        )


@router.post("/login", response_model=AuthResponse)
async def login(login_data: UserLogin):
    """
    Authenticate a user and return their role.
    """
    logger.info(f"Login attempt for email: {login_data.email}")
    
    try:
        # Step 1: Get user from MongoDB
        user = get_user_by_email(login_data.email)
        
        # Step 2: Check if user exists
        if not user:
            logger.warning(f"Login failed - user not found: {login_data.email}")
            return AuthResponse(
                success=False,
                message="Invalid email or password",
                role=None,
                user=None
            )
        
        # Step 3: Verify password
        if not verify_password(login_data.password, user["password_hash"]):
            logger.warning(f"Login failed - invalid password for: {login_data.email}")
            return AuthResponse(
                success=False,
                message="Invalid email or password",
                role=None,
                user=None
            )
        
        logger.info(f"Login successful: {login_data.email} (Role: {user['role']})")
        
        # Step 4: Return success with user role
        return AuthResponse(
            success=True,
            message="Login successful",
            role=user["role"],
            user=UserResponse(
                user_id=user["user_id"],
                name=user["name"],
                email=user["email"],
                role=user["role"],
                created_at=user.get("created_at")
            )
        )
        
    except Exception as e:
        logger.error(f"Login error for {login_data.email}: {str(e)}")
        return AuthResponse(
            success=False,
            message=f"An error occurred during login: {str(e)}",
            role=None,
            user=None
        )


@router.get("/check-email/{email}")
async def check_email_exists(email: str):
    """
    Check if an email is already registered.
    """
    user = get_user_by_email(email)
    return {
        "exists": user is not None,
        "message": "Email already registered" if user else "Email available"
    }


@router.get("/test")
async def test_auth():
    """Test endpoint to verify auth router is working"""
    return {
        "status": "active",
        "message": "Authentication API is running",
        "database": "connected" if db.is_connected else "disconnected",
        "endpoints": ["/auth/signup", "/auth/login", "/auth/check-email/{email}"]
    }


@router.post("/create-test-user")
async def create_test_user():
    """Create a test user for development purposes"""
    try:
        # Check if test user already exists
        test_email = "test@example.com"
        existing = get_user_by_email(test_email)
        
        if existing:
            return {
                "message": "Test user already exists", 
                "user": {
                    "email": test_email,
                    "password": "Test12345",
                    "role": existing["role"]
                }
            }
        
        # Create test user
        password_hash = hash_password("Test12345")
        user = create_user(
            email=test_email,
            name="Test User",
            password_hash=password_hash,
            role="recruiter"
        )
        
        return {
            "message": "Test user created successfully",
            "user": {
                "email": test_email,
                "password": "Test12345",
                "role": "recruiter"
            }
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/list-users")
async def list_users():
    """List all users in the database (for debugging)"""
    try:
        users_collection = db.get_collection("users")
        users = list(users_collection.find({}, {"password_hash": 0}))  # Exclude password hash
        
        # Convert ObjectId to string
        for user in users:
            user["_id"] = str(user["_id"])
        
        return {
            "count": len(users),
            "users": users
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/delete-user/{email}")
async def delete_user(email: str):
    """Delete a user by email (for debugging)"""
    try:
        users_collection = db.get_collection("users")
        result = users_collection.delete_one({"email": email.lower()})
        
        if result.deleted_count > 0:
            return {"success": True, "message": f"User {email} deleted"}
        else:
            return {"success": False, "message": f"User {email} not found"}
    except Exception as e:
        return {"error": str(e)}


# ============================
# NEW ENDPOINTS FOR PRANAV
# ============================

@router.get("/force-create-pranav")
async def force_create_pranav():
    """Force delete and recreate pranav user with password Test@123"""
    try:
        users_collection = db.get_collection("users")
        from database import generate_id
        
        # Delete if exists
        users_collection.delete_one({"email": "pranav123@gmail.com"})
        
        # Create fresh with proper hash
        password_hash = hash_password("Test@123")
        
        # Generate unique user ID
        user_id = generate_id("user_")
        
        user_doc = {
            "user_id": user_id,
            "name": "Pranav",
            "email": "pranav123@gmail.com",
            "password_hash": password_hash,
            "role": "recruiter",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "is_active": True
        }
        
        result = users_collection.insert_one(user_doc)
        
        if result.inserted_id:
            return {
                "success": True,
                "message": "User force created successfully",
                "credentials": {
                    "email": "pranav123@gmail.com",
                    "password": "Test@123"
                }
            }
        else:
            return {"success": False, "message": "Failed to create user"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/test-login-direct")
async def test_login_direct():
    """Test login directly without frontend"""
    try:
        email = "pranav123@gmail.com"
        password = "Test@123"
        
        user = get_user_by_email(email)
        
        if not user:
            return {
                "success": False,
                "message": "User not found",
                "email": email
            }
        
        password_valid = verify_password(password, user["password_hash"])
        
        return {
            "success": password_valid,
            "message": "Login successful" if password_valid else "Invalid password",
            "email": email,
            "user_exists": True,
            "password_valid": password_valid,
            "user_role": user.get("role")
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/reset-pranav-password")
async def reset_pranav_password():
    """Reset password for pranav123@gmail.com"""
    try:
        users_collection = db.get_collection("users")
        
        # Check if user exists
        user = get_user_by_email("pranav123@gmail.com")
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        # New password hash
        new_password_hash = hash_password("Test@123")
        
        # Update the user
        result = users_collection.update_one(
            {"email": "pranav123@gmail.com"},
            {"$set": {"password_hash": new_password_hash}}
        )
        
        return {
            "success": True,
            "message": "Password reset successfully",
            "credentials": {
                "email": "pranav123@gmail.com",
                "password": "Test@123"
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/debug-password")
async def debug_password():
    """Debug password hashing for pranav123@gmail.com"""
    try:
        results = {
            "tests": []
        }
        
        # Test 1: Basic hashing test
        test_password = "Test@123"
        test_hash = hash_password(test_password)
        test_verify = verify_password(test_password, test_hash)
        
        results["tests"].append({
            "name": "Basic hashing test",
            "password": test_password,
            "hash": test_hash[:30] + "...",
            "verification": test_verify
        })
        
        # Test 2: Get user from database
        user = get_user_by_email("pranav123@gmail.com")
        
        if user:
            stored_hash = user.get("password_hash")
            verify_stored = verify_password(test_password, stored_hash) if stored_hash else False
            
            results["tests"].append({
                "name": "User from database",
                "email": user["email"],
                "name": user["name"],
                "verification_with_Test@123": verify_stored
            })
        else:
            results["tests"].append({
                "name": "User from database",
                "error": "User not found"
            })
        
        return results
    except Exception as e:
        return {"error": str(e)}