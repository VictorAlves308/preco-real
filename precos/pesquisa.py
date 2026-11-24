"""Pesquisa com IA: gera buscas, julga produtos e (no nível completo) pesquisa avaliações na web.

Tudo fica em cache (só produto novo custa) e respeita o teto de gasto mensal.
Se a IA falhar ou o teto for atingido, a ferramenta segue só com as regras fixas.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from urllib.parse import quote

from .config import Config, Item
from .estado import Estado
from .ia import NOMES, ErroIA, classificar_erro

log = logging.getLogger(__name__)

SISTEMA = (
    "Você ajuda uma pessoa no Brasil a escolher o que comprar. Seja objetivo e responda "
    "somente no formato JSON pedido, sem texto antes ou depois."
)


def _json(texto: str, abre: str, fecha: str):
    i, j = texto.find(abre), texto.rfind(fecha)
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(texto[i:j + 1])
    except ValueError:
        return None


class Pesquisador:
    def __init__(self, cfg: Config, estado: Estado, provedores: dict, hoje: date | None = None,
                 notificar=None):
        self.cfg = cfg
        self.estado = estado
        # {"economica": [(id, provedor), ...]} em ordem de prioridade (aceita um provedor solto também)
        self.provedores = {n: self._lista(v) for n, v in provedores.items()}
        self._pulados: set[str] = set()  # IAs que falharam nesta rodada: não insiste nelas
        self.mes = (hoje or date.today()).strftime("%Y-%m")
        self.notificar = notificar

    def _lista(self, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [x for x in v if x and x[1] is not None]
        return [(self.cfg.ia.provedor, v)]

    # ---- orçamento e chamada ----
    def _orcamento_ok(self) -> bool:
        if self.estado.gasto(self.mes) < self.cfg.ia.limite_gasto_mensal:
            return True
        chave = f"orcamento_avisado:{self.mes}"
        if not self.estado.cache_ler(chave):
            self.estado.cache_gravar(chave, "1")
            msg = (f"Pesquisa com IA pausada: o limite de US$ {self.cfg.ia.limite_gasto_mensal:.2f} "
                   "deste mês foi atingido. Até o mês virar, sigo só com as regras fixas.")
            log.warning(msg)
            if self.notificar:
                self.notificar(msg)
        return False

    def _chamar(self, nivel: str, prompt: str, web: bool = False) -> str | None:
        """Tenta as IAs ligadas em ordem; se uma falhar (limite do plano, login, rede), usa a próxima."""
        lista = [(pid, prov) for pid, prov in self.provedores.get(nivel, []) if pid not in self._pulados]
        if not lista or not self._orcamento_ok():
            return None
        falhas: list[ErroIA] = []
        for pid, prov in lista:
            try:
                r = prov.gerar(SISTEMA, prompt, web=web)
            except Exception as e:  # noqa: BLE001 - IA nunca derruba a rodada
                erro = e if isinstance(e, ErroIA) else ErroIA(classificar_erro(str(e)), NOMES.get(pid, "IA"), str(e))
                log.warning("IA %s falhou (%s): %s", pid, erro.tipo, erro.detalhe or erro.mensagem)
                self._status(pid, erro.tipo, erro.mensagem)
                self._pulados.add(pid)
                falhas.append(erro)
                continue
            self._status(pid, "ok", "")
            self.estado.somar_gasto(self.mes, r.custo)
            for f in falhas:
                self._avisar(f, f"{f.mensagem} Usando {NOMES.get(pid, pid)} enquanto isso.")
            return r.texto
        for f in falhas:
            self._avisar(f, f"{f.mensagem} Até lá sigo só com as regras." if f.tipo == "limite" else f.mensagem)
        return None

    def _avisar(self, erro: ErroIA, texto: str) -> None:
        if erro.tipo not in ("limite", "login") or not self.notificar:
            return
        chave = f"ia_avisado:{erro.nome}:{erro.tipo}:{date.today().isoformat()}"
        if not self.estado.cache_ler(chave):  # no máximo um aviso por dia para cada IA
            self.estado.cache_gravar(chave, "1")
            self.notificar(texto)

    def _status(self, pid: str, tipo: str, mensagem: str) -> None:
        """Situação de cada IA, mostrada no app (faixa de aviso e Configurações)."""
        self.estado.cache_gravar(f"ia_status:{pid}", json.dumps(
            {"tipo": tipo, "mensagem": mensagem, "provedor": pid,
             "quando": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False))

    # ---- recursos ----
    def buscas_para(self, item: Item) -> list[str]:
        if item.pesquisa == "nenhuma" or not item.descricao:
            return []
        chave = f"buscas:{item.descricao}"
        termos = None
        salvo = self.estado.cache_ler(chave)
        if salvo:
            termos = json.loads(salvo)
        else:
            txt = self._chamar("economica", (
                f"A pessoa quer: {item.descricao!r}. Sugira até 4 termos curtos de busca para o site "
                "zoom.com.br que tragam os melhores candidatos (marcas/modelos bons e categoria). "
                'Responda só uma lista JSON de strings, ex.: ["air fryer mondial 4l"].'))
            termos = _json(txt or "", "[", "]")
            if isinstance(termos, list):
                termos = [str(t) for t in termos][:4]
                self.estado.cache_gravar(chave, json.dumps(termos, ensure_ascii=False))
            else:
                termos = []
        return [f"https://www.zoom.com.br/search?q={quote(t)}" for t in termos]

    def filtrar(self, item: Item, nomes: list[str]) -> dict[str, tuple[bool, str]]:
        """Aprova/reprova nomes de produtos para o item. Sem IA, aprova todos."""
        res: dict[str, tuple[bool, str]] = {}
        novos = []
        for n in dict.fromkeys(nomes):
            salvo = self.estado.cache_ler(f"julga:{item.nome}:{n}")
            if salvo:
                ok, motivo = json.loads(salvo)
                res[n] = (ok, motivo)
            else:
                novos.append(n)
        if novos and item.pesquisa != "nenhuma":
            lista = "\n".join(f"{i}. {n}" for i, n in enumerate(novos, 1))
            txt = self._chamar("economica", (
                f"A pessoa quer: {item.descricao or item.nome!r}.\nProdutos encontrados:\n{lista}\n\n"
                "Para cada um, diga se vale considerar (produto certo, de marca/qualidade decente, "
                "sem ser peça, acessório ou usado). Responda só uma lista JSON: "
                '[{"i": 1, "ok": true, "motivo": "até 8 palavras"}].'))
            dados = _json(txt or "", "[", "]")
            if isinstance(dados, list):
                for d in dados:
                    try:
                        n = novos[int(d["i"]) - 1]
                    except (KeyError, ValueError, IndexError, TypeError):
                        continue
                    res[n] = (bool(d.get("ok", True)), str(d.get("motivo", "")))
                    self.estado.cache_gravar(f"julga:{item.nome}:{n}", json.dumps(res[n], ensure_ascii=False))
        for n in novos:
            res.setdefault(n, (True, ""))
        return res

    def avaliar(self, item: Item, nome: str) -> tuple[int | None, str, bool] | None:
        """Nível completo: pesquisa avaliações na web. Devolve (nota, resumo, veto) ou None."""
        if item.pesquisa != "completa":
            return None
        chave = f"avalia:{nome}"
        salvo = self.estado.cache_ler(chave)
        if salvo:
            return tuple(json.loads(salvo))
        txt = self._chamar("completa", (
            f"Pesquise na web avaliações reais e defeitos conhecidos do produto {nome!r} "
            f"(a pessoa quer: {item.descricao or item.nome!r}). Dê uma nota de 0 a 10 de custo-benefício "
            "e vete se tiver defeito crônico ou reclamações graves. Responda só JSON: "
            '{"nota": 7, "resumo": "até 15 palavras", "veto": false}.'), web=True)
        d = _json(txt or "", "{", "}")
        if not isinstance(d, dict):
            return None
        nota = d.get("nota")
        r = (int(nota) if isinstance(nota, (int, float)) else None, str(d.get("resumo", "")), bool(d.get("veto")))
        self.estado.cache_gravar(chave, json.dumps(r, ensure_ascii=False))
        return r
