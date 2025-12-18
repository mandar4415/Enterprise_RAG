"""
User and OTP models for authentication.
Extends existing database without modifying RAG models.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum

# Import existing Base to keep all models in same metadata
from src.db import Base


class AuthProvider(enum.Enum):
    """Authentication provider types."""
    EMAIL = "email"
    GOOGLE = "google"


class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)  # Null for OAuth users
    
    # Authentication provider
    auth_provider = Column(String(50), default="email", nullable=False)
    google_id = Column(String(255), unique=True, nullable=True)  # For Google OAuth
    
    # Email verification
    is_email_verified = Column(Boolean, default=False, nullable=False)
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Profile
    profile_picture = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    otp_codes = relationship("OTPCode", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class OTPCode(Base):
    """OTP codes for email verification."""
    __tablename__ = "otp_codes"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(6), nullable=False)
    purpose = Column(String(50), nullable=False)  # 'signup', 'reset_password', 'login'
    
    # Validity
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="otp_codes")
    
    def __repr__(self):
        return f"<OTPCode {self.code} for user {self.user_id}>"
