"""Eval cases for apex mode — Apex explanation and refactoring capability."""
from evals.eval_case import EvalCase

CASES = [
    EvalCase(
        description="Reads source before explaining (get_source must be called)",
        query="Explain what PricingFlowAction does",
        mode="apex",
        required=["PricingFlowAction", "@InvocableMethod"],
        forbidden=[],
    ),
    EvalCase(
        description="Grounds explanation in dependency graph",
        query="Explain PricingFlowAction and its dependencies",
        mode="apex",
        required=["PricingFlowAction", "OpportunitySelector", "PricingService"],
        forbidden=[],
    ),
    EvalCase(
        description="Identifies callers when explaining blast radius",
        query="What is the blast radius if I refactor PricingFlowAction?",
        mode="apex",
        required=["Opportunity_Sales_Orchestration_Flow"],
        forbidden=[],
    ),
    EvalCase(
        description="Does not explain code it has not read",
        query="Explain OpportunitySelector",
        mode="apex",
        # Must fetch source — cannot explain without reading
        required=["OpportunitySelector"],
        forbidden=["I cannot read", "no source available"],
    ),
    EvalCase(
        description="Handles unknown class gracefully without hallucinating",
        query="Explain NonExistentClass99999",
        mode="apex",
        required=[],
        forbidden=["OpportunitySelector", "PricingService"],
    ),
]