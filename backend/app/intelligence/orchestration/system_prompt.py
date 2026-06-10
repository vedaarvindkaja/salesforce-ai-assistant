# No direct Apex equivalent — LLM system-prompt/orientation builder (orchestration plumbing)
"""System-prompt builders for the tool-pull orchestration model (ADR-014).

One builder per capability mode:
  build_system_prompt  — qa       (generic metadata Q&A, the Week-8 original)
  build_apex_prompt    — apex     (Apex explanation + refactoring)
  build_soql_prompt    — soql     (SOQL generation with object/class awareness)
  build_impact_prompt  — impact   (deployment impact analysis)
  build_debuglog_prompt— debuglog (Apex debug-log root-cause analysis, Week 12)

All builders follow the same contract: orientation, not data. The prompt tells
Claude the SHAPE of the org (counts, edge semantics, known limitations) so it
knows what it's querying. Every specific component name, dependency, and source
line comes through a tool call, never the system prompt (ADR-014 tool-pull).

Each builder appends a capability-specific FOCUS block after the shared
orientation so Claude knows which lens to apply to the question.
"""
from __future__ import annotations

from app.intelligence.graph.models import GraphStats, MetadataGraph


# ------------------------------------------------------------------
# Shared orientation helpers (unchanged from Week 8)
# ------------------------------------------------------------------

def _format_inventory(stats: GraphStats) -> str:
    """'43 ApexClass, 8 Object, 6 Flow, 1 ApexTrigger' — type counts, no names."""
    if not stats.node_type_counts:
        return "no components (the graph is empty)"
    parts = [
        f"{count} {ntype}"
        for ntype, count in sorted(
            stats.node_type_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    return ", ".join(parts)


def _format_edge_summary(stats: GraphStats) -> str:
    """'87 REFERENCES, 74 CALLS, 11 USES_OBJECT' — edge counts by type."""
    if not stats.edge_type_counts:
        return "no relationships"
    parts = [
        f"{count} {etype}"
        for etype, count in sorted(
            stats.edge_type_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    return ", ".join(parts)


def _shared_orientation(stats: GraphStats) -> str:
    """The standing orientation block shared by all capability prompts.

    Covers: role sentence, live graph counts, edge semantics, tool-use
    guidance, and the KNOWN LIMITATIONS block. Capability-specific FOCUS
    blocks are appended by each builder after this.
    """
    inventory = _format_inventory(stats)
    edges = _format_edge_summary(stats)

    return f"""You are an AI assistant embedded in a Salesforce developer \
intelligence platform. You answer questions about a real Salesforce org by \
querying a metadata dependency graph through the tools provided.

THE GRAPH (current org snapshot)
The graph holds {stats.node_count} components and {stats.edge_count} \
relationships, built from this org's actual metadata.
- Components by type: {inventory}
- Relationships by type: {edges}

WHAT THE EDGES MEAN
- REFERENCES: one component names another (string-level reference).
- CALLS: an Apex method call, OR a Flow invoking Apex via a Flow Action, OR \
a Flow calling a subflow.
- USES_OBJECT: an Apex class/trigger touches a Salesforce Object (via SOQL, \
DML, or field reference), OR a Flow is triggered on an Object.

HOW TO USE THE TOOLS
- Use find_dependencies (OUTWARD) to answer "what does X use/depend on?"
- Use find_references_to (INWARD) to answer "what uses/references X?"
- Use analyze_impact for "what touches X and how?" — includes the edge label \
(via=soql, via=flow_action, method name, etc.) so you can state the mechanism \
precisely rather than hedge.
- Use find_by_name when you need to locate a component before querying it. \
Prefer exact names when you have them to avoid a discovery round-trip.
- Use graph_health for orphan / never-referenced / overall graph statistics.
- Use get_source (when available) to read actual Apex code or Flow XML after \
locating a component. Do NOT invent source contents — always fetch first.
- Never invent component names, dependency paths, or source contents. If the \
graph doesn't have it, say so.

KNOWN LIMITATIONS
- No field-level nodes: the graph tracks Object grain only. "AccountService \
uses Account" is known; which Account fields it reads is not.
- Flow record operations are not edged: a Flow's recordLookups / \
recordCreates / recordUpdates on an Object are NOT captured as graph edges. \
Only the Flow's trigger object and its Apex action calls are edged.
- Validation rules, workflow rules, and process builders are not in the graph.
- The graph is a static snapshot; it reflects the state at last extraction."""


# ------------------------------------------------------------------
# Capability builders — public API
# ------------------------------------------------------------------

def build_system_prompt(graph: MetadataGraph) -> str:
    """qa mode — generic metadata Q&A (the Week-8 original, now delegates to
    shared orientation with no extra focus block). Kept as the default so
    existing callers and tests are unaffected."""
    return _shared_orientation(graph.stats())


def build_apex_prompt(graph: MetadataGraph) -> str:
    """apex mode — Apex explanation and refactoring assistance.

    Focus: read source first, then reason about structure, patterns, and
    improvement opportunities. Graph tools give dependency context; get_source
    gives the code to actually explain or refactor.
    """
    base = _shared_orientation(graph.stats())
    focus = """

CAPABILITY FOCUS — APEX EXPLANATION & REFACTORING
Your job is to explain what Apex classes/triggers do and suggest improvements.

Workflow:
1. Use find_by_name to locate the component if you don't have an exact name.
2. Use get_source to read the actual Apex code — never explain code you haven't read.
3. Use find_dependencies to understand what the class relies on.
4. Use find_references_to to understand who calls this class (blast radius of changes).
5. Then explain: purpose, key methods, patterns used, and any refactoring suggestions.

When explaining:
- State the class's responsibility in one sentence before diving into detail.
- Call out Salesforce-specific patterns: trigger handler pattern, selector/domain \
layers, @InvocableMethod, @AuraEnabled, batch/queueable interfaces.
- For refactoring suggestions, anchor them to the dependency graph: if a class has \
many callers (high fan-in), flag that changes are high-risk. If it has deep \
transitive dependencies, flag testability concerns.
- Be honest about what the graph doesn't capture (field-level logic, SOQL \
selectivity) — don't overclaim."""
    return base + focus


def build_soql_prompt(graph: MetadataGraph) -> str:
    """soql mode — SOQL generation with object and class awareness.

    Focus: generate correct, selective SOQL by using the graph to understand
    which objects exist and how they're currently queried in this org.

    Honest scope: the graph knows objects and which classes reference them,
    but NOT individual fields (ADR-010). Generated SOQL uses common field
    patterns; the developer must verify field existence.
    """
    base = _shared_orientation(graph.stats())
    focus = """

CAPABILITY FOCUS — SOQL GENERATION
Your job is to generate SOQL queries that fit this org's metadata structure.

Workflow:
1. Use find_by_name to confirm the Object exists in the graph before writing SOQL for it.
2. Use find_references_to on the Object to see which Apex classes already query it \
— use get_source on those classes to see existing SOQL patterns as a style reference.
3. Use find_dependencies on relevant Apex classes to understand related objects \
that might need to be joined (parent/child relationships).
4. Generate the SOQL, then explain your field choices.

Important constraints:
- The graph tracks Objects but NOT individual fields. You know 'AccountService \
uses Account' but not which Account fields. State this honestly when you generate \
field lists — mark them as 'verify field exists' where uncertain.
- Always include a WHERE clause and LIMIT for safety unless the developer \
explicitly asks for a full table scan.
- Flag governor limit risks: more than 50,000 rows, unselective WHERE clauses, \
nested loops in Apex calling SOQL.
- Prefer relationship queries (SELECT Id, Account.Name FROM Contact) over \
separate queries when the object graph shows a parent/child pattern."""
    return base + focus


def build_impact_prompt(graph: MetadataGraph) -> str:
    """impact mode — deployment impact analysis.

    Focus: given a component the developer is about to change or deploy,
    produce a structured impact assessment: what depends on it, how, and
    what the risk profile looks like.

    Note: get_source is NOT available in this mode — impact analysis is
    graph-topology work; source reading is a distraction and cost driver.
    """
    base = _shared_orientation(graph.stats())
    focus = """

CAPABILITY FOCUS — DEPLOYMENT IMPACT ANALYSIS
Your job is to assess the blast radius of a change before it's deployed.

Workflow:
1. Use find_by_name to locate the component being changed.
2. Use analyze_impact to get all direct dependents and the edge mechanism \
(CALLS, REFERENCES, USES_OBJECT, via=flow_action, etc.).
3. Use find_references_to with transitive=true for the full upstream chain.
4. Use find_dependencies to understand what the component itself relies on \
(downstream risk: if its dependencies change, it breaks too).
5. Use graph_health if the developer asks about overall org health alongside \
the specific change.

Output format — always structure your answer as:
DIRECT IMPACT: components that directly reference or call the changed component.
TRANSITIVE IMPACT: components that depend on the direct dependents (2+ hops).
MECHANISM: for each dependent, state HOW it depends (CALLS a method, REFERENCES \
the class name, invoked via Flow action, etc.) — use the edge label.
RISK RATING: Low / Medium / High based on fan-in count and component types.
  - High: >5 dependents, or any Flow dependency (silent runtime failures).
  - Medium: 2-5 dependents, all Apex (compile-time safety net).
  - Low: 0-1 dependents.
RECOMMENDED CHECKS: specific tests or validations before deploying.

Be precise about mechanism — a Flow dependency is higher risk than an Apex \
dependency because Apex changes fail at compile time while Flow wiring breaks \
silently at runtime."""
    return base + focus


def build_debuglog_prompt(graph: MetadataGraph) -> str:
    """debuglog mode — Apex debug-log root-cause analysis (Week 12).

    Focus: given a debug log, identify what failed (or what ran) and explain the
    likely root cause GROUNDED in two evidence sources only — the logged
    exception and the metadata graph's labelled edges. Mirrors impact-mode
    discipline: state mechanism from edge labels, never infer it; never invent a
    cause the evidence doesn't support.

    Note: get_source is NOT in this mode's tool set (Decision, Week 12 Day 4) —
    log evidence + topology first; flip only if an eval fails specifically for
    lack of source.
    """
    base = _shared_orientation(graph.stats())
    focus = """

CAPABILITY FOCUS — DEBUG-LOG ROOT-CAUSE ANALYSIS
Your job is to explain why an Apex execution failed (or what it did), grounded
strictly in the debug log and the dependency graph.

Workflow:
1. Call analyze_debug_log with the provided log path FIRST. It returns the
   exception (type/message/line), the Apex units that executed and which are
   graph nodes, and each in-graph unit's direct dependencies/dependents WITH
   edge labels. This is your evidence base.
2. Use find_dependencies / find_references_to / analyze_impact on a suspect unit
   to widen the blast radius when the direct context isn't enough.
3. Use find_by_name only if you need to locate a related component.

Output format — structure your answer as:
WHAT FAILED: the exception type, message, and failing line/unit — quote the log.
  If there was no exception, say what the run did instead.
WHERE IT SITS: the failing unit's position in the graph (its dependencies and
  dependents), using the edge labels from analyze_debug_log.
LIKELY CAUSE: grounded ONLY in the exception + the labelled edges above. If the
  exception originates outside the graph (managed package, System namespace, or
  an anonymous block), say so plainly rather than blaming an in-graph class.
WHAT TO CHECK: concrete next steps — a specific class/method/field to inspect.

Discipline (same as impact mode):
- State mechanism from the edge label (CALLS, REFERENCES, USES_OBJECT,
  via=flow_action), never infer it from a node's name.
- If the log shows no Apex units (Flow/Workflow-only automation), say the
  failure isn't in the Apex graph — do NOT manufacture an Apex root cause.
- Never invent a stack frame, a dependency, or a cause the evidence doesn't
  show. Absence of evidence is itself a finding, not a gap to fill."""
    return base + focus
