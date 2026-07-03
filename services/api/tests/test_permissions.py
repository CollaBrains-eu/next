from api.permissions import ROLE_PERMISSIONS, has_permission


def test_member_and_admin_grant_the_same_permissions_for_existing_tools():
    # deliberate: none of the five existing tools are role-gated today, see ADR 0023
    assert ROLE_PERMISSIONS["member"] == ROLE_PERMISSIONS["admin"]


def test_service_role_has_no_permissions_by_default():
    assert ROLE_PERMISSIONS["service"] == frozenset()


def test_has_permission_true_when_role_grants_all_required():
    assert has_permission("member", ["documents.read"]) is True
    assert has_permission("member", ["documents.read", "tasks.write"]) is True


def test_has_permission_false_when_role_is_missing_any_required_permission():
    assert has_permission("service", ["documents.read"]) is False
    assert has_permission("member", ["documents.read", "not_a_real_permission"]) is False


def test_has_permission_true_for_empty_requirements():
    assert has_permission("service", []) is True


def test_has_permission_false_for_unknown_role():
    assert has_permission("not-a-real-role", ["documents.read"]) is False
