"""
Retriever — busca semântica com filtro de relevância.

Fluxo:
  1. Recebe a query do usuário (ou do agente)
  2. Gera embedding da query
  3. Busca os K vetores mais similares no ChromaDB
  4. Filtra resultados com score abaixo do threshold
  5. Retorna apenas os chunks relevantes

Como evitar contexto irrelevante?
  - SIMILARITY_THRESHOLD = 0.2 → descarta chunks com baixa similaridade
  - Se a query não tem relação com nenhum documento, retorna lista vazia
  - O agente recebe "nada encontrado" e não alucina com contexto ruim

Em produção, adicionar:
  - Reranking com cross-encoder (ms-marco-MiniLM-L6-v2)
  - Hybrid search (keyword + semântico)
  - Cache de queries frequentes
"""

from __future__ import annotations

import time

from src.core.config import settings
from src.rag.vectorstore import get_vectorstore
from src.observability.logging import get_logger

logger = get_logger("rag.retriever")

SIMILARITY_THRESHOLD = 0.2


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """
    Busca documentos relevantes para a query usando similaridade semântica.
    """
    start = time.perf_counter()
    k = top_k or settings.rag_top_k

    logger.info(
        "🔍 [RAG] RETRIEVE_START — Busca semântica iniciada",
        query=query,
        top_k=k,
        similarity_threshold=SIMILARITY_THRESHOLD,
        embedding_model=settings.embedding_model,
    )

    store = get_vectorstore()
    results = store.similarity_search_with_relevance_scores(query, k=k)

    search_duration = (time.perf_counter() - start) * 1000

    # Log de todos os resultados antes do filtro
    all_scores = [round(score, 4) for _, score in results]
    logger.info(
        "🔍 [RAG] RETRIEVE_RAW — Resultados brutos do ChromaDB (antes do filtro)",
        query=query,
        num_raw_results=len(results),
        raw_scores=all_scores,
        threshold=SIMILARITY_THRESHOLD,
    )

    relevant = []
    filtered_out = 0
    for doc, score in results:
        if score < SIMILARITY_THRESHOLD:
            filtered_out += 1
            continue
        relevant.append(
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "score": round(score, 4),
            }
        )

    duration = (time.perf_counter() - start) * 1000

    logger.info(
        "🔍 [RAG] RETRIEVE_END — Busca semântica finalizada",
        query=query,
        num_results_after_filter=len(relevant),
        num_filtered_out=filtered_out,
        sources=[r["source"] for r in relevant],
        scores=[r["score"] for r in relevant],
        duration_ms=round(duration, 2),
    )

    return relevant
