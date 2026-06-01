"""Eval cases for soql mode — SOQL generation capability."""
from evals.eval_case import EvalCase

CASES = [
    EvalCase(
        description="Generates valid SOQL for a known object",
        query="Write a SOQL query to get all Opportunity records",
        mode="soql",
        required=["SELECT", "FROM Opportunity"],
        forbidden=[],
    ),
    EvalCase(
        description="Confirms object exists in graph before generating SOQL",
        query="Write a SOQL query for Account records modified this month",
        mode="soql",
        required=["SELECT", "FROM Account"],
        forbidden=[],
    ),
    EvalCase(
        description="Generates SOQL with a WHERE clause when asked",
        query="Write SOQL to get Opportunities with Amount greater than 10000",
        mode="soql",
        required=["SELECT", "FROM Opportunity", "WHERE", "Amount"],
        forbidden=[],
    ),
    EvalCase(
        description="Acknowledges field uncertainty honestly (ADR-010 boundary)",
        query="Write SOQL to get all Opportunity fields",
        mode="soql",
        # Must not claim to know every field — FIELD nodes not in graph
        required=["SELECT", "FROM Opportunity"],
        forbidden=[],
    ),
    EvalCase(
        description="Refuses or flags SOQL for an object not in the graph",
        query="Write SOQL for a custom object called Spaceship__c",
        mode="soql",
        required=[],
        # Should not confidently generate SOQL for an unknown object
        # without flagging it
        forbidden=[],
    ),
]