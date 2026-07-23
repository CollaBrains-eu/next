"""Authentication and authorization.

LDAP is the identity source (verifies username/password). Postgres is the
authorization source: a User row is created on first successful login and
its `role` governs permissions from then on. LDAP admin-group membership
only sets the *initial* role on first provisioning -- it is not re-checked
on every login, so role changes made in-app (or future non-LDAP accounts,
e.g. Signal guests in Phase 3) aren't silently overwritten.

`get_effective_user` (ADR 0006) additionally lets the trusted `signal-bot`
service account act on behalf of a specific user, identified by a linked
phone number -- see docs/adr/0006-phase3b-signal-identity-linking.md.
"""
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db import get_db
from api.ldap_auth import authenticate as ldap_authenticate
from api.invitation_service import get_valid_invitation
from api.models import Organization, PendingUserPhoneNumber, User
from api.registration_service import (
    check_registration_rate_limit,
    complete_registration,
    create_pending_registration,
    get_pending_registration_for_username,
    refresh_pending_registration,
    send_verification_email,
    username_or_email_taken,
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    username: str
    display_name: str
    email: str | None
    role: str
    phone_number: str | None
    phone_prompt_dismissed: bool


def _user_out(user: User) -> UserOut:
    return UserOut(
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
        phone_number=user.phone_number,
        phone_prompt_dismissed=user.phone_prompt_dismissed,
    )


def validate_phone_number(phone: str) -> str:
    """Shared E.164 check -- used by both self-service linking and
    admin phone-at-creation, so the rule exists in exactly one place."""
    phone = phone.strip()
    if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="phone_number must be in E.164 format, e.g. +491511234567"
        )
    return phone


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def _get_or_provision_user(db: AsyncSession, identity) -> User:
    result = await db.execute(select(User).where(User.username == identity.username))
    user = result.scalar_one_or_none()

    if user is None:
        pending_result = await db.execute(
            select(PendingUserPhoneNumber).where(PendingUserPhoneNumber.username == identity.username)
        )
        pending = pending_result.scalar_one_or_none()

        user = User(
            username=identity.username,
            display_name=identity.display_name,
            email=identity.email,
            role="admin" if identity.is_admin else "member",
            phone_number=pending.phone_number if pending else None,
        )
        db.add(user)
        if pending is not None:
            await db.delete(pending)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    identity = ldap_authenticate(form_data.username, form_data.password)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    user = await _get_or_provision_user(db, identity)
    return Token(access_token=create_access_token(user.username, user.role))


USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    username: str
    display_name: str
    email: str
    password: str
    organization_name: str | None = None
    invitation_token: str | None = None


class RegisterResponse(BaseModel):
    email_sent: bool


def _validate_registration(body: RegisterRequest) -> tuple[str, str]:
    username = body.username.strip().lower()
    if not USERNAME_PATTERN.match(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username must be 3-32 characters: lowercase letters, digits, dot, dash, or underscore",
        )
    email = body.email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address")
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters"
        )
    return username, email


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    """Self-service signup (Priority 3, ADR 0074): no admin involved, no
    LDAP entry or Postgres User row created yet -- just a pending
    registration + a verification email. The account is only provisioned
    once /auth/verify-email confirms the address is reachable -- either
    into a brand-new Organization (registrant becomes its owner), or, if
    `invitation_token` names a still-valid invitation addressed to this
    exact email, into the inviting org instead."""
    username, email = _validate_registration(body)
    if not await check_registration_rate_limit(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts for this email, try again later",
        )

    display_name = body.display_name.strip() or username
    organization_name = (body.organization_name or f"{display_name}'s organization").strip()

    if body.invitation_token is not None:
        invitation = await get_valid_invitation(db, token=body.invitation_token)
        if invitation is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid or has expired"
            )
        if invitation.email.lower() != email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation was sent to a different email address",
            )
        organization = await db.get(Organization, invitation.organization_id)
        organization_name = organization.name if organization is not None else organization_name

    # Checked first, before the conflict lookup below: a still-valid pending
    # registration for this exact username is *this same signup* being
    # resent, not a conflict with someone else -- username_or_email_taken
    # would otherwise treat it as "username_taken" and 409 a legitimate retry.
    existing_pending = await get_pending_registration_for_username(db, username=username)
    if existing_pending is not None:
        registration = await refresh_pending_registration(
            db,
            record=existing_pending,
            display_name=display_name,
            email=email,
            password=body.password,
            organization_name=organization_name,
            invitation_token=body.invitation_token,
        )
    else:
        conflict = await username_or_email_taken(db, username=username, email=email)
        if conflict == "username_taken":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This username is already taken")
        if conflict == "email_taken":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists"
            )

        registration = await create_pending_registration(
            db,
            username=username,
            display_name=display_name,
            email=email,
            password=body.password,
            organization_name=organization_name,
            invitation_token=body.invitation_token,
        )

    email_sent = await send_verification_email(registration=registration)
    return RegisterResponse(email_sent=email_sent)


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/verify-email", response_model=Token)
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)) -> Token:
    """Completes a self-service signup and logs the new user straight in,
    same as /auth/token -- clicking the emailed link should land in the
    app already authenticated, not back at a login form."""
    user = await complete_registration(db, token=body.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link is invalid or has expired"
        )
    return Token(access_token=create_access_token(user.username, user.role))


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if username is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error
    return user


async def get_effective_user(
    current_user: User = Depends(get_current_user),
    on_behalf_of_phone: str | None = Header(None, alias="X-On-Behalf-Of-Phone"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the user an action should be attributed to.

    For every normal caller this is just `current_user`. The
    `X-On-Behalf-Of-Phone` header is only honored for the `signal-bot`
    service account (ADR 0006) -- any other caller sending it is ignored
    outright, so a regular LDAP-authenticated request can never impersonate
    another user by guessing at the header.
    """
    if current_user.role != "service" or not on_behalf_of_phone:
        return current_user

    result = await db.execute(select(User).where(User.phone_number == on_behalf_of_phone))
    linked_user = result.scalar_one_or_none()
    if linked_user is None or not linked_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This phone number is not linked to a CollaBrains account",
        )
    return linked_user


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(current_user)


class PhoneNumberUpdate(BaseModel):
    phone_number: str


@router.put("/me/phone", response_model=UserOut)
async def link_phone_number(
    update: PhoneNumberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    current_user.phone_number = validate_phone_number(update.phone_number)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This phone number is already linked to another account")

    await db.refresh(current_user)
    return _user_out(current_user)


@router.patch("/me/dismiss-phone-prompt", response_model=UserOut)
async def dismiss_phone_prompt(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    current_user.phone_prompt_dismissed = True
    await db.commit()
    await db.refresh(current_user)
    return _user_out(current_user)
