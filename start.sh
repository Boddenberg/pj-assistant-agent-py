#!/bin/bash
# =============================================================================
# start.sh — Script de Startup para Produção (Railway)
# =============================================================================
#
# Ordem de execução:
#   1. Ingere a base de conhecimento no ChromaDB (RAG)
#   2. Sobe o servidor uvicorn na porta $PORT (injetada pelo Railway)
#
# Por que ingerir no startup?
#   O Railway usa volumes efêmeros — o ChromaDB não persiste entre deploys.
#   A ingestão é rápida (~5s para os 3 arquivos .md da knowledge base).
#   Em produção com volume persistente, poderia pular esse passo se já ingerido.
#
# PORT é injetada automaticamente pelo Railway (geralmente 8080).
# Fallback para 8000 em caso de rodar localmente com este script.
# =============================================================================

set -e  # Para o script se qualquer comando falhar

PORT="${PORT:-8000}"

echo "🚀 PJ Assistant Agent — Iniciando..."
echo "📦 Porta: $PORT"

# Passo 1: Ingerir base de conhecimento no ChromaDB
echo "📚 Ingerindo base de conhecimento (RAG)..."
python -m src.rag.ingest
echo "✅ Base de conhecimento ingerida!"

# Passo 2: Subir servidor uvicorn
echo "🌐 Subindo servidor na porta $PORT..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --log-level info

