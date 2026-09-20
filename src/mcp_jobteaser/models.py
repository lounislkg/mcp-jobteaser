"""Data models returned by the JobTeaser MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JobOffer(BaseModel):
    id: str
    title: str
    company: str
    url: str
    location: str | None = None
    contract_type: str | None = None
    posted_relative: str | None = Field(
        default=None,
        description="Relative publish date as shown by JobTeaser, e.g. 'il y a 6 jours'.",
    )
    sponsored: bool = False
    easy_apply: bool = False


class SearchResult(BaseModel):
    query: str
    total_offers_found: int
    pages_scanned: int
    reached_end_of_results: bool = Field(
        description="True if pagination stopped because JobTeaser returned an "
        "empty results page, False if it stopped because max_offers was reached."
    )
    offers: list[JobOffer]


class JobOfferDetails(BaseModel):
    id: str
    url: str
    title: str
    company: str
    location: str | None = None
    contract_type: str | None = None
    start_date: str | None = None
    salary: str | None = None
    remote_policy: str | None = None
    study_level: str | None = None
    function: str | None = None
    application_deadline: str | None = None
    posted_at: str | None = Field(
        default=None,
        description="Publication date as an ISO date (YYYY-MM-DD).",
    )
    description: str = Field(
        description="Full offer text (missions, required profile...), as plain text."
    )
    description_truncated: bool = Field(
        default=False,
        description="True if the description was cut to fit `max_chars`.",
    )


class OfferDetailsError(BaseModel):
    id: str
    error: Literal["invalid_id", "not_found", "blocked", "timeout"] = Field(
        description="invalid_id: not a UUID. not_found: offer expired or removed. "
        "blocked: JobTeaser's anti-bot challenge intercepted the page. "
        "timeout: the page did not load in time. blocked and timeout are "
        "transient and worth retrying later."
    )
    message: str


class OfferDetailsResult(BaseModel):
    offers: list[JobOfferDetails]
    errors: list[OfferDetailsError] = Field(
        description="One entry per requested id that could not be fetched. "
        "A failure on one id never prevents the others from being returned."
    )
