"""Leitura de config.toml (itens) e segredos.toml (dados pessoais, fora do git)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class Item:
    nome: str
    url: str
    tipo: Literal["produto", "busca"] = "produto"
    modo: Literal["promocao", "mais_barato"] = "promocao"
    limite_total: float | None = None
    polegadas_min: float | None = None
    polegadas_max: float | None = None
    hz_min: int | None = None
    marcas: list[str] = field(default_factory=list)
    exigir: list[str] = field(default_factory=list)
    excluir: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)  # buscas extras (tipo busca)
    ordem: Literal["menor_preco", "parcelas"] = "menor_preco"  # parcelas = 10x+ primeiro


@dataclass
class Config:
    itens: list[Item]
    ntfy_topico: str | None = None
    ntfy_servidor: str = "https://ntfy.sh"
    cep: str | None = None
    callmebot_fone: str | None = None
    callmebot_apikey: str | None = None


def _ler(path: Path) -> dict:
    if not path.exists():
        return {}
    # utf-8-sig: aceita arquivo salvo com BOM (Bloco de Notas / PowerShell no Windows)
    return tomllib.loads(path.read_text(encoding="utf-8-sig"))


def carregar(config_path: Path, segredos_path: Path) -> Config:
    dados = _ler(Path(config_path))
    seg = _ler(Path(segredos_path))
    itens = []
    for d in dados.get("itens", []):
        if d.get("limite_total") is not None:
            d["limite_total"] = float(d["limite_total"])
        itens.append(Item(**d))
    return Config(
        itens=itens,
        ntfy_topico=seg.get("ntfy_topico") or None,
        ntfy_servidor=seg.get("ntfy_servidor", "https://ntfy.sh"),
        cep=seg.get("cep"),
        callmebot_fone=seg.get("callmebot_fone"),
        callmebot_apikey=seg.get("callmebot_apikey"),
    )
