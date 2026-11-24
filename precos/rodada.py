"""Uma rodada: para cada item, busca ofertas, aplica as regras e avisa o que vale a pena."""
from __future__ import annotations

import logging
import random
import time
from datetime import date
from urllib.parse import parse_qs, urlparse

from . import zoom
from .avisos import Achado, abrir_janela, enviar_ntfy, enviar_whatsapp, formatar
from .config import Config, Item
from .estado import Estado
from .regras import elegivel, ordenar, passa_filtro_nome, veredito
from .zoom import Hit, Oferta

log = logging.getLogger(__name__)

MAX_POR_ITEM = 3
MAX_PAGINAS_BUSCA = 8


def _oferta_de_hit(h: Hit) -> Oferta:
    oid = parse_qs(urlparse(h.url).query).get("oid", [h.url])[0]
    return Oferta(oid, h.nome, h.loja, h.preco_vista, h.total_parcelado, h.parcelas, None,
                  h.sem_juros, h.marketplace, h.url)


def _candidatos_produto(html: str, url: str, item: Item, hoje: date, tags: list[str]):
    p = zoom.parse_produto(zoom.extrair_estado(html), url)
    return [(o, veredito(o.preco_vista, p.historico, hoje), tags)
            for o in ordenar([o for o in p.ofertas if elegivel(o, item)])]


def _candidatos(item: Item, baixar, hoje: date, dormir):
    html = baixar(item.url)
    if item.tipo == "produto":
        return _candidatos_produto(html, item.url, item, hoje, [])
    hits, urls_vistas = [], set()
    paginas = [html]
    for u in item.urls:
        dormir(random.uniform(3, 6))
        try:
            paginas.append(baixar(u))
        except Exception as e:  # noqa: BLE001
            log.warning("%s: busca %s falhou: %s", item.nome, u, e)
    for pagina in paginas:
        for h in zoom.parse_busca(zoom.extrair_estado(pagina)):
            ok, tags = passa_filtro_nome(h.nome, item)
            if ok and h.url not in urls_vistas:
                urls_vistas.add(h.url)
                hits.append((h, tags))
    hits.sort(key=lambda ht: ht[0].total_parcelado or float("inf"))
    out = []
    for h, tags in hits[:MAX_PAGINAS_BUSCA]:
        if "/lead?" in h.url:
            o = _oferta_de_hit(h)
            if elegivel(o, item):
                out.append((o, "sem_historico", tags))
            continue
        dormir(random.uniform(3, 6))
        try:
            out += _candidatos_produto(baixar(h.url), h.url, item, hoje, tags)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: página %s falhou: %s", item.nome, h.url, e)
    return out


def _escolher(item: Item, cands, estado: Estado) -> list[Achado]:
    menor = estado.menor_visto(item.nome)
    escolhidos, vistos = [], set()
    # Entre produtos diferentes vale o mais barato; dentro de um produto, 10x vem primeiro (ordenar).
    for o, v, tags in sorted(cands, key=lambda c: c[0].total_parcelado):
        if o.offer_id in vistos or v == "maquiada":
            continue
        if v == "normal" and not (item.modo == "mais_barato" and (menor is None or o.total_parcelado < menor)):
            continue
        if estado.ja_avisado(item.nome, o.offer_id, o.total_parcelado):
            continue
        vistos.add(o.offer_id)
        escolhidos.append(Achado(item.nome, o, v, list(tags)))
        if len(escolhidos) == MAX_POR_ITEM:
            break
    if cands:
        estado.registrar_preco(item.nome, min(c[0].total_parcelado for c in cands))
    return escolhidos


def avisar_todos(cfg: Config):
    def avisar(achados: list[Achado]) -> None:
        titulo, corpo = formatar(achados)
        links = [a.oferta.link for a in achados]
        try:
            abrir_janela(titulo, corpo, links)
        except Exception as e:  # noqa: BLE001
            log.warning("janela falhou: %s", e)
        enviar_ntfy(cfg, titulo, corpo, links[0] if links else None)
        enviar_whatsapp(cfg, f"{titulo}\n\n{corpo}")
    return avisar


def rodar(cfg: Config, estado: Estado, baixar=zoom.baixar, avisar=None,
          hoje: date | None = None, dormir=time.sleep) -> list[Achado]:
    hoje = hoje or date.today()
    avisar = avisar or avisar_todos(cfg)
    achados: list[Achado] = []
    for i, item in enumerate(cfg.itens):
        if i:
            dormir(random.uniform(3, 6))
        try:
            cands = _candidatos(item, baixar, hoje, dormir)
            novos = _escolher(item, cands, estado)
            log.info("%s: %d elegíveis, %d para avisar", item.nome, len(cands), len(novos))
            if not cands:
                log.info("%s: nenhuma oferta elegível", item.nome)
            achados += novos
        except Exception as e:  # noqa: BLE001 - um item com problema não derruba os outros
            log.warning("%s: erro %s", item.nome, e)
    if achados:
        avisar(achados)
        for a in achados:
            estado.registrar_aviso(a.item, a.oferta.offer_id, a.oferta.total_parcelado)
    return achados
