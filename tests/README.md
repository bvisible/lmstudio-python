# LM Studio Python SDK semi-automated test suite

The SDK test suite is currently only partially automated: the
tests need to be executed on a machine with the LM Studio
desktop application already running locally. If the test suite
is running on Windows under WSL, WSL must be running with mirrored
networking enabled (otherwise the test suite won't be able to
access the desktop app via the local loopback interface).

In addition to the desktop app being app and run, the following
conditions must also be met for the test suite to pass:

- the API server must be enabled and running on port 1234
- the following models model must be loaded with their default identifiers
  - `text-embedding-nomic-embed-text-v1.5` (text embedding model)
  - `llama-3.2-1b-instruct` (text LLM)
  - `ZiangWu/MobileVLM_V2-1.7B-GGUF` (visual LLM)
  - `qwen2.5-7b-instruct-1m` (tool using LLM)

Additional models should NOT be loaded when running the test suite,
as some model querying tests may fail in that case.

There are also some JIT model loading/unloading test cases which
expect `smollm2-135m` (small text LLM) to already be downloaded.
A full test run will download this model (since it is also the
model used for the end-to-end search-and-download test case).

There's no problem with having additional models downloaded.
The only impact is that the test that checks all of the expected
models can be found in the list of downloaded models will take a
little longer to run.


# Loading and unloading the required models

The `load-test-models` `tox` environment can be used to ensure the required
models are loaded *without* a time-to-live set:

```console
$ tox -m load-test-models
```

To ensure the test models are loaded with the config expected by the test suite,
any previously loaded instances are unloaded first.

There is also an `unload-test-models` `tox` environment that can be used to
explicitly unload the test models:

```console
$ tox -m unload-test-models
```

The model downloading test cases can be specifically run with:

```console
$ tox -m test -- -k test_download_model
```


# Testing with Cloudflare WAF

The SDK includes integration tests for LM Studio instances protected by Cloudflare WAF (Web Application Firewall). These tests verify that the SDK correctly sends HTTP headers (`X-API-Key`) in the WebSocket handshake to pass through firewall authentication.

## Setup

1. **Copy environment configuration template:**
   ```console
   $ cp .env.example .env
   ```

2. **Edit `.env` with your actual configuration:**
   ```bash
   LMSTUDIO_CLOUDFLARE_HOST=lmstudio.noraai.ch:443
   LMSTUDIO_X_API_KEY=your-actual-api-key-here
   ```

   **Security Note:** Never commit `.env` file to git (it's in `.gitignore`)

3. **Load environment variables before running tests:**
   ```console
   $ source .env                    # Linux/macOS
   $ set -a; source .env; set +a    # Alternative for bash
   ```

## Running Cloudflare Tests

Run Cloudflare integration tests only:
```console
$ tox -m test -- tests/test_cloudflare_integration.py -v
```

Run all tests including Cloudflare:
```console
$ tox -m test -- -v
```

Skip Cloudflare tests (default if env vars not set):
```console
$ tox -m test
```

## Quick Connection Test

Verify connectivity to your Cloudflare-protected instance:

```console
$ source .env
$ python -c "
from lmstudio import Client
client = Client('$LMSTUDIO_CLOUDFLARE_HOST', x_api_key='$LMSTUDIO_X_API_KEY')
print(f'✅ Connected to {client.api_host}')
client.close()
"
```

## What the Tests Cover

The Cloudflare integration tests verify:

- ✅ Connection succeeds **with** `X-API-Key` header
- ✅ Connection fails **without** `X-API-Key` (WAF blocks it)
- ✅ `x_api_key` parameter works correctly
- ✅ `http_headers` parameter works correctly
- ✅ `LMSTUDIO_X_API_KEY` environment variable works
- ✅ Both sync (`Client`) and async (`AsyncClient`) APIs work
- ✅ Complete LLM predictions work through the WAF
- ✅ Combined authentication (`api_token` + `x_api_key`) works

## Understanding HTTP Headers vs WebSocket Auth

The SDK supports **two independent layers** of authentication:

1. **HTTP Header Auth (`x_api_key`)**: Checked by Cloudflare WAF **before** WebSocket connection
   - Set via `x_api_key` parameter or `http_headers` dict
   - Sent in HTTP handshake request
   - Required to pass through WAF/firewall

2. **WebSocket Auth (`api_token`)**: Checked by LM Studio **after** WebSocket is established
   - Set via `api_token` parameter or `LMSTUDIO_API_TOKEN` env var
   - Sent in WebSocket payload
   - Required if LM Studio has authentication enabled

You can use both together for double authentication:
```python
from lmstudio import Client

client = Client(
    "lmstudio.noraai.ch:443",
    api_token="sk-lm-xxx",           # For LM Studio auth
    x_api_key="your-cloudflare-key", # For WAF auth
)
```


## Adding new tests

Test files should follow the following naming conventions:

- `test_XYZ.py`: either a mix of async and sync test cases for `XYZ` that aren't amenable to
  automated conversion (for whatever reason; for example, `anyio.fail_after` has no sync counterpart),
  or else test cases for a behaviour which currently only exists in one API or the other
- `async/test_XYZ_async.py` : async test cases for `XYZ` that are amenable to automated sync conversion;
  all test method names should also end in `_async`.
- `sync/test_XYZ_sync.py` : sync test cases auto-generated from `test_XYZ_async.py`

`python async2sync.py` will run the automated conversion (there are no external dependencies,
so there's no dedicated `tox` environment for this).

## Marking slow tests

`pytest` accepts a `--durations=N` option to print the "N" slowest tests (and their durations).

Any tests that consistently take more than 3 seconds to execute should be marked as slow. It's
also reasonable to mark any tests that take more than a second as slow.

Tests that are missing the marker can be identified via:

```
tox -m test -- --durations=10 -m "not slow"
```

Tests that have the marker but shouldn't can be identified via:

```
tox -m test -- --durations=0 -m "slow"
```

(the latter command prints the durations for all executed tests)
