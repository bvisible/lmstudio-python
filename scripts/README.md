# Scripts Directory

This directory contains helper scripts for working with the LM Studio Python SDK.

## Available Scripts

### `test_cloudflare.sh`

Quick test script for Cloudflare WAF integration testing.

**Prerequisites:**
1. Create `.env` file in the repository root:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

2. Install test dependencies:
   ```bash
   pip install tox tox-pdm
   # or
   pip install pytest pytest-asyncio
   ```

**Usage:**

```bash
# Run all Cloudflare integration tests
./scripts/test_cloudflare.sh

# Run with verbose output
./scripts/test_cloudflare.sh -v

# Run specific tests
./scripts/test_cloudflare.sh -k test_connection

# Run with pytest options
./scripts/test_cloudflare.sh -v --tb=short
```

**What it does:**

1. ✅ Checks if `.env` file exists
2. ✅ Loads environment variables
3. ✅ Validates required variables are set
4. ✅ Tests connection to Cloudflare instance
5. ✅ Runs full test suite
6. ✅ Reports results with colored output

**Exit codes:**

- `0`: All tests passed
- `1`: Setup error (missing .env, invalid config, etc.)
- Other: Test failures (from pytest/tox)

## Adding New Scripts

When adding new scripts to this directory:

1. Make them executable: `chmod +x scripts/your_script.sh`
2. Add shebang line: `#!/bin/bash`
3. Include usage documentation in comments
4. Update this README
