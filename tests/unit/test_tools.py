"""
Testes unitários — tools do agente.

Testa as 2 tools determinísticas (não dependem de LLM):
  1. analyze_transactions → análise de transações
  2. assess_credit_profile → avaliação de perfil de crédito

A 3ª tool (search_knowledge_base) é testada em integração
porque depende do ChromaDB com dados ingeridos.

Padrão de teste:
  - Cada tool recebe JSON string como input (LLM gera JSON)
  - Testamos: dados válidos, dados vazios, JSON inválido
  - Tools NUNCA devem lançar exceção (retornam "Erro: ...")
    porque exceções quebrariam o loop do LangGraph

Por que as tools recebem JSON string?
  - O LLM (GPT-4o-mini) gera os argumentos como string
  - LangChain converte em dict, mas o campo é string
  - Isso permite que o LLM construa o input incrementalmente
"""

import json
import pytest

from src.agent.tools import analyze_transactions, assess_credit_profile


class TestAnalyzeTransactions:
    """Testes da tool analyze_transactions."""

    def test_valid_transactions(self, sample_transactions):
        """Transações válidas devem gerar relatório com totais e categorias."""
        # Serializa as transações como JSON (igual ao LLM faria)
        data = json.dumps([t.model_dump() for t in sample_transactions])

        result = analyze_transactions.invoke({"transactions_json": data})

        # Deve conter o total movimentado (soma de absolutos)
        assert "Total movimentado" in result

        # Deve listar as categorias encontradas
        assert "Vendas" in result

    def test_empty_transactions(self):
        """Lista vazia deve retornar mensagem informativa, não erro."""
        result = analyze_transactions.invoke({"transactions_json": "[]"})

        # Deve indicar que não há transações (não deve quebrar)
        assert "Nenhuma transação" in result

    def test_invalid_json(self):
        """JSON inválido deve retornar erro gracioso (não exception)."""
        result = analyze_transactions.invoke({"transactions_json": "not json"})

        # Deve conter "Erro" na resposta (o LLM vai ver isso e adaptar)
        assert "Erro" in result


class TestAssessCreditProfile:
    """Testes da tool assess_credit_profile."""

    def test_valid_profile(self, sample_profile):
        """Perfil válido com score 720 deve ser classificado como risco baixo."""
        data = sample_profile.model_dump_json()

        result = assess_credit_profile.invoke({"profile_json": data})

        # Deve mencionar o nome da empresa
        assert "Acme Ltda" in result

        # Score 720 >= 700 → risco "baixo"
        assert "baixo" in result

    def test_high_risk_profile(self):
        """Score 300 (< 400) deve ser classificado como risco alto."""
        data = json.dumps({
            "customer_id": "x",
            "company_name": "Risky Corp",
            "credit_score": 300,
        })

        result = assess_credit_profile.invoke({"profile_json": data})

        # Score 300 < 400 → risco "alto"
        assert "alto" in result

    def test_invalid_profile(self):
        """JSON inválido deve retornar erro gracioso."""
        result = assess_credit_profile.invoke({"profile_json": "bad"})

        # Mesmo com input ruim, a tool não deve lançar exceção
        assert "Erro" in result
