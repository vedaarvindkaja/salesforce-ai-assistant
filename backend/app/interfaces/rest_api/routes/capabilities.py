# No direct Apex equivalent — REST capability surface (transport-layer plumbing).
"""REST capability endpoints (ADR-016).

Four explicit, typed routes — one per capability — over the SHARED
``build_capability_client`` wiring (capabilities.py), so this route layer adds
no capability logic of its own and the OpenAPI surface at ``/docs`` is
self-describing for the Week-13 VS Code extension to generate a typed client
from.

Each public route is a thin wrapper that delegates to one private helper
(``_capability_response``). Day 1 ships the qa route; apex/soql/impact follow on
Day 2 via the same helper, and the parked 5th capability (debug-log) later drops
in as one more wrapper.

Streaming: REST is the STREAMING consumer of the orchestration loop (the mirror
of the MCP server's collected consumer). Claude's text chunks are streamed to
the client over Server-Sent Events via sse-starlette's ``EventSourceResponse``,
which handles SSE framing, heartbeats during the quiet agentic tool-call turns,
and client-disconnect cancellation (an abandoned request stops the Claude loop
instead of burning the full token cost).

Graph availability is gated by ``get_graph_engine`` BEFORE streaming starts: a
missing graph is a 503 (server-side readiness), not a 401 — the caller can't fix
it by re-authenticating.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from app.dependencies import get_graph_engine
from app.intelligence.orchestration.capabilities import build_capability_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["capabilities"])


class CapabilityRequest(BaseModel):
    """Body for every capability route — a single natural-language question."""

    question: str = Field(
        ...,
        min_length=1,
        description="Natural-language question about the org's metadata graph.",
        examples=["Which Apex classes reference AccountTriggerHandler?"],
    )


async def _stream(client, schemas, question: str, mode: str):
    """Async SSE generator: yield Claude's text chunks as they stream.

    Emits a ``chunk`` event per text fragment, a terminal ``done`` event on
    success, or an ``error`` event if the agentic loop raises — a long-lived
    server surfaces a readable failure rather than dropping the connection
    opaquely.
    """
    try:
        async for chunk in client.ask(question, tools=schemas):
            yield {"event": "chunk", "data": chunk}
    except Exception as exc:  # noqa: BLE001 — surface any loop failure to the client
        logger.exception("capability %r stream failed", mode)
        yield {"event": "error", "data": str(exc)}
        return
    yield {"event": "done", "data": ""}


def _capability_response(mode: str, question: str, bundle) -> EventSourceResponse:
    """Shared body of all four capability routes (ADR-016).

    Builds a mode-configured client from the SHARED capabilities wiring, then
    returns an SSE response streaming the agentic loop. Building happens here,
    synchronously, so a wiring failure surfaces before the stream opens; only
    the ``ask()`` loop runs inside the generator.
    """
    engine, graph, cache, org_key = bundle
    client, schemas = build_capability_client(
        mode, engine, graph, cache, org_key, handler_wrapper=None
    )
    return EventSourceResponse(_stream(client, schemas, question, mode))


@router.post("/metadata-qa")
async def metadata_qa(
    body: CapabilityRequest,
    bundle=Depends(get_graph_engine),
) -> EventSourceResponse:
    """Q&A over the org's metadata graph. Streams the answer as SSE."""
    return _capability_response("qa", body.question, bundle)
