"""
Ponto de entrada para rodar o projeto localmente (PyCharm / terminal).

Como usar:
  - No PyCharm: clique com botão direito neste arquivo → Run 'run'
  - No terminal: python run.py

Ele faz duas coisas:
  1. Ingere a base de conhecimento no ChromaDB (RAG)
  2. Sobe o servidor FastAPI na porta configurada

Depois acesse:
  - Swagger UI: http://localhost:8000/docs
  - Health:     http://localhost:8000/healthz
"""

import time
import uvicorn
from src.core.config import settings
from src.rag.ingest import run_ingestion


if __name__ == "__main__":
    print()
    print("=" * 62)
    print("  🏦  PJ ASSISTANT AGENT — Inicializando...")
    print("=" * 62)
    print()

    # Passo 1: Ingerir base de conhecimento
    print("📚 [1/2] Ingerindo base de conhecimento no ChromaDB (RAG)...")
    ingest_start = time.perf_counter()
    count = run_ingestion()
    ingest_duration = time.perf_counter() - ingest_start
    print(f"✅ [1/2] {count} chunks ingeridos com sucesso! ({ingest_duration:.1f}s)")
    print()

    # Passo 2: Subir servidor
    print(f"🚀 [2/2] Subindo servidor na porta {settings.port}...")
    print()

    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
