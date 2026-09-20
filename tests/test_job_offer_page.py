"""Tests for JobOfferPage parsing logic, using a saved HTML fixture so they
run offline and don't depend on JobTeaser's anti-bot protection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from mcp_jobteaser.pages.job_offer_page import JobOfferPage

FIXTURES_DIR = Path(__file__).parent / "fixtures"
OFFER_ID = "15da512c-99cc-4dfa-b651-c273675018b1"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def offer_page(browser):
    # JavaScript is disabled on purpose, see test_job_offers_search_page.py.
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.set_content((FIXTURES_DIR / "job_offer_page.html").read_text(encoding="utf-8"))
    yield JobOfferPage(page)
    context.close()


def test_build_url_uses_the_bare_id():
    assert JobOfferPage.build_url(OFFER_ID) == f"https://www.jobteaser.com/fr/job-offers/{OFFER_ID}"


def test_extract_details(offer_page):
    details = offer_page.extract_details(OFFER_ID, max_chars=20000)

    assert details.id == OFFER_ID
    assert details.url == f"https://www.jobteaser.com/fr/job-offers/{OFFER_ID}"
    assert details.title == "STAGE - Assistant analyste Cybersécurité (H/F)"
    assert details.company == "Banque de France"
    assert details.location == "Paris (France)"
    assert details.contract_type == "Stage 4 à 6 mois"
    assert details.start_date == "Dès que possible"
    assert details.study_level == "Niveau Master, MSc ou Programme Grande Ecole"
    assert details.function == "Infra, Réseaux & Télécoms"
    assert details.posted_at == "2026-09-18"


def test_placeholder_fields_are_reported_as_none(offer_page):
    details = offer_page.extract_details(OFFER_ID, max_chars=20000)

    # The page shows "Information non renseignée", "Non spécifié" and
    # "Tant que l’offre est en ligne" for these.
    assert details.salary is None
    assert details.remote_policy is None
    assert details.application_deadline is None


def test_description_is_the_full_text_without_ui_noise(offer_page):
    details = offer_page.extract_details(OFFER_ID, max_chars=20000)

    assert details.description.startswith("Type de recrutement :")
    assert "CERT-BDF" in details.description
    assert "Profil recherché:" in details.description
    assert details.description.endswith("glasses")
    assert "Voir plus" not in details.description
    assert "\n\n\n" not in details.description
    assert not details.description_truncated


def test_description_is_truncated_to_max_chars(offer_page):
    details = offer_page.extract_details(OFFER_ID, max_chars=200)

    assert details.description_truncated
    assert len(details.description) <= 201
    assert details.description.endswith("…")
