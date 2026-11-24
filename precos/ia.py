"""Provedores de IA (Claude ou OpenAI) com estimativa de custo por chamada."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import ConfigIA

log = logging.getLogger(__name__)

# US$ por 1 milhão de tokens (entrada, saída). Modelos fora da tabela: use preco_entrada/preco_saida
# em [ia] no config.toml; sem isso, usamos uma estimativa alta para o teto de gasto não estourar.
PRECOS = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
PRECO_DESCONHECIDO = (5.00, 25.00)
CUSTO_BUSCA_WEB = 0.01  # US$ por busca na web

PADRAO = {
    "claude": {"economica": "claude-haiku-5-5", "completa": "claude-opus-5-5"},
    "openai": {"economica": "gpt-5-mini", "completa": "gpt-5"},
    # Pelo plano da pessoa (programa instalado). None = modelo padrão que ela usa no programa.
    "claude_code": {"economica": "haiku", "completa": None},
    "codex": {"economica": None, "completa": None},
}
NOMES = {"claude": "Claude (API)", "openai": "OpenAI (API)", "claude_code": "Claude Code", "codex": "Codex"}

# ---------------------------------------------------------------- erros com mensagem amigável

_PADROES = [
    ("limite", r"usage limit|rate.?limit|limit reached|hit your .*limit|quota|\b429\b|too many requests|"
               r"credit balance|insufficient_quota|exceeded"),
    ("login", r"not logged in|/login|codex login|log ?in again|unauthori[sz]ed|\b401\b|\b403\b|"
              r"invalid api key|authentication|expired"),
    ("conexao", r"connection|timed? ?out|network|enotfound|getaddrinfo|econnre|unreachable|\b50[234]\b|overloaded"),
]


def classificar_erro(texto: str) -> str:
    t = (texto or "").lower()
    for tipo, padrao in _PADROES:
        if re.search(padrao, t):
            return tipo
    return "outro"


class ErroIA(Exception):
    def __init__(self, tipo: str, nome: str, detalhe: str = ""):
        self.tipo, self.nome, self.detalhe = tipo, nome, (detalhe or "").strip()[:300]
        self.mensagem = {
            "limite": f"{nome}: o limite de uso do seu plano acabou. Ele volta sozinho quando o limite renovar.",
            "login": f"{nome}: você não está conectado (ou o login expirou). Clique em Entrar nas Configurações.",
            "nao_instalado": f"{nome} não está instalado neste PC.",
            "conexao": f"Não consegui falar com {nome} (sem internet ou serviço fora do ar). "
                       "Tento de novo na próxima verificação.",
            "outro": f"{nome} respondeu com erro: {self.detalhe or 'sem detalhes'}",
        }[tipo]
        super().__init__(self.mensagem)


def _rodar_cmd(cmd: list[str], entrada: str, timeout: int, cwd: str):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, cwd=cwd, creationflags=flags)
    return r.returncode, r.stdout, r.stderr
# Modelos que aceitam a busca na web nova e o fallback do servidor
_CLAUDE_COM_WEB = ("claude-opus-5-5", "claude-sonnet-5-5")


@dataclass
class Resposta:
    texto: str
    custo: float


def custo(modelo: str, tokens_entrada: int, tokens_saida: int, buscas: int = 0,
          preco: tuple[float, float] | None = None) -> float:
    pe, ps = preco or PRECOS.get(modelo, PRECO_DESCONHECIDO)
    return tokens_entrada * pe / 1e6 + tokens_saida * ps / 1e6 + buscas * CUSTO_BUSCA_WEB


class Claude:
    def __init__(self, modelo: str, api_key: str | None = None, cliente=None, preco=None):
        self.modelo = modelo
        self.preco = preco
        if cliente is None:
            import anthropic

            cliente = anthropic.Anthropic(api_key=api_key)
        self.cliente = cliente

    def gerar(self, sistema: str, prompt: str, web: bool = False) -> Resposta:
        kw = {
            "model": self.modelo,
            "max_tokens": 16000,
            "system": sistema,
            "output_config": {"effort": "low"},
        }
        if self.modelo in _CLAUDE_COM_WEB:
            kw["betas"] = ["server-side-fallback-2026-07-01"]
            kw["fallbacks"] = "default"
            if web:
                kw["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}]
        mensagens = [{"role": "user", "content": prompt}]
        total = 0.0
        for _ in range(4):  # pause_turn: a busca na web pode pausar o turno; continua até 3 vezes
            r = self.cliente.beta.messages.create(messages=mensagens, **kw)
            uso = r.usage
            buscas = getattr(getattr(uso, "server_tool_use", None), "web_search_requests", 0) or 0
            total += custo(self.modelo, uso.input_tokens, uso.output_tokens, buscas, self.preco)
            if r.stop_reason != "pause_turn":
                break
            mensagens = mensagens + [{"role": "assistant", "content": r.content}]
        if r.stop_reason == "refusal":
            log.warning("IA recusou a pergunta")
            return Resposta("", total)
        texto = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return Resposta(texto, total)


class OpenAIProv:
    def __init__(self, modelo: str, api_key: str | None = None, cliente=None, preco=None):
        self.modelo = modelo
        self.preco = preco
        if cliente is None:
            import openai

            cliente = openai.OpenAI(api_key=api_key)
        self.cliente = cliente

    def gerar(self, sistema: str, prompt: str, web: bool = False) -> Resposta:
        kw = {"model": self.modelo, "instructions": sistema, "input": prompt}
        if web:
            kw["tools"] = [{"type": "web_search"}]
        r = self.cliente.responses.create(**kw)
        uso = r.usage
        return Resposta(r.output_text or "", custo(self.modelo, uso.input_tokens, uso.output_tokens, 0, self.preco))


class ClaudeCode:
    """Usa o plano Claude da pessoa pelo programa Claude Code (claude -p)."""

    nome = "Claude Code"

    def __init__(self, exe: str, modelo: str | None = None, rodar=_rodar_cmd, timeout: int = 300):
        self.exe, self.modelo, self.rodar, self.timeout = exe, modelo, rodar, timeout

    def gerar(self, sistema: str, prompt: str, web: bool = False) -> Resposta:
        cmd = [self.exe, "-p", "--output-format", "json"]
        if self.modelo:
            cmd += ["--model", self.modelo]
        if web:
            cmd += ["--allowedTools", "WebSearch", "WebFetch"]
        with tempfile.TemporaryDirectory() as pasta:  # pasta vazia: o programa não lê nada do PC
            try:
                rc, out, err = self.rodar(cmd, f"{sistema}\n\n{prompt}", self.timeout, pasta)
            except FileNotFoundError as e:
                raise ErroIA("nao_instalado", self.nome, str(e)) from e
            except subprocess.TimeoutExpired as e:
                raise ErroIA("conexao", self.nome, "demorou demais") from e
        try:
            d = json.loads(out)
        except ValueError:
            raise ErroIA(classificar_erro(err or out), self.nome, err or out) from None
        if d.get("is_error") or rc != 0:
            msg = str(d.get("result") or err)
            raise ErroIA(classificar_erro(msg), self.nome, msg)
        return Resposta(str(d.get("result", "")), 0.0)  # pelo plano: sem custo por uso


class Codex:
    """Usa o plano ChatGPT da pessoa pelo programa Codex (codex exec)."""

    nome = "Codex"

    def __init__(self, exe: str, modelo: str | None = None, rodar=_rodar_cmd, timeout: int = 300):
        self.exe, self.modelo, self.rodar, self.timeout = exe, modelo, rodar, timeout

    def gerar(self, sistema: str, prompt: str, web: bool = False) -> Resposta:
        with tempfile.TemporaryDirectory() as pasta:
            saida = str(Path(pasta) / "resposta.txt")
            cmd = [self.exe] + (["--search"] if web else []) + ["exec", "--skip-git-repo-check", "-s", "read-only"]
            if self.modelo:
                cmd += ["-m", self.modelo]
            cmd += ["-o", saida, "-"]
            try:
                rc, out, err = self.rodar(cmd, f"{sistema}\n\n{prompt}", self.timeout, pasta)
            except FileNotFoundError as e:
                raise ErroIA("nao_instalado", self.nome, str(e)) from e
            except subprocess.TimeoutExpired as e:
                raise ErroIA("conexao", self.nome, "demorou demais") from e
            texto = Path(saida).read_text(encoding="utf-8", errors="replace") if Path(saida).exists() else ""
        if rc != 0 or not texto.strip():
            msg = (err or out or "").strip()
            raise ErroIA(classificar_erro(msg), self.nome, msg)
        return Resposta(texto.strip(), 0.0)


EXECUTAVEIS = {"claude_code": "claude", "codex": "codex"}


def modelo_escolhido(cfg: ConfigIA, provedor: str, nivel: str) -> str | None:
    """Modelo escolhido para o provedor (tela), senão o campo antigo, senão o padrão."""
    escolhido = (cfg.modelos.get(provedor) or {}).get(nivel)
    if escolhido:
        return escolhido
    if provedor == cfg.provedor:
        antigo = cfg.modelo_completo if nivel == "completa" else cfg.modelo_economico
        if antigo:
            return antigo
    return PADRAO.get(provedor, {}).get(nivel)


def criar(cfg: ConfigIA, nivel: str, chaves: dict, provedor: str | None = None):
    """Devolve o provedor para o nível ('economica' ou 'completa'), ou None se não houver IA."""
    if provedor is not None:
        from dataclasses import replace

        cfg = replace(cfg, provedor=provedor)
    if cfg.provedor not in PADRAO:
        return None
    if cfg.provedor in EXECUTAVEIS:  # pelo plano: precisa do programa instalado
        exe = shutil.which(EXECUTAVEIS[cfg.provedor])
        if not exe:
            log.info("IA: %s não está instalado, usando só as regras", NOMES[cfg.provedor])
            return None
        return (ClaudeCode if cfg.provedor == "claude_code" else Codex)(exe, modelo_escolhido(cfg, cfg.provedor, nivel))
    nome_chave = "anthropic_api_key" if cfg.provedor == "claude" else "openai_api_key"
    chave = chaves.get(nome_chave) or os.environ.get(nome_chave.upper())
    if not chave:
        log.info("IA: sem %s, usando só as regras", nome_chave)
        return None
    modelo = modelo_escolhido(cfg, cfg.provedor, nivel)
    preco = (cfg.preco_entrada, cfg.preco_saida) if cfg.preco_entrada is not None and cfg.preco_saida is not None else None
    cls = Claude if cfg.provedor == "claude" else OpenAIProv
    return cls(modelo, api_key=chave, preco=preco)
