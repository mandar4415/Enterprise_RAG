"""
Email service for sending OTP codes via SMTP.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from src.auth.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, SMTP_FROM_NAME, OTP_EXPIRY_MINUTES
)


def is_smtp_configured() -> bool:
    """Check if SMTP is properly configured."""
    return bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD and SMTP_FROM_EMAIL)


def send_otp_email(to_email: str, otp_code: str, purpose: str = "verification") -> tuple[bool, str]:
    """
    Send OTP code via email.
    
    Args:
        to_email: Recipient email address
        otp_code: OTP code to send
        purpose: Purpose of OTP ('signup', 'reset_password', 'login')
    
    Returns:
        (success, error_message)
    """
    if not is_smtp_configured():
        return False, "SMTP not configured. Please set SMTP environment variables."
    
    # Email content based on purpose
    subjects = {
        "signup": "Verify Your Email - Enterprise RAG",
        "reset_password": "Reset Your Password - Enterprise RAG",
        "login": "Login Verification - Enterprise RAG"
    }
    
    subject = subjects.get(purpose, "Verification Code - Enterprise RAG")
    
    # Create HTML email
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 24px; }}
            .content {{ padding: 40px 30px; text-align: center; }}
            .otp-code {{ font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #333; background: #f8f9fa; padding: 20px 30px; border-radius: 8px; display: inline-block; margin: 20px 0; border: 2px dashed #667eea; }}
            .message {{ color: #666; font-size: 14px; line-height: 1.6; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #999; font-size: 12px; }}
            .warning {{ color: #e74c3c; font-size: 12px; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Enterprise RAG</h1>
            </div>
            <div class="content">
                <p class="message">Your verification code is:</p>
                <div class="otp-code">{otp_code}</div>
                <p class="message">
                    This code will expire in <strong>{OTP_EXPIRY_MINUTES} minutes</strong>.<br>
                    If you didn't request this code, please ignore this email.
                </p>
                <p class="warning">⚠️ Never share this code with anyone.</p>
            </div>
            <div class="footer">
                <p>© 2024 Enterprise RAG. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text fallback
    text_content = f"""
    Enterprise RAG - Verification Code
    
    Your verification code is: {otp_code}
    
    This code will expire in {OTP_EXPIRY_MINUTES} minutes.
    
    If you didn't request this code, please ignore this email.
    Never share this code with anyone.
    """
    
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        
        # Attach parts
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())
        
        return True, ""
        
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed. Check username/password."
    except smtplib.SMTPException as e:
        return False, f"Failed to send email: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
