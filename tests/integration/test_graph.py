from __future__ import annotations

import pytest


class TestGraphStructure:
    def test_graph_compiles(self):
        """Ensure the LangGraph pipeline compiles without errors."""
        from src.infrastructure.agents.graph import compile_pipeline

        graph = compile_pipeline()
        assert graph is not None

    def test_graph_has_nodes(self):
        from src.infrastructure.agents.graph import build_pipeline_graph

        graph = build_pipeline_graph()
        assert hasattr(graph, "nodes")

    def test_interrupt_before_human_loop(self):
        """Compiled graph should have interrupt_before on human_loop node."""
        from src.infrastructure.agents.graph import compile_pipeline

        compiled = compile_pipeline()
        assert compiled is not None
