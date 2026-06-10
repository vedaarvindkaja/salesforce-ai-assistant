# No direct Apex equivalent — REST capability surface (transport-layer plumbing).
"""REST capability endpoints (ADR-016).

Five explicit, typed routes — one per capability — over the SHARED
``build_capability_client`` wiring (capabilities.py), so this route layer adds
no capability logic of its own and the OpenAPI surface at ``/docs`` is
self-describing for the Week-13 VS Code extension to generate a typed client
from.

Each public route is a thin wrapper that delegates to one private helper
(``_capability_response``). The debug-log route (Week 12) is the one whose input
is a log REFERENCE rather than a question (ADR-017): it takes
``DebugLogRequest{log_path, question?}`` instead of ``CapabilityRequest``,
composes the message via the SHARED ``compose_debuglog_input`` helper (the same
framing the CLI and MCP surfaces use), then reuses the identical streaming seam.

Streaming: REST is the STREAMING consumer of the orchestration loop (the mirror
of the MCP server's collected consumer). Claude's text chunks are streamed to
the client over Server-Sent Events via sse-starlette's ``EventSourceResponse``,
which handles SSE framing, heartbeats during the quiet agentic tool-call turns,
and client-disconnect cancellation (an abandoned request stops the Claude loop
instead of burning the full token cost).

Graph availability is gated by ``get_graph_engine`` BEFORE streaming starts: a
missing graph is a 503 (server-side readiness), not a 401 — the caller can't fix
it by re-authenticating. The ``impact`` mode's restricted tool subset
(``_GRAPH_ONLY``) is applied inside ``build_capability_client`` via the registry,
so the routes stay uniform.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from app.dependencies import get_graph_engine
from app.intelligence.orchestration.capabilities import (
    build_capability_client,
    compose_debuglog_input,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["capabilities"])


class CapabilityRequest(BaseModel):
    """Body for every question-shaped capability route — one question."""

    question: str = Field(
        ...,
        min_length=1,
        description="Natural-language question about the org's metadata graph.",
        examples=["Which Apex classes reference AccountTriggerHandler?"],
    )


class DebugLogRequest(BaseModel):
    """Body for the debug-log route — a server-readable log path plus an
    optional focus question (ADR-017: a log REFERENCE, not a bare question).

    log_text is intentionally NOT accepted yet: Phase 1 is local/single-user, so
    a server-side path avoids pushing a large log through the request body. The
    hosted-client log_text variant is the documented future extension.
    """

    log_path: str = Field(
        ...,
        min_length=1,
        description="Path to a Salesforce debug log readable by the server "
                    "(absolute, or relative to the backend dir).",
        examples=["/srv/logs/case_insert.log"],
    )
    question: str | None = Field(
        default=None,
        description="Optional specific question to focus the analysis.",
        examples=["why did the insert fail?"],
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
    """Shared body of all capability routes (ADR-016).

    Builds a mode-configured client from the SHARED capabilities wiring, then
    returns an SSE response streaming the agentic loop. Building happens here,
    synchronously, so a wiring failure surfaces before the stream opens; only
    the ``ask()`` loop runs inside the generator. ``question`` is the message
    Claude receives — for debuglog that's the composed log-reference message.
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


@router.post("/apex-explain")
async def apex_explain(
    body: CapabilityRequest,
    bundle=Depends(get_graph_engine),
) -> EventSourceResponse:
    """Explain Apex with graph-aware dependency context. Streams as SSE."""
    return _capability_response("apex", body.question, bundle)


@router.post("/soql-generate")
async def soql_generate(
    body: CapabilityRequest,
    bundle=Depends(get_graph_engine),
) -> EventSourceResponse:
    """Generate SOQL grounded in the org's schema graph. Streams as SSE."""
    return _capability_response("soql", body.question, bundle)


@router.post("/deployment-impact")
async def deployment_impact(
    body: CapabilityRequest,
    bundle=Depends(get_graph_engine),
) -> EventSourceResponse:
    """Assess deployment blast-radius from the dependency graph. Streams as SSE."""
    return _capability_response("impact", body.question, bundle)


@router.post("/debug-log-analysis")
async def debug_log_analysis(
    body: DebugLogRequest,
    bundle=Depends(get_graph_engine),
) -> EventSourceResponse:
    """Root-cause a Salesforce debug log against the dependency graph.

    Takes a server-readable log path (ADR-017), composes it into the capability
    message via the shared helper, and streams the structured root-cause
    analysis as SSE. The raw log is parsed/correlated server-side inside the
    agentic loop; only structured prose reaches the model.
    """
    message = compose_debuglog_input(body.log_path, body.question)
    return _capability_response("debuglog", message, bundle)
