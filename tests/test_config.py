from pathlib import Path

from precos.config import carregar

RAIZ = Path(__file__).resolve().parent.parent


def test_carrega_exemplo():
    cfg = carregar(RAIZ / "config.exemplo.toml", RAIZ / "segredos.exemplo.toml")
    assert len(cfg.itens) == 3
    cpu = next(i for i in cfg.itens if i.nome == "Ryzen 7 5700X")
    assert cpu.tipo == "produto"
    tv = next(i for i in cfg.itens if i.nome == "TV 32-40")
    assert tv.limite_total == 1500.0
    assert len(tv.urls) == 1


def test_sem_segredos(tmp_path):
    cfg = carregar(RAIZ / "config.exemplo.toml", tmp_path / "nao_existe.toml")
    assert cfg.ntfy_topico is None
    assert cfg.ntfy_servidor == "https://ntfy.sh"


def test_aceita_arquivo_com_bom(tmp_path):
    seg = tmp_path / "segredos.toml"
    seg.write_bytes('﻿ntfy_topico = "abc"\n'.encode("utf-8"))
    cfg = carregar(RAIZ / "config.exemplo.toml", seg)
    assert cfg.ntfy_topico == "abc"
