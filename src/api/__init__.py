"""
API — camada HTTP (FastAPI).

Este pacote contém:
  - main.py   → Factory da aplicação FastAPI (lifespan, CORS, Prometheus)
  - routes.py → Endpoints REST (/v1/assistant, /healthz, /readyz)

Fluxo de uma request:
  1. BFA (Go) → POST /v1/assistant { customer_id, query, profile, transactions }
  2. routes.py valida, sanitiza, chama o agente
  3. Agente retorna AssistantResponse
  4. routes.py registra métricas e devolve JSON

Padrão seguido:
  - Separação clara entre app factory (main) e rotas (routes)
  - Rotas NÃO conhecem detalhes de como o agente funciona
  - Rotas NÃO fazem regras de negócio, apenas orquestram
"""
