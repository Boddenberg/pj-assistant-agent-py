# 🤖 PJ Assistant Agent — Agente de IA (Python)

> Microsserviço de IA generativa que atende clientes **Pessoa Jurídica**: guia a abertura de conta campo a campo, responde dúvidas sobre produtos com RAG e analisa dados financeiros por meio de tools. É chamado pelo [BFA em Go](https://github.com/Boddenberg/pj-assistant-bfa-go).

**Stack:** Python 3.11 · LangGraph · LangChain · FastAPI · ChromaDB · GPT-4o-mini · Prometheus · OpenTelemetry · LangFuse · Docker · Railway

---

## 📑 Índice

- [Visão geral](#visão-geral)
- [Arquitetura do agente](#arquitetura-do-agente)
- [RAG](#rag)
- [API](#api)
- [Como rodar](#como-rodar)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Testes](#testes)
- [Observabilidade](#observabilidade)
- [Segurança](#segurança)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Documentação completa](#documentação-completa)

---

## Visão geral

| Capacidade | O que faz |
| --- | --- |
| **Onboarding PJ** | Máquina de estados que coleta 10 campos um por vez (CNPJ, razão social, nome fantasia, e-mail, dados do representante, senha), com validação e correção de campo |
| **Perguntas sobre produtos** | Busca semântica na base de conhecimento (PIX, cartões, boletos, conta corrente, analytics) |
| **Análise financeira** | Tools que leem transações e perfil de crédito através do BFA |
| **Avaliação** | `ConversationEvaluator` (LLM-as-judge) para medir qualidade das respostas |

## Arquitetura do agente

O grafo LangGraph tem quatro nós:

```
planner → executor ⇄ tools → synthesizer
```

- **planner** — interpreta a mensagem e decide o caminho (onboarding, conhecimento ou dado financeiro);
- **executor** — decide se precisa chamar tool e qual;
- **tools** — devolve o resultado ao executor (ciclo até não haver mais chamadas);
- **synthesizer** — redige a resposta final ao cliente.

Três tools estão disponíveis ao modelo:

| Tool | Função |
| --- | --- |
| `search_knowledge_base` | busca semântica na base de conhecimento (RAG) |
| `analyze_transactions` | analisa o extrato do cliente |
| `assess_credit_profile` | avalia o perfil de crédito |

O fluxo de onboarding vive em `src/agent/onboarding/`, separado em `state_machine`, `fields`, `intent`, `validators` e `responses`, para que a coleta de dados não dependa da criatividade do modelo.

## RAG

A base em `data/knowledge_base/` cobre os passos do onboarding e os domínios de produto (`pix/`, `cartoes/`, `conta/`, `pagamentos/`, `analytics/`, `auth/`, `geral/`).

O pipeline é `chunker → ingest → vectorstore (ChromaDB) → retriever`, com embeddings `text-embedding-3-small`. A ingestão roda no startup (`start.sh`), porque o volume do Railway é efêmero.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| `POST` | `/v1/chat` | conversa com o agente |
| `GET` | `/healthz` | liveness |
| `GET` | `/readyz` | readiness |

Swagger em `http://localhost:8000/docs`.

## Como rodar

```bash
cp .env.example .env        # preencha OPENAI_API_KEY
pip install -e ".[dev]"
python run.py               # ingere a base e sobe a API na porta 8000
```

Com Docker:

```bash
docker compose up --build
```

`run.py` e `start.sh` fazem a mesma sequência: ingerir a base de conhecimento e subir o uvicorn. `start.sh` é o entrypoint de produção e respeita a `PORT` injetada pelo Railway.

## Variáveis de ambiente

Todas são carregadas por `pydantic-settings` em `src/core/config.py`. Veja `.env.example` para a lista comentada.

| Grupo | Variáveis |
| --- | --- |
| LLM | `OPENAI_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE` |
| BFA | `BFA_BASE_URL` |
| RAG | `CHROMA_PERSIST_DIR`, `EMBEDDING_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RAG_TOP_K` |
| Observabilidade | `LANGFUSE_*`, `AXIOM_*`, `LOG_LEVEL` |
| Limites | `MAX_INPUT_LENGTH`, `MAX_TOKENS_PER_REQUEST`, `MAX_COST_PER_REQUEST_USD` |
| Servidor | `HOST`, `PORT` |

## Testes

```bash
pytest                 # suíte completa
ruff check .           # lint
mypy src               # tipagem
```

São 9 suítes unitárias (`onboarding`, `security`, `tools`, `financial`, `metrics`, `models`, `auth_guard`, `context_resolver`, `evaluation`) e 2 de integração (`test_agent_workflow`, `test_api`).

## Observabilidade

- **structlog** para log estruturado, com envio opcional ao Axiom;
- **Prometheus** com `agent_requests_total`, `agent_tokens_total`, `agent_tool_errors_total`, `agent_model_errors_total`, `agent_fallback_total` e `agent_request_duration_seconds`;
- **OpenTelemetry** instrumentando o FastAPI;
- **LangFuse** para traces de prompt, custo e latência do LLM.

## Segurança

`src/security/sanitizer.py` expõe `validate_input` (tamanho e conteúdo da entrada) e `mask_sensitive_data` (mascaramento antes do log). `src/agent/auth_guard.py` restringe as tools que exigem cliente autenticado. O teto de custo por requisição funciona como circuit breaker.

## Estrutura do repositório

```
src/
├── agent/           # grafo, prompts, tools, estado e onboarding
├── api/             # FastAPI: rotas, avaliação e app
├── core/            # config, exceções e modelos Pydantic
├── rag/             # chunker, ingest, vectorstore e retriever
├── evaluation/      # LLM-as-judge
├── observability/   # logging, métricas e tracing
└── security/        # sanitização e mascaramento
data/knowledge_base/ # base de conhecimento (markdown)
docs/                # contratos do BFA e guia de onboarding
tests/               # unitários e integração
```

## Documentação completa

- [`CASE_DOCUMENTATION.md`](CASE_DOCUMENTATION.md) — documentação completa do case: decisões de design, trade-offs, métricas, governança e critérios de avaliação;
- [`docs/BFA_CONTRACT_v9.md`](docs/BFA_CONTRACT_v9.md) — contrato vigente com o BFA;
- [`docs/BFA_ONBOARDING_GUIDE.md`](docs/BFA_ONBOARDING_GUIDE.md) — guia do fluxo de onboarding.

## Ecossistema

| Repositório | Papel |
| --- | --- |
| [pj-assistant-agent-py](https://github.com/Boddenberg/pj-assistant-agent-py) | este agente de IA |
| [pj-assistant-bfa-go](https://github.com/Boddenberg/pj-assistant-bfa-go) | backend Go (BaaS + orquestração) |
| [pj-assistant-web](https://github.com/Boddenberg/pj-assistant-web) | app mobile React Native |
| [pj-assistant-case-docs](https://github.com/Boddenberg/pj-assistant-case-docs) | documentação publicada |
