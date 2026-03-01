# =============================================================================
# Dockerfile — PJ Assistant Agent
# =============================================================================
#
# Build:   docker build -t pj-assistant-agent .
# Run:     docker run -p 8000:8000 --env-file .env pj-assistant-agent
#
# Otimizações:
#   - Multi-stage build      → imagem final sem compiladores
#   - Sem torch              → embeddings via OpenAI API (imagem ~3x menor)
#   - --no-cache-dir         → sem cache pip na imagem
#   - Non-root user          → segurança
#   - .dockerignore          → evita copiar .venv, .git, __pycache__
#
# Por que OpenAI Embeddings em vez de sentence-transformers?
#   torch + sentence-transformers = ~800MB na imagem Docker.
#   Isso causava build timeout no Railway ("importing to docker").
#   Com text-embedding-3-small da OpenAI:
#     - Imagem final ~500MB (vs ~1.5GB)
#     - Build ~3x mais rápido
#     - Qualidade de embedding superior para português
#     - Custo desprezível (~$0.02/milhão de tokens)
# =============================================================================

# ─── Stage 1: Builder (compila dependências nativas) ───────────────
FROM python:3.11-slim AS builder

# Dependências de compilação (gcc/g++ para chromadb)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copiar pyproject.toml e instalar dependências
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# ─── Stage 2: Runtime (imagem final enxuta) ────────────────────────
FROM python:3.11-slim

ARG APP_USER=appuser
ARG APP_DIR=/app

# Apenas runtime deps (sem gcc/g++)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root
RUN useradd --create-home --shell /bin/bash $APP_USER

WORKDIR $APP_DIR

# Copiar site-packages instalados no builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar código do projeto
COPY . .

# Permissões
RUN chmod +x start.sh && \
    mkdir -p data/chroma && \
    chown -R $APP_USER:$APP_USER $APP_DIR && \
    chown -R $APP_USER:$APP_USER /home/$APP_USER

USER $APP_USER

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/healthz')" || exit 1

CMD ["bash", "start.sh"]