# =============================================================================
# Dockerfile — PJ Assistant Agent
# =============================================================================
#
# Build:   docker build -t pj-assistant-agent .
# Run:     docker run -p 8000:8000 --env-file .env pj-assistant-agent
#
# Otimizações:
#   - python:3.11-slim → imagem menor (~150MB vs ~1GB)
#   - Non-root user    → segurança (princípio do menor privilégio)
#   - Cache de deps    → pyproject.toml copiado antes do código
#   - HEALTHCHECK      → Railway/Docker detecta quando app está pronta
# =============================================================================

FROM python:3.11-slim

# Variáveis de build
ARG APP_USER=appuser
ARG APP_DIR=/app

# Instala dependências de sistema necessárias para compilar pacotes nativos
# (chromadb e sentence-transformers precisam de gcc/g++)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Cria usuário não-root (segurança)
RUN useradd --create-home --shell /bin/bash $APP_USER

WORKDIR $APP_DIR

# 1. Copia apenas pyproject.toml primeiro (cache de dependências)
#    Docker cacheia essa layer — só rebuilda se pyproject.toml mudar.
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# 2. Copia o restante do projeto (código, data, script de startup)
COPY . .

# Garante que start.sh seja executável
RUN chmod +x start.sh

# Cria diretório de dados com permissão para o usuário da app
RUN mkdir -p data/chroma && chown -R $APP_USER:$APP_USER $APP_DIR

# Troca para usuário não-root
USER $APP_USER

# Porta padrão (Railway injeta $PORT em runtime — o start.sh usa $PORT)
EXPOSE 8000

# Healthcheck: Railway e Docker verificam este endpoint para saber se o serviço está up
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/healthz')" || exit 1

# Comando de startup: ingere RAG + sobe uvicorn (ver start.sh)
CMD ["bash", "start.sh"]
