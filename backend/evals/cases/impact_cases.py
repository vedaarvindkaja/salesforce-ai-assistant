"""Eval cases for impact mode — deployment impact capability.

These cases are the most critical: impact mode is the capability where
over-narration is most harmful (developers act on this output).
Refinement #10 fixed the root cause; these cases are the regression guard.
"""
from evals.eval_case import EvalCase

CASES = [
    EvalCase(
        description="Identifies direct dependent of PricingFlowAction correctly",
        query="What is the deployment impact of PricingFlowAction?",
        mode="impact",
        required=[
            "Opportunity_Sales_Orchestration_Flow",
            "URSIP_Opportunity_After_Save",
            "OpportunitySelector",
            "PricingService",
        ],
        forbidden=[
            "core pricing logic",        # Week 9 over-narration
            "query interface",           # Week 9 over-narration
        ],
    ),
    EvalCase(
        description="States mechanism via edge label not inference",
        query="What is the deployment impact of PricingFlowAction?",
        mode="impact",
        required=["via", "Opportunity_Sales_Orchestration_Flow"],
        forbidden=[
            "core pricing logic",      # Week 9 over-narration — invented from node name
            "query interface",         # Week 9 over-narration — inferred mechanism
        ],
    ),
    EvalCase(
        description="Impact analysis for a high-fan-in class",
        query="What is the deployment impact of TriggerBase?",
        mode="impact",
        required=["TriggerBase"],
        forbidden=[],
    ),
    EvalCase(
        description="Impact analysis for an Object node",
        query="What is the deployment impact of changing the Opportunity object?",
        mode="impact",
        required=["Opportunity", "OpportunitySelector"],
        forbidden=[],
    ),
    EvalCase(
        description="Handles a component with no dependents gracefully",
        query="What is the deployment impact of URSIP_Opportunity_After_Save?",
        mode="impact",
        required=["URSIP_Opportunity_After_Save"],
        forbidden=[],
    ),
]