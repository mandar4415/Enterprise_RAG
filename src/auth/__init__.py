"""
Authentication module for Enterprise RAG.
Provides both Google OAuth and Email/Password with OTP verification.
"""
from src.auth.models import User, OTPCode
from src.auth.oauth import get_google_login_url, verify_google_token, GoogleUserInfo
from src.auth.password import (
    hash_password, verify_password, generate_otp, verify_otp,
    create_access_token, decode_access_token
)
from src.auth.email import send_otp_email
from src.auth.dependencies import get_current_user, get_current_user_optional

__all__ = [
    # Models
    'User', 'OTPCode',
    # OAuth
    'get_google_login_url', 'verify_google_token', 'GoogleUserInfo',
    # Password Auth
    'hash_password', 'verify_password', 'generate_otp', 'verify_otp',
    'create_access_token', 'decode_access_token',
    # Email
    'send_otp_email',
    # Dependencies
    'get_current_user', 'get_current_user_optional'
]
