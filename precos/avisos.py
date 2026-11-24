"""Avisos: texto da mensagem, ntfy (celular), WhatsApp (CallMeBot) e janela no PC."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from statistics import median
from dataclasses import dataclass, field
from pathlib import Path

import requests

from .config import Config
from .zoom import Oferta

log = logging.getLogger(__name__)

ROTULOS = {
    "real": "✅ promoção real",
    "sem_historico": "⚠️ sem histórico, não confirmado",
    "normal": "menor preço já visto",
}


@dataclass
class Achado:
    item: str
    oferta: Oferta
    veredito: str
    tags: list[str] = field(default_factory=list)
    historico: list[float] = field(default_factory=list)  # preços diários (à vista)


def moeda(v: float) -> str:
    s = f"{v:,.2f}"  # 1,529.40
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def maiuscula(s: str) -> str:
    """Todo texto solto começa com maiúscula."""
    return s[:1].upper() + s[1:]


def _frete(loja: str) -> str:
    return "Frete grátis (Meli+)" if "mercado livre" in loja.lower() else "Frete: confira na loja"


ROTULOS_JANELA = {"real": "Promoção real", "sem_historico": "Sem histórico", "normal": "Menor preço já visto",
                  "maquiada": "Desconto maquiado"}


def _parcelas(o: Oferta) -> str:
    if o.parcelas and o.parcelas > 12:
        return f"em {o.parcelas}x (confira sem juros na loja)"
    return f"em {o.parcelas}x sem juros"


def dados_janela(achados: list[Achado]) -> list[dict]:
    """Dados separados de cada oferta, para a janela montar os cartões."""
    return [
        {
            "item": a.item, "nome": a.oferta.nome, "loja": a.oferta.loja,
            "preco": moeda(a.oferta.total_parcelado), "parcelas": maiuscula(_parcelas(a.oferta)),
            "pix": f"PIX {moeda(a.oferta.preco_vista)}", "veredito": a.veredito,
            "rotulo": ROTULOS_JANELA.get(a.veredito, a.veredito), "tags": [maiuscula(t) for t in a.tags],
            "frete": _frete(a.oferta.loja), "link": a.oferta.link, "imagem": a.oferta.imagem,
            "historico": list(a.historico[-90:]),
            "vista_num": a.oferta.preco_vista,
            "minimo": moeda(min(a.historico)) if a.historico else "",
            "mediana": moeda(median(a.historico)) if a.historico else "",
        }
        for a in achados
    ]


def _bloco(a: Achado) -> str:
    o = a.oferta
    parc = _parcelas(o)
    rotulo = ROTULOS.get(a.veredito, a.veredito)
    tags = "".join(f" · {t}" for t in a.tags)
    return (
        f"{a.item}: {o.nome}\n"
        f"{o.loja} — {moeda(o.total_parcelado)} {parc} (PIX {moeda(o.preco_vista)})\n"
        f"{rotulo}{tags}\n"
        f"{_frete(o.loja)}\n"
        f"{o.link}"
    )


def formatar(achados: list[Achado]) -> tuple[str, str]:
    n = len(achados)
    titulo = f"Monitor de preços: {n} oferta{'s' if n != 1 else ''}"
    return titulo, "\n\n".join(_bloco(a) for a in achados)


def enviar_ntfy(cfg: Config, titulo: str, corpo: str, link: str | None, sessao=None) -> bool:
    if not cfg.ntfy_topico:
        log.info("ntfy: nenhum tópico em segredos.toml, aviso no celular desligado")
        return False
    payload = {"topic": cfg.ntfy_topico, "title": titulo, "message": corpo, "tags": ["moneybag"]}
    if link:
        payload["click"] = link
    try:
        r = (sessao or requests).post(cfg.ntfy_servidor, json=payload, timeout=15)
        ok = r.status_code == 200
        if not ok:
            log.warning("ntfy respondeu %s", r.status_code)
        return ok
    except Exception as e:  # noqa: BLE001 - aviso nunca derruba a rodada
        log.warning("ntfy falhou: %s", e)
        return False


def enviar_whatsapp(cfg: Config, corpo: str, sessao=None) -> bool:
    if not (cfg.callmebot_fone and cfg.callmebot_apikey):
        return False
    try:
        r = (sessao or requests).get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": cfg.callmebot_fone, "text": corpo, "apikey": cfg.callmebot_apikey},
            timeout=20,
        )
        return r.status_code == 200
    except Exception as e:  # noqa: BLE001
        log.warning("whatsapp falhou: %s", e)
        return False


def abrir_janela(titulo: str, corpo: str, links: list[str], itens: list[dict] | None = None,
                 tema: str = "sistema") -> None:
    """Abre a janela em outro processo, para a rodada não ficar presa esperando fechar."""
    fd, caminho = tempfile.mkstemp(suffix=".json", prefix="precos_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"titulo": titulo, "corpo": corpo, "links": links, "itens": itens or [], "tema": tema}, f,
                  ensure_ascii=False)
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    raiz = Path(__file__).resolve().parent.parent
    subprocess.Popen(
        [str(pyw if pyw.exists() else exe), "-m", "precos.janela", caminho],
        cwd=raiz,
        creationflags=flags,
        close_fds=True,
    )
