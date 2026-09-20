"""Fetches the full detail of JobTeaser offers, identified by their id."""

from __future__ import annotations

import logging
import re
import time

from playwright.sync_api import Browser, TimeoutError as PlaywrightTimeoutError, sync_playwright

from mcp_jobteaser.browser import launch_browser, new_context
from mcp_jobteaser.config import (
    DEFAULT_DESCRIPTION_MAX_CHARS,
    HARD_CAP_DESCRIPTION_MAX_CHARS,
    MAX_IDS_PER_DETAILS_CALL,
    PAGE_DELAY_SECONDS,
)
from mcp_jobteaser.models import JobOfferDetails, OfferDetailsError, OfferDetailsResult
from mcp_jobteaser.pages.job_offer_page import JobOfferPage, OfferBlockedError, OfferNotFoundError

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# Same reasoning as in search_service.py: a challenged page is worth one retry
# in a fresh context before giving up.
_MAX_ATTEMPTS_PER_OFFER = 2


def _fetch_offer(browser: Browser, offer_id: str, max_chars: int) -> JobOfferDetails | OfferDetailsError:
    code: str = "timeout"
    message = ""
    for attempt in range(1, _MAX_ATTEMPTS_PER_OFFER + 1):
        context = new_context(browser)
        try:
            page = JobOfferPage(context.new_page())
            page.goto(offer_id)
            return page.extract_details(offer_id, max_chars)
        except OfferNotFoundError:
            return OfferDetailsError(
                id=offer_id,
                error="not_found",
                message="Offer not found: it has probably expired or been removed.",
            )
        except OfferBlockedError:
            code, message = "blocked", "The offer did not show up (likely JobTeaser's bot challenge)."
        except PlaywrightTimeoutError:
            code, message = "timeout", "The page did not load in time."
        finally:
            context.close()

        logger.warning(
            "Attempt %d/%d for offer %s failed (%s)", attempt, _MAX_ATTEMPTS_PER_OFFER, offer_id, code
        )
        if attempt < _MAX_ATTEMPTS_PER_OFFER:
            time.sleep(PAGE_DELAY_SECONDS)

    return OfferDetailsError(id=offer_id, error=code, message=message)  # type: ignore[arg-type]


def get_job_offers_details(ids: list[str], max_chars: int | None = None) -> OfferDetailsResult:
    """Fetch the detail of each offer in `ids`.

    A failure on one offer is reported in `errors` and never prevents the
    others from being fetched. Raises ValueError if more than
    MAX_IDS_PER_DETAILS_CALL ids are requested, since that is a caller
    mistake rather than something worth partially honouring.
    """
    if len(ids) > MAX_IDS_PER_DETAILS_CALL:
        raise ValueError(
            f"Too many ids: {len(ids)} requested, at most {MAX_IDS_PER_DETAILS_CALL} per call. "
            "Split them across several calls."
        )
    limit = min(max_chars or DEFAULT_DESCRIPTION_MAX_CHARS, HARD_CAP_DESCRIPTION_MAX_CHARS)

    offers: list[JobOfferDetails] = []
    errors: list[OfferDetailsError] = []

    to_fetch: list[str] = []
    for raw_id in ids:
        offer_id = raw_id.strip().lower()
        if offer_id in to_fetch:
            continue
        if not _UUID_RE.fullmatch(offer_id):
            errors.append(
                OfferDetailsError(
                    id=raw_id,
                    error="invalid_id",
                    message="Expected the offer `id` (a UUID) as returned by the search tool.",
                )
            )
            continue
        to_fetch.append(offer_id)

    if not to_fetch:
        return OfferDetailsResult(offers=offers, errors=errors)

    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            for index, offer_id in enumerate(to_fetch):
                if index:
                    time.sleep(PAGE_DELAY_SECONDS)
                logger.info("Fetching offer %s (%d/%d)", offer_id, index + 1, len(to_fetch))
                outcome = _fetch_offer(browser, offer_id, limit)
                if isinstance(outcome, JobOfferDetails):
                    offers.append(outcome)
                else:
                    errors.append(outcome)
        finally:
            browser.close()

    return OfferDetailsResult(offers=offers, errors=errors)
