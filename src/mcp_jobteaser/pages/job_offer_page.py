"""Page Object for a single JobTeaser job offer page.

All CSS selectors and URL-building logic for this specific page live here, so
that if JobTeaser changes its markup, this is the only file that needs to
change.
"""

from __future__ import annotations

import json
import re

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from mcp_jobteaser.config import BASE_URL, NAVIGATION_TIMEOUT_MS
from mcp_jobteaser.models import JobOfferDetails

_TITLE_SELECTOR = '[data-testid="jobad-DetailView__Heading__title"]'
_COMPANY_SELECTOR = '[data-testid="jobad-DetailView__Heading__company_name"]'
# The article holds the description block plus a "Voir plus" button; only the
# first child is the text itself.
_DESCRIPTION_SELECTOR = '[data-testid="jobad-DetailView__Description"] > div'
_JSON_LD_SELECTOR = 'script[type="application/ld+json"]'

# The details list renders these placeholders when the recruiter left a field
# empty; they carry no information, so they are reported as None instead.
_PLACEHOLDERS = {
    "Information non renseignée",
    "Non spécifié",
    "Tant que l’offre est en ligne",
}


class OfferNotFoundError(Exception):
    """JobTeaser answered 404: the offer expired or was removed."""


class OfferBlockedError(Exception):
    """The navigation succeeded but the offer never showed up.

    Same symptom as in the search page: JobTeaser's bot challenge intercepted
    the request.
    """


class JobOfferPage:
    """Wraps a Playwright page browsing a single JobTeaser offer."""

    def __init__(self, page: Page):
        self._page = page

    @staticmethod
    def build_url(offer_id: str) -> str:
        # The slug that JobTeaser appends to the id is cosmetic: the bare id
        # redirects to the canonical URL.
        return f"{BASE_URL}/{offer_id}"

    def goto(self, offer_id: str) -> None:
        response = self._page.goto(
            self.build_url(offer_id),
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT_MS,
        )
        if response is not None and response.status == 404:
            raise OfferNotFoundError(offer_id)
        try:
            self._page.wait_for_selector(_TITLE_SELECTOR, timeout=NAVIGATION_TIMEOUT_MS)
        except PlaywrightTimeoutError as exc:
            raise OfferBlockedError(offer_id) from exc

    def extract_details(self, offer_id: str, max_chars: int) -> JobOfferDetails:
        description = _clean_description(self._text(_DESCRIPTION_SELECTOR) or "")
        truncated = len(description) > max_chars
        if truncated:
            description = description[:max_chars].rstrip() + "…"

        return JobOfferDetails(
            id=offer_id,
            url=self.build_url(offer_id),
            title=self._text(_TITLE_SELECTOR) or "",
            company=self._text(_COMPANY_SELECTOR) or "",
            location=self._field("jobad-DetailView__CandidacyDetails__Locations"),
            contract_type=self._field("jobad-DetailView__CandidacyDetails__Contract"),
            start_date=self._field("jobad-DetailView__CandidacyDetails__start_date"),
            salary=self._field("jobad-DetailView__CandidacyDetails__Wage"),
            remote_policy=self._field("jobad-DetailView__CandidacyDetails__RemotePolicy"),
            study_level=self._field("jobad-DetailView__Summary__studyLevels", "dd"),
            function=self._field("jobad-DetailView__Summary__function", "dd"),
            application_deadline=self._field("jobad-DetailView__Summary__application_deadline", "dd"),
            posted_at=self._posted_at(),
            description=description,
            description_truncated=truncated,
        )

    def _text(self, selector: str) -> str | None:
        locator: Locator = self._page.locator(selector).first
        return locator.inner_text().strip() if locator.count() else None

    def _field(self, testid: str, inner: str = "") -> str | None:
        value = self._text(f'[data-testid="{testid}"] {inner}'.strip())
        if value is None:
            return None
        value = re.sub(r"\s+", " ", value)
        return None if not value or value in _PLACEHOLDERS else value

    def _posted_at(self) -> str | None:
        """Publication date from the schema.org JobPosting block, as YYYY-MM-DD.

        The visible date is French prose ("Publiée le 18 septembre 2026"),
        while the JSON-LD one is machine-readable.
        """
        blocks = self._page.locator(_JSON_LD_SELECTOR)
        for i in range(blocks.count()):
            try:
                data = json.loads(blocks.nth(i).text_content() or "")
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                date_posted = data.get("datePosted")
                return date_posted[:10] if isinstance(date_posted, str) else None
        return None


def _clean_description(text: str) -> str:
    lines = (re.sub(r"[ \t]+", " ", line.replace(" ", " ")).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
