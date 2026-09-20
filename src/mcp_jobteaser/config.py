"""Configuration constants for the JobTeaser MCP server."""

from __future__ import annotations

import os

BASE_URL = "https://www.jobteaser.com/fr/job-offers"

DEFAULT_MAX_OFFERS = 50
HARD_CAP_MAX_OFFERS = 100

# Each offer detail costs one browser page load plus a delay, so a single
# call is capped to keep it well under typical MCP client timeouts.
MAX_IDS_PER_DETAILS_CALL = 10
DEFAULT_DESCRIPTION_MAX_CHARS = 6000
HARD_CAP_DESCRIPTION_MAX_CHARS = 20000

# Delay between paginated page loads, to stay polite towards JobTeaser and
# reduce the chance of triggering their anti-bot protection.
PAGE_DELAY_SECONDS = float(os.environ.get("JOBTEASER_PAGE_DELAY_SECONDS", "1.5"))

NAVIGATION_TIMEOUT_MS = int(os.environ.get("JOBTEASER_NAV_TIMEOUT_MS", "30000"))
POST_LOAD_WAIT_MS = int(os.environ.get("JOBTEASER_POST_LOAD_WAIT_MS", "1500"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Path to a system-installed Chromium binary (used on ARM devices such as a
# Raspberry Pi, where Playwright's bundled Chromium build is unreliable).
# Leave unset to use Playwright's own bundled browser.
CHROMIUM_EXECUTABLE_PATH = os.environ.get("CHROMIUM_EXECUTABLE_PATH") or None

# Extra Chromium CLI flags, comma-separated. Typically needed in Docker
# (e.g. "--no-sandbox,--disable-dev-shm-usage") since a container usually
# lacks the namespaces Chromium's own sandbox expects.
CHROMIUM_EXTRA_ARGS = [
    arg for arg in os.environ.get("CHROMIUM_EXTRA_ARGS", "").split(",") if arg
]

# Bearer token required on every HTTP request when the server runs over the
# streamable-http transport. Must be set in production since the server is
# reachable from the internet.
MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN")
MCP_HTTP_HOST = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
MCP_HTTP_PORT = int(os.environ.get("MCP_HTTP_PORT", "8000"))

# Public hostname of the server, used to configure the streamable-http transport.
MCP_PUBLIC_HOST = os.environ.get("MCP_PUBLIC_HOST", "mcp-jobteaser.beuteuchat.tech")
