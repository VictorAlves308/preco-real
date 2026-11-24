"""Ponto de entrada: python -m precos  [--teste-aviso]"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .avisos import Achado, enviar_ntfy
from .config import Config, carregar
from .estado import Estado
from .ia import criar
from .pesquisa import Pesquisador
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
    logging.basicConfig(level=logging.INFO, handlers=[h], force=True)


def _montar_pesquisador(cfg: Config, estado: Estado):
    provs = {n: criar(cfg.ia, n, cfg.chaves) for n in ("economica", "completa")}
    if not any(provs.values()):
        return None
    return Pesquisador(cfg, estado, provs,
                       notificar=lambda t: enviar_ntfy(cfg, "Monitor de preços", t, None))


def main(argv: list[str]) -> int:
    _prioridade_baixa()
    _logs()
    try:
        return _executar(argv)
    except Exception:  # noqa: BLE001 - no agendador (pythonw) não há console: o erro tem que ir pro log
        logging.exception("rodada falhou")
        print("ERRO: veja dados/precos.log")
        return 1


def _executar(argv: list[str]) -> int:
    cfg = carregar(RAIZ / "config.toml", RAIZ / "segredos.toml")
    if "--teste-aviso" in argv:
        o = Oferta("teste", "Produto de teste", "Loja Teste", 999.9, 1099.9, 10, 109.99, True, False,
                   "https://www.zoom.com.br")
        res = avisar_todos(cfg)([Achado("Teste", o, "real", [])])
        for canal, ok in res.items():
            print(f"{canal}: {'ok' if ok else 'FALHOU (ou não configurado)'}")
        return 0
    if not cfg.itens:
        print("Nenhum item em config.toml (copie config.exemplo.toml)")
        return 1
    estado = Estado(DADOS / "estado.db")
    achados = rodar(cfg, estado, pesquisador=_montar_pesquisador(cfg, estado))
    logging.info("rodada terminou: %d achados", len(achados))
    print(f"OK: {len(achados)} achados")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
