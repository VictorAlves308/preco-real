"""Regras: filtro pelo nome, quem pode ser avisado, veredito de promoção e ordenação."""
from __future__ import annotations

import re
from datetime import date, timedelta
from statistics import median
from typing import Literal

from .config import Item
from .zoom import Oferta

Veredito = Literal["real", "maquiada", "normal", "sem_historico"]

_RE_POL = re.compile(r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:\"|''|”|pol\b|polegadas)", re.I)
_RE_NUM = re.compile(r"\b(\d{2}(?:[.,]\d)?)\b(?!\s*(?:hz|ms|k\b|p\b|w\b|%))", re.I)
_RE_HZ = re.compile(r"(\d{2,3})\s*hz", re.I)
_RE_PAINEL = re.compile(r"\b(IPS|VA)\b", re.I)

DIAS_JANELA = 90
MIN_DIAS = 14


def _palavra(p: str, texto: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", texto, re.I) is not None


def _polegadas(nome: str) -> float | None:
    m = _RE_POL.search(nome) or _RE_NUM.search(nome)
    return float(m.group(1).replace(",", ".")) if m else None


def passa_filtro_nome(nome: str, item: Item) -> tuple[bool, list[str]]:
    tags: list[str] = []
    if item.polegadas_min is not None or item.polegadas_max is not None:
        pol = _polegadas(nome)
        if pol is None:
            return False, tags
        if item.polegadas_min is not None and pol < item.polegadas_min:
            return False, tags
        if item.polegadas_max is not None and pol > item.polegadas_max:
            return False, tags
    if item.hz_min is not None:
        hz = [int(h) for h in _RE_HZ.findall(nome)]
        if not hz or max(hz) < item.hz_min:
            return False, tags
    if item.marcas and not any(_palavra(m, nome) for m in item.marcas):
        return False, tags
    if not all(_palavra(p, nome) for p in item.exigir):
        return False, tags
    if any(_palavra(p, nome) for p in item.excluir):
        return False, tags
    if item.hz_min is not None and not _RE_PAINEL.search(nome):
        tags.append("painel não confirmado")
    return True, tags


def elegivel(o: Oferta, item: Item) -> bool:
    if not (o.sem_juros and not o.marketplace and o.parcelas and o.total_parcelado):
        return False
    if item.limite_total is not None and o.total_parcelado > item.limite_total:
        return False
    if item.limite_vista is not None and o.preco_vista > item.limite_vista:
        return False
    return True


def veredito(preco_vista: float, historico: list[tuple[date, float]], hoje: date) -> Veredito:
    inicio = hoje - timedelta(days=DIAS_JANELA)
    precos = [p for d, p in historico if inicio <= d <= hoje]
    if len(precos) < MIN_DIAS:
        return "sem_historico"
    med, mini = median(precos), min(precos)
    if preco_vista <= 0.90 * med and preco_vista <= 1.03 * mini:
        return "real"
    if preco_vista >= 1.05 * med:
        return "maquiada"
    return "normal"


def ordenar(ofertas: list[Oferta]) -> list[Oferta]:
    return sorted(ofertas, key=lambda o: ((o.parcelas or 0) < 10, o.total_parcelado or float("inf")))


_RE_UNIDADE_FIM = re.compile(r"\d+(?:HZ|MS|GB|TB|MB|GHZ|MHZ|K|P|W|MP|V|MAH|MM|CM|POL)", re.I)


def extrair_codigo(nome: str) -> str | None:
    """Código do modelo no nome do anúncio (ex.: '24U411B-B.AWZM' -> '24U411B'), ou None.

    Serve para ligar um anúncio solto ao produto do catálogo e para o histórico próprio.
    """
    melhor = None
    for token in re.split(r"[\s,;()\[\]|]+", nome or ""):
        t = re.split(r"[-./]", token.strip("\"'”“"))[0].upper()
        if not re.fullmatch(r"[A-Z0-9]{4,16}", t):
            continue
        if sum(c.isdigit() for c in t) < 2 or not any(c.isalpha() for c in t):
            continue
        if _RE_UNIDADE_FIM.fullmatch(t):
            continue
        if melhor is None or len(t) > len(melhor):
            melhor = t
    return melhor
