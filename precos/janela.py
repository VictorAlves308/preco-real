"""Janela de aviso: fica por cima de tudo e só some quando você fecha.

Uso: python -m precos.janela <arquivo.json>  (json com titulo, corpo, links)
"""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import scrolledtext


def mostrar(titulo: str, corpo: str, links: list[str]) -> None:
    root = tk.Tk()
    root.title(titulo)
    root.attributes("-topmost", True)
    root.geometry("720x520")
    tk.Label(root, text=titulo, font=("Segoe UI", 14, "bold")).pack(padx=12, pady=(12, 4), anchor="w")
    txt = scrolledtext.ScrolledText(root, wrap="word", font=("Segoe UI", 11), height=18)
    txt.insert("1.0", corpo)
    txt.configure(state="disabled")
    txt.pack(fill="both", expand=True, padx=12, pady=4)
    botoes = tk.Frame(root)
    botoes.pack(fill="x", padx=12, pady=(4, 12))
    for i, link in enumerate(links, 1):
        tk.Button(botoes, text=f"Abrir oferta {i}", command=lambda l=link: webbrowser.open(l)).pack(side="left", padx=(0, 6))
    tk.Button(botoes, text="Fechar", command=root.destroy).pack(side="right")
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
    mostrar(dados["titulo"], dados["corpo"], dados.get("links", []))


if __name__ == "__main__":
    main(sys.argv[1])
