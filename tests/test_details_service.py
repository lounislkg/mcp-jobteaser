"""Tests for the input handling of get_job_offers_details. None of these cases
reach the browser, so they run offline.
"""

from __future__ import annotations

import pytest

from mcp_jobteaser.config import MAX_IDS_PER_DETAILS_CALL
from mcp_jobteaser.details_service import get_job_offers_details


def test_invalid_ids_are_reported_without_launching_a_browser():
    result = get_job_offers_details(["not-a-uuid", "https://www.jobteaser.com/fr/job-offers/abc"])

    assert result.offers == []
    assert [e.error for e in result.errors] == ["invalid_id", "invalid_id"]
    assert [e.id for e in result.errors] == ["not-a-uuid", "https://www.jobteaser.com/fr/job-offers/abc"]


def test_empty_ids_returns_empty_result():
    result = get_job_offers_details([])

    assert result.offers == []
    assert result.errors == []


def test_too_many_ids_is_rejected():
    ids = ["15da512c-99cc-4dfa-b651-c273675018b1"] * (MAX_IDS_PER_DETAILS_CALL + 1)

    with pytest.raises(ValueError, match="Too many ids"):
        get_job_offers_details(ids)
