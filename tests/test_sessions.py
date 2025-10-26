"""Test common client session behaviour."""

import logging
import os

from typing import Generator
from unittest import mock

import pytest
from pytest import LogCaptureFixture as LogCap

from lmstudio import (
    AsyncClient,
    Client,
    LMStudioValueError,
    LMStudioWebsocketError,
)
from lmstudio.async_api import (
    _AsyncLMStudioWebsocket,
    _AsyncSession,
    _AsyncSessionSystem,
)
from lmstudio.json_api import ClientBase
from lmstudio.sync_api import (
    SyncLMStudioWebsocket,
    _SyncSession,
    _SyncSessionSystem,
)
from lmstudio._ws_impl import AsyncTaskManager
from lmstudio._ws_thread import AsyncWebsocketThread

# This API token is structurally valid
_VALID_API_TOKEN = "sk-lm-abcDEF78:abcDEF7890abcDEF7890"


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_auth_message_default(client_cls: ClientBase) -> None:
    with mock.patch.dict(os.environ) as env:
        env.pop("LMSTUDIO_API_TOKEN", None)
        auth_message = client_cls._create_auth_from_token(None)
        assert auth_message["authVersion"] == 1
        assert auth_message["clientIdentifier"].startswith("guest:")
        client_key = auth_message["clientPasskey"]
        assert client_key != ""
        assert isinstance(client_key, str)


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_auth_message_empty_token(client_cls: ClientBase) -> None:
    with mock.patch.dict(os.environ) as env:
        # Set a valid token in the env to ensure it is ignored
        env["LMSTUDIO_API_TOKEN"] = _VALID_API_TOKEN
        auth_message = client_cls._create_auth_from_token("")
        assert auth_message["authVersion"] == 1
        assert auth_message["clientIdentifier"].startswith("guest:")
        client_key = auth_message["clientPasskey"]
        assert client_key != ""
        assert isinstance(client_key, str)


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_auth_message_empty_token_from_env(client_cls: ClientBase) -> None:
    with mock.patch.dict(os.environ) as env:
        env["LMSTUDIO_API_TOKEN"] = ""
        auth_message = client_cls._create_auth_from_token(None)
        assert auth_message["authVersion"] == 1
        assert auth_message["clientIdentifier"].startswith("guest:")
        client_key = auth_message["clientPasskey"]
        assert client_key != ""
        assert isinstance(client_key, str)


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_auth_message_valid_token(client_cls: ClientBase) -> None:
    auth_message = client_cls._create_auth_from_token(_VALID_API_TOKEN)
    assert auth_message["authVersion"] == 1
    assert auth_message["clientIdentifier"] == "abcDEF78"
    assert auth_message["clientPasskey"] == "abcDEF7890abcDEF7890"


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_auth_message_valid_token_from_env(client_cls: ClientBase) -> None:
    with mock.patch.dict(os.environ) as env:
        env["LMSTUDIO_API_TOKEN"] = _VALID_API_TOKEN
        auth_message = client_cls._create_auth_from_token(None)
        assert auth_message["authVersion"] == 1
        assert auth_message["clientIdentifier"] == "abcDEF78"
        assert auth_message["clientPasskey"] == "abcDEF7890abcDEF7890"


_INVALID_TOKENS = [
    "missing-token-prefix",
    "sk-lm-missing-id-and-key-separator",
    "sk-lm-invalid_id:invalid_key",
    "sk-lm-idtoolong:abcDEF7890abcDEF7890",
    "sk-lm-abcDEF78:keytooshort",
]


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
@pytest.mark.parametrize("api_token", _INVALID_TOKENS)
def test_auth_message_invalid_token(client_cls: ClientBase, api_token: str) -> None:
    with mock.patch.dict(os.environ) as env:
        env["LMSTUDIO_API_TOKEN"] = _VALID_API_TOKEN
        with pytest.raises(LMStudioValueError):
            client_cls._create_auth_from_token(api_token)


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
@pytest.mark.parametrize("api_token", _INVALID_TOKENS)
def test_auth_message_invalid_token_from_env(
    client_cls: ClientBase, api_token: str
) -> None:
    with mock.patch.dict(os.environ) as env:
        env["LMSTUDIO_API_TOKEN"] = api_token
        with pytest.raises(LMStudioValueError):
            client_cls._create_auth_from_token(None)


async def check_connected_async_session(session: _AsyncSession) -> None:
    assert session.connected
    session_ws = session._lmsws
    assert session_ws is not None
    assert session_ws.connected
    # Attempting explicit reconnection fails when connected
    with pytest.raises(LMStudioWebsocketError, match="already connected"):
        await session.connect()
    # Reentering a session has no effect if the websocket is open
    async with session:
        assert session.connected
        assert session_ws.connected
        assert session._lmsws is session_ws
    # But the session is closed after the *first* CM exit
    assert not session.connected
    assert not session_ws.connected


@pytest.mark.asyncio
@pytest.mark.lmstudio
async def test_session_cm_async(caplog: LogCap) -> None:
    caplog.set_level(logging.DEBUG)
    api_host = await AsyncClient.find_default_local_api_host()
    client = AsyncClient(api_host)
    session = _AsyncSessionSystem(client)
    # Sessions start out disconnected
    assert not session.connected
    # Disconnecting should run without error
    await session.disconnect()
    # Entering a session opens the websocket if it isn't already open
    async with client._task_manager, session as entry_result:
        # Sessions are their own entry result
        assert entry_result is session
        # Check connected session behaves as expected
        await check_connected_async_session(session)


# Check the synchronous session API


def check_connected_sync_session(session: _SyncSession) -> None:
    assert session.connected
    session_ws = session._lmsws
    assert session_ws is not None
    assert session_ws.connected
    # Attempting explicit reconnection fails when connected
    with pytest.raises(LMStudioWebsocketError, match="already connected"):
        session.connect()
    # Reentering a session has no effect if the websocket is open
    with session:
        assert session.connected
        assert session_ws.connected
        assert session._lmsws is session_ws
    # But the session is closed after the *first* CM exit
    assert not session.connected
    assert not session_ws.connected


@pytest.mark.lmstudio
def test_session_cm_sync(caplog: LogCap) -> None:
    caplog.set_level(logging.DEBUG)
    api_host = Client.find_default_local_api_host()
    client = Client(api_host)
    session = _SyncSessionSystem(client)
    # Sessions start out disconnected
    assert not session.connected
    # Disconnecting should run without error
    session.disconnect()
    # Entering a session opens the websocket if it isn't already open
    with session as entry_result:
        # Sessions are their own entry result
        assert entry_result is session
        # Check connected session behaves as expected
        check_connected_sync_session(session)


# Sessions support implicit creation of the underlying websocket


@pytest.mark.lmstudio
def test_implicit_connection_sync(caplog: LogCap) -> None:
    caplog.set_level(logging.DEBUG)
    api_host = Client.find_default_local_api_host()
    client = Client(api_host)
    session = _SyncSessionSystem(client)
    # Sessions start out disconnected
    assert not session.connected
    try:
        # Sync sessions will connect implicitly
        models = session.remote_call("listDownloadedModels")
        assert models is not None
        # Check connected session behaves as expected
        check_connected_sync_session(session)
    finally:
        # Still close the session even if an assertion fails
        session.close()


@pytest.mark.lmstudio
def test_implicit_reconnection_sync(caplog: LogCap) -> None:
    caplog.set_level(logging.DEBUG)
    api_host = Client.find_default_local_api_host()
    client = Client(api_host)
    session = _SyncSessionSystem(client)
    with session:
        assert session.connected
    # Session is disconnected after use
    assert not session.connected
    try:
        # Sync sessions will reconnect implicitly
        models = session.remote_call("listDownloadedModels")
        assert models is not None
        # Check connected session behaves as expected
        check_connected_sync_session(session)
    finally:
        # Still close the session even if an assertion fails
        session.close()


# Also test the underlying websocket helper classes directly

# From RFC 6455 via
# http://python-hyper.org/projects/wsproto/en/stable/api.html#wsproto.connection.ConnectionState
WS_STATE_OPEN = 1
WS_STATE_LOCAL_CLOSING = 3
WS_STATE_CLOSED = 4
# We only expect local websocket closure, not remote
WS_CLOSING_STATES = (WS_STATE_LOCAL_CLOSING, WS_STATE_CLOSED)


@pytest.mark.asyncio
@pytest.mark.lmstudio
async def test_websocket_cm_async(caplog: LogCap) -> None:
    caplog.set_level(logging.DEBUG)
    api_host = await AsyncClient.find_default_local_api_host()
    auth_details = AsyncClient._create_auth_from_token(None)
    tm = AsyncTaskManager(on_activation=None)
    lmsws = _AsyncLMStudioWebsocket(tm, f"http://{api_host}/system", auth_details)
    # SDK client websockets start out disconnected
    assert not lmsws.connected
    # Entering the CM opens the websocket if it isn't already open
    async with tm, lmsws as entry_result:
        assert lmsws.connected
        httpx_ws = lmsws._httpx_ws
        assert httpx_ws is not None
        assert httpx_ws.connection.state.value == WS_STATE_OPEN
        # Sessions are their own entry result
        assert entry_result is lmsws
        # Attempting explicit reconnection fails when connected
        with pytest.raises(LMStudioWebsocketError, match="already connected"):
            await lmsws.connect()
        # Reentering the CM has no effect if the websocket is open
        async with lmsws:
            assert lmsws.connected
            assert httpx_ws.connection.state.value == WS_STATE_OPEN
            assert lmsws._httpx_ws is httpx_ws
        # But the websocket is closed after the *first* CM exit
        assert not lmsws.connected
        assert httpx_ws.connection.state.value in WS_CLOSING_STATES


@pytest.fixture
def ws_thread() -> Generator[AsyncWebsocketThread, None, None]:
    ws_thread = AsyncWebsocketThread()
    ws_thread.start()
    try:
        yield ws_thread
    finally:
        ws_thread.terminate()


@pytest.mark.lmstudio
def test_websocket_cm_sync(ws_thread: AsyncWebsocketThread, caplog: LogCap) -> None:
    caplog.set_level(logging.DEBUG)
    api_host = Client.find_default_local_api_host()
    auth_details = Client._create_auth_from_token(None)
    lmsws = SyncLMStudioWebsocket(ws_thread, f"http://{api_host}/system", auth_details)
    # SDK client websockets start out disconnected
    assert not lmsws.connected
    # Entering the CM opens the websocket if it isn't already open
    with lmsws as entry_result:
        assert lmsws.connected
        httpx_ws = lmsws._httpx_ws
        assert httpx_ws is not None
        assert httpx_ws.connection.state.value == WS_STATE_OPEN
        # Sessions are their own entry result
        assert entry_result is lmsws
        # Attempting explicit reconnection fails when connected
        with pytest.raises(LMStudioWebsocketError, match="already connected"):
            lmsws.connect()
        # Reentering the CM has no effect if the websocket is open
        with lmsws:
            assert lmsws.connected
            assert httpx_ws.connection.state.value == WS_STATE_OPEN
            assert lmsws._httpx_ws is httpx_ws
        # But the websocket is closed after the *first* CM exit
        assert not lmsws.connected
        assert httpx_ws.connection.state.value in WS_CLOSING_STATES

# HTTP headers tests


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_http_headers_stored(client_cls: type[ClientBase]) -> None:
    """Test that HTTP headers are stored in the client."""
    headers = {"X-Custom": "value1", "Authorization": "Bearer token"}
    client = client_cls("localhost:1234", http_headers=headers)
    assert client._http_headers == headers


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_x_api_key_shortcut(client_cls: type[ClientBase]) -> None:
    """Test that x_api_key parameter sets X-API-Key header."""
    client = client_cls("localhost:1234", x_api_key="test-api-key")
    assert client._http_headers.get("X-API-Key") == "test-api-key"


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_x_api_key_from_env(client_cls: type[ClientBase]) -> None:
    """Test that X-API-Key is read from environment variable."""
    with mock.patch.dict(os.environ, {"LMSTUDIO_X_API_KEY": "env-api-key"}):
        client = client_cls("localhost:1234")
        assert client._http_headers.get("X-API-Key") == "env-api-key"


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_x_api_key_parameter_overrides_env(client_cls: type[ClientBase]) -> None:
    """Test that x_api_key parameter overrides environment variable."""
    with mock.patch.dict(os.environ, {"LMSTUDIO_X_API_KEY": "env-api-key"}):
        client = client_cls("localhost:1234", x_api_key="param-api-key")
        assert client._http_headers.get("X-API-Key") == "param-api-key"


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_http_headers_combined_with_x_api_key(client_cls: type[ClientBase]) -> None:
    """Test that http_headers and x_api_key are combined correctly."""
    headers = {"X-Custom": "value1"}
    client = client_cls("localhost:1234", http_headers=headers, x_api_key="api-key")
    assert client._http_headers.get("X-Custom") == "value1"
    assert client._http_headers.get("X-API-Key") == "api-key"


@pytest.mark.parametrize("client_cls", [AsyncClient, Client])
def test_http_headers_default_empty(client_cls: type[ClientBase]) -> None:
    """Test that http_headers defaults to empty dict when no env var set."""
    with mock.patch.dict(os.environ) as env:
        env.pop("LMSTUDIO_X_API_KEY", None)
        client = client_cls("localhost:1234")
        assert client._http_headers == {}
