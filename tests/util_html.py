"""Utilitários de teste: monta HTML no formato do Zoom a partir de uma fixture JSON."""
import json
from pathlib import Path

FIXT = Path(__file__).resolve().parent / "fixtures"


def estado(nome: str) -> dict:
    return json.loads((FIXT / nome).read_text(encoding="utf-8"))


def html_de(est: dict) -> str:
    dados = {"props": {"initialReduxState": est}}
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(dados, ensure_ascii=False)
        + "</script></body></html>"
    )


class Resp:
    def __init__(self, status: int, text: str = ""):
        self.status_code = status
        self.text = text


class SessaoFake:
    """Responde por host: {"www.zoom.com.br": Resp, ...}; guarda as URLs pedidas."""

    def __init__(self, por_host: dict):
        self.por_host = por_host
        self.urls = []

    def get(self, url, **kw):
        self.urls.append(url)
        for host, resp in self.por_host.items():
            if host in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return Resp(404)
