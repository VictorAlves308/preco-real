"""Busca e leitura das páginas do Zoom (com Buscapé de reserva).

As duas páginas são Next.js e trazem tudo num JSON em <script id="__NEXT_DATA__">.
A leitura usa só esse JSON (nada de HTML).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

import requests

BASE = "https://www.zoom.com.br"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
_RE_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class SemDados(Exception):
    """Página sem os dados esperados (bloqueio, captcha, mudança de layout)."""


@dataclass
class Oferta:
    offer_id: str
    nome: str
    loja: str
    preco_vista: float
    total_parcelado: float | None
    parcelas: int | None
    valor_parcela: float | None
    sem_juros: bool
    marketplace: bool
    link: str


@dataclass
class Produto:
    produto_id: str
    nome: str
    url: str
    ofertas: list[Oferta] = field(default_factory=list)
    historico: list[tuple[date, float]] = field(default_factory=list)


@dataclass
class Hit:
    nome: str
    url: str
    tipo: str
    preco_vista: float
    total_parcelado: float | None
    parcelas: int | None
    sem_juros: bool
    marketplace: bool


def _sem_juros(parcelas, total) -> bool:
    # O "hasInterest" do Zoom NÃO indica juros (só diz se o parcelado é maior que o à vista).
    # As lojas mostram o parcelamento máximo sem juros, então confiamos nele.
    return parcelas is not None and parcelas >= 1 and total is not None


def extrair_estado(html: str) -> dict:
    m = _RE_NEXT.search(html or "")
    if not m:
        raise SemDados("página sem __NEXT_DATA__")
    try:
        return json.loads(m.group(1))["props"]["initialReduxState"]
    except (ValueError, KeyError, TypeError) as e:
        raise SemDados(f"JSON inesperado: {e}") from e


def parse_produto(estado: dict, url: str) -> Produto:
    offers = estado.get("offers") or {}
    lista = offers.get("offerList") or offers.get("displayOffers") or []
    produto_id = str(offers.get("currentProductID") or "")
    ofertas = []
    for o in lista:
        parcelas = o.get("numParcels") or None
        total = o.get("totalParceledValue") or None
        ofertas.append(
            Oferta(
                offer_id=str(o["id"]),
                nome=o.get("name", ""),
                loja=o.get("sellerName", ""),
                preco_vista=float(o["price"]),
                total_parcelado=float(total) if total else None,
                parcelas=int(parcelas) if parcelas else None,
                valor_parcela=o.get("parcelValue"),
                sem_juros=_sem_juros(parcelas, total),
                marketplace=bool(o.get("sellerIsMarketplace")),
                link=f"{BASE}/lead?oid={o['id']}",
            )
        )
    dias = (
        ((estado.get("priceHistory") or {}).get("priceHistory") or {})
        .get(produto_id, {})
        .get("days", [])
    )
    minimo: dict[date, float] = {}
    for d in dias:
        dia = date.fromisoformat(d["date"])
        p = float(d["price"])
        minimo[dia] = min(p, minimo.get(dia, p))
    nome = ofertas[0].nome if ofertas else ""
    return Produto(produto_id, nome, url, ofertas, sorted(minimo.items()))


def parse_busca(estado: dict) -> list[Hit]:
    hits = ((estado.get("hits") or {}).get("hits")) or []
    out = []
    for h in hits:
        inst = h.get("installments") or {}
        parcelas = inst.get("amount_months") or None
        total = inst.get("total_value") or None
        url = h.get("url", "")
        if url.startswith("/"):
            url = BASE + url
        out.append(
            Hit(
                nome=h.get("name", ""),
                url=url,
                tipo=h.get("type", ""),
                preco_vista=float(h.get("price") or 0),
                total_parcelado=float(total) if total else None,
                parcelas=int(parcelas) if parcelas else None,
                sem_juros=_sem_juros(parcelas, total),
                marketplace=bool(h.get("marketplace")),
            )
        )
    return out


def _tentar(sessao, url: str) -> str:
    r = sessao.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"}, timeout=20)
    if r.status_code != 200:
        raise SemDados(f"HTTP {r.status_code} em {url}")
    extrair_estado(r.text)  # valida
    return r.text


def baixar(url: str, sessao: requests.Session | None = None) -> str:
    """Baixa a página; se o Zoom falhar, tenta o mesmo caminho no Buscapé."""
    sessao = sessao or requests.Session()
    try:
        return _tentar(sessao, url)
    except (SemDados, requests.RequestException) as e1:
        alt = url.replace("www.zoom.com.br", "www.buscape.com.br")
        try:
            return _tentar(sessao, alt)
        except (SemDados, requests.RequestException) as e2:
            raise SemDados(f"zoom: {e1}; buscape: {e2}") from e2
