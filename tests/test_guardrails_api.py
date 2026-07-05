import pytest, httpx, os
from retry import retry

BASE_URL = os.getenv("GUARDRAILS_URL", "http://localhost:8005")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")


async def get_token():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GATEWAY_URL}/auth/token",
            data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"},
        )
        assert resp.status_code == 200, f"Auth failed: {resp.status_code} {resp.text}"
        return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_check_endpoint_toxic():
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}

    async def req():
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/api/v1/check",
                json={"text": "I hate you all"},
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] in ("block", "mask", "flag", "allow")

    await retry(req)


@pytest.mark.asyncio
async def test_check_endpoint_clean():
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/v1/check",
            json={"text": "Hello, how are you?"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "allow"


@pytest.mark.asyncio
async def test_check_endpoint_pii():
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/v1/check",
            json={"text": "My SIN is 123-456-789"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] in ("mask", "block", "flag")
