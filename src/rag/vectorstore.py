"""
Vector Store — armazenamento vetorial com ChromaDB.

O que é um vector store?
  É um banco de dados que armazena textos como vetores numéricos (embeddings).
  Quando o usuário faz uma pergunta, geramos o embedding da pergunta
  e buscamos os vetores mais similares (busca semântica).

Stack escolhida:
  - ChromaDB: banco vetorial leve, persistente em disco, zero infra
  - all-MiniLM-L6-v2: modelo de embedding compacto (384 dimensões)

Por que ChromaDB?
  - Perfeito para dev/MVP: pip install e pronto
  - Persistência em disco: sobrevive a restarts
  - API simples e compatível com LangChain
  - Em produção: migrar para pgvector (PostgreSQL) ou Pinecone

Por que all-MiniLM-L6-v2?
  - Roda em CPU (sem GPU necessária)
  - 384 dimensões (leve, rápido)
  - Suporta português razoavelmente bem
  - Em produção: usar text-embedding-3-large da OpenAI (3072 dim, melhor qualidade)
"""

from __future__ import annotations

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from src.core.config import settings

# Cache do vectorstore — evita recriar a cada chamada.
# Em Python, `global` com None → lazy initialization.
_vectorstore: Chroma | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """
    Cria o modelo de embedding.

    HuggingFaceEmbeddings baixa o modelo automaticamente na primeira execução.
    Depois fica em cache local (~/.cache/huggingface/).

    normalize_embeddings=True: normaliza vetores para unit length.
    Isso melhora a busca por cosseno (similaridade mais precisa).
    """
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,    # all-MiniLM-L6-v2
        model_kwargs={"device": "cpu"},         # Forçar CPU (sem GPU)
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vectorstore() -> Chroma:
    """
    Retorna o vector store (singleton).

    Na primeira chamada: cria o ChromaDB e conecta ao diretório persistente.
    Nas chamadas seguintes: retorna a mesma instância (rápido).

    O ChromaDB armazena:
      - Texto original de cada chunk
      - Embedding (vetor numérico) do chunk
      - Metadados (source, etc.)
    """
    global _vectorstore

    # Se já existe, retorna direto (singleton)
    if _vectorstore is not None:
        return _vectorstore

    # Criar nova instância conectando ao diretório persistente
    _vectorstore = Chroma(
        collection_name="pj_knowledge",         # Nome da coleção no ChromaDB
        embedding_function=_get_embeddings(),    # Modelo de embedding
        persist_directory=settings.chroma_persist_dir,  # ./data/chroma
    )
    return _vectorstore


def ingest(chunks: list) -> None:
    """
    Ingere uma lista de chunks no vector store.

    IMPORTANTE: limpa a coleção inteira antes de re-ingerir.
    Isso evita acúmulo de chunks antigos/duplicados que causam
    alucinação — o LLM recebia contexto de documentos removidos.

    Para cada chunk, o ChromaDB:
      1. Gera o embedding usando o modelo configurado
      2. Armazena texto + embedding + metadados
      3. Persiste em disco automaticamente

    Args:
        chunks: Lista de Document objects (saída do chunker).
    """
    global _vectorstore

    store = get_vectorstore()
    if not chunks:
        return

    # Limpar coleção antes de re-ingerir.
    # Sem isso, cada ingestão acumula chunks — inclusive de arquivos
    # que já foram removidos do knowledge_base/.
    # Foi a causa raiz de alucinação: o RAG retornava chunks de um
    # faq_pj.md antigo que falava "contrato social" e "documentos dos sócios".
    existing = store._collection.count()
    if existing > 0:
        # Pegar todos os IDs e deletar — ChromaDB não aceita where={} vazio.
        all_ids = store._collection.get()["ids"]
        store._collection.delete(ids=all_ids)
        _vectorstore = None                 # Forçar recriar o singleton
        store = get_vectorstore()           # Reconecta limpo

    store.add_documents(chunks)
