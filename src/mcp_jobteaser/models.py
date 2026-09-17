"""Data models returned by the JobTeaser MCP tools."""

from __future__ import annotations

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
