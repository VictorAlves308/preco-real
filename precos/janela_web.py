"""Janela de aviso em HTML (pywebview / Edge WebView2): por cima de tudo até você fechar."""
from __future__ import annotations

import webbrowser
from html import escape

CSS = """
:root{
  --fundo:#F6F5F2; --cartao:#FFFFFF; --borda:#E7E4DE; --texto:#191917; --suave:#6B6862;
  --linha:#B9B5AD; --acento:#1F7A5C; --acento-hover:#18674D; --acento-texto:#FFFFFF;
  --real-bg:#E3F1EA; --real-tx:#1F6B4F; --sem-bg:#F6EDD9; --sem-tx:#7A5512;
  --normal-bg:#EEEDEA; --normal-tx:#4A4843; --foto:#F1EFEA;
}
@media (prefers-color-scheme: dark){
  :root{
    --fundo:#161615; --cartao:#1F1F1D; --borda:#2E2D2A; --texto:#EDECE8; --suave:#9C9A94;
    --linha:#5C5A55; --acento:#4FB38E; --acento-hover:#62C39F; --acento-texto:#0B1F17;
    --real-bg:#173327; --real-tx:#8FD6B5; --sem-bg:#352A12; --sem-tx:#E9C77A;
    --normal-bg:#2A2927; --normal-tx:#C9C6BF; --foto:#FFFFFF;
  }
}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--fundo);color:var(--texto);
  font:14px/1.4 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;
  display:flex;flex-direction:column;-webkit-font-smoothing:antialiased}
header{padding:20px 20px 12px}
h1{font-size:19px;font-weight:650;letter-spacing:-.01em}
header p{color:var(--suave);font-size:12.5px;margin-top:2px}
main{flex:1;overflow-y:auto;padding:4px 20px 16px;display:flex;flex-direction:column;gap:12px}
.cartao{background:var(--cartao);border:1px solid var(--borda);border-radius:12px;padding:16px}
.topo{display:flex;gap:14px;align-items:flex-start}
.foto{width:64px;height:64px;flex:none;border-radius:8px;background:var(--foto);
  object-fit:contain;padding:4px}
.item{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
.nome{font-size:14.5px;font-weight:500;margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}
.preco-linha{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-top:14px}
.preco-linha>div{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:6px}
.preco-linha .chip{margin-top:6px}
.preco{font-size:26px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;white-space:nowrap}
.parc{color:var(--suave);font-size:13px;white-space:nowrap}
.chip{font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;white-space:nowrap}
.chip.real{background:var(--real-bg);color:var(--real-tx)}
.chip.sem_historico{background:var(--sem-bg);color:var(--sem-tx)}
.chip.normal{background:var(--normal-bg);color:var(--normal-tx)}
.loja{color:var(--suave);font-size:12.5px;margin-top:2px;font-variant-numeric:tabular-nums}
.hist{margin-top:14px;padding-top:12px;border-top:1px solid var(--borda)}
.hist svg{display:block;width:100%;height:40px}
.hist figcaption{color:var(--suave);font-size:12px;margin-top:6px;font-variant-numeric:tabular-nums}
.tags{color:var(--suave);font-size:12.5px;margin-top:10px}
.rodape{display:flex;align-items:center;justify-content:space-between;margin-top:14px}
.frete{color:var(--suave);font-size:12.5px}
button{font:inherit;cursor:pointer;border-radius:8px}
.abrir{background:var(--acento);color:var(--acento-texto);border:0;padding:8px 16px;font-weight:600}
.abrir:hover{background:var(--acento-hover)}
footer{padding:12px 20px 16px;display:flex;justify-content:flex-end;border-top:1px solid var(--borda)}
.fechar{background:transparent;color:var(--texto);border:1px solid var(--borda);padding:7px 18px}
.fechar:hover{background:var(--cartao)}
"""

JS = """
document.addEventListener('click', e => {
  const b = e.target.closest('[data-link]');
  if (b) { window.pywebview ? pywebview.api.abrir(b.dataset.link) : window.open(b.dataset.link); }
  if (e.target.closest('.fechar')) { window.pywebview ? pywebview.api.fechar() : window.close(); }
});
"""


def sparkline(valores: list[float], largura: int = 400, altura: int = 40) -> str:
    """Mini gráfico do histórico: linha do preço, linha tracejada da mediana e ponto no preço atual."""
    if not valores:
        return ""
    lo, hi = min(valores), max(valores)
    faixa = (hi - lo) or 1.0
    n = max(len(valores) - 1, 1)
    pad = 3

    def y(v):
        return pad + (altura - 2 * pad) * (1 - (v - lo) / faixa)

    pts = " ".join(f"{i * largura / n:.1f},{y(v):.1f}" for i, v in enumerate(valores))
    ordenados = sorted(valores)
    med = ordenados[len(ordenados) // 2]
    ux, uy = (len(valores) - 1) * largura / n, y(valores[-1])
    return (
        f'<svg viewBox="0 0 {largura} {altura}" preserveAspectRatio="none" aria-hidden="true">'
        f'<line x1="0" x2="{largura}" y1="{y(med):.1f}" y2="{y(med):.1f}" stroke="var(--borda)" '
        f'stroke-width="1" stroke-dasharray="3 3" vector-effect="non-scaling-stroke"/>'
        f'<polyline points="{pts}" fill="none" stroke="var(--linha)" stroke-width="1.5" '
        f'stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
        f'<circle cx="{ux:.1f}" cy="{uy:.1f}" r="3.5" fill="var(--acento)"/>'
        "</svg>"
    )


def _cartao(d: dict) -> str:
    e = escape
    foto = (f'<img class="foto" src="{e(d["imagem"])}" alt="">' if d.get("imagem")
            else '<div class="foto"></div>')
    hist = ""
    if d.get("historico"):
        hist = (f'<figure class="hist">{sparkline(d["historico"])}'
                f'<figcaption>Últimos 90 dias · mín. {e(d["minimo"])} · mediana {e(d["mediana"])}'
                "</figcaption></figure>")
    loja = f'{e(d["loja"])} · {e(d["pix"])}' if d.get("loja") else e(d["pix"])
    tags = f'<p class="tags">{" · ".join(e(t) for t in d["tags"])}</p>' if d.get("tags") else ""
    return (
        '<article class="cartao">'
        f'<div class="topo">{foto}<div><p class="item">{e(d["item"])}</p>'
        f'<h2 class="nome">{e(d["nome"])}</h2></div></div>'
        f'<div class="preco-linha"><div><span class="preco">{e(d["preco"])}</span>'
        f'<span class="parc">{e(d["parcelas"])}</span></div>'
        f'<span class="chip {e(d["veredito"])}">{e(d["rotulo"])}</span></div>'
        f'<p class="loja">{loja}</p>{hist}{tags}'
        f'<div class="rodape"><span class="frete">{e(d["frete"])}</span>'
        f'<button class="abrir" data-link="{e(d["link"])}">Ver oferta</button></div>'
        "</article>"
    )


def html_janela(titulo: str, itens: list[dict], verificado: str) -> str:
    cartoes = "".join(_cartao(d) for d in itens)
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{escape(titulo)}</title><style>{CSS}</style></head><body>"
        f"<header><h1>{escape(titulo)}</h1><p>Verificado às {escape(verificado)}</p></header>"
        f"<main>{cartoes}</main>"
        '<footer><button class="fechar">Fechar</button></footer>'
        f"<script>{JS}</script></body></html>"
    )


class _Api:
    def __init__(self):
        self.janela = None

    def abrir(self, link: str) -> None:
        if link.startswith("https://"):
            webbrowser.open(link)

    def fechar(self) -> None:
        if self.janela:
            self.janela.destroy()


def mostrar(titulo: str, itens: list[dict], verificado: str) -> None:
    import webview

    api = _Api()
    altura = min(150 + 290 * max(len(itens), 1), 780)
    api.janela = webview.create_window(titulo, html=html_janela(titulo, itens, verificado), js_api=api,
                                       width=540, height=altura, min_size=(440, 360), on_top=True)
    webview.start()
