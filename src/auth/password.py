"""
Password hashing, OTP generation, and JWT token management.
"""
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from passlib.context import CryptContext
import jwt

from src.auth.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    OTP_LENGTH, OTP_EXPIRY_MINUTES, PASSWORD_MIN_LENGTH
)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# PASSWORD HASHING
# =============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password meets requirements.
    Returns (is_valid, error_message).
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    return True, ""


# =============================================================================
# OTP GENERATION & VERIFICATION
# =============================================================================

def generate_otp() -> tuple[str, datetime]:
    """
    Generate a random OTP code.
    Returns (code, expiry_datetime).
    """
    # Generate numeric OTP
    code = ''.join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))
    expiry = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    return code, expiry


def verify_otp(stored_code: str, provided_code: str, expires_at: datetime, is_used: bool) -> tuple[bool, str]:
    """
    Verify an OTP code.
    Returns (is_valid, error_message).
    """
    if is_used:
        return False, "OTP has already been used"
    
    if datetime.utcnow() > expires_at:
        return False, "OTP has expired"
    
    if stored_code != provided_code:
        return False, "Invalid OTP code"
    
    return True, ""


# =============================================================================
# JWT TOKENS
# =============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data (should include 'sub' for user ID)
        expires_delta: Optional custom expiry time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
