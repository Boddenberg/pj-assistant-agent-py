"""
Geradores de resposta — respostas determinísticas e contexto LLM.

Dois geradores:
  build_onboarding_response → Resposta FINAL para o cliente (sem LLM)
  build_onboarding_context  → Instrução injetada no prompt do LLM (legado)

O response builder é o gerador principal. Ele interpreta o OnboardingState
e produz a mensagem que o cliente vai ver no chat. Sem LLM = sem custo,
sem hallucination, latência mínima.

O context builder é mantido para compatibilidade — caso algum fluxo
futuro precise passar pelo LLM.
"""

from __future__ import annotations

from src.agent.onboarding.fields import (
    OnboardingField,
    DATA_FIELDS,
    FIELD_PROMPTS,
    FIELD_LABELS,
    FIELD_FORMAT_HINTS,
    MAX_RETRIES,
)
from src.agent.onboarding.state_machine import OnboardingState


def build_onboarding_response(state: OnboardingState) -> str:
    """
    Gera a resposta FINAL para o cliente — determinística, sem LLM.

    Returns:
        String com a resposta pronta para o cliente.
    """
    # ─── Max retries excedido → encerrar com mensagem amigável ─────
    if state.max_retries_exceeded:
        label = FIELD_LABELS.get(state.step, state.step.value)
        return (
            f"Não conseguimos validar o **{label}** após {MAX_RETRIES} tentativas. 😕\n\n"
            "Mas sem problemas! Quando estiver com os dados corretos em mãos, "
            "é só me enviar qualquer mensagem e recomeçamos. 😊"
        )

    # ─── Restart → recomeçar com welcome ───────────────────────────
    if state.is_restart:
        return FIELD_PROMPTS[OnboardingField.WELCOME]

    # ─── Onboarding completo ──────────────────────────────────────
    if state.is_complete:
        lines = ["Parabéns! 🎉 Sua conta PJ foi aberta com sucesso!\n"]
        lines.append("Aqui está o resumo do cadastro:\n")
        for fld in DATA_FIELDS:
            if fld in (OnboardingField.PASSWORD, OnboardingField.PASSWORD_CONFIRMATION):
                continue
            value = state.collected.get(fld.value, "—")
            label = FIELD_LABELS.get(fld, fld.value)
            lines.append(f"- **{label}**: {value}")
        lines.append(
            "\nSeu cadastro será processado e em breve sua conta "
            "PJ estará pronta! 🚀\n\n"
            "Se precisar de mais alguma coisa, é só avisar! 😊"
        )
        return "\n".join(lines)

    # ─── Retomada de sessão (welcome com collected_data) ───────────
    # Se step é welcome, tem campos coletados, e o next_step NÃO é welcome,
    # significa que estamos retomando de uma sessão anterior.
    if (
        state.step == OnboardingField.WELCOME
        and state.collected
        and state.next_step != OnboardingField.WELCOME
    ):
        lines = [
            "Que bom que voltou! 😊 Vi que já temos alguns dados do seu cadastro anterior.\n"
        ]
        lines.append("**Dados já coletados:**")
        for fld in DATA_FIELDS:
            if fld.value in state.collected:
                label = FIELD_LABELS.get(fld, fld.value)
                # Mascarar valores sensíveis no resumo
                value = state.collected[fld.value]
                if fld == OnboardingField.REPRESENTANTE_CPF:
                    value = value[:3] + ".***.***-" + value[-2:] if len(value) >= 5 else "***"
                elif fld == OnboardingField.EMAIL:
                    parts = value.split("@")
                    if len(parts) == 2:
                        value = parts[0][:2] + "***@" + parts[1]
                lines.append(f"  ✅ {label}: {value}")

        lines.append("")  # linha em branco

        # Pedir o próximo campo pendente
        next_prompt = FIELD_PROMPTS.get(state.next_step, "")
        if next_prompt:
            # Remover confirmação do campo anterior (ex: "CNPJ recebido! ✅\n\n")
            # e substituir por mensagem de retomada
            label = FIELD_LABELS.get(state.next_step, state.next_step.value)
            hint = FIELD_FORMAT_HINTS.get(state.next_step, "")
            lines.append(f"Vamos continuar de onde paramos! Agora preciso do **{label}**.")
            if hint:
                lines.append(f"{hint}")
        else:
            label = FIELD_LABELS.get(state.next_step, state.next_step.value)
            lines.append(f"Vamos continuar! Agora preciso do **{label}**.")

        return "\n".join(lines)

    # ─── Erro de validação → pedir de novo ─────────────────────────
    if state.has_validation_error:
        label = FIELD_LABELS.get(state.next_step, state.next_step.value)
        hint = FIELD_FORMAT_HINTS.get(state.next_step, "")
        error_msg = state.validation_error
        remaining = MAX_RETRIES - state.retry_count

        # Se o erro veio do BFA (validation_error_source == "bfa"),
        # adaptar para tom humano se for mensagem técnica.
        if state.validation_error_source == "bfa" and error_msg:
            # Adapta mensagens técnicas para tom humano
            msg = error_msg
            # Exemplo: "já está cadastrado no sistema" → mais amigável
            if "já está cadastrado" in msg:
                msg = f"O {label} informado já está cadastrado. Por favor, informe outro {label.lower()}."
            elif "inválido" in msg:
                msg = f"O {label} informado não foi aceito. Verifique o dado e tente novamente."
            elif "não confere" in msg or "não corresponde" in msg:
                msg = f"A confirmação não corresponde ao valor informado. Tente novamente."
            # Se não bater nenhum padrão, mantém o texto original
            lines = [f"⚠️ {msg}"]
            if hint:
                lines.append(f"\n💡 {hint}")
            if remaining <= 2:
                lines.append(f"\n⏳ Você ainda tem **{remaining}** tentativa(s).")
            lines.append(f"\nPor favor, informe o **{label}** novamente:")
            return "\n".join(lines)

        # Erro da validação inline (formato)
        lines = [f"⚠️ {error_msg}"]
        if hint and hint not in error_msg:
            lines.append(f"\n💡 {hint}")
        if remaining <= 2:
            lines.append(f"\n⏳ Você ainda tem **{remaining}** tentativa(s).")
        lines.append(f"\nPor favor, informe o **{label}** novamente:")
        return "\n".join(lines)

    # ─── Campo normal → usar template ─────────────────────────────
    prompt_text = FIELD_PROMPTS.get(state.next_step, "")
    if prompt_text:
        return prompt_text

    label = FIELD_LABELS.get(state.next_step, state.next_step.value)
    return f"Agora preciso do **{label}**."


def build_onboarding_context(state: OnboardingState) -> str:
    """
    Gera instrução determinística injetada no prompt do LLM.

    Inclui:
      - Campos já coletados (para o LLM saber o progresso)
      - Qual campo pedir agora (com template)
      - Reforço para NÃO pular, NÃO mudar, NÃO inventar campos
    """
    lines: list[str] = []
    lines.append("\n## [INSTRUÇÃO DE ONBOARDING — SIGA À RISCA]")
    lines.append("IMPORTANTE: NÃO chame search_knowledge_base para onboarding.")
    lines.append("NÃO pule campos. NÃO peça um campo diferente do indicado abaixo.")

    # ── Progresso: campos já coletados ─────────────────────────────
    if state.collected:
        lines.append("\n### Campos já coletados:")
        for fld in DATA_FIELDS:
            if fld.value in state.collected:
                label = FIELD_LABELS.get(fld, fld.value)
                lines.append(f"  ✅ {label}")

    # ── Campos restantes ───────────────────────────────────────────
    remaining = [
        FIELD_LABELS.get(fld, fld.value)
        for fld in DATA_FIELDS
        if fld.value not in state.collected
        and fld != state.next_step
    ]
    if remaining and not state.is_complete:
        lines.append(f"\n### Campos restantes depois deste: {', '.join(remaining)}")

    # ── Onboarding completo ────────────────────────────────────────
    if state.is_complete:
        lines.append("\n### ✅ ONBOARDING COMPLETO!")
        lines.append("Todos os dados foram coletados com sucesso.")
        lines.append("Parabenize o cliente e mostre o resumo.")
        lines.append("\nResumo dos dados (NÃO inclua a senha):")
        for fld in DATA_FIELDS:
            if fld in (OnboardingField.PASSWORD, OnboardingField.PASSWORD_CONFIRMATION):
                continue
            value = state.collected.get(fld.value, "—")
            label = FIELD_LABELS.get(fld, fld.value)
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    # ── Erro de validação ──────────────────────────────────────────
    if state.has_validation_error:
        label = FIELD_LABELS.get(state.next_step, state.next_step.value)
        hint = FIELD_FORMAT_HINTS.get(state.next_step, "")
        lines.append(f"\n### ⚠️ Dado rejeitado: {label}")
        if state.validation_error_source == "bfa":
            lines.append(f"Erro do sistema bancário: {state.validation_error}")
        else:
            lines.append(f"Erro de formato: {state.validation_error}")
        if hint:
            lines.append(f"Formato esperado: {hint}")
        lines.append(f"\n→ AÇÃO OBRIGATÓRIA: Peça SOMENTE o campo **{label}**.")
        lines.append(f"⛔ NÃO peça nenhum outro campo. APENAS **{label}**.")
        return "\n".join(lines)

    # ── Campo normal ───────────────────────────────────────────────
    prompt_text = FIELD_PROMPTS.get(state.next_step, "")
    label = FIELD_LABELS.get(state.next_step, state.next_step.value)
    lines.append(f"\n### Próximo campo a pedir: **{label}**")
    lines.append(f'\nMensagem sugerida:\n"{prompt_text}"')
    lines.append(f"\n→ AÇÃO OBRIGATÓRIA: Peça SOMENTE o campo **{label}**.")
    lines.append(f"⛔ NÃO peça nenhum outro campo. APENAS **{label}**.")
    return "\n".join(lines)
