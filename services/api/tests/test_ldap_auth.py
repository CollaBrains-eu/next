from unittest.mock import MagicMock, patch

import pytest

from api.ldap_auth import LdapAdminError, register_user


def _mock_connection(*, add_result: bool, description: str) -> MagicMock:
    conn = MagicMock()
    conn.bind.return_value = True
    conn.search.return_value = True
    conn.entries = []
    conn.add.return_value = add_result
    conn.result = {"description": description}
    return conn


def test_register_user_raises_a_human_readable_already_exists_message():
    """Regression test: ldap3's raw result description for a duplicate
    entry is "entryAlreadyExists" (no space) -- every caller of
    register_user/create_user matches the phrase "already exists" (with a
    space) to decide whether to recover gracefully. A prior version of
    _add_ldap_person passed that raw description straight through,
    silently breaking the match and turning a normal
    already-registered-retry into an unhandled 500 on /auth/verify-email
    (production incident, Sentry COLLABRAINS-API-7)."""
    conn = _mock_connection(add_result=False, description="entryAlreadyExists")
    with patch("api.ldap_auth.Connection", return_value=conn), patch("api.ldap_auth.Server"):
        with pytest.raises(LdapAdminError) as exc_info:
            register_user(username="dupeuser", display_name="Dupe User", email="dupe@example.com", password_hash="x")

    assert "already exists" in str(exc_info.value).lower()


def test_register_user_preserves_other_ldap_failure_descriptions():
    conn = _mock_connection(add_result=False, description="unwillingToPerform")
    with patch("api.ldap_auth.Connection", return_value=conn), patch("api.ldap_auth.Server"):
        with pytest.raises(LdapAdminError) as exc_info:
            register_user(username="baduser", display_name="Bad User", email="bad@example.com", password_hash="x")

    assert str(exc_info.value) == "unwillingToPerform"
