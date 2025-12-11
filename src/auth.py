"""
Authentication for Enterprise RAG
Google OAuth2 + Email OTP + JWT Token Management
"""
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, EmailStr

from src.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_HOURS,
    SMTP_HOST, SMTP_PORT, SMTP_EMAIL, SMTP_PASSWORD,
    OTP_EXPIRE_MINUTES, OTP_LENGTH
)
from src.db import get_db, User, OTPCode

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict

class UserResponse(BaseModel):
    """User info response."""
    id: int
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    auth_provider: Optional[str] = None

class EmailRequest(BaseModel):
    """Email request for OTP."""
    email: EmailStr

class OTPVerifyRequest(BaseModel):
    """OTP verification request."""
    email: EmailStr
    otp: str

class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    status: str = "success"

# =============================================================================
# OAUTH SETUP (Google)
# =============================================================================

oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# =============================================================================
# JWT TOKEN FUNCTIONS
# =============================================================================

def create_access_token(user_id: int, email: str) -> tuple[str, int]:
    """Create JWT access token. Returns (token, expires_in_seconds)."""
    expires_delta = timedelta(hours=JWT_EXPIRE_HOURS)
    expire = datetime.now(timezone.utc) + expires_delta
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def verify_token(token: str) -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

# =============================================================================
# EMAIL OTP FUNCTIONS
# =============================================================================

def generate_otp() -> str:
    """Generate a random 6-digit OTP."""
    return ''.join([str(random.randint(0, 9)) for _ in range(OTP_LENGTH)])


def send_otp_email(email: str, otp: str) -> bool:
    """Send OTP email using Gmail SMTP."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("SMTP not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Your Enterprise RAG Login Code: {otp}'
        msg['From'] = f'Enterprise RAG <{SMTP_EMAIL}>'
        msg['To'] = email
        
        # HTML email body
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Enterprise RAG</h1>
            </div>
            <div style="padding: 30px; background: #f9f9f9;">
                <h2 style="color: #333;">Your Login Code</h2>
                <p style="color: #666; font-size: 16px;">Use this code to sign in to your account:</p>
                <div style="background: white; border: 2px solid #667eea; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0;">
                    <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #667eea;">{otp}</span>
                </div>
                <p style="color: #999; font-size: 14px;">This code expires in {OTP_EXPIRE_MINUTES} minutes.</p>
                <p style="color: #999; font-size: 14px;">If you didn't request this code, please ignore this email.</p>
            </div>
            <div style="padding: 20px; text-align: center; color: #999; font-size: 12px;">
                © 2024 Enterprise RAG - Secure Document Intelligence
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text = f"Your Enterprise RAG login code is: {otp}\n\nThis code expires in {OTP_EXPIRE_MINUTES} minutes."
        
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, email, msg.as_string())
        
        print(f"OTP sent to {email}")
        return True
        
    except Exception as e:
        print(f"Failed to send OTP email: {e}")
        return False


def create_otp(email: str) -> str:
    """Create and store OTP for email."""
    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    
    with get_db() as db:
        # Invalidate any existing OTPs for this email
        db.query(OTPCode).filter(
            OTPCode.email == email,
            OTPCode.is_used == 0
        ).update({"is_used": 1})
        
        # Create new OTP
        otp_record = OTPCode(
            email=email,
            code=otp,
            expires_at=expires_at
        )
        db.add(otp_record)
        db.commit()
    
    return otp


def verify_otp(email: str, otp: str) -> bool:
    """Verify OTP for email."""
    with get_db() as db:
        otp_record = db.query(OTPCode).filter(
            OTPCode.email == email,
            OTPCode.code == otp,
            OTPCode.is_used == 0,
            OTPCode.expires_at > datetime.utcnow()
        ).first()
        
        if otp_record:
            otp_record.is_used = 1
            db.commit()
            return True
        return False

# =============================================================================
# USER MANAGEMENT
# =============================================================================

def get_or_create_google_user(google_user: dict) -> dict:
    """Get or create user from Google OAuth."""
    email = google_user.get("email")
    google_id = google_user.get("sub")
    name = google_user.get("name")
    picture = google_user.get("picture")
    
    with get_db() as db:
        # Try to find by google_id first
        user = db.query(User).filter(User.google_id == google_id).first()
        
        if not user:
            # Try by email
            user = db.query(User).filter(User.email == email).first()
            if user:
                user.google_id = google_id
                user.auth_provider = "google"
        
        if not user:
            # Create new user
            user = User(
                email=email,
                name=name,
                picture=picture,
                google_id=google_id,
                auth_provider="google"
            )
            db.add(user)
            db.flush()
        else:
            user.last_login = datetime.utcnow()
            user.name = name or user.name
            user.picture = picture or user.picture
        
        db.commit()
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "auth_provider": user.auth_provider
        }


def get_or_create_email_user(email: str) -> dict:
    """Get or create user from email OTP login."""
    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            # Create new user
            user = User(
                email=email,
                name=email.split('@')[0],  # Use email prefix as name
                auth_provider="email"
            )
            db.add(user)
            db.flush()
        else:
            user.last_login = datetime.utcnow()
        
        db.commit()
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "auth_provider": user.auth_provider
        }


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "auth_provider": user.auth_provider,
                "is_active": user.is_active
            }
        return None

# =============================================================================
# FASTAPI DEPENDENCIES
# =============================================================================

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Get current user (returns None if not authenticated)."""
    if not credentials:
        return None
    
    payload = verify_token(credentials.credentials)
    user_id = int(payload.get("sub"))
    
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="User account is disabled")
    
    return user


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> dict:
    """Require authentication - raises 401 if not authenticated."""
    payload = verify_token(credentials.credentials)
    user_id = int(payload.get("sub"))
    
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="User account is disabled")
    
    return user
