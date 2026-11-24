"""Uma rodada: para cada item, busca ofertas, aplica as regras e avisa o que vale a pena."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import replace
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
from .regras import elegivel, extrair_codigo, ordenar, passa_filtro_nome, veredito
from .zoom import Hit, Oferta

log = logging.getLogger(__name__)

MAX_POR_ITEM = 3
MAX_PAGINAS_BUSCA = 8  # páginas de produto abertas por item
MAX_CONSULTAS_CODIGO = 3  # buscas extras pelo código do modelo por item


def _oferta_de_hit(h: Hit) -> Oferta:
    oid = parse_qs(urlparse(h.url).query).get("oid", [h.url])[0]
    return Oferta(oid, h.nome, h.loja, h.preco_vista, h.total_parcelado, h.parcelas, None,
                  h.sem_juros, h.marketplace, h.url, h.imagem)


def _candidatos_produto(html: str, url: str, item: Item, hoje: date, tags: list[str]):
    p = zoom.parse_produto(zoom.extrair_estado(html), url)
    hist = [v for d, v in p.historico if (hoje - d).days <= 90]
    return [(o, veredito(o.preco_vista, p.historico, hoje), tags, hist)
            for o in ordenar([o for o in p.ofertas if elegivel(o, item)])]


def chave_modelo(nome: str) -> str:
    return extrair_codigo(nome) or " ".join(nome.lower().split())


MAX_PAGINAS_CATEGORIA = 3
DIAS_CATEGORIA = 7


def escolher_filtros(item: Item, categoria: str, links: list[tuple[str, str]]) -> list[str]:
    """Páginas de categoria do Zoom que batem com o cadastro, do mais barato ao mais caro."""
    escolhidas = []
    for rotulo, caminho in links:
        if not caminho.startswith(f"/{categoria}/"):
            continue
        pol = re.fullmatch(r'(\d+)"', rotulo.strip())
        if pol and (item.polegadas_min is not None or item.polegadas_max is not None):
            n = int(pol.group(1))
            if (item.polegadas_min or 0) <= n <= (item.polegadas_max or 999):
                escolhidas.append(caminho)
        hz = re.fullmatch(r"(\d+)\s*Hz", rotulo.strip(), re.I)
        if hz and item.hz_min and int(hz.group(1)) >= item.hz_min:
            escolhidas.append(caminho)
    escolhidas = escolhidas[:MAX_PAGINAS_CATEGORIA] or [f"/{categoria}"]
    return [f"{zoom.BASE}{c}?sortBy=price_asc" for c in escolhidas]


def _paginas_de_categoria(item: Item, hits, estado, baixar, dormir, hoje: date) -> list[str]:
    """Descobre a categoria pelos resultados da busca e escolhe os filtros (guardado por 7 dias)."""
    if estado is None:
        return []
    chave = f"categorias:{item.nome}"
    try:
        salvo = json.loads(estado.cache_ler(chave) or "{}")
    except ValueError:
        salvo = {}
    if salvo.get("quando") and (hoje - date.fromisoformat(salvo["quando"])).days < DIAS_CATEGORIA:
        return salvo.get("urls", [])
    cats = Counter(h.categoria for h, _ in hits if h.categoria)
    if not cats:
        return []
    categoria = cats.most_common(1)[0][0]
    dormir(random.uniform(3, 6))
    try:
        links = zoom.parse_links(zoom.extrair_estado(baixar(f"{zoom.BASE}/{categoria}")))
    except Exception as e:  # noqa: BLE001
        log.info("%s: categoria %s indisponível: %s", item.nome, categoria, e)
        return []
    urls = escolher_filtros(item, categoria, links)
    estado.cache_gravar(chave, json.dumps({"quando": hoje.isoformat(), "urls": urls}))
    return urls


def _produto_do_codigo(codigo: str, catalogo: dict, estado, baixar, dormir, consultas: list) -> str | None:
    """URL do produto de catálogo com exatamente esse código de modelo (ou None)."""
    if codigo in catalogo:
        return catalogo[codigo]
    salvo = estado.cache_ler(f"catalogo:{codigo}") if estado is not None else None
    if salvo is not None:
        return salvo or None
    if estado is None or len(consultas) >= MAX_CONSULTAS_CODIGO:
        return None
    consultas.append(codigo)
    dormir(random.uniform(3, 6))
    url = ""
    try:
        for h in zoom.parse_busca(zoom.extrair_estado(baixar(f"{zoom.BASE}/search?q={codigo}"))):
            if h.tipo == "product" and extrair_codigo(h.nome) == codigo:
                url = h.url
                break
    except Exception as e:  # noqa: BLE001
        log.info("busca pelo código %s falhou: %s", codigo, e)
        return None
    estado.cache_gravar(f"catalogo:{codigo}", url)
    return url or None


def _candidatos(item: Item, baixar, hoje: date, dormir, pesquisador=None, estado=None):
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

    def juntar(pagina, filtro=item):
        for h in zoom.parse_busca(zoom.extrair_estado(pagina)):
            ok, tags = passa_filtro_nome(h.nome, filtro)
            if ok and h.url not in urls_vistas:
                urls_vistas.add(h.url)
                hits.append((h, tags))

    for pagina in paginas:
        juntar(pagina)
    # Afunila: a página de categoria com filtro (ex.: /tv/tamanho-32-polegadas) traz produtos de
    # catálogo, que têm histórico, do mais barato ao mais caro.
    for u in _paginas_de_categoria(item, hits, estado, baixar, dormir, hoje):
        dormir(random.uniform(3, 6))
        # o filtro do próprio Zoom já garante Hz/tamanho: não exige isso no nome do produto
        filtro = replace(item, hz_min=None if "-hz" in u else item.hz_min,
                         polegadas_min=None if "polegadas" in u else item.polegadas_min,
                         polegadas_max=None if "polegadas" in u else item.polegadas_max)
        try:
            juntar(baixar(u), filtro)
        except Exception as e:  # noqa: BLE001
            log.info("%s: categoria %s falhou: %s", item.nome, u, e)
    if usar_ia and hits:
        julg = pesquisador.filtrar(item, [h.nome for h, _ in hits])
        hits = [(h, t) for h, t in hits if julg.get(h.nome, (True, ""))[0]]
    hits.sort(key=lambda ht: ht[0].total_parcelado or float("inf"))
    # Produtos de catálogo têm histórico; anúncios soltos (/lead?) não. Liga o anúncio ao produto
    # pelo código do modelo, aceitando só código idêntico (24U411B não é 24U511SB).
    catalogo = {}
    for h, _ in hits:
        cod = extrair_codigo(h.nome) if "/lead?" not in h.url else None
        if cod:
            catalogo.setdefault(cod, h.url)
    out, abertos, consultas = [], set(), []

    def abrir(url, tags):
        if url in abertos or len(abertos) >= MAX_PAGINAS_BUSCA:
            return url in abertos
        abertos.add(url)
        dormir(random.uniform(3, 6))
        try:
            out.extend(_candidatos_produto(baixar(url), url, item, hoje, tags))
        except Exception as e:  # noqa: BLE001
            log.warning("%s: página %s falhou: %s", item.nome, url, e)
        return True

    for h, tags in hits:
        if "/lead?" not in h.url:
            abrir(h.url, tags)
            continue
        o = _oferta_de_hit(h)
        if not elegivel(o, item):
            continue
        cod = extrair_codigo(h.nome)
        url = _produto_do_codigo(cod, catalogo, estado, baixar, dormir, consultas) if cod else None
        if url and abrir(url, tags):
            continue
        hist = estado.historico_proprio(chave_modelo(h.nome)) if estado is not None else []
        recente = [v for d, v in hist if (hoje - d).days <= 90]
        out.append((o, veredito(o.preco_vista, hist, hoje), tags, recente))
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
            cands = _candidatos(item, baixar, hoje, dormir, pesquisador, estado)
            for c in cands:  # histórico próprio: menor preço do modelo no dia
                estado.registrar_observacao(chave_modelo(c[0].nome), hoje, c[0].preco_vista)
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
