"""Leitura de config.toml (itens) e segredos.toml (dados pessoais, fora do git)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import quote


def url_busca(termo: str) -> str:
    """Endereço da busca no Zoom para um termo (ninguém precisa colar link)."""
    return "https://www.zoom.com.br/search?q=" + quote(termo.strip())


@dataclass
class Item:
    nome: str
    url: str = ""
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
    pesquisa: Literal["nenhuma", "economica", "completa"] = "nenhuma"  # uso de IA
    descricao: str = ""  # o que você quer, em texto livre (usado pela IA)
    buscas: list[str] = field(default_factory=list)  # termos de busca no Zoom


@dataclass
class ConfigIA:
    provedor: Literal["nenhum", "claude", "openai", "claude_code", "codex"] = "nenhum"
    limite_gasto_mensal: float = 5.0  # em dólares
    modelo_economico: str | None = None
    modelo_completo: str | None = None
    preco_entrada: float | None = None  # US$ por 1 milhão de tokens (modelos fora da tabela)
    preco_saida: float | None = None
    modelos: dict = field(default_factory=dict)  # {provedor: {"economica": nome, "completa": nome}}
    conexoes: list[str] = field(default_factory=list)  # IAs ligadas, em ordem (a 1ª é a principal)

    def ligadas(self) -> list[str]:
        """IAs ligadas em ordem de prioridade. Configurações antigas tinham só 'provedor'."""
        validas = ("claude_code", "codex", "claude", "openai")
        if self.conexoes:
            return [c for c in self.conexoes if c in validas]
        return [self.provedor] if self.provedor in validas else []


@dataclass
class Config:
    itens: list[Item]
    ntfy_topico: str | None = None
    ntfy_servidor: str = "https://ntfy.sh"
    cep: str | None = None
    callmebot_fone: str | None = None
    callmebot_apikey: str | None = None
    ia: ConfigIA = field(default_factory=ConfigIA)
    chaves: dict = field(default_factory=dict)  # anthropic_api_key, openai_api_key
    tema: str = "sistema"  # janela de aviso: sistema | claro | escuro


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
        it = Item(**d)
        if it.buscas and not it.url:
            it.tipo = "busca"
            it.url = url_busca(it.buscas[0])
            it.urls = [url_busca(b) for b in it.buscas[1:]] + it.urls
        itens.append(it)
    return Config(
        itens=itens,
        ntfy_topico=seg.get("ntfy_topico") or None,
        ntfy_servidor=seg.get("ntfy_servidor", "https://ntfy.sh"),
        cep=seg.get("cep"),
        callmebot_fone=seg.get("callmebot_fone"),
        callmebot_apikey=seg.get("callmebot_apikey"),
        ia=ConfigIA(**dados.get("ia", {})),
        chaves={k: seg[k] for k in ("anthropic_api_key", "openai_api_key") if seg.get(k)},
        tema=dados.get("aparencia", {}).get("tema", "sistema"),
    )
