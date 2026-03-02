"""
Testes unitários — onboarding campo-a-campo (v8.1.0).

Testa o módulo de onboarding conversacional que:
  - Determina qual campo pedir com base no histórico
  - Gera instruções determinísticas para o LLM (build_onboarding_context)
  - Gera respostas determinísticas SEM LLM (build_onboarding_response)
  - Detecta intenção de abertura de conta

O agente NÃO valida dados — isso é responsabilidade do BFA (Go).
"""

import pytest
from src.agent.onboarding import (
    OnboardingField,
    OnboardingState,
    FIELD_SEQUENCE,
    DATA_FIELDS,
    FIELD_PROMPTS,
    FIELD_LABELS,
    FIELD_FORMAT_HINTS,
    determine_current_field,
    build_onboarding_context,
    build_onboarding_response,
    is_onboarding_intent,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_history(n_data_turns: int) -> list[dict[str, str]]:
    """Cria histórico simulado com n_data_turns campos já respondidos."""
    history: list[dict[str, str]] = []

    # Turno 0 — cliente pediu abertura
    history.append({"query": "Quero abrir minha conta PJ", "answer": "Vamos lá!"})

    # Turnos de dados (1 campo por turno)
    field_values = [
        "12.345.678/0001-99",
        "Empresa Teste LTDA",
        "Empresa Teste",
        "contato@empresa.com",
        "João da Silva Santos",
        "123.456.789-00",
        "(11) 99999-8888",
        "15/03/1990",
        "123456",
        "123456",
    ]

    for i in range(min(n_data_turns, len(field_values))):
        history.append({
            "query": field_values[i],
            "answer": f"Campo {i + 1} recebido! ✅",
        })

    return history


# =============================================================================
# TestOnboardingField — enum e sequência
# =============================================================================

class TestOnboardingField:
    """Testes da enum OnboardingField e constantes relacionadas."""

    def test_field_count(self):
        """São 12 membros no enum (welcome + 10 dados + completed)."""
        assert len(OnboardingField) == 12

    def test_field_sequence_order(self):
        """A sequência começa com WELCOME e termina com COMPLETED."""
        assert FIELD_SEQUENCE[0] == OnboardingField.WELCOME
        assert FIELD_SEQUENCE[-1] == OnboardingField.COMPLETED

    def test_data_fields_exclude_welcome_and_completed(self):
        """DATA_FIELDS tem 10 campos (sem welcome e completed)."""
        assert len(DATA_FIELDS) == 10
        assert OnboardingField.WELCOME not in DATA_FIELDS
        assert OnboardingField.COMPLETED not in DATA_FIELDS

    def test_data_fields_in_correct_order(self):
        """DATA_FIELDS segue a ordem: CNPJ → ... → PASSWORD_CONFIRMATION."""
        assert DATA_FIELDS[0] == OnboardingField.CNPJ
        assert DATA_FIELDS[-1] == OnboardingField.PASSWORD_CONFIRMATION

    def test_every_data_field_has_prompt(self):
        """Cada campo de dados deve ter um template de prompt."""
        for field in DATA_FIELDS:
            assert field in FIELD_PROMPTS, f"{field.value} missing from FIELD_PROMPTS"

    def test_welcome_has_prompt(self):
        """Welcome também tem prompt."""
        assert OnboardingField.WELCOME in FIELD_PROMPTS

    def test_every_data_field_has_format_hint(self):
        """Cada campo de dados deve ter dica de formato."""
        for field in DATA_FIELDS:
            assert field in FIELD_FORMAT_HINTS, f"{field.value} missing from FIELD_FORMAT_HINTS"

    def test_label_fields(self):
        """Labels existem para os campos que aparecem no resumo final."""
        for field in [
            OnboardingField.CNPJ,
            OnboardingField.RAZAO_SOCIAL,
            OnboardingField.NOME_FANTASIA,
            OnboardingField.EMAIL,
            OnboardingField.REPRESENTANTE_NAME,
            OnboardingField.REPRESENTANTE_CPF,
            OnboardingField.REPRESENTANTE_PHONE,
            OnboardingField.REPRESENTANTE_BIRTH_DATE,
        ]:
            assert field in FIELD_LABELS, f"{field.value} missing from FIELD_LABELS"


# =============================================================================
# TestDetermineCurrentField — state machine
# =============================================================================

class TestDetermineCurrentField:
    """Testes da função determine_current_field."""

    def test_empty_history_returns_welcome(self):
        """Sem histórico → WELCOME (primeira interação)."""
        state = determine_current_field([], "Quero abrir conta")
        assert state.current_field == OnboardingField.WELCOME
        assert state.field_value == "Quero abrir conta"
        assert not state.is_complete
        assert not state.has_validation_error

    def test_after_welcome_asks_cnpj(self):
        """Após turno 0 (welcome), cliente responde CNPJ, next é Razão Social."""
        history = _make_history(0)  # só turno 0 (abertura)
        state = determine_current_field(history, "12.345.678/0001-99")
        assert state.current_field == OnboardingField.CNPJ
        assert state.next_field == OnboardingField.RAZAO_SOCIAL
        assert state.field_value == "12.345.678/0001-99"

    def test_after_cnpj_asks_razao_social(self):
        """Após 1 campo respondido (CNPJ), cliente responde Razão Social, next é Nome Fantasia."""
        history = _make_history(1)
        state = determine_current_field(history, "Empresa Teste LTDA")
        assert state.current_field == OnboardingField.RAZAO_SOCIAL
        assert state.next_field == OnboardingField.NOME_FANTASIA

    def test_after_razao_social_asks_nome_fantasia(self):
        """Após 2 campos, cliente responde Nome Fantasia, next é Email."""
        history = _make_history(2)
        state = determine_current_field(history, "Empresa Teste")
        assert state.current_field == OnboardingField.NOME_FANTASIA
        assert state.next_field == OnboardingField.EMAIL

    def test_after_nome_fantasia_asks_email(self):
        """Após 3 campos, cliente responde Email, next é Representante Name."""
        history = _make_history(3)
        state = determine_current_field(history, "contato@empresa.com")
        assert state.current_field == OnboardingField.EMAIL
        assert state.next_field == OnboardingField.REPRESENTANTE_NAME

    def test_after_email_asks_representante_name(self):
        """Após 4 campos, cliente responde nome representante, next é CPF."""
        history = _make_history(4)
        state = determine_current_field(history, "João da Silva Santos")
        assert state.current_field == OnboardingField.REPRESENTANTE_NAME
        assert state.next_field == OnboardingField.REPRESENTANTE_CPF

    def test_after_name_asks_cpf(self):
        """Após 5 campos, cliente responde CPF, next é Telefone."""
        history = _make_history(5)
        state = determine_current_field(history, "123.456.789-00")
        assert state.current_field == OnboardingField.REPRESENTANTE_CPF
        assert state.next_field == OnboardingField.REPRESENTANTE_PHONE

    def test_after_cpf_asks_phone(self):
        """Após 6 campos, cliente responde telefone, next é data nascimento."""
        history = _make_history(6)
        state = determine_current_field(history, "(11) 99999-8888")
        assert state.current_field == OnboardingField.REPRESENTANTE_PHONE
        assert state.next_field == OnboardingField.REPRESENTANTE_BIRTH_DATE

    def test_after_phone_asks_birth_date(self):
        """Após 7 campos, cliente responde data nascimento, next é password."""
        history = _make_history(7)
        state = determine_current_field(history, "15/03/1990")
        assert state.current_field == OnboardingField.REPRESENTANTE_BIRTH_DATE
        assert state.next_field == OnboardingField.PASSWORD

    def test_after_birth_date_asks_password(self):
        """Após 8 campos, cliente responde senha, next é confirmação."""
        history = _make_history(8)
        state = determine_current_field(history, "123456")
        assert state.current_field == OnboardingField.PASSWORD
        assert state.next_field == OnboardingField.PASSWORD_CONFIRMATION

    def test_after_password_asks_confirmation(self):
        """Após 9 campos, cliente responde confirmação, next é COMPLETED."""
        history = _make_history(9)
        state = determine_current_field(history, "123456")
        assert state.current_field == OnboardingField.PASSWORD_CONFIRMATION
        assert state.next_field == OnboardingField.COMPLETED

    def test_all_fields_done_returns_completed(self):
        """Após 10 campos respondidos → is_complete=True, next=COMPLETED."""
        history = _make_history(10)
        state = determine_current_field(history, "pronto")
        assert state.next_field == OnboardingField.COMPLETED
        assert state.is_complete is True

    def test_collected_tracks_previous_fields(self):
        """Campos coletados devem incluir o campo atual + anteriores."""
        history = _make_history(3)
        state = determine_current_field(history, "contato@empresa.com")
        # Campos do history + campo atual (email)
        assert OnboardingField.CNPJ.value in state.collected
        assert OnboardingField.RAZAO_SOCIAL.value in state.collected
        assert OnboardingField.NOME_FANTASIA.value in state.collected
        assert OnboardingField.EMAIL.value in state.collected
        assert state.collected[OnboardingField.CNPJ.value] == "12.345.678/0001-99"
        assert state.collected[OnboardingField.EMAIL.value] == "contato@empresa.com"

    def test_field_value_captures_current_query(self):
        """field_value deve ser a query atual (valor cru do campo)."""
        history = _make_history(2)
        state = determine_current_field(history, "Minha Empresa Legal")
        assert state.field_value == "Minha Empresa Legal"


# =============================================================================
# TestDetermineCurrentField — validation_error
# =============================================================================

class TestDetermineCurrentFieldValidationError:
    """Testes de reenvio quando o BFA rejeita um campo."""

    def test_validation_error_repeats_field(self):
        """Se BFA enviou validation_error, repetir o campo rejeitado."""
        history = _make_history(1)  # CNPJ já respondido
        state = determine_current_field(
            history,
            "12345",
            validation_error="CNPJ inválido: deve ter 14 dígitos",
        )
        assert state.current_field == OnboardingField.CNPJ
        assert state.has_validation_error is True
        assert state.validation_error == "CNPJ inválido: deve ter 14 dígitos"

    def test_validation_error_removes_from_collected(self):
        """Campo rejeitado deve ser removido dos coletados."""
        history = _make_history(2)  # CNPJ + Razão Social respondidos
        state = determine_current_field(
            history,
            "AB",
            validation_error="Razão Social: mínimo 3 caracteres",
        )
        assert state.current_field == OnboardingField.RAZAO_SOCIAL
        assert OnboardingField.RAZAO_SOCIAL.value not in state.collected
        # CNPJ ainda deve estar nos coletados
        assert OnboardingField.CNPJ.value in state.collected

    def test_validation_error_on_first_field(self):
        """Erro no primeiro campo (CNPJ) deve repetir CNPJ."""
        history = _make_history(1)  # CNPJ respondido (mas BFA rejeitou)
        state = determine_current_field(
            history,
            "invalido",
            validation_error="CNPJ inválido",
        )
        assert state.current_field == OnboardingField.CNPJ
        assert state.has_validation_error is True
        assert len(state.collected) == 0

    def test_validation_error_on_password(self):
        """Erro na senha deve repetir PASSWORD."""
        history = _make_history(9)  # 9 campos (password respondido)
        state = determine_current_field(
            history,
            "abc",
            validation_error="Senha deve ter 6 dígitos numéricos",
        )
        assert state.current_field == OnboardingField.PASSWORD
        assert state.has_validation_error is True

    def test_no_validation_error_advances(self):
        """Sem validation_error, o fluxo avança normalmente."""
        history = _make_history(1)  # CNPJ respondido
        state = determine_current_field(history, "Empresa LTDA")
        assert state.current_field == OnboardingField.RAZAO_SOCIAL
        assert state.next_field == OnboardingField.NOME_FANTASIA
        assert state.has_validation_error is False


# =============================================================================
# TestBuildOnboardingContext — geração de instrução para o LLM
# =============================================================================

class TestBuildOnboardingContext:
    """Testes da função build_onboarding_context."""

    def test_welcome_context(self):
        """Welcome: gera instrução com prompt de boas-vindas."""
        state = OnboardingState(
            current_field=OnboardingField.WELCOME,
            next_field=OnboardingField.WELCOME,
            field_value="Quero abrir conta",
        )
        ctx = build_onboarding_context(state)
        assert "[INSTRUÇÃO DE ONBOARDING" in ctx
        assert "CNPJ" in ctx  # welcome prompt pede CNPJ
        assert "search_knowledge_base" in ctx  # instrução de NÃO chamar

    def test_normal_field_context(self):
        """Campo normal: LLM recebe instrução para pedir o PRÓXIMO campo."""
        state = OnboardingState(
            current_field=OnboardingField.RAZAO_SOCIAL,
            next_field=OnboardingField.NOME_FANTASIA,
            collected={
                OnboardingField.CNPJ.value: "12.345.678/0001-99",
                OnboardingField.RAZAO_SOCIAL.value: "Empresa Teste LTDA",
            },
            field_value="Empresa Teste LTDA",
        )
        ctx = build_onboarding_context(state)
        assert "Nome Fantasia" in ctx  # LLM deve pedir o PRÓXIMO campo
        assert "SOMENTE" in ctx

    def test_validation_error_context(self):
        """Erro de validação: gera instrução com erro e dica de formato."""
        state = OnboardingState(
            current_field=OnboardingField.CNPJ,
            next_field=OnboardingField.CNPJ,  # re-ask same field
            has_validation_error=True,
            validation_error="CNPJ deve ter 14 dígitos",
            field_value="123",
        )
        ctx = build_onboarding_context(state)
        assert "rejeitado" in ctx.lower() or "⚠️" in ctx
        assert "CNPJ deve ter 14 dígitos" in ctx
        assert FIELD_FORMAT_HINTS[OnboardingField.CNPJ] in ctx

    def test_completed_context(self):
        """Completo: gera resumo sem a senha."""
        collected = {
            OnboardingField.CNPJ.value: "12.345.678/0001-99",
            OnboardingField.RAZAO_SOCIAL.value: "Empresa Teste LTDA",
            OnboardingField.NOME_FANTASIA.value: "Empresa Teste",
            OnboardingField.EMAIL.value: "contato@empresa.com",
            OnboardingField.REPRESENTANTE_NAME.value: "João da Silva",
            OnboardingField.REPRESENTANTE_CPF.value: "123.456.789-00",
            OnboardingField.REPRESENTANTE_PHONE.value: "(11) 99999-8888",
            OnboardingField.REPRESENTANTE_BIRTH_DATE.value: "15/03/1990",
            OnboardingField.PASSWORD.value: "123456",
            OnboardingField.PASSWORD_CONFIRMATION.value: "123456",
        }
        state = OnboardingState(
            current_field=OnboardingField.PASSWORD_CONFIRMATION,
            next_field=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        ctx = build_onboarding_context(state)
        assert "COMPLETO" in ctx or "✅" in ctx
        assert "12.345.678/0001-99" in ctx  # CNPJ no resumo
        assert "João da Silva" in ctx  # nome no resumo
        assert "123456" not in ctx  # senha NÃO deve aparecer no resumo

    def test_completed_context_excludes_password_fields(self):
        """No resumo final, PASSWORD e PASSWORD_CONFIRMATION não aparecem."""
        collected = {f.value: f"valor_{f.value}" for f in DATA_FIELDS}
        state = OnboardingState(
            current_field=OnboardingField.PASSWORD_CONFIRMATION,
            next_field=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        ctx = build_onboarding_context(state)
        # Deve ter os labels de dados (CNPJ, Razão Social, etc.)
        assert "CNPJ" in ctx
        assert "E-mail" in ctx
        # Mas não as senhas
        assert "valor_password" not in ctx
        assert "valor_passwordConfirmation" not in ctx

    def test_context_always_has_no_search_instruction(self):
        """Toda instrução deve dizer para NÃO chamar search_knowledge_base."""
        pairs = [
            (OnboardingField.WELCOME, OnboardingField.WELCOME),
            (OnboardingField.CNPJ, OnboardingField.RAZAO_SOCIAL),
            (OnboardingField.EMAIL, OnboardingField.REPRESENTANTE_NAME),
        ]
        for current, nxt in pairs:
            state = OnboardingState(
                current_field=current,
                next_field=nxt,
                field_value="qualquer",
            )
            ctx = build_onboarding_context(state)
            assert "search_knowledge_base" in ctx


# =============================================================================
# TestBuildOnboardingResponse — resposta determinística (sem LLM)
# =============================================================================

class TestBuildOnboardingResponse:
    """Testes da função build_onboarding_response (v8.1.0 — bypass do LLM)."""

    def test_welcome_response(self):
        """Welcome: retorna template de boas-vindas pedindo CNPJ."""
        state = OnboardingState(
            current_field=OnboardingField.WELCOME,
            next_field=OnboardingField.WELCOME,
            field_value="Quero abrir conta",
        )
        resp = build_onboarding_response(state)
        assert "CNPJ" in resp
        assert "passo a passo" in resp.lower() or "guiar" in resp.lower()

    def test_normal_field_uses_template(self):
        """Campo normal: resposta É o template de FIELD_PROMPTS."""
        state = OnboardingState(
            current_field=OnboardingField.CNPJ,
            next_field=OnboardingField.RAZAO_SOCIAL,
            collected={OnboardingField.CNPJ.value: "12.345.678/0001-99"},
            field_value="12.345.678/0001-99",
        )
        resp = build_onboarding_response(state)
        assert resp == FIELD_PROMPTS[OnboardingField.RAZAO_SOCIAL]

    def test_nome_fantasia_to_email_response(self):
        """Caso que causava alucinação: Nome Fantasia → Email."""
        state = OnboardingState(
            current_field=OnboardingField.NOME_FANTASIA,
            next_field=OnboardingField.EMAIL,
            collected={
                OnboardingField.CNPJ.value: "87382356000115",
                OnboardingField.RAZAO_SOCIAL.value: "Kasjsjskaja",
                OnboardingField.NOME_FANTASIA.value: "Uauauahaha",
            },
            field_value="Uauauahaha",
        )
        resp = build_onboarding_response(state)
        assert "Nome Fantasia recebido" in resp
        assert "e-mail" in resp.lower()
        # NÃO deve conter "telefone" — era a alucinação
        assert "telefone" not in resp.lower()

    def test_each_field_transition_uses_correct_template(self):
        """Cada transição de campo deve usar o template correto."""
        for i, field in enumerate(DATA_FIELDS):
            if i + 1 < len(DATA_FIELDS):
                next_field = DATA_FIELDS[i + 1]
            else:
                next_field = OnboardingField.COMPLETED
            state = OnboardingState(
                current_field=field,
                next_field=next_field,
                collected={field.value: "valor_qualquer"},
                is_complete=(next_field == OnboardingField.COMPLETED),
                field_value="valor_qualquer",
            )
            resp = build_onboarding_response(state)
            if next_field == OnboardingField.COMPLETED:
                # Último campo → resposta de conclusão
                assert "✅" in resp
            else:
                # Template do próximo campo
                expected_template = FIELD_PROMPTS[next_field]
                assert resp == expected_template, (
                    f"Transition {field.value} → {next_field.value}: "
                    f"expected template for {next_field.value}"
                )

    def test_validation_error_response(self):
        """Erro de validação: mensagem amigável com motivo e dica."""
        state = OnboardingState(
            current_field=OnboardingField.CNPJ,
            next_field=OnboardingField.CNPJ,
            has_validation_error=True,
            validation_error="CNPJ deve ter 14 dígitos",
            field_value="123",
        )
        resp = build_onboarding_response(state)
        assert "⚠️" in resp
        assert "CNPJ" in resp
        assert "14 dígitos" in resp
        assert "novamente" in resp.lower()

    def test_validation_error_includes_hint(self):
        """Erro de validação deve incluir dica de formato."""
        state = OnboardingState(
            current_field=OnboardingField.EMAIL,
            next_field=OnboardingField.EMAIL,
            has_validation_error=True,
            validation_error="Email inválido",
            field_value="invalido",
        )
        resp = build_onboarding_response(state)
        assert "contato@empresa.com" in resp  # from FIELD_FORMAT_HINTS

    def test_completed_response(self):
        """Completo: mostra resumo sem a senha."""
        collected = {
            OnboardingField.CNPJ.value: "12.345.678/0001-99",
            OnboardingField.RAZAO_SOCIAL.value: "Empresa Teste LTDA",
            OnboardingField.NOME_FANTASIA.value: "Empresa Teste",
            OnboardingField.EMAIL.value: "contato@empresa.com",
            OnboardingField.REPRESENTANTE_NAME.value: "João da Silva",
            OnboardingField.REPRESENTANTE_CPF.value: "123.456.789-00",
            OnboardingField.REPRESENTANTE_PHONE.value: "(11) 99999-8888",
            OnboardingField.REPRESENTANTE_BIRTH_DATE.value: "15/03/1990",
            OnboardingField.PASSWORD.value: "123456",
            OnboardingField.PASSWORD_CONFIRMATION.value: "123456",
        }
        state = OnboardingState(
            current_field=OnboardingField.PASSWORD_CONFIRMATION,
            next_field=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        resp = build_onboarding_response(state)
        assert "✅" in resp
        assert "12.345.678/0001-99" in resp  # CNPJ no resumo
        assert "João da Silva" in resp  # nome no resumo
        assert "123456" not in resp  # senha NÃO no resumo

    def test_completed_response_excludes_password_fields(self):
        """No resumo, PASSWORD e PASSWORD_CONFIRMATION não aparecem."""
        collected = {f.value: f"valor_{f.value}" for f in DATA_FIELDS}
        state = OnboardingState(
            current_field=OnboardingField.PASSWORD_CONFIRMATION,
            next_field=OnboardingField.COMPLETED,
            collected=collected,
            is_complete=True,
        )
        resp = build_onboarding_response(state)
        assert "valor_password" not in resp
        assert "valor_passwordConfirmation" not in resp

    def test_response_is_deterministic(self):
        """Mesma entrada → mesma saída, sempre."""
        state = OnboardingState(
            current_field=OnboardingField.RAZAO_SOCIAL,
            next_field=OnboardingField.NOME_FANTASIA,
            collected={
                OnboardingField.CNPJ.value: "12345678000199",
                OnboardingField.RAZAO_SOCIAL.value: "Teste",
            },
            field_value="Teste",
        )
        resp1 = build_onboarding_response(state)
        resp2 = build_onboarding_response(state)
        assert resp1 == resp2


# =============================================================================
# TestIsOnboardingIntent — detecção de intenção
# =============================================================================

class TestIsOnboardingIntent:
    """Testes da função is_onboarding_intent."""

    @pytest.mark.parametrize("query", [
        "Quero abrir conta",
        "Preciso abrir uma conta PJ",
        "Abertura de conta",
        "Criar conta",
        "quero abrir minha conta",
    ])
    def test_detects_opening_queries(self, query):
        """Queries sobre abertura devem ser detectadas."""
        assert is_onboarding_intent(query, []) is True

    @pytest.mark.parametrize("query", [
        "Qual meu saldo?",
        "Oi, tudo bem?",
        "Preciso de ajuda com PIX",
        "Bom dia",
    ])
    def test_ignores_non_opening_queries(self, query):
        """Queries que não são sobre abertura não devem ativar onboarding."""
        assert is_onboarding_intent(query, []) is False

    def test_detects_from_history(self):
        """Se o histórico já contém contexto de onboarding, retorna True."""
        history = [
            {"query": "Quero abrir conta", "answer": "Vamos abrir sua conta PJ!"},
        ]
        assert is_onboarding_intent("12.345.678/0001-99", history) is True

    def test_detects_cnpj_in_history(self):
        """Se histórico menciona CNPJ, é onboarding."""
        history = [
            {"query": "Meu CNPJ é 12.345.678/0001-99", "answer": "CNPJ recebido!"},
        ]
        assert is_onboarding_intent("Empresa LTDA", history) is True

    def test_detects_representante_in_history(self):
        """Se histórico menciona representante, é onboarding."""
        history = [
            {"query": "dados", "answer": "Agora preciso do representante legal"},
        ]
        assert is_onboarding_intent("João Silva", history) is True

    def test_empty_history_and_neutral_query(self):
        """Sem histórico e query neutra → não é onboarding."""
        assert is_onboarding_intent("Bom dia", []) is False


# =============================================================================
# TestOnboardingState — dataclass
# =============================================================================

class TestOnboardingState:
    """Testes do dataclass OnboardingState."""

    def test_defaults(self):
        """Defaults devem ser seguros."""
        state = OnboardingState(
            current_field=OnboardingField.CNPJ,
            next_field=OnboardingField.RAZAO_SOCIAL,
        )
        assert state.collected == {}
        assert state.is_complete is False
        assert state.has_validation_error is False
        assert state.validation_error == ""
        assert state.field_value == ""

    def test_with_all_fields(self):
        """Deve aceitar todos os campos."""
        state = OnboardingState(
            current_field=OnboardingField.EMAIL,
            next_field=OnboardingField.EMAIL,  # re-ask on error
            collected={"cnpj": "12345678000199"},
            is_complete=False,
            has_validation_error=True,
            validation_error="Email inválido",
            field_value="invalido",
        )
        assert state.current_field == OnboardingField.EMAIL
        assert state.next_field == OnboardingField.EMAIL
        assert state.has_validation_error is True
        assert state.validation_error == "Email inválido"


# =============================================================================
# TestFieldSequenceIntegration — fluxo completo campo a campo
# =============================================================================

class TestFieldSequenceIntegration:
    """Testa o fluxo completo: simula todos os 10 campos sendo respondidos."""

    def test_full_flow(self):
        """Percorre todos os campos de WELCOME até COMPLETED."""
        field_values = [
            "12.345.678/0001-99",
            "Empresa Teste LTDA",
            "Empresa Teste",
            "contato@empresa.com",
            "João da Silva Santos",
            "123.456.789-00",
            "(11) 99999-8888",
            "15/03/1990",
            "123456",
            "123456",
        ]

        # 1. Welcome
        state = determine_current_field([], "Quero abrir conta")
        assert state.current_field == OnboardingField.WELCOME
        assert state.next_field == OnboardingField.WELCOME

        history = [{"query": "Quero abrir conta", "answer": "Vamos lá!"}]

        # 2-11. Um campo por vez
        for i, value in enumerate(field_values):
            state = determine_current_field(history, value)
            expected_current = DATA_FIELDS[i]
            assert state.current_field == expected_current, (
                f"Turn {i + 1}: expected current={expected_current.value}, "
                f"got {state.current_field.value}"
            )
            # next_field should be the NEXT data field, or COMPLETED if last
            if i + 1 < len(DATA_FIELDS):
                expected_next = DATA_FIELDS[i + 1]
            else:
                expected_next = OnboardingField.COMPLETED
            assert state.next_field == expected_next, (
                f"Turn {i + 1}: expected next={expected_next.value}, "
                f"got {state.next_field.value}"
            )
            assert state.field_value == value
            history.append({"query": value, "answer": f"Recebido {i + 1}!"})

        # After the last field (passwordConfirmation), is_complete should be True
        # on the last iteration above (i=9)
        assert state.is_complete is True
        assert len(state.collected) == 10

    def test_flow_with_validation_error_retry(self):
        """Fluxo com um erro de validação no CNPJ: deve repetir."""
        # Welcome
        history = [{"query": "Quero abrir conta", "answer": "Vamos lá!"}]

        # CNPJ com valor inválido
        state = determine_current_field(history, "123")
        assert state.current_field == OnboardingField.CNPJ
        history.append({"query": "123", "answer": "CNPJ recebido!"})

        # BFA rejeita → validation_error → deve repetir CNPJ
        state = determine_current_field(
            history,
            "12.345.678/0001-99",
            validation_error="CNPJ inválido",
        )
        assert state.current_field == OnboardingField.CNPJ
        assert state.has_validation_error is True

    def test_completed_state_has_all_data(self):
        """No estado COMPLETED, collected deve ter os 10 campos."""
        history = _make_history(10)
        state = determine_current_field(history, "finalizar")
        assert state.is_complete is True
        assert state.next_field == OnboardingField.COMPLETED
        # Os 10 campos devem estar nos coletados
        for field in DATA_FIELDS:
            assert field.value in state.collected, (
                f"{field.value} missing from collected"
            )
