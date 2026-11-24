"""Janela de aviso: fica por cima de tudo e só some quando você fecha.

Uso: python -m precos.janela <arquivo.json>  (json com titulo, corpo, links e itens)
"""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import font as tkfont

# Paletas planas (sem degradê). Etiquetas: fundo suave + texto escuro da mesma cor.
TEMAS = {
    "claro": {
        "fundo": "#F3F3F3", "cartao": "#FFFFFF", "borda": "#E1E1E1", "texto": "#1A1A1A",
        "suave": "#5F5F5F", "acento": "#005FB8", "acento_texto": "#FFFFFF", "acento_hover": "#0A6CC7",
        "botao": "#FFFFFF", "botao_borda": "#D0D0D0",
        "real": ("#DFF6DD", "#0E700E"), "sem_historico": ("#FFF4CE", "#7A5A00"),
        "normal": ("#EBEBEB", "#3B3B3B"),
    },
    "escuro": {
        "fundo": "#202020", "cartao": "#2B2B2B", "borda": "#3A3A3A", "texto": "#F2F2F2",
        "suave": "#ABABAB", "acento": "#4CC2FF", "acento_texto": "#000000", "acento_hover": "#62CBFF",
        "botao": "#2B2B2B", "botao_borda": "#4A4A4A",
        "real": ("#1F3B1F", "#9BE39B"), "sem_historico": ("#3D3418", "#F2D27A"),
        "normal": ("#383838", "#D6D6D6"),
    },
}


def tema_do_sistema() -> str:
    try:
        import winreg

        chave = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        claro, _ = winreg.QueryValueEx(chave, "AppsUseLightTheme")
        return "claro" if claro else "escuro"
    except Exception:  # noqa: BLE001
        return "claro"


def _fonte(root, tamanho, peso="normal"):
    familias = set(tkfont.families(root))
    for f in ("Segoe UI Variable Text", "Segoe UI", "Helvetica"):
        if f in familias:
            return (f, tamanho, peso)
    return ("TkDefaultFont", tamanho, peso)


def _botao(pai, texto, cmd, t, primario, root):
    cor = t["acento"] if primario else t["botao"]
    b = tk.Label(pai, text=texto, bg=cor, fg=t["acento_texto"] if primario else t["texto"],
                 font=_fonte(root, 10, "bold" if primario else "normal"), padx=14, pady=6,
                 cursor="hand2", highlightthickness=0 if primario else 1,
                 highlightbackground=t["botao_borda"])
    b.bind("<Button-1>", lambda e: cmd())
    if primario:
        b.bind("<Enter>", lambda e: b.configure(bg=t["acento_hover"]))
        b.bind("<Leave>", lambda e: b.configure(bg=cor))
    return b


def _cartao(pai, d: dict, t: dict, root, largura: int) -> tk.Frame:
    c = tk.Frame(pai, bg=t["cartao"], highlightthickness=1, highlightbackground=t["borda"], padx=16, pady=14)
    tk.Label(c, text=d["item"].upper(), bg=t["cartao"], fg=t["suave"], font=_fonte(root, 8, "bold"),
             anchor="w").pack(fill="x")
    tk.Label(c, text=d["nome"], bg=t["cartao"], fg=t["texto"], font=_fonte(root, 11), anchor="w",
             justify="left", wraplength=largura).pack(fill="x", pady=(2, 8))

    preco = tk.Frame(c, bg=t["cartao"])
    preco.pack(fill="x")
    tk.Label(preco, text=d["preco"], bg=t["cartao"], fg=t["texto"], font=_fonte(root, 18, "bold")).pack(side="left")
    tk.Label(preco, text=" " + d["parcelas"], bg=t["cartao"], fg=t["suave"],
             font=_fonte(root, 10)).pack(side="left", anchor="s", pady=(0, 4))
    tk.Label(c, text=f"{d['loja']}  ·  {d['pix']}" if d["loja"] else d["pix"], bg=t["cartao"], fg=t["suave"],
             font=_fonte(root, 9), anchor="w").pack(fill="x", pady=(0, 10))

    linha = tk.Frame(c, bg=t["cartao"])
    linha.pack(fill="x")
    fundo, cor = t.get(d["veredito"], t["normal"])
    tk.Label(linha, text=d["rotulo"], bg=fundo, fg=cor, font=_fonte(root, 9, "bold"),
             padx=8, pady=2).pack(side="left")
    for tag in d["tags"]:
        tk.Label(linha, text=tag, bg=t["cartao"], fg=t["suave"], font=_fonte(root, 9),
                 padx=6).pack(side="left")

    rodape = tk.Frame(c, bg=t["cartao"])
    rodape.pack(fill="x", pady=(12, 0))
    tk.Label(rodape, text=d["frete"], bg=t["cartao"], fg=t["suave"], font=_fonte(root, 9)).pack(side="left")
    _botao(rodape, "Abrir oferta", lambda: webbrowser.open(d["link"]), t, True, root).pack(side="right")
    return c


def construir(root: tk.Tk, titulo: str, itens: list[dict], tema: str) -> list[tk.Frame]:
    t = TEMAS[tema]
    largura = 520
    root.configure(bg=t["fundo"])
    topo = tk.Frame(root, bg=t["fundo"], padx=20, pady=16)
    topo.pack(fill="x")
    tk.Label(topo, text=titulo, bg=t["fundo"], fg=t["texto"], font=_fonte(root, 15, "bold"),
             anchor="w").pack(fill="x")
    tk.Label(topo, text=f"Verificado às {datetime.now():%H:%M}", bg=t["fundo"], fg=t["suave"],
             font=_fonte(root, 9), anchor="w").pack(fill="x")

    base = tk.Frame(root, bg=t["fundo"], padx=20, pady=14)
    base.pack(side="bottom", fill="x")
    _botao(base, "Fechar", root.destroy, t, False, root).pack(side="right")

    area = tk.Frame(root, bg=t["fundo"])
    area.pack(fill="both", expand=True)
    canvas = tk.Canvas(area, bg=t["fundo"], highlightthickness=0, bd=0)
    barra = tk.Scrollbar(area, orient="vertical", command=canvas.yview)
    lista = tk.Frame(canvas, bg=t["fundo"], padx=20)
    lista.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    janela_lista = canvas.create_window((0, 0), window=lista, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(janela_lista, width=e.width))
    canvas.configure(yscrollcommand=barra.set)
    canvas.pack(side="left", fill="both", expand=True)
    if len(itens) > 2:
        barra.pack(side="right", fill="y")
    root.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

    cartoes = []
    for d in itens:
        c = _cartao(lista, d, t, root, largura)
        c.pack(fill="x", pady=(0, 10))
        cartoes.append(c)
    root.after_idle(lambda: canvas.yview_moveto(0))  # abre no topo da lista
    return cartoes


def _nitidez_dpi() -> None:
    """Texto nítido em telas com escala do Windows (125%, 150%...)."""
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass


def mostrar(titulo: str, itens: list[dict], corpo: str = "", links: list[str] | None = None) -> None:
    _nitidez_dpi()
    root = tk.Tk()
    root.title(titulo)
    root.attributes("-topmost", True)
    altura = min(180 + 190 * max(len(itens), 1), 720)
    root.geometry(f"600x{altura}")
    root.minsize(480, 320)
    if itens:
        construir(root, titulo, itens, tema_do_sistema())
    else:  # formato antigo: só texto
        tk.Label(root, text=corpo, justify="left", anchor="nw", padx=16, pady=16).pack(fill="both", expand=True)
        tk.Button(root, text="Fechar", command=root.destroy).pack(pady=8)
    root.lift()
    root.focus_force()
    root.mainloop()


def main(caminho: str) -> None:
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    try:
        os.remove(caminho)
    except OSError:
        pass
    itens = dados.get("itens", [])
    if itens:
        try:  # janela em HTML (Edge WebView2); se não der, cai para a versão tkinter
            from . import janela_web

            janela_web.mostrar(dados["titulo"], itens, f"{datetime.now():%H:%M}")
            return
        except Exception:  # noqa: BLE001
            pass
    mostrar(dados["titulo"], itens, dados.get("corpo", ""), dados.get("links", []))


if __name__ == "__main__":
    main(sys.argv[1])
