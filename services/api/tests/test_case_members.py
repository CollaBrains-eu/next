from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import User


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _create_case(client, token: str, name: str = "Owner's case") -> str:
    response = await client.post("/cases", headers={"Authorization": f"Bearer {token}"}, json={"name": name})
    return response.json()["id"]


async def _user_id_for(username: str) -> str:
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        return str(user.id)


async def _invite(client, owner_token: str, case_id: str, user_id: str, role: str = "member"):
    return await client.post(
        f"/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": user_id, "role": role},
    )


async def _accept(client, member_token: str, case_id: str, user_id: str):
    return await client.post(
        f"/cases/{case_id}/members/{user_id}/accept", headers={"Authorization": f"Bearer {member_token}"}
    )


async def test_owner_can_invite_a_member(client):
    owner_token = await _login(client, _unique("caseownera"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberb")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    response = await _invite(client, owner_token, case_id, member_id, role="worker")
    assert response.status_code == 201
    assert response.json()["role"] == "worker"
    assert response.json()["status"] == "pending"


async def test_invite_rejects_a_role_outside_the_fixed_set(client):
    owner_token = await _login(client, _unique("caseownerrole"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberrole")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    response = await client.post(
        f"/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": member_id, "role": "aannemer"},
    )
    assert response.status_code == 422


async def test_non_owner_cannot_invite_a_member(client):
    owner_token = await _login(client, _unique("caseownerc"))
    case_id = await _create_case(client, owner_token)

    intruder_username = _unique("caseintruderd")
    intruder_token = await _login(client, intruder_username)
    intruder_id = await _user_id_for(intruder_username)

    response = await client.post(
        f"/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {intruder_token}"},
        json={"user_id": intruder_id},
    )
    assert response.status_code == 403


async def test_pending_invitation_does_not_grant_access(client):
    owner_token = await _login(client, _unique("caseownerpending"))
    case_id = await _create_case(client, owner_token, "Renovation project")

    member_username = _unique("casememberpending")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)

    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403


async def test_accepted_member_can_read_a_case_they_do_not_own(client):
    owner_token = await _login(client, _unique("caseownere"))
    case_id = await _create_case(client, owner_token, "Renovation project")

    member_username = _unique("casememberf")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)
    accept_response = await _accept(client, member_token, case_id, member_id)
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renovation project"


async def test_only_the_invited_user_can_accept_their_invitation(client):
    owner_token = await _login(client, _unique("caseownerforbidacc"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberforbidacc")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)

    response = await client.post(
        f"/cases/{case_id}/members/{member_id}/accept", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 403


async def test_declining_an_invitation_does_not_grant_access(client):
    owner_token = await _login(client, _unique("caseownerdecline"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberdecline")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)

    decline_response = await client.post(
        f"/cases/{case_id}/members/{member_id}/decline", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert decline_response.status_code == 200
    assert decline_response.json()["status"] == "declined"

    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403


async def test_accepting_an_already_accepted_invitation_returns_404(client):
    owner_token = await _login(client, _unique("caseownerdoubleaccept"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberdoubleaccept")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)
    await _accept(client, member_token, case_id, member_id)

    second_accept = await _accept(client, member_token, case_id, member_id)
    assert second_accept.status_code == 404


async def test_non_member_cannot_read_a_case_they_do_not_own(client):
    owner_token = await _login(client, _unique("caseownerg"))
    case_id = await _create_case(client, owner_token)

    outsider_token = await _login(client, _unique("caseoutsiderh"))
    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert response.status_code == 403


async def test_accepted_member_appears_in_their_own_case_list_pending_does_not(client):
    owner_token = await _login(client, _unique("caseowneri"))
    case_id = await _create_case(client, owner_token, "Shared case")

    member_username = _unique("casememberj")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)

    before_accept = await client.get("/cases", headers={"Authorization": f"Bearer {member_token}"})
    assert case_id not in {c["id"] for c in before_accept.json()}

    await _accept(client, member_token, case_id, member_id)
    after_accept = await client.get("/cases", headers={"Authorization": f"Bearer {member_token}"})
    ids = {c["id"] for c in after_accept.json()}
    assert case_id in ids


async def test_pending_invitation_appears_in_invitations_list(client):
    owner_token = await _login(client, _unique("caseownerinvlist"))
    case_id = await _create_case(client, owner_token, "Invited case")

    member_username = _unique("casememberinvlist")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id, role="worker")

    response = await client.get("/cases/invitations", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    invitations = response.json()
    assert len(invitations) == 1
    assert invitations[0]["case_id"] == case_id
    assert invitations[0]["role"] == "worker"
    assert invitations[0]["status"] == "pending"

    await _accept(client, member_token, case_id, member_id)
    after_accept = await client.get("/cases/invitations", headers={"Authorization": f"Bearer {member_token}"})
    assert after_accept.json() == []


async def test_removing_membership_revokes_access(client):
    owner_token = await _login(client, _unique("caseownerk"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberl")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)
    await _accept(client, member_token, case_id, member_id)
    assert (await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})).status_code == 200

    remove_response = await client.delete(
        f"/cases/{case_id}/members/{member_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert remove_response.status_code == 204

    after = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert after.status_code == 403


async def test_non_owner_cannot_remove_a_member(client):
    owner_token = await _login(client, _unique("caseownerm"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casemembern")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)

    intruder_token = await _login(client, _unique("caseintruderp"))
    response = await client.delete(
        f"/cases/{case_id}/members/{member_id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert response.status_code == 403


async def test_inviting_the_same_user_twice_resets_to_pending_with_new_role(client):
    owner_token = await _login(client, _unique("caseownerq"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberr")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    first = await _invite(client, owner_token, case_id, member_id, role="member")
    assert first.status_code == 201
    await _accept(client, member_token, case_id, member_id)

    second = await _invite(client, owner_token, case_id, member_id, role="worker")
    assert second.status_code == 201
    assert second.json()["role"] == "worker"
    assert second.json()["status"] == "pending"

    listing = await client.get(f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"})
    assert len(listing.json()) == 1


async def test_pending_member_cannot_view_member_list_or_add_members(client):
    owner_token = await _login(client, _unique("caseowners"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casembert")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)

    listing = await client.get(f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {member_token}"})
    assert listing.status_code == 403

    other_username = _unique("caseotheru")
    await _login(client, other_username)
    other_id = await _user_id_for(other_username)
    add_attempt = await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {member_token}"}, json={"user_id": other_id}
    )
    assert add_attempt.status_code == 403


async def test_accepted_member_can_view_member_list_but_not_add_members(client):
    owner_token = await _login(client, _unique("caseownersacc"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casembertacc")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)
    await _accept(client, member_token, case_id, member_id)

    listing = await client.get(f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {member_token}"})
    assert listing.status_code == 200

    other_username = _unique("caseotherv")
    await _login(client, other_username)
    other_id = await _user_id_for(other_username)
    add_attempt = await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {member_token}"}, json={"user_id": other_id}
    )
    assert add_attempt.status_code == 403


async def test_delete_case_stays_owner_only_even_for_accepted_members(client):
    owner_token = await _login(client, _unique("caseownerv"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberw")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)
    await _accept(client, member_token, case_id, member_id)

    response = await client.delete(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403


async def test_case_member_responses_include_case_name_and_user_display_name(client):
    owner_token = await _login(client, _unique("caseownerx"))
    case_id = await _create_case(client, owner_token, name="Enriched matter")

    member_username = _unique("casememberx")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    invite_response = await _invite(client, owner_token, case_id, member_id)
    body = invite_response.json()
    assert body["case_name"] == "Enriched matter"
    assert body["username"] == member_username
    assert body["user_display_name"] == member_username

    listing = await client.get(f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"})
    listed = listing.json()[0]
    assert listed["case_name"] == "Enriched matter"
    assert listed["username"] == member_username


async def test_my_invitations_are_enriched_too(client):
    owner_token = await _login(client, _unique("caseownery"))
    case_id = await _create_case(client, owner_token, name="Invited-to matter")

    member_username = _unique("casembertoy")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)

    invitations = await client.get("/cases/invitations", headers={"Authorization": f"Bearer {member_token}"})
    matching = [i for i in invitations.json() if i["case_id"] == case_id]
    assert len(matching) == 1
    assert matching[0]["case_name"] == "Invited-to matter"


async def test_case_dashboard_is_owner_true_for_owner_false_for_accepted_member(client):
    owner_token = await _login(client, _unique("caseownerz"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberz")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await _invite(client, owner_token, case_id, member_id)
    await _accept(client, member_token, case_id, member_id)

    owner_view = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert owner_view.json()["is_owner"] is True

    member_view = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert member_view.json()["is_owner"] is False
