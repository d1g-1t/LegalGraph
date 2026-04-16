"""LangGraph pipeline graph — durable, resumable agent orchestration.

Topology:
  START → classifier → (conditional) → retriever → generator → verifier → (conditional) → END
  Branches to: escalation, human_loop
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from src.core.config import get_settings
from src.infrastructure.agents.nodes import (
    classifier_node,
    escalation_node,
    generator_node,
    human_loop_node,
    retriever_node,
    verifier_node,
)
from src.infrastructure.agents.state import PipelineState


def _route_after_classifier(state: PipelineState) -> str:
    """Conditional edge after classifier."""
    settings = get_settings()
    risk = state.get("risk_level", "MEDIUM")
    confidence = state.get("classifier_confidence", 1.0) or 1.0

    # Immediate escalation for critical risk or very low confidence
    if risk == "CRITICAL" or confidence < settings.classifier_confidence_threshold:
        return "escalation"

    # HITL for high risk or explicit flag
    if risk == "HIGH" or state.get("requires_human_review", False):
        return "human_loop"

    # Normal flow
    return "retriever"


def _route_after_verifier(state: PipelineState) -> str:
    """Conditional edge after verifier."""
    settings = get_settings()

    if state.get("verification_passed"):
        return END

    if state.get("hallucination_detected"):
        return "escalation"

    accuracy = state.get("legal_accuracy_score", 1.0) or 1.0
    if accuracy < settings.verifier_accuracy_threshold:
        return "escalation"

    retry_count = state.get("generation_retry_count", 0)
    if retry_count < settings.max_generation_retries:
        return "generator"

    # Max retries exhausted
    return "escalation"


def _route_after_human(state: PipelineState) -> str:
    """Conditional edge after human review resume."""
    decision = state.get("human_decision", "")
    if decision == "APPROVED":
        return END
    if decision == "EDITED":
        return "verifier"
    # REJECTED or unknown
    return "escalation"


def build_pipeline_graph() -> StateGraph:
    """Construct the LangGraph StateGraph for the legal pipeline.

    Returns a compiled graph ready for invocation.
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("classifier", classifier_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("generator", generator_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("human_loop", human_loop_node)

    # Entry
    graph.add_edge(START, "classifier")

    # After classifier — conditional
    graph.add_conditional_edges(
        "classifier",
        _route_after_classifier,
        {
            "retriever": "retriever",
            "escalation": "escalation",
            "human_loop": "human_loop",
        },
    )

    # Linear flow: retriever → generator → verifier
    graph.add_edge("retriever", "generator")
    graph.add_edge("generator", "verifier")

    # After verifier — conditional
    graph.add_conditional_edges(
        "verifier",
        _route_after_verifier,
        {
            END: END,
            "generator": "generator",
            "escalation": "escalation",
        },
    )

    # Escalation → END
    graph.add_edge("escalation", END)

    # Human loop — interrupt_before so we pause BEFORE the node
    # After resume, route based on decision
    graph.add_conditional_edges(
        "human_loop",
        _route_after_human,
        {
            END: END,
            "verifier": "verifier",
            "escalation": "escalation",
        },
    )

    return graph


def compile_pipeline():
    """Build and compile the pipeline graph."""
    graph = build_pipeline_graph()
    return graph.compile(interrupt_before=["human_loop"])
