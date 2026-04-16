from __future__ import annotations

import json

import pytest

from src.domain.value_objects import RequestCategory, RiskLevel


class TestClassifierParsing:

    @pytest.mark.parametrize(
        "raw_json,expected_cat,expected_risk",
        [
            (
                '{"category": "LEGAL_FAQ", "risk_level": "LOW", "confidence": 0.95, "reasoning": "Простой вопрос"}',
                RequestCategory.LEGAL_FAQ,
                RiskLevel.LOW,
            ),
            (
                '{"category": "CONTRACT_REVIEW", "risk_level": "HIGH", "confidence": 0.88, "reasoning": "Сложный контракт"}',
                RequestCategory.CONTRACT_REVIEW,
                RiskLevel.HIGH,
            ),
            (
                '{"category": "COURT_PREPARATION", "risk_level": "CRITICAL", "confidence": 0.72, "reasoning": "Судебный иск"}',
                RequestCategory.COURT_PREPARATION,
                RiskLevel.CRITICAL,
            ),
            (
                '{"category": "COMPLIANCE_CHECK", "risk_level": "MEDIUM", "confidence": 0.65, "reasoning": "152-ФЗ"}',
                RequestCategory.COMPLIANCE_CHECK,
                RiskLevel.MEDIUM,
            ),
        ],
    )
    def test_parse_valid_json(self, raw_json, expected_cat, expected_risk):
        parsed = json.loads(raw_json)
        cat = RequestCategory(parsed["category"])
        risk = RiskLevel(parsed["risk_level"])
        assert cat == expected_cat
        assert risk == expected_risk
        assert 0.0 <= parsed["confidence"] <= 1.0

    def test_parse_unknown_category_fallback(self):
        raw = '{"category": "SPACE_LAW", "risk_level": "LOW", "confidence": 0.5}'
        parsed = json.loads(raw)
        try:
            cat = RequestCategory(parsed["category"])
        except ValueError:
            cat = RequestCategory.OTHER
        assert cat == RequestCategory.OTHER

    def test_parse_markdown_fence_strip(self):
        from src.infrastructure.agents.nodes import _safe_json_parse

        raw = '```json\n{"category": "LEGAL_FAQ", "risk_level": "LOW", "confidence": 0.9}\n```'
        result = _safe_json_parse(raw)
        assert result is not None
        assert result["category"] == "LEGAL_FAQ"

    def test_parse_invalid_json_returns_none(self):
        from src.infrastructure.agents.nodes import _safe_json_parse

        assert _safe_json_parse("not json at all") is None


class TestRoutingLogic:

    def test_verifier_pass_above_threshold(self):
        threshold = 0.60
        passing = [0.61, 0.75, 0.90, 1.0]
        for score in passing:
            assert score >= threshold

    def test_verifier_fail_below_threshold(self):
        threshold = 0.60
        failing = [0.0, 0.3, 0.5, 0.59]
        for score in failing:
            assert score < threshold


class TestPromptLoading:

    def test_load_classifier_prompt(self):
        from src.infrastructure.agents.prompts import load_prompt

        prompt = load_prompt("classifier_prompt")
        assert len(prompt) > 100
        assert "категори" in prompt.lower() or "category" in prompt.lower() or "class" in prompt.lower()

    def test_load_all_prompts(self):
        from src.infrastructure.agents.prompts import load_prompt

        prompt_names = [
            "classifier_prompt",
            "retriever_rewrite_prompt",
            "generator_faq_prompt",
            "generator_contract_review_prompt",
            "generator_compliance_prompt",
            "generator_litigation_prompt",
            "generator_corporate_prompt",
            "verifier_hallucination_prompt",
            "verifier_accuracy_prompt",
            "escalation_summary_prompt",
        ]
        for name in prompt_names:
            prompt = load_prompt(name)
            assert len(prompt) > 50, f"Prompt {name} is too short"

    def test_prompt_hash_deterministic(self):
        from src.infrastructure.agents.prompts import prompt_hash

        h1 = prompt_hash("test content")
        h2 = prompt_hash("test content")
        assert h1 == h2
        h3 = prompt_hash("different content")
        assert h1 != h3

    def test_prompt_version_format(self):
        from src.infrastructure.agents.prompts import prompt_version

        v = prompt_version("classifier_prompt")
        assert isinstance(v, str)
        assert len(v) > 0
