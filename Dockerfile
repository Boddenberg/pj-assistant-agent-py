# =============================================================================
# Dockerfile — PJ Assistant Agent
# =============================================================================
#
# Build:   docker build -t pj-assistant-agent .
# Run:     docker run -p 8000:8000 --env-file .env pj-assistant-agent
#
# Otimizações:
#   - Multi-stage build     → imagem final sem compiladores (~60% menor)
#   - PyTorch CPU-only      → sem CUDA (economiza ~4-5GB)
#   - --no-cache-dir        → sem cache pip na imagem
#   - Non-root user         → segurança
#   - .dockerignore         → evita copiar .venv, .git, __pycache__
# =============================================================================

# ─── Stage 1: Builder (compila dependências nativas) ───────────────
FROM python:3.11-slim AS builder

# Dependências de compilação (gcc/g++ para chromadb, sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Instalar PyTorch CPU-ONLY primeiro (sem CUDA = ~200MB vs ~5GB)
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Copiar pyproject.toml e instalar dependências (cache de layer)
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

# Copiar site-packages instalados no builder (sem recompilar)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Pré-baixar modelo de embedding no build (evita download no startup)
# Sem isso, o primeiro startup no Railway baixa ~90MB do HuggingFace,
# podendo estourar o timeout do health check (120s).
# O cache fica em /home/appuser/.cache/huggingface/ acessível pelo appuser.
ENV HF_HOME=/home/$APP_USER/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copiar código do projeto
COPY . .

# Permissões
RUN chmod +x start.sh && \
    mkdir -p data/chroma && \
    chown -R $APP_USER:$APP_USER $APP_DIR && \
    chown -R $APP_USER:$APP_USER /home/$APP_USER

USER $APP_USER

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/healthz')" || exit 1

CMD ["bash", "start.sh"]