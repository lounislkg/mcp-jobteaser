"""Chromium launch and context setup shared by the scraping services."""

from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, Playwright

from mcp_jobteaser.config import CHROMIUM_EXECUTABLE_PATH, CHROMIUM_EXTRA_ARGS, USER_AGENT


def launch_browser(playwright: Playwright) -> Browser:
    return playwright.chromium.launch(
        headless=True,
        executable_path=CHROMIUM_EXECUTABLE_PATH,
        args=CHROMIUM_EXTRA_ARGS,
    )


def new_context(browser: Browser) -> BrowserContext:
    """A clean context (no shared cookies), to be used for a single page load.

    See the note in search_service.py on why contexts must not be reused
    across navigations.
    """
    return browser.new_context(
        locale="fr-FR",
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 900},
    )
