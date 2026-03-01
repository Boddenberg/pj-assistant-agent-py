# =============================================================================
# Dockerfile — PJ Assistant Agent
# =============================================================================
#
# Build:   docker build -t pj-assistant-agent .
# Run:     docker run -p 8000:8000 --env-file .env pj-assistant-agent
#
# Otimizações:
#   - Multi-stage build      → imagem final sem compiladores
#   - PyTorch CPU-only       → sem CUDA (economiza ~4-5GB)
#   - Cleanup torch tests    → remove ~120MB de testes/dados do torch
#   - --no-cache-dir         → sem cache pip na imagem
#   - Non-root user          → segurança
#   - .dockerignore          → evita copiar .venv, .git, __pycache__
#
# Por que cleanup do torch?
#   O torch CPU-only ainda ocupa ~200MB. Dentro dele, ~120MB são pastas
#   de testes, benchmarks e dados que NÃO são usados em runtime.
#   Removê-los reduz a imagem final e acelera o push para o registry
#   (o "importing to docker" no Railway é proporcional ao tamanho).
# =============================================================================

# ─── Stage 1: Builder (compila dependências nativas) ───────────────
FROM python:3.11-slim AS builder

# Dependências de compilação (gcc/g++ para chromadb, sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Instalar PyTorch CPU-ONLY (sem CUDA = ~200MB vs ~5GB)
# + instalar projeto num único pip install para melhor cache de layer
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir .

# Cleanup: remover partes do torch/triton que não usamos em runtime.
# Isso economiza ~120-150MB na imagem final, acelerando o push.
RUN find /usr/local/lib/python3.11/site-packages/torch -type d -name "test" -exec rm -rf {} + 2>/dev/null; \
    find /usr/local/lib/python3.11/site-packages/torch -type d -name "tests" -exec rm -rf {} + 2>/dev/null; \
    rm -rf /usr/local/lib/python3.11/site-packages/torch/lib/*.a 2>/dev/null; \
    rm -rf /usr/local/lib/python3.11/site-packages/torch/include 2>/dev/null; \
    rm -rf /usr/local/lib/python3.11/site-packages/torch/share 2>/dev/null; \
    rm -rf /usr/local/lib/python3.11/site-packages/torch/_inductor 2>/dev/null; \
    rm -rf /usr/local/lib/python3.11/site-packages/torch/_dynamo 2>/dev/null; \
    rm -rf /usr/local/lib/python3.11/site-packages/torch/_export 2>/dev/null; \
    rm -rf /usr/local/lib/python3.11/site-packages/torch/_functorch 2>/dev/null; \
    find /usr/local/lib/python3.11/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
    true

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

# Copiar site-packages instalados no builder (já limpos)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Pré-baixar modelo de embedding no build (evita download no startup)
# Sem isso, o primeiro startup no Railway baixa ~90MB do HuggingFace,
# podendo estourar o timeout do health check.
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