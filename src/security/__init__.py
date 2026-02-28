# =============================================================================
# Security — sanitização, proteção e governança
# =============================================================================
# Responsável por:
#   - Validar e sanitizar inputs do usuário
#   - Detectar tentativas de prompt injection
#   - Mascarar dados sensíveis (CPF, CNPJ, cartão, email)
#   - Proteger contra vazamento de contexto interno
#
# Princípio: NUNCA confiar no input do usuário.
# Tudo que chega da API passa por aqui antes de ir pro agente.
# =============================================================================
