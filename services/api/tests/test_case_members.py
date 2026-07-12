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


async def test_owner_can_add_a_member(client):
    owner_token = await _login(client, _unique("caseownera"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberb")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    response = await client.post(
        f"/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": member_id, "role": "aannemer"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "aannemer"


async def test_non_owner_cannot_add_a_member(client):
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


async def test_member_can_read_a_case_they_do_not_own(client):
    owner_token = await _login(client, _unique("caseownere"))
    case_id = await _create_case(client, owner_token, "Renovation project")

    member_username = _unique("casememberf")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": member_id}
    )

    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renovation project"


async def test_non_member_cannot_read_a_case_they_do_not_own(client):
    owner_token = await _login(client, _unique("caseownerg"))
    case_id = await _create_case(client, owner_token)

    outsider_token = await _login(client, _unique("caseoutsiderh"))
    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert response.status_code == 403


async def test_member_appears_in_their_own_case_list(client):
    owner_token = await _login(client, _unique("caseowneri"))
    case_id = await _create_case(client, owner_token, "Shared case")

    member_username = _unique("casememberj")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": member_id}
    )

    response = await client.get("/cases", headers={"Authorization": f"Bearer {member_token}"})
    names = {c["name"] for c in response.json()}
    assert "Shared case" in names
    ids = {c["id"] for c in response.json()}
    assert case_id in ids


async def test_removing_membership_revokes_access(client):
    owner_token = await _login(client, _unique("caseownerk"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberl")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": member_id}
    )
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
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": member_id}
    )

    intruder_token = await _login(client, _unique("caseintruderp"))
    response = await client.delete(
        f"/cases/{case_id}/members/{member_id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert response.status_code == 403


async def test_adding_the_same_member_twice_updates_role_instead_of_erroring(client):
    owner_token = await _login(client, _unique("caseownerq"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberr")
    await _login(client, member_username)
    member_id = await _user_id_for(member_username)

    first = await client.post(
        f"/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": member_id, "role": "viewer"},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": member_id, "role": "aannemer"},
    )
    assert second.status_code == 201
    assert second.json()["role"] == "aannemer"

    listing = await client.get(f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"})
    assert len(listing.json()) == 1


async def test_member_can_view_member_list_but_not_add_members(client):
    owner_token = await _login(client, _unique("caseowners"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casembert")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": member_id}
    )

    listing = await client.get(f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {member_token}"})
    assert listing.status_code == 200

    other_username = _unique("caseotheru")
    await _login(client, other_username)
    other_id = await _user_id_for(other_username)
    add_attempt = await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {member_token}"}, json={"user_id": other_id}
    )
    assert add_attempt.status_code == 403


async def test_delete_case_stays_owner_only_even_for_members(client):
    owner_token = await _login(client, _unique("caseownerv"))
    case_id = await _create_case(client, owner_token)

    member_username = _unique("casememberw")
    member_token = await _login(client, member_username)
    member_id = await _user_id_for(member_username)
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": member_id}
    )

    response = await client.delete(f"/cases/{case_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403
