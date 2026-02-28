# =============================================================================
# RAG — Retrieval-Augmented Generation
# =============================================================================
# Pipeline completo de RAG:
#   1. chunker.py    → Carrega documentos e divide em chunks
#   2. vectorstore.py → Gera embeddings e armazena no ChromaDB
#   3. retriever.py  → Busca semântica com filtro de relevância
#   4. ingest.py     → Script para popular a base vetorial
#
# Decisões de design:
#   - ChromaDB local: zero infra, bom para dev/MVP
#   - Embedding local (sentence-transformers): sem custo, roda em CPU
#   - Threshold de similaridade: evita poluir o prompt com lixo
# =============================================================================
