"""Ponto de entrada: python -m precos  [--teste-aviso]"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .avisos import Achado
from .config import carregar
from .estado import Estado
from .rodada import avisar_todos, rodar
from .zoom import Oferta

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"


def _prioridade_baixa() -> None:
    try:
        if os.name == "nt":
            import ctypes

            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
        else:
            os.nice(10)
    except Exception:  # noqa: BLE001
        pass


def _logs() -> None:
    DADOS.mkdir(exist_ok=True)
    h = RotatingFileHandler(DADOS / "precos.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h])


def main(argv: list[str]) -> int:
    _prioridade_baixa()
    _logs()
    cfg = carregar(RAIZ / "config.toml", RAIZ / "segredos.toml")
    if "--teste-aviso" in argv:
        o = Oferta("teste", "Produto de teste", "Loja Teste", 999.9, 1099.9, 10, 109.99, True, False,
                   "https://www.zoom.com.br")
        avisar_todos(cfg)([Achado("Teste", o, "real", [])])
        print("OK: aviso de teste enviado")
        return 0
    if not cfg.itens:
        print("Nenhum item em config.toml (copie config.exemplo.toml)")
        return 1
    achados = rodar(cfg, Estado(DADOS / "estado.db"))
    logging.info("rodada terminou: %d achados", len(achados))
    print(f"OK: {len(achados)} achados")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
