from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.services.email_service import email_service
from app.utils.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class SignupRequest(BaseModel):
    """Request model for user signup"""
    email: EmailStr
    password: str


class SigninRequest(BaseModel):
    """Request model for user signin"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response model for authentication tokens"""
    access_token: str
    token_type: str = "bearer"
    user: dict


class ForgotPasswordRequest(BaseModel):
    """Request model for forgot password"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request model for password reset"""
    token: str
    new_password: str


@router.post("/signup", response_model=TokenResponse)
async def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user

    Creates a new user account with email and password.
    Returns an access token for immediate login.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Validate password length
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    # Hash password
    hashed_password = get_password_hash(request.password)

    # Create new user
    new_user = User(
        email=request.email,
        hashed_password=hashed_password,
        is_active=True,
        is_verified=False,
        preferences={}
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )

    # Create access token (sub must be string for JWT)
    access_token = create_access_token(data={"sub": str(new_user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": new_user.to_dict()
    }


@router.post("/signin", response_model=TokenResponse)
async def signin(
    request: SigninRequest,
    db: Session = Depends(get_db)
):
    """
    Sign in an existing user

    Authenticates user with email and password.
    Returns an access token on successful authentication.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Create access token (sub must be string for JWT)
    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information

    Returns the profile of the currently authenticated user.
    Requires a valid JWT token in the Authorization header.
    """
    return current_user.to_dict()


@router.post("/verify-token")
async def verify_token(
    current_user: User = Depends(get_current_user)
):
    """
    Verify if a token is valid

    Checks if the provided JWT token is valid and returns user info.
    """
    return {
        "valid": True,
        "user": current_user.to_dict()
    }


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset email

    Sends an email with a password reset link to the user's email address.
    The reset token expires after 1 hour.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    # Check if user exists - return error if not found
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address"
        )

    try:
        # Generate secure reset token
        reset_token = PasswordResetToken.generate_token()
        expiry = PasswordResetToken.calculate_expiry(hours=1)

        # Save token to database
        token_record = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            expires_at=expiry,
            used=False
        )
        db.add(token_record)
        db.commit()

        # Send password reset email
        email_sent = email_service.send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token,
            user_name=user.email.split('@')[0]  # Use email prefix as name
        )

        if not email_sent:
            # Log error but don't reveal to user
            print(f"[Auth] Failed to send password reset email to {user.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send password reset email. Please try again later."
            )

        return {
            "success": True,
            "message": "Password reset link has been sent to your email. Please check your inbox."
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[Auth] Error in forgot password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request. Please try again later."
        )


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using a reset token

    Validates the reset token and updates the user's password.
    The token is marked as used after successful password reset.
    """
    try:
        # Find token in database
        token_record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == request.token
        ).first()

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        # Check if token is valid (not used and not expired)
        if not token_record.is_valid():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        # Find user first
        user = db.query(User).filter(User.id == token_record.user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Validate new password length BEFORE hashing
        if len(request.new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )

        if len(request.new_password) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is too long. Please use a password with 72 characters or less."
            )

        # Hash new password
        new_hashed_password = get_password_hash(request.new_password)
        user.hashed_password = new_hashed_password

        # Mark token as used
        token_record.used = True

        db.commit()

        return {
            "success": True,
            "message": "Password has been reset successfully. You can now sign in with your new password."
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[Auth] Error in reset password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting password: {str(e)}"
        )
