"""
Retriever — busca semântica com filtro de relevância.

Fluxo:
  1. Recebe a query do usuário (ou do agente)
  2. Gera embedding da query
  3. Busca os K vetores mais similares no ChromaDB
  4. Filtra resultados com score abaixo do threshold
  5. Retorna apenas os chunks relevantes

Como evitar contexto irrelevante?
  - SIMILARITY_THRESHOLD = 0.3 → descarta chunks com baixa similaridade
  - Se a query não tem relação com nenhum documento, retorna lista vazia
  - O agente recebe "nada encontrado" e não alucina com contexto ruim

Em produção, adicionar:
  - Reranking com cross-encoder (ms-marco-MiniLM-L6-v2)
  - Hybrid search (keyword + semântico)
  - Cache de queries frequentes
"""

from __future__ import annotations

from src.core.config import settings
from src.rag.vectorstore import get_vectorstore

# Score mínimo de similaridade para considerar um chunk relevante.
# Abaixo disso, o chunk é descartado (provavelmente irrelevante).
# 0.3 é conservador — em produção, calibrar com base em testes.
SIMILARITY_THRESHOLD = 0.3


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """
    Busca documentos relevantes para a query usando similaridade semântica.

    Processo:
      1. ChromaDB gera o embedding da query (mesmo modelo usado na ingestão)
      2. Calcula distância coseno entre query e todos os chunks
      3. Retorna os top-K mais similares com seus scores
      4. Filtramos pelo threshold para remover ruído

    Args:
        query: Texto de busca (pergunta do cliente ou do agente).
        top_k: Quantos resultados retornar (default: settings.rag_top_k).

    Returns:
        Lista de dicts com:
          - content: texto do chunk
          - source: arquivo de origem (rastreabilidade)
          - score: score de similaridade (0 a 1, quanto maior melhor)
    """
    k = top_k or settings.rag_top_k
    store = get_vectorstore()

    # Busca semântica com scores de relevância.
    # Retorna lista de tuplas: (Document, score)
    results = store.similarity_search_with_relevance_scores(query, k=k)

    # Filtrar chunks com score abaixo do threshold.
    # Isso evita que o agente receba contexto irrelevante no prompt.
    relevant = []
    for doc, score in results:
        if score < SIMILARITY_THRESHOLD:
            continue  # Descarta — similaridade muito baixa
        relevant.append(
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "score": round(score, 4),
            }
        )

    return relevant
