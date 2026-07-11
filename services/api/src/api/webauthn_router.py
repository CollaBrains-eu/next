"""Passkey (WebAuthn) login (Phase 25) -- ported from CollaBrains v2, which
used `webauthn==2.8.0` for the same purpose (docs/superpowers/plans/
2026-07-11-webauthn-login.md).

Additive alongside `/auth/token` (LDAP password login, auth.py): a user
registers a passkey while already logged in via Settings, and can from then
on use either method interchangeably -- unlike v2's optional
`passkey_required` flag, nothing here can ever lock a user out of password
login. That's a deliberate scope cut for this port: v2's admin-enforced
"passkey required" lockout touches how a *different* user's account can log
in, which is exactly the class of live-credential-affecting change this
project holds back pending specifically-named authorization (see PR history
around admin_router.py / ldap_auth.py).

Challenges are cached in Redis (5 min TTL), not the in-memory dict v2 used --
v2's own code flagged that as a known shortcut that breaks under more than
one worker process. Credential lookup on login is an indexed query on
`credential_id` (unique), not v2's documented linear scan over every user's
single stored credential -- and a user can register more than one passkey
here, since credentials are their own table rather than one JSONB column.
"""
import json
import logging
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from api.auth import create_access_token, get_current_user
from api.config import settings
from api.db import get_db
from api.models import User, WebauthnCredential

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/webauthn", tags=["webauthn"])

_redis = Redis.from_url(settings.redis_url)
_CHALLENGE_TTL_SECONDS = 300


class CredentialOut(BaseModel):
    id: UUID
    label: str | None
    created_at: str
    last_used_at: str | None

    class Config:
        from_attributes = True


def _credential_out(credential: WebauthnCredential) -> CredentialOut:
    return CredentialOut(
        id=credential.id,
        label=credential.label,
        created_at=credential.created_at.isoformat(),
        last_used_at=credential.last_used_at.isoformat() if credential.last_used_at else None,
    )


@router.get("/credentials", response_model=list[CredentialOut])
async def list_credentials(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CredentialOut]:
    result = await db.execute(
        select(WebauthnCredential)
        .where(WebauthnCredential.user_id == current_user.id)
        .order_by(WebauthnCredential.created_at.desc())
    )
    return [_credential_out(row) for row in result.scalars().all()]


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    credential = await db.get(WebauthnCredential, credential_id)
    if credential is None or credential.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passkey not found")
    await db.delete(credential)
    await db.commit()


@router.post("/register/begin")
async def register_begin(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    existing = await db.execute(
        select(WebauthnCredential.credential_id).where(WebauthnCredential.user_id == current_user.id)
    )
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=str(current_user.id).encode(),
        user_name=current_user.username,
        user_display_name=current_user.display_name,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred_id)) for cred_id, in existing
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED
        ),
    )
    await _redis.set(
        f"webauthn:reg:{current_user.id}", bytes_to_base64url(options.challenge), ex=_CHALLENGE_TTL_SECONDS
    )
    return json.loads(options_to_json(options))


class RegisterCompleteRequest(BaseModel):
    credential: dict
    label: str | None = None


@router.post("/register/complete", response_model=CredentialOut)
async def register_complete(
    body: RegisterCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialOut:
    challenge_b64 = await _redis.getdel(f"webauthn:reg:{current_user.id}")
    if challenge_b64 is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration challenge expired, try again")

    try:
        verification = verify_registration_response(
            credential=body.credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Passkey registration failed: {exc}") from exc

    credential = WebauthnCredential(
        user_id=current_user.id,
        credential_id=bytes_to_base64url(verification.credential_id),
        public_key=bytes_to_base64url(verification.credential_public_key),
        sign_count=verification.sign_count,
        label=body.label,
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return _credential_out(credential)


@router.post("/login/begin")
async def login_begin() -> dict:
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id, user_verification=UserVerificationRequirement.REQUIRED
    )
    session_key = secrets.token_urlsafe(16)
    await _redis.set(
        f"webauthn:login:{session_key}", bytes_to_base64url(options.challenge), ex=_CHALLENGE_TTL_SECONDS
    )
    body = json.loads(options_to_json(options))
    body["session_key"] = session_key
    return body


class LoginCompleteRequest(BaseModel):
    session_key: str
    credential: dict


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login/complete", response_model=Token)
async def login_complete(body: LoginCompleteRequest, db: AsyncSession = Depends(get_db)) -> Token:
    challenge_b64 = await _redis.getdel(f"webauthn:login:{body.session_key}")
    if challenge_b64 is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login challenge expired, try again")

    raw_id = body.credential.get("rawId") or body.credential.get("id")
    if not raw_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed passkey credential")
    credential_id = bytes_to_base64url(base64url_to_bytes(raw_id))

    result = await db.execute(select(WebauthnCredential).where(WebauthnCredential.credential_id == credential_id))
    stored = result.scalar_one_or_none()
    if stored is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passkey not recognized")

    try:
        verification = verify_authentication_response(
            credential=body.credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=base64url_to_bytes(stored.public_key),
            credential_current_sign_count=stored.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Passkey verification failed: {exc}") from exc

    user = await db.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passkey not recognized")

    from datetime import datetime, timezone

    stored.sign_count = verification.new_sign_count
    stored.last_used_at = datetime.now(timezone.utc)
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return Token(access_token=create_access_token(user.username, user.role))
