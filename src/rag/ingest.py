"""
Script de ingestão — popula a base vetorial com a base de conhecimento.

Usage:
  python -m src.rag.ingest

O que faz:
  1. Carrega todos os .md de data/knowledge_base/
  2. Divide em chunks (512 chars, overlap 64)
  3. Gera embeddings para cada chunk
  4. Armazena no ChromaDB (persiste em data/chroma/)

Quando rodar:
  - Na primeira vez, antes de iniciar o servidor
  - Sempre que adicionar/atualizar documentos na base de conhecimento
  - Em produção: parte do pipeline de CI/CD
"""

from src.rag.chunker import load_and_chunk
from src.rag.vectorstore import ingest


def run_ingestion(knowledge_dir: str = "data/knowledge_base") -> int:
    """
    Pipeline completo de ingestão.

    Fluxo:
      load_and_chunk() → lista de Document chunks
      ingest()         → armazena no ChromaDB com embeddings

    Args:
        knowledge_dir: Diretório com os documentos .md

    Returns:
        Número de chunks ingeridos.
    """
    # Passo 1: Carregar e dividir documentos em chunks
    chunks = load_and_chunk(knowledge_dir)

    # Passo 2: Gerar embeddings e armazenar no vector store
    ingest(chunks)

    return len(chunks)


# Permite rodar diretamente: python -m src.rag.ingest
if __name__ == "__main__":
    count = run_ingestion()
    print(f"✅ {count} chunks ingeridos com sucesso.")
