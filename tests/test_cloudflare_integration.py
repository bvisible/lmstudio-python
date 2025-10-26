"""Integration tests for LM Studio behind Cloudflare WAF.

These tests verify that the SDK correctly sends HTTP headers (X-API-Key)
in the WebSocket handshake to pass through Cloudflare WAF authentication.

Required environment variables:
    LMSTUDIO_CLOUDFLARE_HOST: The Cloudflare-protected LM Studio host (e.g., lmstudio.example.com:443)
    LMSTUDIO_X_API_KEY: The API key for Cloudflare WAF authentication

Setup:
    1. Copy .env.example to .env
    2. Fill in your actual values in .env
    3. Run: source .env (or use python-dotenv)
    4. Run: pytest tests/test_cloudflare_integration.py -v
"""

import os

import pytest

from lmstudio import AsyncClient, Client, LMStudioClientError

# Skip all tests in this module if environment variables are not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("LMSTUDIO_CLOUDFLARE_HOST")
    or not os.environ.get("LMSTUDIO_X_API_KEY"),
    reason="Cloudflare integration tests require LMSTUDIO_CLOUDFLARE_HOST and LMSTUDIO_X_API_KEY environment variables",
)


def get_cloudflare_config() -> tuple[str, str]:
    """Get Cloudflare configuration from environment variables."""
    host = os.environ["LMSTUDIO_CLOUDFLARE_HOST"]
    api_key = os.environ["LMSTUDIO_X_API_KEY"]
    return host, api_key


@pytest.mark.lmstudio
def test_cloudflare_connection_with_x_api_key() -> None:
    """Test that connection succeeds with X-API-Key header."""
    host, api_key = get_cloudflare_config()

    # Test with explicit x_api_key parameter
    with Client(host, x_api_key=api_key) as client:
        # Verify we're connected to the expected host
        assert client.api_host == host
        # Test a basic operation to ensure the connection works
        models = client.list_downloaded_models()
        assert isinstance(models, list)


@pytest.mark.lmstudio
def test_cloudflare_connection_with_http_headers() -> None:
    """Test that connection succeeds with http_headers parameter."""
    host, api_key = get_cloudflare_config()

    # Test with http_headers dict
    headers = {"X-API-Key": api_key}
    with Client(host, http_headers=headers) as client:
        assert client.api_host == host
        models = client.list_downloaded_models()
        assert isinstance(models, list)


@pytest.mark.lmstudio
def test_cloudflare_connection_from_env_variable() -> None:
    """Test that LMSTUDIO_X_API_KEY environment variable works."""
    host, _ = get_cloudflare_config()

    # Environment variable should already be set (required by pytestmark)
    # Create client without explicit x_api_key - should use env var
    with Client(host) as client:
        assert client.api_host == host
        models = client.list_downloaded_models()
        assert isinstance(models, list)


@pytest.mark.lmstudio
def test_cloudflare_connection_fails_without_key() -> None:
    """Test that connection fails WITHOUT X-API-Key (WAF should block)."""
    host, _ = get_cloudflare_config()

    # Temporarily remove the environment variable to ensure no auth
    original_key = os.environ.pop("LMSTUDIO_X_API_KEY", None)
    try:
        # Connection should fail because Cloudflare WAF blocks requests without X-API-Key
        with pytest.raises((LMStudioClientError, ConnectionError, OSError)):
            with Client(host) as client:
                # This should not be reached
                client.list_downloaded_models()
    finally:
        # Restore environment variable
        if original_key:
            os.environ["LMSTUDIO_X_API_KEY"] = original_key


@pytest.mark.lmstudio
@pytest.mark.asyncio
async def test_cloudflare_async_connection() -> None:
    """Test async client connection through Cloudflare WAF."""
    host, api_key = get_cloudflare_config()

    async with AsyncClient(host, x_api_key=api_key) as client:
        assert client.api_host == host
        models = await client.list_downloaded_models()
        assert isinstance(models, list)


@pytest.mark.lmstudio
@pytest.mark.slow
def test_cloudflare_llm_basic_prediction() -> None:
    """Test complete LLM prediction through Cloudflare WAF."""
    host, api_key = get_cloudflare_config()

    with Client(host, x_api_key=api_key) as client:
        # Get any available LLM
        models = client.llm.list_loaded()
        if not models:
            pytest.skip("No LLM loaded on the server")

        # Use the first available model
        model = models[0]

        # Simple prediction test
        response = model.respond("Say 'test successful' if you can read this.")

        # Verify we got a response
        assert isinstance(response, str)
        assert len(response) > 0


@pytest.mark.lmstudio
@pytest.mark.asyncio
@pytest.mark.slow
async def test_cloudflare_async_llm_prediction() -> None:
    """Test async LLM prediction through Cloudflare WAF."""
    host, api_key = get_cloudflare_config()

    async with AsyncClient(host, x_api_key=api_key) as client:
        # Get any available LLM
        models = await client.llm.list_loaded()
        if not models:
            pytest.skip("No LLM loaded on the server")

        # Use the first available model
        model = models[0]

        # Simple prediction test
        response = await model.respond("Say 'test successful' if you can read this.")

        # Verify we got a response
        assert isinstance(response, str)
        assert len(response) > 0


@pytest.mark.lmstudio
def test_cloudflare_combined_auth() -> None:
    """Test using both api_token (WebSocket auth) and x_api_key (HTTP header auth)."""
    host, api_key = get_cloudflare_config()

    # Get LM Studio API token from env if available
    api_token = os.environ.get("LMSTUDIO_API_TOKEN")

    with Client(host, api_token=api_token, x_api_key=api_key) as client:
        assert client.api_host == host
        models = client.list_downloaded_models()
        assert isinstance(models, list)


@pytest.mark.lmstudio
def test_cloudflare_header_priority() -> None:
    """Test that x_api_key parameter overrides environment variable."""
    host, env_key = get_cloudflare_config()

    # Use a different key explicitly (this will fail to connect, but we test priority)
    fake_key = "fake-key-for-priority-test"

    # This should fail because fake_key won't pass WAF
    with pytest.raises((LMStudioClientError, ConnectionError, OSError)):
        with Client(host, x_api_key=fake_key) as client:
            client.list_downloaded_models()

    # Verify that the environment variable is still set correctly
    assert os.environ["LMSTUDIO_X_API_KEY"] == env_key
