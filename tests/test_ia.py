from types import SimpleNamespace as NS

import pytest

from precos.config import ConfigIA
from precos.ia import Claude, OpenAIProv, criar, custo


def test_custo_tabela():
    assert custo("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert custo("claude-opus-5-5", 1_000_000, 0, buscas=2) == pytest.approx(4.02)


def test_custo_override_config():
    assert custo("modelo-x", 1_000_000, 1_000_000, preco=(1.0, 2.0)) == pytest.approx(3.0)


def test_criar_sem_chave(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert criar(ConfigIA(provedor="claude"), "economica", {}) is None
    assert criar(ConfigIA(provedor="nenhum"), "economica", {"anthropic_api_key": "k"}) is None


def test_criar_modelos_padrao():
    p = criar(ConfigIA(provedor="claude"), "completa", {"anthropic_api_key": "k"})
    assert isinstance(p, Claude) and p.modelo == "claude-opus-5-5"
    p = criar(ConfigIA(provedor="openai", modelo_economico="gpt-x"), "economica", {"openai_api_key": "k"})
    assert isinstance(p, OpenAIProv) and p.modelo == "gpt-x"


class FakeClaude:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.chamadas.append(kw)
        return self.respostas.pop(0)


def _msg(texto, stop="end_turn", buscas=0):
    return NS(content=[NS(type="text", text=texto)], stop_reason=stop,
              usage=NS(input_tokens=1000, output_tokens=500,
                       server_tool_use=NS(web_search_requests=buscas)))


def test_claude_requisicao_completa_com_web():
    fake = FakeClaude([_msg("ok", buscas=1)])
    r = Claude("claude-opus-5-5", cliente=fake).gerar("sis", "pergunta", web=True)
    kw = fake.chamadas[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["system"] == "sis"
    assert kw["tools"][0]["type"] == "web_search_20260209"
    assert kw["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in kw["betas"]
    assert r.texto == "ok"
    assert r.custo == pytest.approx(custo("claude-opus-5-5", 1000, 500, buscas=1))


def test_claude_haiku_sem_fallback_nem_web():
    fake = FakeClaude([_msg("ok")])
    Claude("claude-haiku-5-5", cliente=fake).gerar("s", "p")
    kw = fake.chamadas[0]
    assert "fallbacks" not in kw and "tools" not in kw


def test_claude_continua_pause_turn():
    fake = FakeClaude([_msg("parcial", stop="pause_turn"), _msg("fim")])
    r = Claude("claude-opus-5-5", cliente=fake).gerar("s", "p", web=True)
    assert len(fake.chamadas) == 2
    assert fake.chamadas[1]["messages"][-1]["role"] == "assistant"
    assert r.texto == "fim"


def test_claude_recusa_vira_vazio():
    fake = FakeClaude([NS(content=[], stop_reason="refusal",
                          usage=NS(input_tokens=10, output_tokens=0, server_tool_use=None))])
    assert Claude("claude-opus-5-5", cliente=fake).gerar("s", "p").texto == ""


def test_openai_requisicao():
    chamadas = []

    def create(**kw):
        chamadas.append(kw)
        return NS(output_text="resposta", usage=NS(input_tokens=100, output_tokens=50))

    fake = NS(responses=NS(create=create))
    r = OpenAIProv("gpt-x", cliente=fake, preco=(1.0, 1.0)).gerar("sis", "p", web=True)
    assert chamadas[0]["model"] == "gpt-x"
    assert chamadas[0]["instructions"] == "sis"
    assert chamadas[0]["tools"] == [{"type": "web_search"}]
    assert r.texto == "resposta"
    assert r.custo == pytest.approx(150 / 1_000_000)
