"""
Onboarding — fluxo conversacional campo-a-campo (v9).

Arquitetura:
  O agente Python é a CAMADA CONVERSACIONAL.
  O BFA (Go) é a CAMADA DE NEGÓCIO.

  Responsabilidades do agente:
    - Detectar intenção de abertura de conta
    - Determinar o step atual com base no history enriquecido
    - Validar formato básico dos campos (guard rail inline)
    - Gerar respostas determinísticas (templates, sem LLM)
    - Devolver step + valor cru + next_step na resposta

  Responsabilidades do BFA (Go):
    - Validar regras de negócio (CNPJ único, dígito verificador, 18+)
    - Persistir dados
    - Retornar validated=True/False no history
    - Controlar o fluxo de sessão

Módulos internos:
  fields.py        → Enum, sequência, prompts, labels, hints
  validators.py    → Validação de formato inline (guard rail)
  state_machine.py → State machine: determina campo atual/próximo
  responses.py     → Gerador de resposta determinística (sem LLM)
  intent.py        → Detecção de intenção de onboarding e restart
"""

# Re-export público — mantém backwards compatibility.
# Quem importa `from src.agent.onboarding import X` continua funcionando.

from src.agent.onboarding.fields import (  # noqa: F401
    OnboardingField,
    FIELD_SEQUENCE,
    DATA_FIELDS,
    FIELD_PROMPTS,
    FIELD_LABELS,
    FIELD_FORMAT_HINTS,
    MAX_RETRIES,
)

from src.agent.onboarding.validators import (  # noqa: F401
    validate_field_format,
)

from src.agent.onboarding.state_machine import (  # noqa: F401
    OnboardingState,
    determine_current_field,
)

from src.agent.onboarding.responses import (  # noqa: F401
    build_onboarding_response,
    build_onboarding_context,
)

from src.agent.onboarding.intent import (  # noqa: F401
    is_onboarding_intent,
)
