from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Document, User


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id_for(username: str) -> str:
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        return str(user.id)


async def _invite(client, owner_token: str, user_id: str, can_export: bool = False):
    return await client.post(
        "/workspace/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": user_id, "can_export": can_export},
    )


async def _accept(client, member_token: str, owner_id: str):
    return await client.post(
        f"/workspace/invitations/{owner_id}/accept", headers={"Authorization": f"Bearer {member_token}"}
    )


async def _create_document(owner_username: str) -> str:
    async with async_session() as db:
        owner = (await db.execute(select(User).where(User.username == owner_username))).scalar_one()
        document = Document(
            owner_id=owner.id, title="shared-doc.pdf", filename="shared-doc.pdf",
            mime_type="application/pdf", status="ready", ocr_text="content",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return str(document.id)


async def _setup_owner_and_member(client, prefix: str, *, can_export: bool = False):
    """Creates an owner + member, invites, and accepts. Returns
    (owner_username, owner_token, owner_id, member_username, member_token, member_id)."""
    owner_username = _unique(f"{prefix}owner")
    owner_token = await _login(client, owner_username)
    owner_id = await _user_id_for(owner_username)
    member_username = _unique(f"{prefix}member")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    await _invite(client, owner_token, member_id, can_export=can_export)
    await _accept(client, member_token, owner_id)

    return owner_username, owner_token, owner_id, member_username, member_token, member_id


async def test_owner_can_invite_a_member(client):
    owner_token = await _login(client, _unique("wsownera"))
    member_username = _unique("wsmemberb")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    response = await _invite(client, owner_token, member_id)
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["can_export"] is False


async def test_cannot_invite_yourself(client):
    owner_username = _unique("wsself")
    owner_token = await _login(client, owner_username)
    owner_id = await _user_id_for(owner_username)

    response = await _invite(client, owner_token, owner_id)
    assert response.status_code == 400


async def test_inviting_an_unknown_user_returns_404(client):
    owner_token = await _login(client, _unique("wsunknown"))
    response = await _invite(client, owner_token, str(uuid4()))
    assert response.status_code == 404


async def test_pending_invitation_does_not_grant_access(client):
    owner_username = _unique("wspendowner")
    owner_token = await _login(client, owner_username)
    member_username = _unique("wspendmember")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    await _invite(client, owner_token, member_id)

    document_id = await _create_document(owner_username)
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403


async def test_accepted_member_can_read_a_document_they_do_not_own(client):
    owner_username, _, _, _, member_token, _ = await _setup_owner_and_member(client, "wsread")

    document_id = await _create_document(owner_username)
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200


async def test_non_member_cannot_read_a_document_they_do_not_own(client):
    owner_username = _unique("wsnonmemberowner")
    await _login(client, owner_username)
    outsider_token = await _login(client, _unique("wsoutsider"))

    document_id = await _create_document(owner_username)
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert response.status_code == 403


async def test_accepted_member_sees_owners_documents_in_list_via_owner_id_param(client):
    owner_username, _, owner_id, _, member_token, _ = await _setup_owner_and_member(client, "wslist")

    document_id = await _create_document(owner_username)
    response = await client.get(
        "/documents", params={"owner_id": owner_id}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert document_id in {d["id"] for d in response.json()}


async def test_non_member_gets_403_listing_someone_elses_workspace(client):
    owner_username = _unique("wslistdenyowner")
    await _login(client, owner_username)
    owner_id = await _user_id_for(owner_username)
    outsider_token = await _login(client, _unique("wslistoutsider"))

    response = await client.get(
        "/documents", params={"owner_id": owner_id}, headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert response.status_code == 403


async def test_export_requires_can_export_flag(client):
    owner_id_holder = await _setup_owner_and_member(client, "wsexport", can_export=False)
    _, _, owner_id, _, member_token, _ = owner_id_holder

    response = await client.get(
        "/documents/export.csv", params={"owner_id": owner_id}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 403


async def test_export_succeeds_when_can_export_granted(client):
    _, _, owner_id, _, member_token, _ = await _setup_owner_and_member(client, "wsexportok", can_export=True)

    response = await client.get(
        "/documents/export.csv", params={"owner_id": owner_id}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200


async def test_declining_an_invitation_does_not_grant_access(client):
    owner_username = _unique("wsdeclineowner")
    owner_token = await _login(client, owner_username)
    owner_id = await _user_id_for(owner_username)
    member_username = _unique("wsdeclinemember")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    await _invite(client, owner_token, member_id)
    decline = await client.post(
        f"/workspace/invitations/{owner_id}/decline", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert decline.status_code == 200
    assert decline.json()["status"] == "declined"

    document_id = await _create_document(owner_username)
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403


async def test_revoking_membership_revokes_access(client):
    owner_username, owner_token, owner_id, _, member_token, member_id = await _setup_owner_and_member(
        client, "wsrevoke"
    )

    document_id = await _create_document(owner_username)
    before = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert before.status_code == 200

    revoke = await client.delete(
        f"/workspace/members/{member_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert revoke.status_code == 204

    after = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert after.status_code == 403


async def test_only_the_owner_can_revoke_a_member(client):
    _, _, _, _, _, member_id = await _setup_owner_and_member(client, "wsrevokedeny")
    outsider_token = await _login(client, _unique("wsrevokedenyoutsider"))

    # The outsider is not the owner, so from their perspective no such
    # membership exists to revoke (owner_id is scoped to current_user).
    response = await client.delete(
        f"/workspace/members/{member_id}", headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert response.status_code == 404


async def test_member_cannot_delete_owners_document(client):
    owner_username, _, _, _, member_token, _ = await _setup_owner_and_member(client, "wsdelete")

    document_id = await _create_document(owner_username)
    response = await client.delete(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403


async def test_third_invitation_is_rejected_once_two_are_active(client):
    owner_token = await _login(client, _unique("wscapowner"))

    for i in range(2):
        member_username = _unique(f"wscapmember{i}")
        await _login(client, member_username)
        member_id = await _user_id_for(member_username)
        response = await _invite(client, owner_token, member_id)
        assert response.status_code == 201

    third_username = _unique("wscapmemberthird")
    await _login(client, third_username)
    third_id = await _user_id_for(third_username)
    response = await _invite(client, owner_token, third_id)
    assert response.status_code == 409


async def test_removing_a_member_frees_a_capacity_slot(client):
    owner_token = await _login(client, _unique("wsfreeowner"))
    member_ids = []
    for i in range(2):
        member_username = _unique(f"wsfreemember{i}")
        await _login(client, member_username)
        member_id = await _user_id_for(member_username)
        member_ids.append(member_id)
        assert (await _invite(client, owner_token, member_id)).status_code == 201

    revoke = await client.delete(
        f"/workspace/members/{member_ids[0]}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert revoke.status_code == 204

    third_username = _unique("wsfreememberthird")
    await _login(client, third_username)
    third_id = await _user_id_for(third_username)
    response = await _invite(client, owner_token, third_id)
    assert response.status_code == 201


async def test_invitations_list_shows_pending_invites_to_me(client):
    owner_username = _unique("wsinvowner")
    owner_token = await _login(client, owner_username)
    member_username = _unique("wsinvmember")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    await _invite(client, owner_token, member_id)

    response = await client.get("/workspace/invitations", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["owner_username"] == owner_username
    assert body[0]["member_username"] == member_username


async def test_shared_with_me_lists_only_accepted(client):
    _, _, owner_id, _, member_token, _ = await _setup_owner_and_member(client, "wsswm")

    response = await client.get("/workspace/shared-with-me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["owner_id"] == owner_id
    assert body[0]["status"] == "accepted"


async def test_admin_can_read_any_document_without_a_workspace_share(client):
    owner_username = _unique("wsadminowner")
    await _login(client, owner_username)
    admin_token = await _login(client, _unique("wsadmin"), is_admin=True)

    document_id = await _create_document(owner_username)
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
