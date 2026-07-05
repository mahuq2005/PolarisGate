import pytest
import httpx
import asyncio

GATEWAY_URL = "http://gateway:8000"
COLLECTOR_URL = "http://collector:8006"
TOXIC_TEXT = "I hate everyone"

async def get_token():
    async with httpx.AsyncClient() as client:
        # Try setup first (idempotent)
        await client.post(
            f"{GATEWAY_URL}/auth/setup",
            data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"},
        )
        resp = await client.post(
            f"{GATEWAY_URL}/auth/token",
            data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"}
        )
        assert resp.status_code == 200, f"Auth failed: {resp.status_code} {resp.text}"
        return resp.json()["access_token"]

@pytest.mark.asyncio
async def test_end_to_end_toxic_trace():
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        trace_resp = await client.post(
            f"{COLLECTOR_URL}/api/v1/traces",
            headers=headers,
            json={
                "prompt": "test",
                "completion": TOXIC_TEXT,
                "model_id": "e2e-test",
                "user_id": "tester",
                "tags": {"language": "en"}
            }
        )
        assert trace_resp.status_code == 201
        trace_id = trace_resp.json()["trace_id"]

    for _ in range(10):
        await asyncio.sleep(2)
        async with httpx.AsyncClient() as client:
            incidents_resp = await client.get(
                f"{GATEWAY_URL}/api/v1/dashboard/incidents?limit=5",
                headers=headers
            )
            incidents = incidents_resp.json()
            for inc in incidents:
                if inc["trace_id"] == trace_id and inc["toxic"]:
                    return
    pytest.fail(f"Trace {trace_id} never appeared as toxic incident")
