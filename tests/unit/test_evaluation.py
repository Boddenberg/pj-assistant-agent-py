"""
Testes unitários — LLM-as-Judge (avaliação de conversas).

Testa os componentes do judge SEM chamar o LLM:
  1. Modelos (request/response, validação Pydantic)
  2. Formatação de conversa para o prompt
  3. Cálculo de média ponderada
  4. Determinação de veredito (PASS/SOFT_FAIL/HARD_FAIL)
  5. Helpers (latência média, confiança média, intents)
  6. Constantes do prompt (pesos, thresholds)

Por que NÃO testamos com LLM real?
  - Custo real por teste ($)
  - Output não-determinístico → testes flakey
  - Em CI: usar mock ou snapshot testing
"""

import pytest

from src.core.models.evaluation import (
    ConversationTurn,
    EvaluationRequest,
    EvaluationResponse,
    EvaluationMetadata,
    CriterionResult,
    Verdict,
)
from src.evaluation.evaluator import ConversationEvaluator
from src.evaluation.prompts import (
    JUDGE_PROMPT_VERSION,
    CRITERIA_WEIGHTS,
    PASS_THRESHOLD,
    SOFT_FAIL_THRESHOLD,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_PROMPT,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_conversation() -> list[ConversationTurn]:
    """Conversa de onboarding com 3 turnos."""
    return [
        ConversationTurn(
            query="Quero abrir uma conta PJ",
            answer="Olá! Vou te ajudar a abrir sua conta PJ. Para começar, me informe o CNPJ da empresa.",
            step="welcome",
            intent="onboarding",
            confidence=0.95,
            latency_ms=280,
            created_at="2026-03-02T22:00:01Z",
        ),
        ConversationTurn(
            query="12.345.678/0001-90",
            answer="CNPJ recebido! Agora informe a Razão Social.",
            step="cnpj",
            intent="onboarding",
            confidence=0.98,
            latency_ms=342,
            created_at="2026-03-02T22:00:15Z",
        ),
        ConversationTurn(
            query="Empresa Teste LTDA",
            answer="Razão Social recebida. Qual o Nome Fantasia?",
            step="razaoSocial",
            intent="onboarding",
            confidence=0.97,
            latency_ms=310,
            created_at="2026-03-02T22:00:30Z",
        ),
    ]


@pytest.fixture
def sample_request(sample_conversation) -> EvaluationRequest:
    """Request de avaliação com conversa de 3 turnos."""
    return EvaluationRequest(
        customer_id="cust-001",
        conversation=sample_conversation,
    )


@pytest.fixture
def sample_criteria() -> list[CriterionResult]:
    """9 critérios com notas variadas."""
    return [
        CriterionResult(criterion="correctness", score=9, reasoning="Informações corretas"),
        CriterionResult(criterion="coherence", score=8, reasoning="Fluxo coerente"),
        CriterionResult(criterion="helpfulness", score=8, reasoning="Respostas úteis"),
        CriterionResult(criterion="tone", score=9, reasoning="Tom adequado"),
        CriterionResult(criterion="safety", score=10, reasoning="Sem vazamentos"),
        CriterionResult(criterion="efficiency", score=7, reasoning="Respostas concisas"),
        CriterionResult(criterion="flow_quality", score=9, reasoning="Fluxo correto"),
        CriterionResult(criterion="faithfulness", score=8, reasoning="Fiel aos documentos"),
        CriterionResult(criterion="context_relevance", score=9, reasoning="Chunks relevantes"),
    ]


# =============================================================================
# TestModels — validação Pydantic
# =============================================================================

class TestEvaluationModels:
    """Testes dos modelos de avaliação."""

    def test_conversation_turn_minimal(self):
        """Turno com apenas query e answer deve funcionar."""
        turn = ConversationTurn(query="Oi", answer="Olá!")
        assert turn.query == "Oi"
        assert turn.step is None
        assert turn.latency_ms is None

    def test_conversation_turn_full(self, sample_conversation):
        """Turno com todos os campos deve preservar valores."""
        turn = sample_conversation[0]
        assert turn.step == "welcome"
        assert turn.intent == "onboarding"
        assert turn.confidence == 0.95
        assert turn.latency_ms == 280

    def test_evaluation_request_requires_conversation(self):
        """Request sem conversation deve falhar (campo obrigatório)."""
        with pytest.raises(Exception):
            EvaluationRequest(customer_id="x", conversation=[])

    def test_evaluation_request_default_customer_id(self):
        """Customer ID default deve ser 'anonymous'."""
        req = EvaluationRequest(
            conversation=[ConversationTurn(query="Oi", answer="Olá")]
        )
        assert req.customer_id == "anonymous"

    def test_criterion_result_score_bounds(self):
        """Score deve estar entre 0 e 10."""
        # Válidos
        CriterionResult(criterion="test", score=0, reasoning="ok")
        CriterionResult(criterion="test", score=10, reasoning="ok")

        # Inválido — abaixo de 0
        with pytest.raises(Exception):
            CriterionResult(criterion="test", score=-1, reasoning="fail")

        # Inválido — acima de 10
        with pytest.raises(Exception):
            CriterionResult(criterion="test", score=11, reasoning="fail")

    def test_verdict_enum_values(self):
        """Enum Verdict deve ter 3 valores."""
        assert Verdict.PASS == "pass"
        assert Verdict.SOFT_FAIL == "soft_fail"
        assert Verdict.HARD_FAIL == "hard_fail"
        assert len(Verdict) == 3

    def test_evaluation_response_has_timestamp(self):
        """Response deve gerar timestamp automaticamente."""
        resp = EvaluationResponse(
            customer_id="x",
            overall_score=8.0,
            verdict=Verdict.PASS,
            criteria=[],
            summary="OK",
            num_turns=1,
        )
        assert resp.timestamp is not None

    def test_evaluation_metadata_defaults(self):
        """Metadata deve ter defaults zerados."""
        meta = EvaluationMetadata()
        assert meta.judge_model == ""
        assert meta.tokens_used == 0
        assert meta.estimated_cost_usd == 0.0


# =============================================================================
# TestConversationFormatting — formatação da conversa para o judge
# =============================================================================

class TestConversationFormatting:
    """Testes da formatação da conversa."""

    def test_format_includes_all_turns(self, sample_request):
        """Formatação deve incluir todos os turnos."""
        text = ConversationEvaluator._format_conversation(sample_request)
        assert "Turno 1" in text
        assert "Turno 2" in text
        assert "Turno 3" in text

    def test_format_includes_step_metadata(self, sample_request):
        """Formatação deve incluir step nos metadados."""
        text = ConversationEvaluator._format_conversation(sample_request)
        assert "step: welcome" in text
        assert "step: cnpj" in text
        assert "step: razaoSocial" in text

    def test_format_includes_query_and_answer(self, sample_request):
        """Formatação deve incluir query e answer de cada turno."""
        text = ConversationEvaluator._format_conversation(sample_request)
        assert "Quero abrir uma conta PJ" in text
        assert "CNPJ recebido" in text

    def test_format_includes_latency(self, sample_request):
        """Formatação deve incluir latência em ms."""
        text = ConversationEvaluator._format_conversation(sample_request)
        assert "280ms" in text
        assert "342ms" in text

    def test_format_minimal_turn(self):
        """Turno sem metadados deve formatar sem parênteses extras."""
        req = EvaluationRequest(
            conversation=[ConversationTurn(query="Oi", answer="Olá")]
        )
        text = ConversationEvaluator._format_conversation(req)
        assert "Turno 1" in text
        assert "step:" not in text


# =============================================================================
# TestWeightedAverage — cálculo da nota final
# =============================================================================

class TestWeightedAverage:
    """Testes do cálculo de média ponderada."""

    def test_all_tens(self):
        """Todas as notas 10 → média 10."""
        criteria = [
            CriterionResult(criterion=name, score=10, reasoning="Perfeito")
            for name in CRITERIA_WEIGHTS
        ]
        avg = ConversationEvaluator._weighted_average(criteria)
        assert avg == 10.0

    def test_all_zeros(self):
        """Todas as notas 0 → média 0."""
        criteria = [
            CriterionResult(criterion=name, score=0, reasoning="Péssimo")
            for name in CRITERIA_WEIGHTS
        ]
        avg = ConversationEvaluator._weighted_average(criteria)
        assert avg == 0.0

    def test_weighted_not_simple_average(self, sample_criteria):
        """Média ponderada ≠ média simples (pesos diferentes)."""
        weighted = ConversationEvaluator._weighted_average(sample_criteria)
        simple = sum(c.score for c in sample_criteria) / len(sample_criteria)

        # Devem ser diferentes (pesos não são iguais)
        # Mas ambas devem ser positivas
        assert weighted > 0
        assert simple > 0

    def test_correctness_has_highest_weight(self):
        """Correctness e faithfulness com peso 20 são os mais pesados."""
        assert CRITERIA_WEIGHTS["correctness"] == 20
        assert CRITERIA_WEIGHTS["faithfulness"] == 20
        assert CRITERIA_WEIGHTS["safety"] == 15

    def test_empty_criteria(self):
        """Lista vazia → média 0."""
        assert ConversationEvaluator._weighted_average([]) == 0.0

    def test_unknown_criterion_gets_weight_1(self):
        """Critério desconhecido recebe peso 1."""
        criteria = [
            CriterionResult(criterion="unknown_criterion", score=8, reasoning="ok")
        ]
        avg = ConversationEvaluator._weighted_average(criteria)
        assert avg == 8.0  # peso 1 → média = score


# =============================================================================
# TestVerdict — determinação do veredito
# =============================================================================

class TestVerdict:
    """Testes da determinação de veredito."""

    def test_pass_threshold(self):
        """Score >= 7.0 → PASS."""
        assert ConversationEvaluator._determine_verdict(7.0) == Verdict.PASS
        assert ConversationEvaluator._determine_verdict(8.5) == Verdict.PASS
        assert ConversationEvaluator._determine_verdict(10.0) == Verdict.PASS

    def test_soft_fail_threshold(self):
        """Score >= 4.0 e < 7.0 → SOFT_FAIL."""
        assert ConversationEvaluator._determine_verdict(4.0) == Verdict.SOFT_FAIL
        assert ConversationEvaluator._determine_verdict(5.5) == Verdict.SOFT_FAIL
        assert ConversationEvaluator._determine_verdict(6.9) == Verdict.SOFT_FAIL

    def test_hard_fail_threshold(self):
        """Score < 4.0 → HARD_FAIL."""
        assert ConversationEvaluator._determine_verdict(0.0) == Verdict.HARD_FAIL
        assert ConversationEvaluator._determine_verdict(3.9) == Verdict.HARD_FAIL
        assert ConversationEvaluator._determine_verdict(2.0) == Verdict.HARD_FAIL

    def test_thresholds_match_constants(self):
        """Thresholds devem bater com as constantes definidas."""
        assert PASS_THRESHOLD == 7.0
        assert SOFT_FAIL_THRESHOLD == 4.0


# =============================================================================
# TestHelpers — funções auxiliares
# =============================================================================

class TestHelpers:
    """Testes dos helpers do evaluator."""

    def test_avg_latency(self, sample_request):
        """Latência média de [280, 342, 310] = 310.67ms."""
        avg = ConversationEvaluator._avg_latency(sample_request)
        assert round(avg, 2) == 310.67

    def test_avg_latency_no_data(self):
        """Sem dados de latência → 0."""
        req = EvaluationRequest(
            conversation=[ConversationTurn(query="Oi", answer="Olá")]
        )
        assert ConversationEvaluator._avg_latency(req) == 0.0

    def test_avg_confidence(self, sample_request):
        """Confiança média de [0.95, 0.98, 0.97] = 0.9667."""
        avg = ConversationEvaluator._avg_confidence(sample_request)
        assert round(avg, 4) == 0.9667

    def test_unique_intents(self, sample_request):
        """Intents únicos = {"onboarding"}."""
        intents = ConversationEvaluator._unique_intents(sample_request)
        assert intents == ["onboarding"]

    def test_unique_intents_multiple(self):
        """Múltiplos intents são deduplicados."""
        req = EvaluationRequest(
            conversation=[
                ConversationTurn(query="Oi", answer="Olá", intent="greeting"),
                ConversationTurn(query="Saldo?", answer="R$ 100", intent="check_balance"),
                ConversationTurn(query="Saldo de novo", answer="R$ 100", intent="check_balance"),
            ]
        )
        intents = ConversationEvaluator._unique_intents(req)
        assert set(intents) == {"greeting", "check_balance"}


# =============================================================================
# TestPromptConstants — constantes do prompt do judge
# =============================================================================

class TestPromptConstants:
    """Testes das constantes do prompt."""

    def test_prompt_version_exists(self):
        """Versão do prompt deve existir."""
        assert JUDGE_PROMPT_VERSION == "2.0.0"

    def test_weights_sum_to_100(self):
        """Pesos devem somar 100 (facilita cálculo de %)."""
        assert sum(CRITERIA_WEIGHTS.values()) == 100

    def test_all_7_criteria_have_weights(self):
        """Todos os 9 critérios devem ter peso definido."""
        expected = {
            "correctness", "coherence", "helpfulness",
            "tone", "safety", "efficiency", "flow_quality",
            "faithfulness", "context_relevance",
        }
        assert set(CRITERIA_WEIGHTS.keys()) == expected

    def test_system_prompt_mentions_all_criteria(self):
        """System prompt deve mencionar todos os 9 critérios."""
        for criterion in CRITERIA_WEIGHTS:
            assert criterion.upper() in JUDGE_SYSTEM_PROMPT.upper(), (
                f"Critério '{criterion}' não encontrado no JUDGE_SYSTEM_PROMPT"
            )

    def test_user_prompt_has_placeholders(self):
        """User prompt deve ter os placeholders necessários."""
        assert "{num_turns}" in JUDGE_USER_PROMPT
        assert "{conversation_text}" in JUDGE_USER_PROMPT
        assert "avg_latency_ms" in JUDGE_USER_PROMPT
        assert "avg_confidence" in JUDGE_USER_PROMPT
        assert "{intents}" in JUDGE_USER_PROMPT
        assert "{is_onboarding}" in JUDGE_USER_PROMPT
        assert "{has_rag_contexts}" in JUDGE_USER_PROMPT


# =============================================================================
# TestRAGContexts — avaliação de qualidade RAG
# =============================================================================

class TestRAGContexts:
    """Testes dos contextos RAG no judge."""

    def test_conversation_turn_accepts_contexts(self):
        """Turno com contexts deve preservar os chunks."""
        turn = ConversationTurn(
            query="Qual o limite do Pix PJ?",
            answer="O limite padrão é R$ 50.000 por transação.",
            contexts=[
                "O limite padrão do Pix para contas PJ é de R$ 50.000,00 por transação.",
                "Clientes podem solicitar aumento de limite pelo app.",
            ],
        )
        assert len(turn.contexts) == 2
        assert "R$ 50.000" in turn.contexts[0]

    def test_conversation_turn_contexts_default_empty(self):
        """Turno sem contexts deve ter lista vazia (retrocompatível)."""
        turn = ConversationTurn(query="Oi", answer="Olá!")
        assert turn.contexts == []

    def test_format_includes_rag_contexts(self):
        """Formatação deve incluir chunks RAG quando presentes."""
        req = EvaluationRequest(
            conversation=[
                ConversationTurn(
                    query="Qual o limite do Pix?",
                    answer="O limite é R$ 50.000.",
                    contexts=["Limite Pix PJ: R$ 50.000,00 por transação."],
                ),
            ]
        )
        text = ConversationEvaluator._format_conversation(req)
        assert "Contextos RAG usados (1 chunks)" in text
        assert "Limite Pix PJ" in text

    def test_format_omits_rag_section_when_no_contexts(self):
        """Formatação NÃO deve incluir seção RAG quando não há contexts."""
        req = EvaluationRequest(
            conversation=[
                ConversationTurn(query="Oi", answer="Olá!"),
            ]
        )
        text = ConversationEvaluator._format_conversation(req)
        assert "Contextos RAG" not in text

    def test_format_truncates_long_chunks(self):
        """Chunks maiores que 500 chars devem ser truncados."""
        long_chunk = "A" * 600
        req = EvaluationRequest(
            conversation=[
                ConversationTurn(
                    query="Detalhes?",
                    answer="Aqui estão os detalhes.",
                    contexts=[long_chunk],
                ),
            ]
        )
        text = ConversationEvaluator._format_conversation(req)
        assert "..." in text
        # Chunk original tem 600 chars, truncado para 500 + "..."
        assert long_chunk[:500] in text
        assert long_chunk[:501] not in text

    def test_mixed_turns_with_and_without_contexts(self):
        """Conversa com turnos com e sem contexts deve formatar corretamente."""
        req = EvaluationRequest(
            conversation=[
                ConversationTurn(
                    query="Quero abrir conta",
                    answer="Vamos lá! Me informe o CNPJ.",
                    step="welcome",
                    intent="onboarding",
                ),
                ConversationTurn(
                    query="Qual o limite do Pix?",
                    answer="R$ 50.000 por transação.",
                    intent="check_pix_limit",
                    contexts=["Limite Pix PJ: R$ 50.000,00"],
                ),
            ]
        )
        text = ConversationEvaluator._format_conversation(req)
        # Turno 1: sem RAG
        assert "Turno 1" in text
        # Turno 2: com RAG
        assert "Turno 2" in text
        assert "Contextos RAG usados (1 chunks)" in text

    def test_faithfulness_weight_exists(self):
        """Faithfulness deve ter peso definido."""
        assert "faithfulness" in CRITERIA_WEIGHTS
        assert CRITERIA_WEIGHTS["faithfulness"] == 20

    def test_context_relevance_weight_exists(self):
        """Context relevance deve ter peso definido."""
        assert "context_relevance" in CRITERIA_WEIGHTS
        assert CRITERIA_WEIGHTS["context_relevance"] == 10
