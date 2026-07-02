from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_and_me():
    login = client.post("/auth/token", data={"username": "dev", "password": "dev"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"username": "dev"}


def test_login_bad_credentials():
    response = client.post("/auth/token", data={"username": "dev", "password": "wrong"})
    assert response.status_code == 401
