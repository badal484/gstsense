"""Integration tests for the authentication endpoints."""

import pytest
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/auth/me"

VALID_PAYLOAD = {
    "full_name": "Priya Nair",
    "email": "priya@example.com",
    "password": "SecurePass1",
    "gstin": "29ABCDE1234F1Z5",
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def test_register_success(client: AsyncClient) -> None:
    resp = await client.post(REGISTER_URL, json=VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]
    assert data["tokens"]["token_type"] == "bearer"
    assert data["user"]["user"]["email"] == VALID_PAYLOAD["email"]
    assert data["user"]["organization"]["gstin"] == VALID_PAYLOAD["gstin"]
    assert data["user"]["organization"]["plan"] == "free"
    assert data["user"]["organization"]["state_code"] == "29"


async def test_register_duplicate_email(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=VALID_PAYLOAD)
    # Second registration with same email
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "gstin": "27XYZAB5678C1Z3"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONF_001"


async def test_register_duplicate_gstin(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=VALID_PAYLOAD)
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "email": "other@example.com"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONF_002"


async def test_register_invalid_gstin_format(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "gstin": "INVALID123"},
    )
    assert resp.status_code == 422


async def test_register_weak_password_no_uppercase(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "password": "weakpass1"},
    )
    assert resp.status_code == 422


async def test_register_weak_password_no_digit(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "password": "WeakPassword"},
    )
    assert resp.status_code == 422


async def test_register_weak_password_too_short(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "password": "Ab1"},
    )
    assert resp.status_code == 422


async def test_register_email_normalized_to_lowercase(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "email": "PRIYA@EXAMPLE.COM"},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["user"]["user"]["email"] == "priya@example.com"


async def test_register_gstin_normalized_to_uppercase(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER_URL,
        json={**VALID_PAYLOAD, "gstin": "29abcde1234f1z5"},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["user"]["organization"]["gstin"] == "29ABCDE1234F1Z5"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def test_login_success(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=VALID_PAYLOAD)
    resp = await client.post(
        LOGIN_URL,
        json={"email": VALID_PAYLOAD["email"], "password": VALID_PAYLOAD["password"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "access_token" in body["data"]["tokens"]


async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=VALID_PAYLOAD)
    resp = await client.post(
        LOGIN_URL,
        json={"email": VALID_PAYLOAD["email"], "password": "WrongPass1"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_001"


async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        LOGIN_URL,
        json={"email": "nobody@example.com", "password": "Whatever1"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_001"


async def test_account_lockout_after_five_failures(client: AsyncClient) -> None:
    """Five wrong passwords → account locked → sixth attempt returns AUTH_004."""
    await client.post(REGISTER_URL, json=VALID_PAYLOAD)

    for _ in range(5):
        resp = await client.post(
            LOGIN_URL,
            json={"email": VALID_PAYLOAD["email"], "password": "WrongPass1"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTH_001"

    # Account is now locked — any attempt (right or wrong) returns AUTH_004
    resp = await client.post(
        LOGIN_URL,
        json={"email": VALID_PAYLOAD["email"], "password": "WrongPass1"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_004"


async def test_correct_password_still_locked(client: AsyncClient) -> None:
    """Even the correct password is rejected while the account is locked."""
    await client.post(REGISTER_URL, json=VALID_PAYLOAD)

    for _ in range(5):
        await client.post(
            LOGIN_URL,
            json={"email": VALID_PAYLOAD["email"], "password": "WrongPass1"},
        )

    resp = await client.post(
        LOGIN_URL,
        json={
            "email": VALID_PAYLOAD["email"],
            "password": VALID_PAYLOAD["password"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_004"


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


async def test_token_refresh(client: AsyncClient) -> None:
    reg = await client.post(REGISTER_URL, json=VALID_PAYLOAD)
    refresh_token = reg.json()["data"]["tokens"]["refresh_token"]

    resp = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]
    # New tokens must differ from the originals (rotation)
    assert body["data"]["access_token"] != reg.json()["data"]["tokens"]["access_token"]


async def test_refresh_with_invalid_token(client: AsyncClient) -> None:
    resp = await client.post(REFRESH_URL, json={"refresh_token": "not.a.valid.token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


async def test_me_returns_current_user(
    client: AsyncClient, registered_user: dict, auth_headers: dict
) -> None:
    resp = await client.get(ME_URL, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["user"]["email"] == "arjun@example.com"
    assert "gstin" in body["data"]["organization"]


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get(ME_URL)
    assert resp.status_code == 401


async def test_me_with_invalid_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get(ME_URL, headers={"Authorization": "Bearer invalid.token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------


async def test_forgot_password_always_returns_200(client: AsyncClient) -> None:
    """Always returns 200 regardless of whether the email exists."""
    for email in ["registered@example.com", "doesnotexist@example.com"]:
        resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


async def test_change_password_success(
    client: AsyncClient, auth_headers: dict
) -> None:
    resp = await client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={"current_password": "StrongPass1", "new_password": "NewPass456!"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert "message" in resp.json()["data"]


async def test_change_password_wrong_current_fails(
    client: AsyncClient, auth_headers: dict
) -> None:
    resp = await client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={"current_password": "WrongPassword9", "new_password": "NewPass456!"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Update profile
# ---------------------------------------------------------------------------


async def test_update_profile_success(
    client: AsyncClient, auth_headers: dict
) -> None:
    resp = await client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={"full_name": "Arjun Updated", "phone": "+919876543210"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["full_name"] == "Arjun Updated"
