"""Page Object for JobTeaser's job offers search results page.

All CSS selectors and URL-building logic for this specific page live here, so
that if JobTeaser changes its markup, this is the only file that needs to
change.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

from playwright.sync_api import Locator, Page

from mcp_jobteaser.config import BASE_URL, NAVIGATION_TIMEOUT_MS, POST_LOAD_WAIT_MS
from mcp_jobteaser.models import JobOffer

_OFFER_CARD_SELECTOR = '[data-testid="jobad-card"]'
_EMPTY_STATE_SELECTOR = '[data-testid="job-ads-empty-state"]'
_UUID_RE = re.compile(
    r"/job-offers/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


class JobOffersSearchPage:
    """Wraps a Playwright page currently browsing a JobTeaser search results page."""

    def __init__(self, page: Page):
        self._page = page

    @staticmethod
    def build_url(query: str, page_number: int) -> str:
        params = {"page": page_number, "q": query, "utm_source": "homepage"}
        return f"{BASE_URL}?{urlencode(params)}"

    def goto(self, query: str, page_number: int) -> None:
        url = self.build_url(query, page_number)
        self._page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        # Results are hydrated client-side; wait for either the offer cards
        # or the empty-state block to actually show up before reading the DOM.
        self._page.wait_for_selector(
            f"{_OFFER_CARD_SELECTOR}, {_EMPTY_STATE_SELECTOR}",
            timeout=NAVIGATION_TIMEOUT_MS,
        )
        self._page.wait_for_timeout(POST_LOAD_WAIT_MS)

    def is_empty(self) -> bool:
        return self._page.locator(_EMPTY_STATE_SELECTOR).count() > 0

    def extract_offers(self) -> list[JobOffer]:
        cards = self._page.locator(_OFFER_CARD_SELECTOR)
        return [self._parse_card(cards.nth(i)) for i in range(cards.count())]

    @staticmethod
    def _text_or_none(locator: Locator) -> str | None:
        return locator.inner_text().strip() if locator.count() else None

    def _parse_card(self, card: Locator) -> JobOffer:
        link = card.locator("h3 a").first
        title = link.inner_text().strip()
        href = link.get_attribute("href") or ""
        url = href if href.startswith("http") else f"https://www.jobteaser.com{href}"

        company = self._text_or_none(card.locator('[data-testid="jobad-card-company-name"]').first) or ""
        location = self._text_or_none(card.locator('[data-testid="jobad-card-location"] span').first)
        contract_type = self._text_or_none(card.locator('[data-testid="jobad-card-contract"] span').first)
        posted_relative = self._text_or_none(card.locator("footer time").first)

        sponsored = card.locator('[data-testid="jobad-card-sponsored"]').count() > 0
        easy_apply = card.locator('[data-testid="jobad-card-internal"]').count() > 0

        uuid_match = _UUID_RE.search(href)
        offer_id = uuid_match.group(1) if uuid_match else href

        return JobOffer(
            id=offer_id,
            title=title,
            company=company,
            url=url,
            location=location,
            contract_type=contract_type,
            posted_relative=posted_relative,
            sponsored=sponsored,
            easy_apply=easy_apply,
        )
