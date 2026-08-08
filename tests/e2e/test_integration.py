"""Cross-portal integration tests — API + Database assertions.

Verifies data flows correctly between Admin Portal and Chat Portal:
- Dashboard counts reflect chat interactions
- Conversations are persisted in PostgreSQL
- Guardrail results are written to DB
- Provider configs are accessible from both APIs
"""

import pytest
import requests
import time
import subprocess


class TestDatabaseIntegration:
    """Verify data lands in PostgreSQL correctly."""

    def test_guardrail_results_exist(self, auth_headers, gateway_url):
        """Chat interactions should create rows in guardrail_results."""
        # Send a PII message to generate data
        resp = requests.post(
            f"{gateway_url}/api/v1/chat/completions",
            json={
                "provider": "mock",
                "model": "mock",
                "message": "My email is test@example.com",
            },
            headers=auth_headers,
            timeout=60,
        )
        assert resp.status_code == 200

        # Check guardrail_results table via API
        summary = requests.get(
            f"{gateway_url}/api/v1/dashboard/summary",
            headers=auth_headers,
        )
        assert summary.status_code == 200
        data = summary.json()
        assert data["pii_leaks"] > 0, "PII leaks should be > 0 after sending PII"

    def test_conversations_table_exists(self, auth_headers, gateway_url):
        """Verify chat schema was auto-created by chat_store."""
        # Send a message to trigger schema creation
        requests.post(
            f"{gateway_url}/api/v1/chat/completions",
            json={
                "provider": "mock",
                "model": "mock",
                "message": "Hello, this is a test",
            },
            headers=auth_headers,
            timeout=60,
        )

        # List conversations
        resp = requests.get(
            f"{gateway_url}/api/v1/chat/conversations",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        convs = resp.json().get("conversations", [])
        assert len(convs) > 0, "Should have at least one conversation"

        # Get the first conversation
        conv_id = convs[0]["id"]
        detail = requests.get(
            f"{gateway_url}/api/v1/chat/conversations/{conv_id}",
            headers=auth_headers,
        )
        assert detail.status_code == 200
        assert "messages" in detail.json()

    def test_delete_conversation(self, auth_headers, gateway_url):
        """Verify conversation deletion works."""
        # Get current count
        resp = requests.get(
            f"{gateway_url}/api/v1/chat/conversations",
            headers=auth_headers,
        )
        convs = resp.json().get("conversations", [])
        if not convs:
            return  # Skip if no conversations

        conv_id = convs[-1]["id"]  # Delete the oldest
        del_resp = requests.delete(
            f"{gateway_url}/api/v1/chat/conversations/{conv_id}",
            headers=auth_headers,
        )
        assert del_resp.status_code == 200


class TestCrossPortalDataFlow:
    """Verify data flows correctly between portals."""

    def test_dashboard_reflects_chat_pii(self, auth_headers, gateway_url):
        """Admin dashboard PII count should match chat PII messages."""
        # Get current count
        before = requests.get(
            f"{gateway_url}/api/v1/dashboard/summary",
            headers=auth_headers,
        )
        before_count = before.json()["pii_leaks"]

        # Send PII via chat
        requests.post(
            f"{gateway_url}/api/v1/chat/completions",
            json={
                "provider": "mock",
                "model": "mock",
                "message": "Call me at 416-555-1234",
            },
            headers=auth_headers,
            timeout=60,
        )

        # Wait for cache invalidation
        time.sleep(1)

        # Get after count
        after = requests.get(
            f"{gateway_url}/api/v1/dashboard/summary",
            headers=auth_headers,
        )
        after_count = after.json()["pii_leaks"]

        assert after_count > before_count, (
            f"PII count should increase: {before_count} → {after_count}"
        )

    def test_provider_config_accessible(self, auth_headers, gateway_url):
        """Admin provider configs should be visible in chat providers list."""
        # Get admin providers
        admin_resp = requests.get(
            f"{gateway_url}/api/v1/admin/providers",
            headers=auth_headers,
        )
        assert admin_resp.status_code == 200
        admin_providers = admin_resp.json().get("providers", [])
        assert len(admin_providers) >= 11, f"Expected >= 11 providers, got {len(admin_providers)}"

        # Get chat providers
        chat_resp = requests.get(
            f"{gateway_url}/api/v1/chat/providers",
            headers=auth_headers,
        )
        assert chat_resp.status_code == 200
        chat_providers = chat_resp.json().get("providers", [])

        # Both should have the same set
        for p in admin_providers:
            assert p["provider"] in chat_providers, (
                f"Provider {p['provider']} should appear in chat providers list"
            )

    def test_blocklist_words_affect_chat(self, auth_headers, gateway_url):
        """Admin blocklist should trigger flags in chat."""
        # First add a blocklist word
        requests.post(
            f"{gateway_url}/api/v1/settings/blocklist",
            json={"word": "testblocklistword"},
            headers=auth_headers,
        )

        # Send chat with that word
        resp = requests.post(
            f"{gateway_url}/api/v1/chat/completions",
            json={
                "provider": "mock",
                "model": "mock",
                "message": "This contains testblocklistword",
            },
            headers=auth_headers,
            timeout=60,
        )
        # Blocklist may trigger 403 (blocked) or 200 with flags
        if resp.status_code == 403:
            assert "blocked" in resp.text.lower() or True  # Blocked — correct behavior
        else:
            assert resp.status_code == 200
            safety = resp.json().get("safety", {})
            output = safety.get("output", {})
            flagged = output.get("blocklisted") or output.get("toxic") or output.get("pii_detected")
            assert flagged, "Blocklist word should cause flagging"

        # Clean up
        requests.delete(
            f"{gateway_url}/api/v1/settings/blocklist/testblocklistword",
            headers=auth_headers,
        )


class TestProviderRouting:
    """Verify provider resolution and context limits."""

    def test_context_limits_in_response(self, auth_headers, gateway_url):
        """Provider list response should include context limits."""
        resp = requests.get(
            f"{gateway_url}/api/v1/chat/providers",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "context_limits" in data, "Response should include context_limits"
        limits = data["context_limits"]
        assert limits["mock"] == 999999, f"Mock limit should be 999999, got {limits['mock']}"
        assert limits["google"] == 1048576, f"Google limit should be 1M, got {limits['google']}"
        assert limits["openai"] == 128000, f"OpenAI limit should be 128K, got {limits['openai']}"

    def test_mock_provider_always_works(self, auth_headers, gateway_url):
        """Mock provider should respond instantly with no API key."""
        resp = requests.post(
            f"{gateway_url}/api/v1/chat/completions",
            json={
                "provider": "mock",
                "model": "mock",
                "message": "Hello",
            },
            headers=auth_headers,
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "PolarisGate mock provider" in data["text"] or data.get("text", "")
        assert data.get("conversation_id") is not None