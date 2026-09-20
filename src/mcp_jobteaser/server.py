"""MCP server exposing JobTeaser job search as a tool over streamable-http."""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_jobteaser.config import (
    DEFAULT_DESCRIPTION_MAX_CHARS,
    DEFAULT_MAX_OFFERS,
    MCP_AUTH_TOKEN,
    MCP_HTTP_HOST,
    MCP_HTTP_PORT,
    MCP_PUBLIC_HOST,
)
from mcp_jobteaser.details_service import get_job_offers_details
from mcp_jobteaser.search_service import search_job_offers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = MCPServer(
    name="jobteaser",
    instructions=(
        "Recherche des offres publiees sur JobTeaser. "
        "`search_job_offers_tool` retourne une liste d'offres (id, titre, "
        "entreprise, lieu, contrat, url) sans le detail complet de chaque "
        "offre. Pour lire le texte complet des offres qui semblent "
        "pertinentes, passer leur `id` a `get_job_offers_details_tool`."
    ),
)

# Both tools drive a headless Chromium; an agent may issue several tool calls
# in parallel, which would otherwise start several browsers at once (memory
# on a small host, and more chances of tripping JobTeaser's anti-bot).
_browser_lock = asyncio.Lock()


@mcp.tool()
async def search_job_offers_tool(query: str, max_offers: int = DEFAULT_MAX_OFFERS) -> dict:
    """Recherche des offres JobTeaser correspondant a `query`.

    Args:
        query: Termes de recherche, equivalent au champ de recherche JobTeaser
            (ex: "stage DevOps").
        max_offers: Nombre maximal d'offres a retourner (defaut 50, plafond 100).
    """
    async with _browser_lock:
        result = await asyncio.to_thread(search_job_offers, query, max_offers)
    return result.model_dump()


@mcp.tool()
async def get_job_offers_details_tool(
    ids: list[str], max_chars: int = DEFAULT_DESCRIPTION_MAX_CHARS
) -> dict:
    """Recupere le detail complet d'offres JobTeaser (description, profil recherche, dates...).

    A utiliser sur les offres jugees pertinentes apres `search_job_offers_tool`,
    pas sur toute la liste : chaque offre demande un chargement de page.

    Args:
        ids: Champs `id` des offres (UUID, tels que retournes par la recherche).
            10 maximum par appel ; au-dela, decouper en plusieurs appels.
        max_chars: Longueur maximale de la description par offre (defaut 6000,
            plafond 20000). `description_truncated` indique si elle a ete coupee.

    Retourne `offers` (les details) et `errors` (une entree par id en echec,
    avec un code : invalid_id, not_found, blocked, timeout). Un echec sur un id
    n'empeche pas les autres d'etre retournes ; blocked et timeout sont
    transitoires et peuvent etre retentes plus tard.
    """
    async with _browser_lock:
        result = await asyncio.to_thread(get_job_offers_details, ids, max_chars)
    return result.model_dump()


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Rejects any request that doesn't carry the expected bearer token.

    Kept deliberately simple (no OAuth flow) since this server has a single
    caller (Claude) authenticating with one static, pre-shared token.
    """

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._expected_header = f"Bearer {token}"

    async def dispatch(self, request: Request, call_next):
        if request.headers.get("authorization") != self._expected_header:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def build_app() -> Starlette:
    app = mcp.streamable_http_app(
        transport_security=TransportSecuritySettings(
            allowed_hosts=[MCP_PUBLIC_HOST, f"{MCP_PUBLIC_HOST}:*"],
            allowed_origins=[f"https://{MCP_PUBLIC_HOST}"],
        )
    )
    if MCP_AUTH_TOKEN:
        app.add_middleware(BearerAuthMiddleware, token=MCP_AUTH_TOKEN)
    else:
        logger.warning(
            "MCP_AUTH_TOKEN is not set: the HTTP server is exposed without authentication."
        )
    return app


def main() -> None:
    uvicorn.run(build_app(), host=MCP_HTTP_HOST, port=MCP_HTTP_PORT)


if __name__ == "__main__":
    main()
