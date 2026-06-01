"""Eval cases for qa mode — metadata Q&A capability."""
from evals.eval_case import EvalCase

CASES = [
    EvalCase(
        description="Identifies a known Apex class by name",
        query="What is PricingFlowAction?",
        mode="qa",
        required=["PricingFlowAction", "Apex"],
        forbidden=[],
    ),
    EvalCase(
        description="Answers a dependency question with real node names",
        query="What does PricingFlowAction depend on?",
        mode="qa",
        required=["OpportunitySelector", "PricingService"],
        forbidden=[],
    ),
    EvalCase(
        description="Identifies what depends on a class (inward direction)",
        query="What depends on PricingFlowAction?",
        mode="qa",
        required=["Opportunity_Sales_Orchestration_Flow"],
        forbidden=[],
    ),
    EvalCase(
        description="Handles a component that has no dependents gracefully",
        query="What depends on URSIP_Opportunity_After_Save?",
        mode="qa",
        required=["URSIP_Opportunity_After_Save"],
        forbidden=["I don't know", "cannot find", "not in the graph"],
    ),
    EvalCase(
        description="Does not hallucinate nodes for an unknown component",
        query="What does NonExistentApexClass12345 depend on?",
        mode="qa",
        required=[],
        forbidden=["OpportunitySelector", "PricingService", "TriggerBase"],
    ),
]