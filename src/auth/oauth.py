"""
Google OAuth authentication.
"""
from typing import Optional
from pydantic import BaseModel
import httpx

from src.auth.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
)

# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleUserInfo(BaseModel):
    """Google user information from OAuth."""
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    verified_email: bool = False


def get_google_login_url(state: Optional[str] = None) -> str:
    """
    Generate Google OAuth login URL.
    
    Args:
        state: Optional state parameter for CSRF protection
    
    Returns:
        Google OAuth authorization URL
    """
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account"
    }
    
    if state:
        params["state"] = state
    
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query_string}"


async def verify_google_token(code: str) -> Optional[GoogleUserInfo]:
    """
    Exchange authorization code for user info.
    
    Args:
        code: Authorization code from Google callback
    
    Returns:
        GoogleUserInfo if successful, None otherwise
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Exchange code for access token
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI
            }
        )
        
        if token_response.status_code != 200:
            print(f"Google token exchange failed: {token_response.text}")
            return None
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            return None
        
        # Get user info
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if userinfo_response.status_code != 200:
            print(f"Google userinfo failed: {userinfo_response.text}")
            return None
        
        user_data = userinfo_response.json()
        
        return GoogleUserInfo(
            id=user_data.get("id", ""),
            email=user_data.get("email", ""),
            name=user_data.get("name", ""),
            picture=user_data.get("picture"),
            verified_email=user_data.get("verified_email", False)
        )


def is_google_oauth_configured() -> bool:
    """Check if Google OAuth is properly configured."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
