"""Tests for CA Firm White-Label System (14 tests)."""

import pytest
from httpx import AsyncClient

CA_FIRM_PAYLOAD = {
    "firm_name": "Sharma & Associates",
    "icai_firm_registration_number": "FRN123456W",
    "primary_ca_name": "Rajesh Sharma",
    "icai_membership_number": "MH123456",
    "phone": "9876543210",
    "city": "Mumbai",
    "state": "Maharashtra",
    "white_label_subdomain": "sharma-associates",
    "primary_color": "#534AB7",
}

VALID_REGISTER_PAYLOAD_CA = {
    "full_name": "Rajesh Sharma",
    "email": "rajesh.ca@example.com",
    "password": "StrongPass1",
    "gstin": "27RAJSH1234F2Z5",
}

CLIENT_ORG_PAYLOAD = {
    "full_name": "Client User",
    "email": "client@example.com",
    "password": "StrongPass1",
    "gstin": "29CLNTS1234F1Z5",
}


async def _register_and_login(client: AsyncClient, payload: dict) -> dict:
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["data"]["tokens"]


async def _upgrade_to_ca_firm_plan(client: AsyncClient, headers: dict) -> None:
    """Directly patch org plan to ca_firm for testing."""
    from app.main import app as _app
    from app.core.database import get_db
    from app.models.organization import Organization, Plan
    from sqlalchemy import select

    db_gen = _app.dependency_overrides[get_db]()
    db = await db_gen.__anext__()
    try:
        me = await client.get("/api/v1/auth/me", headers=headers)
        org_id = me.json()["data"]["organization"]["id"]
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = result.scalar_one()
        org.plan = Plan.ca_firm
        await db.commit()
    finally:
        await db_gen.aclose()


@pytest.mark.asyncio
async def test_register_ca_firm(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, headers)

    r = await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=headers)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["firm_name"] == "Sharma & Associates"
    assert data["icai_firm_registration_number"] == "FRN123456W"
    assert data["white_label_subdomain"] == "sharma-associates"
    assert data["primary_color"] == "#534AB7"


@pytest.mark.asyncio
async def test_register_ca_firm_duplicate(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, headers)

    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=headers)
    r2 = await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=headers)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_register_requires_ca_firm_plan(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=auth_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_ca_firm_profile(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=headers)

    r = await client.get("/api/v1/ca-firms/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["firm_name"] == "Sharma & Associates"


@pytest.mark.asyncio
async def test_update_ca_firm(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=headers)

    r = await client.patch(
        "/api/v1/ca-firms/me",
        json={"city": "Pune", "primary_color": "#FF5733"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["city"] == "Pune"
    assert data["primary_color"] == "#FF5733"


@pytest.mark.asyncio
async def test_add_client(client: AsyncClient):
    # Register CA firm
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)

    # Register client org
    await _register_and_login(client, CLIENT_ORG_PAYLOAD)

    r = await client.post(
        "/api/v1/ca-firms/clients",
        json={"gstin": CLIENT_ORG_PAYLOAD["gstin"], "commission_rate": "0.15"},
        headers=ca_headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["organization_gstin"] == CLIENT_ORG_PAYLOAD["gstin"]
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_add_client_not_found(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)

    r = await client.post(
        "/api/v1/ca-firms/clients",
        json={"gstin": "29NOFND1234F1Z5", "commission_rate": "0.15"},
        headers=ca_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_clients(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)
    await _register_and_login(client, CLIENT_ORG_PAYLOAD)
    await client.post(
        "/api/v1/ca-firms/clients",
        json={"gstin": CLIENT_ORG_PAYLOAD["gstin"], "commission_rate": "0.15"},
        headers=ca_headers,
    )

    r = await client.get("/api/v1/ca-firms/clients", headers=ca_headers)
    assert r.status_code == 200
    clients = r.json()["data"]
    assert len(clients) == 1
    assert clients[0]["organization_gstin"] == CLIENT_ORG_PAYLOAD["gstin"]


@pytest.mark.asyncio
async def test_remove_client(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)
    await _register_and_login(client, CLIENT_ORG_PAYLOAD)
    add_r = await client.post(
        "/api/v1/ca-firms/clients",
        json={"gstin": CLIENT_ORG_PAYLOAD["gstin"], "commission_rate": "0.15"},
        headers=ca_headers,
    )
    org_id = add_r.json()["data"]["organization_id"]

    r = await client.delete(f"/api/v1/ca-firms/clients/{org_id}", headers=ca_headers)
    assert r.status_code == 200

    # Should no longer appear in active list
    list_r = await client.get("/api/v1/ca-firms/clients", headers=ca_headers)
    assert len(list_r.json()["data"]) == 0


@pytest.mark.asyncio
async def test_dashboard_stats(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)

    r = await client.get("/api/v1/ca-firms/me/dashboard", headers=ca_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert "total_clients" in data
    assert "total_commissions_pending" in data
    assert "recent_clients" in data


@pytest.mark.asyncio
async def test_commission_summary_empty(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)

    r = await client.get("/api/v1/ca-firms/commissions/summary", headers=ca_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total_pending"] == "0"
    assert data["count_pending"] == 0


@pytest.mark.asyncio
async def test_get_branding_not_found(client: AsyncClient):
    r = await client.get("/api/v1/ca-firms/branding/nonexistent-subdomain")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_branding_success(client: AsyncClient):
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)

    r = await client.get("/api/v1/ca-firms/branding/sharma-associates")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["firm_name"] == "Sharma & Associates"
    assert data["primary_color"] == "#534AB7"


@pytest.mark.asyncio
async def test_subdomain_taken_conflict(client: AsyncClient):
    # First CA firm takes the subdomain
    tokens = await _register_and_login(client, VALID_REGISTER_PAYLOAD_CA)
    ca_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers)
    await client.post("/api/v1/ca-firms/", json=CA_FIRM_PAYLOAD, headers=ca_headers)

    # Second user tries same subdomain
    second_payload = {
        "full_name": "Another CA",
        "email": "another.ca@example.com",
        "password": "StrongPass1",
        "gstin": "27ANOCA1234F1Z5",
    }
    tokens2 = await _register_and_login(client, second_payload)
    ca_headers2 = {"Authorization": f"Bearer {tokens2['access_token']}"}
    await _upgrade_to_ca_firm_plan(client, ca_headers2)

    duplicate_payload = {**CA_FIRM_PAYLOAD, "icai_firm_registration_number": "FRN999999W"}
    r = await client.post("/api/v1/ca-firms/", json=duplicate_payload, headers=ca_headers2)
    assert r.status_code == 409
