import json
from datetime import date
from pathlib import Path

import pytest

from precos.config import Config, ConfigIA, Item
from precos.estado import Estado
from precos.ia import ClaudeCode, Codex, ErroIA, classificar_erro, criar
from precos.pesquisa import Pesquisador


@pytest.mark.parametrize("texto,tipo", [
    ("Claude AI usage limit reached|1764000000", "limite"),
    ("You've hit your usage limit. Upgrade to Pro", "limite"),
    ("Error code: 429 - rate_limit_error", "limite"),
    ("Your credit balance is too low to access the Anthropic API", "limite"),
    ("insufficient_quota", "limite"),
    ("Invalid API key · Please run /login", "login"),
    ("Not logged in. Run codex login", "login"),
    ("Error code: 401 - authentication_error", "login"),
    ("Connection error.", "conexao"),
    ("getaddrinfo ENOTFOUND api.anthropic.com", "conexao"),
    ("request timed out", "conexao"),
    ("algo estranho", "outro"),
])
def test_classificar_erro(texto, tipo):
    assert classificar_erro(texto) == tipo


def test_erro_ia_mensagem_amigavel():
    e = ErroIA("limite", "Claude Code", "usage limit reached")
    assert "limite de uso do seu plano" in e.mensagem and e.mensagem.startswith("Claude Code")


class Runner:
    def __init__(self, rc=0, out="", err="", arquivo=None):
        self.rc, self.out, self.err, self.arquivo = rc, out, err, arquivo
        self.chamadas = []

    def __call__(self, cmd, entrada, timeout, cwd):
        self.chamadas.append({"cmd": cmd, "entrada": entrada, "cwd": cwd})
        if self.arquivo is not None and "-o" in cmd:
            Path(cmd[cmd.index("-o") + 1]).write_text(self.arquivo, encoding="utf-8")
        return self.rc, self.out, self.err


def test_claude_code_comando_e_resposta():
    r = Runner(out=json.dumps({"type": "result", "is_error": False, "result": "OK"}))
    resp = ClaudeCode("claude.exe", modelo="haiku", rodar=r).gerar("sis", "pergunta", web=True)
    c = r.chamadas[0]
    assert c["cmd"][:4] == ["claude.exe", "-p", "--output-format", "json"]
    assert c["cmd"][c["cmd"].index("--model") + 1] == "haiku"
    assert "WebSearch" in c["cmd"]
    assert "sis" in c["entrada"] and "pergunta" in c["entrada"]
    assert resp.texto == "OK" and resp.custo == 0.0


def test_claude_code_erro_de_limite():
    r = Runner(rc=1, out=json.dumps({"type": "result", "is_error": True, "result": "Claude AI usage limit reached"}))
    with pytest.raises(ErroIA) as e:
        ClaudeCode("claude.exe", rodar=r).gerar("s", "p")
    assert e.value.tipo == "limite"


def test_codex_comando_e_resposta():
    r = Runner(arquivo="resposta final")
    resp = Codex("codex.cmd", rodar=r).gerar("sis", "p", web=True)
    cmd = r.chamadas[0]["cmd"]
    assert cmd[:3] == ["codex.cmd", "--search", "exec"]
    assert "--skip-git-repo-check" in cmd and cmd[-1] == "-"
    assert cmd[cmd.index("-s") + 1] == "read-only"
    assert resp.texto == "resposta final"


def test_codex_sem_login():
    r = Runner(rc=1, err="Error: Not logged in. Run codex login")
    with pytest.raises(ErroIA) as e:
        Codex("codex.cmd", rodar=r).gerar("s", "p")
    assert e.value.tipo == "login"


def test_criar_cli(monkeypatch):
    import precos.ia as ia
    monkeypatch.setattr(ia.shutil, "which", lambda n: None)
    assert criar(ConfigIA(provedor="claude_code"), "economica", {}) is None
    monkeypatch.setattr(ia.shutil, "which", lambda n: f"C:/bin/{n}.cmd")
    p = criar(ConfigIA(provedor="claude_code"), "economica", {})
    assert isinstance(p, ClaudeCode) and p.modelo == "haiku"
    assert isinstance(criar(ConfigIA(provedor="codex"), "completa", {}), Codex)


class Quebra:
    def __init__(self, tipo):
        self.tipo = tipo

    def gerar(self, *a, **k):
        raise ErroIA(self.tipo, "Claude Code", "detalhe")


def test_pesquisador_registra_erro_e_avisa_limite_uma_vez_por_dia(tmp_path):
    avisos = []
    cfg = Config(itens=[], ia=ConfigIA(provedor="claude_code"))
    e = Estado(tmp_path / "e.db")
    item = Item(nome="X", pesquisa="economica", descricao="x")
    p = Pesquisador(cfg, e, {"economica": Quebra("limite")}, hoje=date(2026, 11, 24), notificar=avisos.append)
    assert p.filtrar(item, ["A"]) == {"A": (True, "")}  # sem IA, segue com as regras
    st = json.loads(e.cache_ler("ia_status"))
    assert st["tipo"] == "limite" and "limite de uso" in st["mensagem"]
    p.filtrar(item, ["B"])
    assert len(avisos) == 1


def test_pesquisador_limpa_erro_quando_volta(tmp_path):
    from precos.ia import Resposta

    class Ok:
        def gerar(self, *a, **k):
            return Resposta('[{"i": 1, "ok": true, "motivo": ""}]', 0.0)

    e = Estado(tmp_path / "e.db")
    e.cache_gravar("ia_status", json.dumps({"tipo": "limite", "mensagem": "m"}))
    cfg = Config(itens=[], ia=ConfigIA(provedor="claude_code"))
    Pesquisador(cfg, e, {"economica": Ok()}).filtrar(Item(nome="X", pesquisa="economica"), ["A"])
    assert json.loads(e.cache_ler("ia_status"))["tipo"] == "ok"


def test_modelo_por_provedor(tmp_path, monkeypatch):
    import precos.ia as ia
    from precos.config import carregar
    c = tmp_path / "c.toml"
    c.write_text('[ia]\nprovedor = "claude_code"\n\n[ia.modelos.claude_code]\neconomica = "sonnet"\n', encoding="utf-8")
    cfg = carregar(c, tmp_path / "s.toml")
    assert cfg.ia.modelos == {"claude_code": {"economica": "sonnet"}}
    monkeypatch.setattr(ia.shutil, "which", lambda n: f"C:/bin/{n}.cmd")
    assert criar(cfg.ia, "economica", {}).modelo == "sonnet"
    assert criar(cfg.ia, "completa", {}).modelo is None  # sem escolha: padrão do programa
