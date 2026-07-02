"""Authentication and authorization.

LDAP is the identity source (verifies username/password). Postgres is the
authorization source: a User row is created on first successful login and
its `role` governs permissions from then on. LDAP admin-group membership
only sets the *initial* role on first provisioning -- it is not re-checked
on every login, so role changes made in-app (or future non-LDAP accounts,
e.g. Signal guests in Phase 3) aren't silently overwritten.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db import get_db
from api.ldap_auth import authenticate as ldap_authenticate
from api.models import User

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


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def _get_or_provision_user(db: AsyncSession, identity) -> User:
    result = await db.execute(select(User).where(User.username == identity.username))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            username=identity.username,
            display_name=identity.display_name,
            email=identity.email,
            role="admin" if identity.is_admin else "member",
        )
        db.add(user)

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
    if user is None:
        raise credentials_error
    return user


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        username=current_user.username,
        display_name=current_user.display_name,
        email=current_user.email,
        role=current_user.role,
    )
