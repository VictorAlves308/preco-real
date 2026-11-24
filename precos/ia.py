"""Provedores de IA (Claude ou OpenAI) com estimativa de custo por chamada."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

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
}
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


def criar(cfg: ConfigIA, nivel: str, chaves: dict):
    """Devolve o provedor para o nível ('economica' ou 'completa'), ou None se não houver IA."""
    if cfg.provedor not in PADRAO:
        return None
    nome_chave = "anthropic_api_key" if cfg.provedor == "claude" else "openai_api_key"
    chave = chaves.get(nome_chave) or os.environ.get(nome_chave.upper())
    if not chave:
        log.info("IA: sem %s, usando só as regras", nome_chave)
        return None
    modelo = (cfg.modelo_completo if nivel == "completa" else cfg.modelo_economico) or PADRAO[cfg.provedor][nivel]
    preco = (cfg.preco_entrada, cfg.preco_saida) if cfg.preco_entrada is not None and cfg.preco_saida is not None else None
    cls = Claude if cfg.provedor == "claude" else OpenAIProv
    return cls(modelo, api_key=chave, preco=preco)
