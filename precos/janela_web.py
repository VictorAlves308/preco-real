"""Janela de aviso em HTML (pywebview / Edge WebView2): por cima de tudo até você fechar."""
from __future__ import annotations

import json
import webbrowser
from html import escape
from pathlib import Path

TEMAS = ("sistema", "claro", "escuro")
# Ícones (traço, estilo Lucide, licença ISC) desenhados inline: monitor, sol, lua
ICONES = {
    "sistema": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "claro": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41'
             'M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    "escuro": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
}
MUITO_ACIMA = 1.10  # 10% ou mais acima da mediana: trecho vermelho
PREF = Path(__file__).resolve().parent.parent / "dados" / "preferencias.json"

_CLARO = """
  --fundo:#F6F5F2; --cartao:#FFFFFF; --borda:#E7E4DE; --borda-forte:#CFCBC3; --texto:#191917;
  --suave:#6B6862; --acento:#1F7A5C; --acento-hover:#18674D; --acento-texto:#FFFFFF;
  --real-bg:#E3F1EA; --real-tx:#1F6B4F; --sem-bg:#F6EDD9; --sem-tx:#7A5512;
  --normal-bg:#EEEDEA; --normal-tx:#4A4843; --foto:#FFFFFF;
  --bom-bg:#E6F4EC; --bom-tx:#18714A; --alto-bg:#FCEBD8; --alto-tx:#9A4A00;
  --muito-bg:#FBE1DF; --muito-tx:#A8231B;
  --bom:#1E9D62; --alto:#E07B12; --muito-alto:#D7372F; --mediana:#9A968E; --seg-ativo:#FFFFFF;
"""
_ESCURO = """
  --fundo:#161615; --cartao:#1F1F1D; --borda:#2E2D2A; --borda-forte:#46443F; --texto:#EDECE8;
  --suave:#9C9A94; --acento:#4FB38E; --acento-hover:#62C39F; --acento-texto:#0B1F17;
  --real-bg:#173327; --real-tx:#8FD6B5; --sem-bg:#352A12; --sem-tx:#E9C77A;
  --normal-bg:#2A2927; --normal-tx:#C9C6BF; --foto:#FFFFFF;
  --bom-bg:#16301F; --bom-tx:#86D9AE; --alto-bg:#3A2814; --alto-tx:#F5B26B;
  --muito-bg:#3D1A18; --muito-tx:#F59A93;
  --bom:#45C98A; --alto:#F5A04A; --muito-alto:#F2635B; --mediana:#7C7A74; --seg-ativo:#2E2D2A;
"""

CSS = (
    ":root{" + _CLARO + "}"
    ':root[data-tema="escuro"]{' + _ESCURO + "}"
    '@media (prefers-color-scheme: dark){:root[data-tema="sistema"]{' + _ESCURO + "}}"
    + """
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--fundo);color:var(--texto);
  font:14px/1.4 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;
  display:flex;flex-direction:column;-webkit-font-smoothing:antialiased}
header{padding:20px 20px 12px;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
h1{font-size:19px;font-weight:650;letter-spacing:-.01em}
header p{color:var(--suave);font-size:12.5px;margin-top:2px}
.temas{display:flex;gap:2px;background:var(--cartao);border:1px solid var(--borda);border-radius:999px;
  padding:3px;flex:none}
.temas button{width:30px;height:30px;display:grid;place-items:center;border:0;border-radius:999px;
  background:transparent;color:var(--suave);transition:background .15s,color .15s}
.temas button:hover{color:var(--texto)}
.temas button[aria-pressed="true"]{background:var(--acento);color:var(--acento-texto)}
.ic{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
main{flex:1;overflow-y:auto;padding:4px 14px 16px 20px;display:flex;flex-direction:column;gap:12px;
  scrollbar-gutter:stable}
main::-webkit-scrollbar{width:10px}
main::-webkit-scrollbar-track{background:transparent}
main::-webkit-scrollbar-thumb{background:var(--borda-forte);border-radius:999px;
  border:3px solid var(--fundo)}
main::-webkit-scrollbar-thumb:hover{background:var(--suave)}
.cartao{background:var(--cartao);border:1px solid var(--borda);border-radius:12px;padding:16px}
.topo{display:flex;gap:14px;align-items:flex-start}
.foto{width:64px;height:64px;flex:none;border-radius:8px;background:var(--foto);
  object-fit:contain;padding:4px}
.item{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
.nome{font-size:14.5px;font-weight:500;margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}
.preco-linha{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-top:14px}
.preco-linha>div{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:6px}

.preco{font-size:26px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;white-space:nowrap}
.parc{color:var(--suave);font-size:13px;white-space:nowrap}
.chip{font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;white-space:nowrap}
.chip.real{background:var(--real-bg);color:var(--real-tx)}
.chip.sem_historico{background:var(--sem-bg);color:var(--sem-tx)}
.chip.normal{background:var(--bom-bg);color:var(--bom-tx)}
.chip.alto{background:var(--alto-bg);color:var(--alto-tx)}
.chip.muito,.chip.maquiada{background:var(--muito-bg);color:var(--muito-tx)}
.chips{display:flex;flex-direction:column;align-items:flex-end;gap:6px;margin-top:6px}
.loja{color:var(--suave);font-size:12.5px;margin-top:2px;font-variant-numeric:tabular-nums}
.hist{margin-top:14px;padding-top:12px;border-top:1px solid var(--borda)}
.hist-titulo{display:flex;justify-content:space-between;font-size:12px;color:var(--suave);margin-bottom:6px}
.hist svg{display:block;width:100%;height:auto;overflow:visible}
.legenda{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:8px;font-size:12px;color:var(--suave);
  font-variant-numeric:tabular-nums}
.legenda span{display:inline-flex;align-items:center;gap:6px}
.legenda b{color:var(--texto);font-weight:600}
.ponto{width:9px;height:9px;border-radius:50%;display:inline-block}
.ponto.bom{background:var(--bom)}
.ponto.alto{background:var(--alto)}
.ponto.muito{background:var(--muito-alto)}
.ponto.min{background:var(--cartao);border:2px solid var(--bom)}
.traco{width:14px;border-top:2px dashed var(--mediana);display:inline-block}
.tags{color:var(--suave);font-size:12.5px;margin-top:10px}
.rodape{display:flex;align-items:center;justify-content:space-between;margin-top:14px}
.frete{color:var(--suave);font-size:12.5px}
button{font:inherit;cursor:pointer;border-radius:8px}
.abrir{background:var(--acento);color:var(--acento-texto);border:0;padding:8px 16px;font-weight:600}
.abrir:hover{background:var(--acento-hover)}
footer{padding:12px 20px 16px;display:flex;justify-content:space-between;border-top:1px solid var(--borda)}
.btn-monitor{background:transparent;color:var(--texto);border:1px solid var(--borda);padding:7px 14px}
.btn-monitor:hover{background:var(--cartao)}
.fechar{background:transparent;color:var(--texto);border:1px solid var(--borda);padding:7px 18px}
.fechar:hover{background:var(--cartao)}
"""
)

# Estilos só dos cartões de oferta (reaproveitados no app principal)
CSS_CARTAO = CSS[CSS.index(".cartao{"):CSS.index("footer{")]

JS = """
const raiz = document.documentElement;
function marcar(){ document.querySelectorAll('[data-escolha]').forEach(b =>
  b.setAttribute('aria-pressed', b.dataset.escolha === raiz.dataset.tema)); }
marcar();
document.addEventListener('click', e => {
  const t = e.target.closest('[data-escolha]');
  if (t) { raiz.dataset.tema = t.dataset.escolha; marcar();
           if (window.pywebview) pywebview.api.salvar_tema(t.dataset.escolha); }
  const b = e.target.closest('[data-link]');
  if (b) { window.pywebview ? pywebview.api.abrir(b.dataset.link) : window.open(b.dataset.link); }
  if (e.target.closest('.fechar')) { window.pywebview ? pywebview.api.fechar() : window.close(); }
  if (e.target.closest('.btn-monitor') && window.pywebview) { pywebview.api.abrir_monitor(); }
});
"""


def ler_tema(arquivo: Path, padrao: str = "sistema") -> str:
    try:
        t = json.loads(Path(arquivo).read_text(encoding="utf-8")).get("tema")
        return t if t in TEMAS else padrao
    except (OSError, ValueError, AttributeError):
        return padrao if padrao in TEMAS else "sistema"


def salvar_tema(arquivo: Path, tema: str) -> None:
    if tema not in TEMAS:
        return
    arquivo = Path(arquivo)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"tema": tema}), encoding="utf-8")


def sparkline(valores: list[float], largura: int = 460, altura: int = 64, uid: str = "g") -> str:
    """Gráfico do histórico.

    Linha verde abaixo da mediana (barato), laranja acima (caro) e vermelha 10% ou mais acima (muito caro);
    mediana tracejada; anel verde no menor preço; ponto grande no preço de hoje.
    """
    if not valores:
        return ""
    lo, hi = min(valores), max(valores)
    faixa = (hi - lo) or 1.0
    n = max(len(valores) - 1, 1)
    pad = 7

    def x(i):
        return pad + i * (largura - 2 * pad) / n

    def y(v):
        return pad + (altura - 2 * pad) * (1 - (v - lo) / faixa)

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(valores))
    ordenados = sorted(valores)
    med = ordenados[len(ordenados) // 2]
    ym = y(med)
    yr = max(y(med * MUITO_ACIMA), 0.0)
    imin = valores.index(lo)
    hoje = valores[-1]
    cor_hoje = ("var(--bom)" if hoje <= med else "var(--alto)" if hoje < med * MUITO_ACIMA
                else "var(--muito-alto)")
    return (
        f'<svg viewBox="0 0 {largura} {altura}" aria-hidden="true">'
        f'<defs><clipPath id="{uid}a"><rect x="0" y="{ym:.1f}" width="{largura}" height="{altura}"/></clipPath>'
        f'<clipPath id="{uid}b"><rect x="0" y="{yr:.1f}" width="{largura}" height="{max(ym - yr, 0):.1f}"/></clipPath>'
        f'<clipPath id="{uid}c"><rect x="-10" y="-10" width="{largura + 20}" height="{yr + 10:.1f}"/></clipPath></defs>'
        f'<line x1="0" x2="{largura}" y1="{ym:.1f}" y2="{ym:.1f}" stroke="var(--mediana)" '
        'stroke-width="1.5" stroke-dasharray="4 4"/>'
        f'<polyline points="{pts}" fill="none" stroke="var(--bom)" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round" clip-path="url(#{uid}a)"/>'
        f'<polyline points="{pts}" fill="none" stroke="var(--alto)" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round" clip-path="url(#{uid}b)"/>'
        f'<polyline points="{pts}" fill="none" stroke="var(--muito-alto)" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round" clip-path="url(#{uid}c)"/>'
        f'<circle class="m-min" cx="{x(imin):.1f}" cy="{y(lo):.1f}" r="4.5" fill="var(--cartao)" '
        'stroke="var(--bom)" stroke-width="2.5"/>'
        f'<circle class="m-hoje" cx="{x(len(valores) - 1):.1f}" cy="{y(hoje):.1f}" r="6" '
        f'fill="{cor_hoje}" stroke="var(--cartao)" stroke-width="2.5"/>'
        "</svg>"
    )


def _moeda(v: float) -> str:
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _cartao(d: dict, idx: int) -> str:
    e = escape
    foto = (f'<img class="foto" src="{e(d["imagem"])}" alt="">' if d.get("imagem")
            else '<div class="foto"></div>')
    hist, chip_zona = "", ""
    if d.get("historico"):
        vals = list(d["historico"]) + ([d["vista_num"]] if d.get("vista_num") else [])
        ordenados = sorted(vals)
        med = ordenados[len(ordenados) // 2]
        zona = "bom" if vals[-1] <= med else "alto" if vals[-1] < med * MUITO_ACIMA else "muito"
        resumo = {"bom": "abaixo do normal", "alto": "acima do normal", "muito": "muito acima do normal"}[zona]
        if zona != "bom":
            chip_zona = f'<span class="chip {zona}">{resumo.capitalize()}</span>'
        hist = (
            '<figure class="hist">'
            '<div class="hist-titulo"><span>Preço à vista · últimos 90 dias</span>'
            f'<span>{resumo}</span></div>'
            f"{sparkline(vals, uid=f'g{idx}')}"
            '<figcaption class="legenda">'
            f'<span><i class="ponto {zona}"></i>Hoje <b>{e(_moeda(vals[-1]))}</b></span>'
            f'<span><i class="ponto min"></i>Menor <b>{e(_moeda(min(vals)))}</b></span>'
            f'<span><i class="traco"></i>Mediana <b>{e(_moeda(med))}</b></span>'
            "</figcaption></figure>"
        )
    loja = f'{e(d["loja"])} · {e(d["pix"])}' if d.get("loja") else e(d["pix"])
    tags = f'<p class="tags">{" · ".join(e(t) for t in d["tags"])}</p>' if d.get("tags") else ""
    return (
        '<article class="cartao">'
        f'<div class="topo">{foto}<div><p class="item">{e(d["item"])}</p>'
        f'<h2 class="nome">{e(d["nome"])}</h2></div></div>'
        f'<div class="preco-linha"><div><span class="preco">{e(d["preco"])}</span>'
        f'<span class="parc">{e(d["parcelas"])}</span></div>'
        f'<div class="chips"><span class="chip {e(d["veredito"])}">{e(d["rotulo"])}</span>{chip_zona}</div></div>'
        f'<p class="loja">{loja}</p>{hist}{tags}'
        f'<div class="rodape"><span class="frete">{e(d["frete"])}</span>'
        f'<button class="abrir" data-link="{e(d["link"])}">Ver oferta</button></div>'
        "</article>"
    )


def html_janela(titulo: str, itens: list[dict], verificado: str, tema: str = "sistema") -> str:
    tema = tema if tema in TEMAS else "sistema"
    cartoes = "".join(_cartao(d, i) for i, d in enumerate(itens))
    seletor = "".join(
        f'<button data-escolha="{t}" aria-label="{rotulo}" title="{rotulo}">'
        f'<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">{ICONES[t]}</svg></button>'
        for t, rotulo in (("sistema", "Seguir o sistema"), ("claro", "Tema claro"), ("escuro", "Tema escuro"))
    )
    return (
        f'<!doctype html><html lang="pt-BR" data-tema="{tema}"><head><meta charset="utf-8">'
        f"<title>{escape(titulo)}</title><style>{CSS}</style></head><body>"
        f"<header><div><h1>{escape(titulo)}</h1><p>Verificado às {escape(verificado)}</p></div>"
        f'<div class="temas" role="group" aria-label="Tema">{seletor}</div></header>'
        f"<main>{cartoes}</main>"
        '<footer><button class="btn-monitor">Abrir monitor</button><button class="fechar">Fechar</button></footer>'
        f"<script>{JS}</script></body></html>"
    )


class _Api:
    def __init__(self):
        self._janela = None

    def abrir(self, link: str) -> None:
        if link.startswith("https://"):
            webbrowser.open(link)

    def salvar_tema(self, tema: str) -> None:
        salvar_tema(PREF, tema)

    def abrir_monitor(self) -> None:
        import os
        import subprocess
        import sys

        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        subprocess.Popen([str(pyw if pyw.exists() else exe), "-m", "precos", "--cadastro"],
                         cwd=PREF.parent.parent, creationflags=flags, close_fds=True)
        self.fechar()

    def fechar(self) -> None:
        if self._janela:
            self._janela.destroy()


def mostrar(titulo: str, itens: list[dict], verificado: str, tema_padrao: str = "sistema") -> None:
    import webview

    api = _Api()
    tema = ler_tema(PREF, tema_padrao)
    altura = min(150 + 330 * max(len(itens), 1), 800)
    api._janela = webview.create_window(titulo, html=html_janela(titulo, itens, verificado, tema), js_api=api,
                                       width=560, height=altura, min_size=(460, 360), on_top=True)
    webview.start()
