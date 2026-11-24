"""Uma rodada: para cada item, busca ofertas, aplica as regras e avisa o que vale a pena."""
from __future__ import annotations

import json
import logging
import random
import time
from statistics import median
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import zoom
from .avisos import Achado, abrir_janela, dados_janela, enviar_ntfy, enviar_whatsapp, formatar
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
                  h.sem_juros, h.marketplace, h.url, h.imagem)


def _candidatos_produto(html: str, url: str, item: Item, hoje: date, tags: list[str]):
    p = zoom.parse_produto(zoom.extrair_estado(html), url)
    hist = [v for d, v in p.historico if (hoje - d).days <= 90]
    return [(o, veredito(o.preco_vista, p.historico, hoje), tags, hist)
            for o in ordenar([o for o in p.ofertas if elegivel(o, item)])]


def _candidatos(item: Item, baixar, hoje: date, dormir, pesquisador=None):
    if item.tipo == "produto":
        return _candidatos_produto(baixar(item.url), item.url, item, hoje, [])
    usar_ia = pesquisador is not None and item.pesquisa != "nenhuma"
    urls = [u for u in [item.url, *item.urls] if u]
    if usar_ia:
        urls += [u for u in pesquisador.buscas_para(item) if u not in urls]
    paginas = []
    for i, u in enumerate(urls):
        if i:
            dormir(random.uniform(3, 6))
        try:
            paginas.append(baixar(u))
        except Exception as e:  # noqa: BLE001
            log.warning("%s: busca %s falhou: %s", item.nome, u, e)
    if urls and not paginas:
        raise zoom.SemDados("nenhuma busca respondeu")
    hits, urls_vistas = [], set()
    for pagina in paginas:
        for h in zoom.parse_busca(zoom.extrair_estado(pagina)):
            ok, tags = passa_filtro_nome(h.nome, item)
            if ok and h.url not in urls_vistas:
                urls_vistas.add(h.url)
                hits.append((h, tags))
    if usar_ia and hits:
        julg = pesquisador.filtrar(item, [h.nome for h, _ in hits])
        hits = [(h, t) for h, t in hits if julg.get(h.nome, (True, ""))[0]]
    hits.sort(key=lambda ht: ht[0].total_parcelado or float("inf"))
    out = []
    for h, tags in hits[:MAX_PAGINAS_BUSCA]:
        if "/lead?" in h.url:
            o = _oferta_de_hit(h)
            if elegivel(o, item):
                out.append((o, "sem_historico", tags, []))
            continue
        dormir(random.uniform(3, 6))
        try:
            out += _candidatos_produto(baixar(h.url), h.url, item, hoje, tags)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: página %s falhou: %s", item.nome, h.url, e)
    return out


def _chave(item: Item, o: Oferta):
    if item.ordem == "parcelas":  # 10x ou mais primeiro, depois o mais barato
        return ((o.parcelas or 0) < 10, o.total_parcelado)
    return (o.total_parcelado,)  # menor_preco (padrão)


def _escolher(item: Item, cands, estado: Estado, pesquisador=None) -> list[Achado]:
    menor = estado.menor_visto(item.nome)
    escolhidos, vistos, vetados = [], set(), set()
    for o, v, tags, hist in sorted(cands, key=lambda c: _chave(item, c[0])):
        if o.offer_id in vistos or v == "maquiada":
            continue
        # Só "real" passa direto. "sem_historico" e "normal" só avisam se forem mais baratos que
        # tudo o que já foi visto antes; senão cada rodada avisaria as próximas ofertas, mais caras.
        mais_barato_que_antes = menor is None or o.total_parcelado < menor
        if v == "sem_historico" and not mais_barato_que_antes:
            continue
        if v == "normal" and not (item.modo == "mais_barato" and mais_barato_que_antes):
            continue
        # "Menor preço já visto" não pode estar acima do normal dos 90 dias do Zoom
        if v == "normal" and hist and o.preco_vista > median(hist):
            continue
        if estado.ja_avisado(item.nome, o.offer_id, o.total_parcelado):
            continue
        tags = list(tags)
        if pesquisador is not None:
            av = pesquisador.avaliar(item, o.nome)
            if av and av[2]:
                log.info("%s: IA vetou %s (%s)", item.nome, o.nome, av[1])
                vetados.add(o.offer_id)
                continue
            if av and av[0] is not None:
                tags.append(f"nota {av[0]}/10 · {av[1]}")
        vistos.add(o.offer_id)
        escolhidos.append(Achado(item.nome, o, v, tags, hist))
        if len(escolhidos) == MAX_POR_ITEM:
            break
    validos = [c[0].total_parcelado for c in cands if c[0].offer_id not in vetados]
    if validos:
        estado.registrar_preco(item.nome, min(validos))
    return escolhidos


def _resumo(item: Item, cands, n: int = 3) -> list[dict]:
    """As melhores ofertas do item nesta rodada (para a aba Ofertas), mesmo as que não geram aviso."""
    vistos, sel = set(), []
    for o, v, tags, hist in sorted(cands, key=lambda c: _chave(item, c[0])):
        if o.offer_id not in vistos:
            vistos.add(o.offer_id)
            sel.append(Achado(item.nome, o, v, list(tags), hist))
        if len(sel) == n:
            break
    return dados_janela(sel)


def _gravar_instantaneo(caminho: Path, resumo: dict) -> None:
    try:
        antigo = json.loads(caminho.read_text(encoding="utf-8")).get("itens", {})
    except (OSError, ValueError):
        antigo = {}
    antigo.update(resumo)  # item que deu erro nesta rodada mantém o resultado anterior
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"quando": datetime.now().isoformat(timespec="seconds"), "itens": antigo},
                                  ensure_ascii=False), encoding="utf-8")


def avisar_todos(cfg: Config):
    def avisar(achados: list[Achado]) -> dict[str, bool]:
        titulo, corpo = formatar(achados)
        links = [a.oferta.link for a in achados]
        res = {"janela": False, "ntfy": False, "whatsapp": False}
        try:
            abrir_janela(titulo, corpo, links, dados_janela(achados), cfg.tema)
            res["janela"] = True
        except Exception as e:  # noqa: BLE001
            log.warning("janela falhou: %s", e)
        res["ntfy"] = enviar_ntfy(cfg, titulo, corpo, links[0] if links else None)
        res["whatsapp"] = enviar_whatsapp(cfg, f"{titulo}\n\n{corpo}")
        return res
    return avisar


def rodar(cfg: Config, estado: Estado, baixar=zoom.baixar, avisar=None,
          hoje: date | None = None, dormir=time.sleep, pesquisador=None,
          instantaneo: Path | None = None) -> list[Achado]:
    hoje = hoje or date.today()
    avisar = avisar or avisar_todos(cfg)
    achados: list[Achado] = []
    resumo: dict[str, list[dict]] = {}
    for i, item in enumerate(cfg.itens):
        if i:
            dormir(random.uniform(3, 6))
        try:
            cands = _candidatos(item, baixar, hoje, dormir, pesquisador)
            novos = _escolher(item, cands, estado, pesquisador)
            resumo[item.nome] = _resumo(item, cands)
            fotos = [c[0].imagem for c in sorted(cands, key=lambda c: c[0].total_parcelado) if c[0].imagem]
            if fotos:  # a tela de cadastro mostra a foto do produto
                estado.cache_gravar(f"imagem:{item.nome}", fotos[0])
            log.info("%s: %d elegíveis, %d para avisar", item.nome, len(cands), len(novos))
            if not cands:
                log.info("%s: nenhuma oferta elegível", item.nome)
            achados += novos
        except Exception as e:  # noqa: BLE001 - um item com problema não derruba os outros
            log.warning("%s: erro %s", item.nome, e)
    if instantaneo is not None:
        _gravar_instantaneo(Path(instantaneo), resumo)
    if achados:
        avisar(achados)
        for a in achados:
            estado.registrar_aviso(a.item, a.oferta.offer_id, a.oferta.total_parcelado)
    return achados
