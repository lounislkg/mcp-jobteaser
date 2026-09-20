"""Orchestrates a paginated JobTeaser search using a headless browser."""

from __future__ import annotations

import logging
import time

from playwright.sync_api import Browser, TimeoutError as PlaywrightTimeoutError, sync_playwright

from mcp_jobteaser.browser import launch_browser, new_context
from mcp_jobteaser.config import (
    DEFAULT_MAX_OFFERS,
    HARD_CAP_MAX_OFFERS,
    PAGE_DELAY_SECONDS,
)
from mcp_jobteaser.models import JobOffer, SearchResult
from mcp_jobteaser.pages.job_offers_search_page import JobOffersSearchPage

logger = logging.getLogger(__name__)

# A fresh browser context per page is deliberate: reusing one context (and
# its cookies) across consecutive navigations reliably triggers JobTeaser's
# JS challenge interstitial ("Un instant..."), which never resolves on its
# own. A clean context per request avoids it in practice, but isn't
# guaranteed, hence the retry below.
_MAX_ATTEMPTS_PER_PAGE = 2


def _fetch_page(browser: Browser, query: str, page_number: int) -> list[JobOffer] | None:
    """Fetch one results page.

    Returns the offers found, or None if JobTeaser's empty-results state was
    shown (i.e. this was the last page). Retries once if neither offers nor
    the empty-state show up in time, since that combination means the bot
    challenge intercepted the request rather than JobTeaser actually having
    no more results.
    """
    last_error: PlaywrightTimeoutError | None = None
    for attempt in range(1, _MAX_ATTEMPTS_PER_PAGE + 1):
        context = new_context(browser)
        try:
            search_page = JobOffersSearchPage(context.new_page())
            search_page.goto(query, page_number)
            if search_page.is_empty():
                return None
            return search_page.extract_offers()
        except PlaywrightTimeoutError as exc:
            last_error = exc
            logger.warning(
                "Attempt %d/%d for page %d timed out waiting for recognizable "
                "content (likely JobTeaser's bot challenge); retrying",
                attempt,
                _MAX_ATTEMPTS_PER_PAGE,
                page_number,
            )
            time.sleep(PAGE_DELAY_SECONDS)
        finally:
            context.close()
    assert last_error is not None
    raise last_error


def search_job_offers(query: str, max_offers: int | None = None) -> SearchResult:
    """Search JobTeaser job offers matching `query`.

    Pages through the results, starting at page 1, until either `max_offers`
    is reached or JobTeaser returns an empty results page.
    """
    limit = min(max_offers or DEFAULT_MAX_OFFERS, HARD_CAP_MAX_OFFERS)

    offers: list[JobOffer] = []
    page_number = 1
    pages_scanned = 0
    reached_end = False

    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            while len(offers) < limit:
                logger.info("Fetching page %d for query=%r", page_number, query)

                page_offers = _fetch_page(browser, query, page_number)
                pages_scanned += 1

                if not page_offers:
                    reached_end = True
                    break

                offers.extend(page_offers)
                page_number += 1

                if len(offers) < limit:
                    time.sleep(PAGE_DELAY_SECONDS)
        finally:
            browser.close()

    offers = offers[:limit]

    return SearchResult(
        query=query,
        total_offers_found=len(offers),
        pages_scanned=pages_scanned,
        reached_end_of_results=reached_end,
        offers=offers,
    )
