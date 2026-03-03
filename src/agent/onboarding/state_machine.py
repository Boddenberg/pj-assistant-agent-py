"""
State Machine do onboarding — determina o campo atual e próximo.

Este módulo contém a lógica central do fluxo de onboarding:
  - OnboardingState: dataclass com o estado completo
  - determine_current_field: analisa history + query → OnboardingState

Fluxo:
  1. Pré-carrega collected_data (campos de sessão anterior, se houver)
  2. Detecta restart (cliente quer recomeçar)
  3. Detecta post-max-retries (fluxo anterior encerrou por excesso de erros)
  4. Percorre history para encontrar último step validado
  5. Verifica limite de retries
  6. Valida formato inline (guard rail)
  7. Avança para o próximo campo
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.agent.onboarding.fields import (
    OnboardingField,
    FIELD_SEQUENCE,
    DATA_FIELDS,
    FIELD_LABELS,
    MAX_RETRIES,
)
from src.agent.onboarding.validators import validate_field_format
from src.agent.onboarding.intent import _is_restart_request
from src.observability.logging import get_logger

logger = get_logger("onboarding")


@dataclass
class OnboardingState:
    """Estado do onboarding derivado do history enriquecido."""
    step: OnboardingField               # step que o cliente ACABOU de responder
    next_step: OnboardingField          # step que o agente vai PEDIR agora
    collected: dict[str, str] = field(default_factory=dict)
    is_complete: bool = False
    has_validation_error: bool = False
    validation_error: str = ""
    validation_error_source: str = ""   # "bfa" se veio do BFA, "inline" se validação local
    field_value: str = ""               # valor cru que o cliente enviou
    retry_count: int = 0                # quantas vezes errou o step atual
    max_retries_exceeded: bool = False   # se excedeu o limite de retries
    is_restart: bool = False             # se o cliente pediu para recomeçar


def _get_next_field(current: OnboardingField) -> OnboardingField:
    """Retorna o próximo campo na sequência após 'current'."""
    idx = FIELD_SEQUENCE.index(current)
    if idx + 1 < len(FIELD_SEQUENCE):
        return FIELD_SEQUENCE[idx + 1]
    return OnboardingField.COMPLETED


def determine_current_field(
    history: list[dict],
    current_query: str,
    validation_error: str = "",
    collected_data: list[dict] | None = None,
) -> OnboardingState:
    """
    Determina o estado do onboarding com base no history enriquecido.

    O BFA envia cada turno com step + validated. O agente:
      1. Pré-carrega collected_data (campos de sessão anterior, se houver)
      2. Percorre o history para encontrar o último step validado
      3. Determina o próximo step
      4. Valida formato inline da query atual
      5. Conta retries consecutivos no mesmo step

    Args:
        history: Turnos com {query, answer, step, validated}
        current_query: Mensagem atual do cliente
        validation_error: Erro do BFA se rejeitou o último campo
        collected_data: Campos já coletados em sessão anterior (retomada).
                        Lista de dicts com {key, value, validated}.

    Returns:
        OnboardingState completo
    """
    collected: dict[str, str] = {}

    # ─── Pre-seed: campos de sessão anterior (collected_data) ──────
    # O BFA pode enviar campos já validados de uma sessão anterior
    # para que o onboarding retome de onde parou, sem re-coletar.
    if collected_data:
        for item in collected_data:
            key = item.get("key", "")
            value = item.get("value", "")
            validated = item.get("validated", True)
            if key and value and validated:
                # Só aceitar se é um campo válido do onboarding
                try:
                    OnboardingField(key)
                    collected[key] = value
                except ValueError:
                    logger.warning(
                        "⚠️ [ONBOARDING] Unknown field in collected_data — ignoring",
                        key=key,
                    )

        if collected:
            logger.info(
                "📋 [ONBOARDING] PRE-SEEDED from collected_data (session resumption)",
                collected_count=len(collected),
                collected_fields=list(collected.keys()),
            )

    # ─── Sem history → primeira mensagem ou retomada ───────────────
    if not history:
        if collected:
            # Retomada: temos campos pré-carregados, determinar o próximo
            # Percorre apenas campos de dados (sem WELCOME e COMPLETED)
            last_collected_step: OnboardingField | None = None
            for fld in DATA_FIELDS:
                if fld.value in collected:
                    last_collected_step = fld
                else:
                    break

            if last_collected_step:
                next_step = _get_next_field(last_collected_step)
                if next_step == OnboardingField.COMPLETED:
                    return OnboardingState(
                        step=OnboardingField.COMPLETED,
                        next_step=OnboardingField.COMPLETED,
                        collected=collected,
                        is_complete=True,
                        field_value=current_query,
                    )
                # A "step" aqui é o welcome pois é a primeira mensagem,
                # mas o next_step avança para o próximo campo pendente.
                logger.info(
                    "🔄 [ONBOARDING] RESUMING — Retomando de sessão anterior",
                    collected_count=len(collected),
                    next_step=next_step.value,
                )
                return OnboardingState(
                    step=OnboardingField.WELCOME,
                    next_step=next_step,
                    collected=collected,
                    field_value=current_query,
                )

        return OnboardingState(
            step=OnboardingField.WELCOME,
            next_step=OnboardingField.WELCOME,
            field_value=current_query,
        )

    # ─── Restart: cliente pediu para recomeçar ─────────────────────
    # IMPORTANTE: Verificar restart ANTES de qualquer retry/max_retries check.
    # Isso evita que o cliente fique preso em loop quando erra muitas vezes
    # e tenta recomeçar com "abrir conta".
    # O BFA deve limpar a sessão ao receber step=welcome + is_restart=True.
    if _is_restart_request(current_query):
        has_previous_onboarding = any(
            turn.get("step") is not None for turn in history
        )
        if has_previous_onboarding:
            logger.info(
                "🔄 [ONBOARDING] RESTART — Cliente pediu para recomeçar o onboarding",
                query=current_query,
            )
            return OnboardingState(
                step=OnboardingField.WELCOME,
                next_step=OnboardingField.WELCOME,
                field_value=current_query,
                is_restart=True,
            )

    # ─── Detectar max_retries anterior ────────────────────────────
    # Se o último answer no history indica max_retries (contém "após algumas
    # tentativas" ou "não conseguimos validar"), qualquer nova mensagem é
    # tratada como restart — o max_retries JÁ encerrou o fluxo.
    # O cliente que volta a escrever quer continuar.
    #
    # Também detecta se o BFA marcou max_retries_exceeded=True no último turno
    # (caso o BFA tenha adicionado ao history mesmo sem dever).
    if history:
        last_turn = history[-1]
        last_answer = last_turn.get("answer", "")
        max_retries_phrases = [
            "após algumas tentativas",
            "não conseguimos validar",
            "limite de tentativas",
            "recomeçamos",            # new message format
            "é só me enviar",         # new message format
        ]
        is_post_max_retries = any(
            phrase in last_answer.lower() for phrase in max_retries_phrases
        )

        # Fallback: se o BFA adicionou max_retries_exceeded ao turno
        if not is_post_max_retries and last_turn.get("max_retries_exceeded"):
            is_post_max_retries = True

        if is_post_max_retries:
            logger.info(
                "🔄 [ONBOARDING] RESTART (post max_retries) — Reiniciando após max retries",
                query=current_query,
                last_answer_preview=last_answer[:100],
            )
            return OnboardingState(
                step=OnboardingField.WELCOME,
                next_step=OnboardingField.WELCOME,
                field_value=current_query,
                is_restart=True,
            )

    # ─── Percorrer o history para encontrar o estado ───────────────
    # Estratégia: identificar o último step VALIDADO pelo BFA.
    # O próximo step é o seguinte na sequência.
    last_validated_step: OnboardingField | None = None
    last_rejected_step: OnboardingField | None = None
    retry_count = 0

    for turn in history:
        step_str = turn.get("step")
        validated = turn.get("validated")

        if step_str is None:
            # Turno sem step (ex: welcome, saudação) → ignorar
            continue

        # Converter string para enum
        try:
            step_enum = OnboardingField(step_str)
        except ValueError:
            continue

        if validated is True:
            last_validated_step = step_enum
            collected[step_enum.value] = turn["query"]
            retry_count = 0  # resetar contagem ao validar
            last_rejected_step = None  # resetar rejeição
        elif validated is False:
            # Só contar rejeições do step ATUAL (step seguinte ao último validado).
            # Rejeições de steps anteriores já foram resolvidas.
            retry_count += 1
            last_rejected_step = step_enum

    # ─── Determinar o step que o cliente está respondendo AGORA ────
    if last_validated_step is None:
        # Nenhum campo validado ainda → cliente está respondendo CNPJ
        current_step = OnboardingField.CNPJ
    else:
        current_step = _get_next_field(last_validated_step)

    logger.debug(
        "📋 [ONBOARDING] HISTORY_TRAVERSED",
        last_validated_step=last_validated_step.value if last_validated_step else None,
        current_step=current_step.value,
        retry_count_from_history=retry_count,
        collected_count=len(collected),
        current_query_preview=current_query[:30],
    )

    # Se já completou todos os campos
    if current_step == OnboardingField.COMPLETED:
        return OnboardingState(
            step=OnboardingField.COMPLETED,
            next_step=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
            field_value=current_query,
        )

    # ─── Fallback: BFA rejeitou (validated=false) sem validation_error ─
    # Se o último turno do history tem validated=false e o BFA NÃO enviou
    # validation_error (string vazia), gerar uma mensagem genérica
    # contextual ao campo — para que a resposta não pareça "chumbada".
    if not validation_error and last_rejected_step is not None:
        label = FIELD_LABELS.get(current_step, current_step.value)
        validation_error = (
            f"O **{label}** informado não foi aceito pelo sistema. "
            f"Verifique o dado e tente novamente."
        )
        logger.info(
            "⚠️ [ONBOARDING] BFA rejected without error message — using fallback",
            step=current_step.value,
            last_rejected_step=last_rejected_step.value,
            retry_count=retry_count,
        )

    # ─── Verificar limite de retries ───────────────────────────────
    # retry_count já contém todas as tentativas falhadas do history.
    # validation_error indica que o BFA rejeitou a última tentativa —
    # mas essa rejeição já está contada como validated=False no history.
    # NÃO incrementar novamente para evitar double-counting.

    logger.debug(
        "📋 [ONBOARDING] RETRY_CHECK",
        step=current_step.value,
        retry_count=retry_count,
        max_retries=MAX_RETRIES,
        has_validation_error=bool(validation_error),
        has_last_rejected_step=last_rejected_step is not None,
    )

    if retry_count >= MAX_RETRIES:
        # Safety net: se mesmo depois de todos os checks anteriores
        # ainda chegou aqui com um pedido de restart, forçar restart
        # para não prender o cliente em loop infinito.
        if _is_restart_request(current_query):
            logger.info(
                "🔄 [ONBOARDING] RESTART (safety net in max_retries) — Forçando restart",
                step=current_step.value,
                retry_count=retry_count,
                query=current_query,
            )
            return OnboardingState(
                step=OnboardingField.WELCOME,
                next_step=OnboardingField.WELCOME,
                field_value=current_query,
                is_restart=True,
            )

        logger.info(
            "🚫 [ONBOARDING] Max retries exceeded",
            step=current_step.value,
            retry_count=retry_count,
            max_retries=MAX_RETRIES,
        )
        return OnboardingState(
            step=current_step,
            next_step=current_step,
            collected=collected,
            has_validation_error=True,
            validation_error=validation_error or "Limite de tentativas excedido",
            validation_error_source="bfa" if validation_error else "inline",
            field_value=current_query,
            retry_count=retry_count,
            max_retries_exceeded=True,
        )

    # ─── Se o BFA rejeitou → pedir o mesmo campo de novo ──────────
    if validation_error:
        return OnboardingState(
            step=current_step,
            next_step=current_step,
            collected=collected,
            has_validation_error=True,
            validation_error=validation_error,
            validation_error_source="bfa",
            field_value=current_query,
            retry_count=retry_count,
        )

    # ─── Validação inline de formato (guard rail) ──────────────────
    format_error = validate_field_format(current_step, current_query)
    if format_error:
        retry_count += 1

        logger.info(
            "⚠️ [ONBOARDING] Inline validation failed",
            step=current_step.value,
            value_preview=current_query[:20],
            error_preview=format_error[:80],
            retry_count_after_increment=retry_count,
            max_retries=MAX_RETRIES,
            will_exceed_max=retry_count >= MAX_RETRIES,
        )

        if retry_count >= MAX_RETRIES:
            return OnboardingState(
                step=current_step,
                next_step=current_step,
                collected=collected,
                has_validation_error=True,
                validation_error=format_error,
                validation_error_source="inline",
                field_value=current_query,
                retry_count=retry_count,
                max_retries_exceeded=True,
            )

        return OnboardingState(
            step=current_step,
            next_step=current_step,
            collected=collected,
            has_validation_error=True,
            validation_error=format_error,
            validation_error_source="inline",
            field_value=current_query,
            retry_count=retry_count,
        )

    # ─── Formato válido → avançar ──────────────────────────────────
    collected[current_step.value] = current_query
    next_step = _get_next_field(current_step)

    is_complete = next_step == OnboardingField.COMPLETED

    logger.info(
        "📋 [ONBOARDING] State determined",
        step=current_step.value,
        next_step=next_step.value,
        collected_count=len(collected),
        is_complete=is_complete,
    )

    return OnboardingState(
        step=current_step,
        next_step=next_step,
        collected=collected,
        is_complete=is_complete,
        field_value=current_query,
    )
