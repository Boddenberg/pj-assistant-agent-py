"""
Serviço do LLM-as-Judge — avalia qualidade de conversas.

Responsabilidade única: receber uma conversa e devolver uma avaliação.
NÃO conhece HTTP, rotas, ou FastAPI — é puro domínio.

Fluxo:
  1. Recebe EvaluationRequest (conversa com turnos)
  2. Formata a conversa em texto legível para o judge
  3. Chama o LLM com o prompt de avaliação
  4. Parseia o JSON retornado pelo LLM
  5. Calcula nota final (média ponderada)
  6. Determina veredito (PASS / SOFT_FAIL / HARD_FAIL)
  7. Retorna EvaluationResponse

Por que uma classe separada?
  - Testável isoladamente (mock do LLM)
  - Pode trocar de modelo sem mudar a rota
  - Pode virar um serviço separado no futuro
"""

from __future__ import annotations

import json
import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.core.config import settings
from src.core.models.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationMetadata,
    CriterionResult,
    Verdict,
)
from src.evaluation.prompts import (
    JUDGE_PROMPT_VERSION,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_PROMPT,
    CRITERIA_WEIGHTS,
    PASS_THRESHOLD,
    SOFT_FAIL_THRESHOLD,
)
from src.observability.logging import get_logger
from src.observability.metrics import estimate_cost

logger = get_logger("evaluation.evaluator")


class ConversationEvaluator:
    """
    Avaliador de conversas via LLM-as-Judge.

    Usa um LLM separado para avaliar a qualidade da conversa
    entre o cliente e o agente. O judge não participa da conversa
    original — ele é um observador imparcial.

    O modelo do judge é o MESMO do agente (gpt-4o-mini) por custo.
    Em produção: usar um modelo DIFERENTE (gpt-4o) para evitar
    viés de auto-avaliação.
    """

    def __init__(self) -> None:
        """Inicializa o LLM do judge."""
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0.0,          # Judge precisa ser determinístico
            api_key=settings.openai_api_key,
        )

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResponse:
        """
        Avalia uma conversa e retorna a avaliação completa.

        Args:
            request: Conversa com todos os turnos.

        Returns:
            EvaluationResponse com notas, veredito e sugestões.
        """
        start = time.perf_counter()

        logger.info(
            "🧑‍⚖️ [JUDGE] EVALUATION_STARTED — Iniciando avaliação",
            customer_id=request.customer_id,
            num_turns=len(request.conversation),
        )

        # ── 1. Formatar conversa para o judge ───────────────────────
        conversation_text = self._format_conversation(request)
        avg_latency = self._avg_latency(request)
        avg_confidence = self._avg_confidence(request)
        intents = self._unique_intents(request)
        is_onboarding = any(
            t.intent == "onboarding" or t.step is not None
            for t in request.conversation
        )

        rag_turns = sum(1 for t in request.conversation if t.contexts)
        has_rag = f"{rag_turns}/{len(request.conversation)}" if rag_turns else "Nenhum"

        user_prompt = JUDGE_USER_PROMPT.format(
            num_turns=len(request.conversation),
            conversation_text=conversation_text,
            avg_latency_ms=avg_latency,
            avg_confidence=avg_confidence,
            intents=", ".join(intents) if intents else "N/A",
            is_onboarding="Sim" if is_onboarding else "Não",
            has_rag_contexts=has_rag,
        )

        # ── 2. Chamar o LLM judge ──────────────────────────────────
        messages = [
            SystemMessage(content=JUDGE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await self._llm.ainvoke(messages)

        # ── 3. Extrair tokens ──────────────────────────────────────
        tokens_in = 0
        tokens_out = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_in = response.usage_metadata.get("input_tokens", 0)
            tokens_out = response.usage_metadata.get("output_tokens", 0)

        # ── 4. Parsear JSON do judge ───────────────────────────────
        raw = response.content.strip()
        # Remover ```json ... ``` se o LLM envolver em code block
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

        parsed = json.loads(raw)

        # ── 5. Montar critérios ────────────────────────────────────
        criteria = [
            CriterionResult(
                criterion=c["criterion"],
                score=c["score"],
                reasoning=c["reasoning"],
            )
            for c in parsed["criteria"]
        ]

        # ── 6. Calcular nota final (média ponderada) ──────────────
        overall_score = self._weighted_average(criteria)

        # ── 7. Determinar veredito ─────────────────────────────────
        verdict = self._determine_verdict(overall_score)

        duration_ms = (time.perf_counter() - start) * 1000
        cost = estimate_cost(tokens_in, tokens_out)

        logger.info(
            "🧑‍⚖️ [JUDGE] EVALUATION_COMPLETED — Avaliação finalizada",
            customer_id=request.customer_id,
            overall_score=round(overall_score, 2),
            verdict=verdict.value,
            num_criteria=len(criteria),
            tokens_used=tokens_in + tokens_out,
            cost_usd=cost,
            duration_ms=round(duration_ms, 2),
        )

        return EvaluationResponse(
            customer_id=request.customer_id,
            overall_score=round(overall_score, 2),
            verdict=verdict,
            criteria=criteria,
            summary=parsed.get("summary", ""),
            improvements=parsed.get("improvements", []),
            num_turns=len(request.conversation),
            metadata=EvaluationMetadata(
                judge_model=settings.llm_model,
                judge_prompt_version=JUDGE_PROMPT_VERSION,
                tokens_used=tokens_in + tokens_out,
                estimated_cost_usd=cost,
                evaluation_duration_ms=round(duration_ms, 2),
            ),
        )

    # ─── Helpers privados ───────────────────────────────────────────

    @staticmethod
    def _format_conversation(request: EvaluationRequest) -> str:
        """
        Formata a conversa como texto legível para o judge.

        Cada turno vira:
          --- Turno 1 (step: welcome, latência: 280ms) ---
          Cliente: "Quero abrir uma conta PJ"
          Agente: "Olá! Vou te ajudar..."
        """
        lines: list[str] = []
        for i, turn in enumerate(request.conversation, 1):
            meta_parts: list[str] = []
            if turn.step:
                meta_parts.append(f"step: {turn.step}")
            if turn.intent:
                meta_parts.append(f"intent: {turn.intent}")
            if turn.latency_ms is not None:
                meta_parts.append(f"latência: {turn.latency_ms:.0f}ms")
            if turn.confidence is not None:
                meta_parts.append(f"confiança: {turn.confidence:.2f}")

            meta = f" ({', '.join(meta_parts)})" if meta_parts else ""
            lines.append(f"--- Turno {i}{meta} ---")
            lines.append(f'Cliente: "{turn.query}"')
            lines.append(f'Agente: "{turn.answer}"')

            # Incluir chunks RAG usados (se houver)
            if turn.contexts:
                lines.append(f"Contextos RAG usados ({len(turn.contexts)} chunks):")
                for j, ctx in enumerate(turn.contexts, 1):
                    # Truncar chunks longos para não explodir o prompt
                    truncated = ctx[:500] + "..." if len(ctx) > 500 else ctx
                    lines.append(f"  [{j}] {truncated}")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _avg_latency(request: EvaluationRequest) -> float:
        """Calcula latência média dos turnos (0 se não informado)."""
        latencies = [
            t.latency_ms for t in request.conversation
            if t.latency_ms is not None
        ]
        return sum(latencies) / len(latencies) if latencies else 0.0

    @staticmethod
    def _avg_confidence(request: EvaluationRequest) -> float:
        """Calcula confiança média dos turnos (0 se não informado)."""
        confidences = [
            t.confidence for t in request.conversation
            if t.confidence is not None
        ]
        return sum(confidences) / len(confidences) if confidences else 0.0

    @staticmethod
    def _unique_intents(request: EvaluationRequest) -> list[str]:
        """Retorna intents únicas da conversa."""
        return list({
            t.intent for t in request.conversation
            if t.intent is not None
        })

    @staticmethod
    def _weighted_average(criteria: list[CriterionResult]) -> float:
        """
        Calcula média ponderada usando os pesos de CRITERIA_WEIGHTS.

        Fórmula:
          score = Σ(score_i × peso_i) / Σ(peso_i)

        Critérios desconhecidos (sem peso definido) recebem peso 1.
        """
        total_weighted = 0.0
        total_weight = 0

        for c in criteria:
            weight = CRITERIA_WEIGHTS.get(c.criterion, 1)
            total_weighted += c.score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total_weighted / total_weight

    @staticmethod
    def _determine_verdict(score: float) -> Verdict:
        """
        Determina veredito baseado na nota final.

          >= 7.0 → PASS (OK)
          >= 4.0 → SOFT_FAIL (melhorias necessárias)
          <  4.0 → HARD_FAIL (escalar para humano)
        """
        if score >= PASS_THRESHOLD:
            return Verdict.PASS
        if score >= SOFT_FAIL_THRESHOLD:
            return Verdict.SOFT_FAIL
        return Verdict.HARD_FAIL
