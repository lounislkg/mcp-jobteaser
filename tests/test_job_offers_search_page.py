"""Tests for JobOffersSearchPage parsing logic, using saved HTML fixtures so
they run offline and don't depend on JobTeaser's anti-bot protection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from mcp_jobteaser.pages.job_offers_search_page import JobOffersSearchPage

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


def _load_fixture(browser, filename: str):
    # JavaScript is disabled on purpose: the saved fixture already contains
    # the fully hydrated markup we want to parse, and letting Next.js'
    # hydration scripts run again against a static snapshot (no matching
    # server data) wipes the DOM instead of reproducing it.
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    html = (FIXTURES_DIR / filename).read_text(encoding="utf-8")
    page.set_content(html)
    return page


def test_build_url():
    url = JobOffersSearchPage.build_url("stage DevOps", 2)
    assert url == "https://www.jobteaser.com/fr/job-offers?page=2&q=stage+DevOps&utm_source=homepage"


def test_extract_offers_from_results_page(browser):
    page = _load_fixture(browser, "search_results_page1.html")
    search_page = JobOffersSearchPage(page)

    assert not search_page.is_empty()

    offers = search_page.extract_offers()
    assert len(offers) == 21

    first = offers[0]
    assert first.title == "Stage - 6 mois - Développeur Observability & Monitoring F/H"
    assert first.company == "Natixis"
    assert first.location == "Paris, France"
    assert first.contract_type == "Stage 4 à 6 mois"
    assert first.sponsored is True
    assert first.url.startswith("https://www.jobteaser.com/fr/job-offers/")
    assert first.id == "6be8179b-926e-447b-8214-82fd77b27a47"

    page.close()


def test_extract_offers_from_empty_page(browser):
    page = _load_fixture(browser, "empty_results.html")
    search_page = JobOffersSearchPage(page)

    assert search_page.is_empty()
    assert search_page.extract_offers() == []

    page.close()
