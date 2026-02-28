"""
Ponto de entrada para rodar o projeto localmente (PyCharm / terminal).

Como usar:
  - No PyCharm: clique com botão direito neste arquivo → Run 'run'
  - No terminal: python run.py

Ele faz duas coisas:
  1. Ingere a base de conhecimento no ChromaDB (RAG)
  2. Sobe o servidor FastAPI na porta 8000

Depois acesse:
  - Swagger UI: http://localhost:8000/docs
  - Health:     http://localhost:8000/healthz
"""

import uvicorn
from src.rag.ingest import run_ingestion


if __name__ == "__main__":
    # Passo 1: Ingerir base de conhecimento
    print("📚 Ingerindo base de conhecimento (RAG)...")
    count = run_ingestion()
    print(f"✅ {count} chunks ingeridos com sucesso!")

    # Passo 2: Subir servidor
    print("🚀 Subindo servidor em http://localhost:8000")
    print("📖 Swagger UI em http://localhost:8000/docs")
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

