"""
Chunking da base de conhecimento.

O que é chunking?
  Documentos grandes não cabem inteiros no prompt do LLM.
  Precisamos quebrá-los em pedaços menores (chunks) e buscar
  apenas os pedaços relevantes para cada pergunta.

Estratégia escolhida:
  - RecursiveCharacterTextSplitter (LangChain)
  - Separadores hierárquicos: parágrafo → linha → frase → palavra
  - chunk_size=512 chars (~128 tokens) — bom equilíbrio
  - chunk_overlap=64 chars — evita cortar informação nas bordas

Por que 512 chars?
  - Muito pequeno (<200): perde contexto, chunks ficam incoerentes
  - Muito grande (>1000): busca perde precisão, retorna ruído
  - 512 é o sweet spot para documentos de política/FAQ

Por que overlap?
  Se um parágrafo importante fica exatamente na borda entre 2 chunks,
  o overlap garante que ele aparece nos dois. Sem overlap, perdemos informação.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.core.config import settings


def load_and_chunk(knowledge_dir: str = "data/knowledge_base") -> list:
    """
    Carrega documentos .md da base de conhecimento e retorna chunks.

    Fluxo:
      1. Escaneia o diretório recursivamente por arquivos .md
      2. Carrega o conteúdo de cada arquivo como um Document
      3. Divide cada Document em chunks menores
      4. Preserva metadados (source) para rastreabilidade

    Args:
        knowledge_dir: Caminho para o diretório com os documentos.

    Returns:
        Lista de Document objects (chunks) prontos para embedding.
    """

    # Verificar se o diretório existe
    path = Path(knowledge_dir)
    if not path.exists():
        return []

    # ─── Passo 1: Carregar documentos ───────────────────────────────
    # DirectoryLoader escaneia o diretório e carrega cada .md como Document.
    # TextLoader lê o conteúdo como texto puro (UTF-8).
    loader = DirectoryLoader(
        str(path),
        glob="**/*.md",                     # Apenas arquivos Markdown
        loader_cls=TextLoader,              # Loader simples de texto
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()

    # ─── Passo 2: Dividir em chunks ────────────────────────────────
    # RecursiveCharacterTextSplitter tenta dividir por separadores na ordem:
    #   1. "\n\n" (parágrafo) — preferido, mantém unidade semântica
    #   2. "\n" (linha) — segundo melhor
    #   3. ". " (frase) — se o parágrafo ainda é grande demais
    #   4. " " (palavra) — último recurso
    #   5. "" (caractere) — emergência
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(docs)

    # ─── Passo 3: Garantir metadados ───────────────────────────────
    # Cada chunk mantém o `source` (arquivo de origem).
    # Isso permite rastrear de onde veio cada informação na resposta.
    for chunk in chunks:
        chunk.metadata.setdefault("source", chunk.metadata.get("source", "unknown"))

    return chunks
