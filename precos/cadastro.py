"""Tela de cadastro: produtos monitorados e configurações, no mesmo visual da janela de aviso.

Abre com:  python -m precos --cadastro
Grava no config.toml e no segredos.toml (quem preferir pode continuar editando os arquivos).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import time

from . import zoom
from .config import carregar, url_busca
from .estado import Estado
from .regras import passa_filtro_nome
from datetime import datetime
import webbrowser

from . import janela_web
from .janela_web import _CLARO, _ESCURO, CSS_CARTAO, ICONES, PREF, TEMAS, cor_fundo, salvar_tema

RAIZ = Path(__file__).resolve().parent.parent
CABECALHO = (
    "# Gerado pela tela de cadastro (python -m precos --cadastro).\n"
    "# Pode editar à mão; veja config.exemplo.toml para todos os campos.\n\n"
)

# ---------------------------------------------------------------- TOML

def _valor(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_valor(x) for x in v) + "]"
    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{s}"'


def para_toml(dados: dict) -> str:
    linhas = []
    for k, v in dados.items():
        if not isinstance(v, (dict, list)) or (isinstance(v, list) and not (v and isinstance(v[0], dict))):
            linhas.append(f"{k} = {_valor(v)}")
    for k, v in dados.items():
        if isinstance(v, dict):
            linhas += ["", f"[{k}]"] + [f"{kk} = {_valor(vv)}" for kk, vv in v.items()]
    for k, v in dados.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            for t in v:
                linhas += ["", f"[[{k}]]"] + [f"{kk} = {_valor(vv)}" for kk, vv in t.items()]
    return "\n".join(linhas).lstrip("\n") + "\n"


def _ler(path: Path) -> dict:
    try:
        return tomllib.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}


def _gravar(path: Path, dados: dict, cabecalho: str = "") -> None:
    path = Path(path)
    bak = path.with_suffix(path.suffix + ".bak")
    if path.exists() and not bak.exists():
        shutil.copyfile(path, bak)  # guarda a versão original (com comentários) uma vez
    path.write_text(cabecalho + para_toml(dados), encoding="utf-8")


# ---------------------------------------------------------------- formulário <-> item

def _lista(txt) -> list[str]:
    if isinstance(txt, list):
        return [str(x).strip() for x in txt if str(x).strip()]
    return [p.strip() for p in re.split(r"[,\n]", txt or "") if p.strip()]


def _numero(txt, campo: str, inteiro: bool = False):
    s = str(txt or "").replace("R$", "").replace(" ", "").strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        raise ValueError(f"Valor de {campo} inválido: use só números, ex.: 1500.") from None
    return int(n) if inteiro else n


def _termo_do_link(url: str) -> str | None:
    u = urlparse(url)
    return parse_qs(u.query).get("q", [None])[0] if u.path.rstrip("/") == "/search" else None


def item_do_form(form: dict, antigo: dict | None = None) -> dict:
    nome = (form.get("nome") or "").strip()
    if not nome:
        raise ValueError("Dê um nome ao produto.")
    it: dict = {"nome": nome}
    buscas = _lista(form.get("buscas"))
    if buscas:
        it["buscas"] = buscas
    elif antigo and antigo.get("url"):
        for k in ("url", "urls", "tipo"):
            if antigo.get(k):
                it[k] = antigo[k]
    else:
        raise ValueError("Diga o que buscar (ex.: ryzen 7 5700x).")
    limite = _numero(form.get("limite_total"), "preço máximo")
    if limite is not None:
        it["limite_total"] = limite
    it["modo"] = form.get("modo") if form.get("modo") in ("promocao", "mais_barato") else "promocao"
    if form.get("ordem") == "parcelas":
        it["ordem"] = "parcelas"
    if form.get("pesquisa") in ("economica", "completa"):
        it["pesquisa"] = form["pesquisa"]
    if (form.get("descricao") or "").strip():
        it["descricao"] = form["descricao"].strip()
    for campo in ("marcas", "exigir", "excluir"):
        v = _lista(form.get(campo))
        if campo == "exigir" and form.get("exigir_palavras") and buscas:
            v += [p for p in buscas[0].lower().split() if p not in v]
        if v:
            it[campo] = v
    for campo, rotulo, inteiro in (("polegadas_min", "polegadas mínimas", False),
                                   ("polegadas_max", "polegadas máximas", False),
                                   ("hz_min", "Hz mínimo", True)):
        n = _numero(form.get(campo), rotulo, inteiro)
        if n is not None:
            it[campo] = n
    return it


def form_de_item(raw: dict) -> dict:
    termos = list(raw.get("buscas", []))
    produto_fixo = False
    if not termos and raw.get("url"):
        for u in [raw["url"], *raw.get("urls", [])]:
            t = _termo_do_link(u)
            if t:
                termos.append(t)
            elif u == raw["url"]:
                produto_fixo = True

    def txt(v):
        return "" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))

    return {
        "nome": raw.get("nome", ""), "buscas": ", ".join(termos), "produto_fixo": produto_fixo,
        "limite_total": txt(raw.get("limite_total")), "modo": raw.get("modo", "promocao"),
        "ordem": raw.get("ordem", "menor_preco"), "pesquisa": raw.get("pesquisa", "nenhuma"),
        "descricao": raw.get("descricao", ""), "marcas": ", ".join(raw.get("marcas", [])),
        "exigir": ", ".join(raw.get("exigir", [])), "excluir": ", ".join(raw.get("excluir", [])),
        "polegadas_min": txt(raw.get("polegadas_min")), "polegadas_max": txt(raw.get("polegadas_max")),
        "hz_min": txt(raw.get("hz_min")), "exigir_palavras": False,
    }


# ---------------------------------------------------------------- ponte com a janela

class Api:
    def __init__(self, config_path: Path = RAIZ / "config.toml", segredos_path: Path = RAIZ / "segredos.toml",
                 estado_path: Path = RAIZ / "dados" / "estado.db", baixar=None,
                 instantaneo: Path = RAIZ / "dados" / "ultima_rodada.json"):
        self._config_path = Path(config_path)
        self._segredos_path = Path(segredos_path)
        self._estado_path = Path(estado_path)
        self._baixar = baixar or zoom.baixar
        self._instantaneo = Path(instantaneo)

    def ofertas(self) -> dict:
        """Aba Ofertas: as melhores ofertas de cada produto na última verificação."""
        try:
            snap = json.loads(self._instantaneo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"quando": "", "html": '<div class="vazio"><b>Ainda não verifiquei os preços</b>'
                    'Clique em Verificar agora. Leva cerca de um minuto.</div>'}
        quando = datetime.fromisoformat(snap["quando"]).strftime("%d/%m às %H:%M")
        partes, idx = [], 0
        for raw in _ler(self._config_path).get("itens", []):
            nome = raw.get("nome", "")
            cartoes = snap.get("itens", {}).get(nome)
            partes.append(f'<section class="grupo"><h3>{escape(nome)}</h3>')
            if not cartoes:
                msg = ("Nenhuma oferta passou nos seus filtros na última verificação." if cartoes is not None
                       else "Ainda não verificado. Clique em Verificar agora.")
                partes.append(f'<div class="cartao nada">{msg}</div></section>')
                continue
            partes.append(janela_web._cartao(cartoes[0], idx)); idx += 1
            if len(cartoes) > 1:
                partes.append(f'<details class="mais"><summary>Mais {len(cartoes) - 1} '
                              f'oferta{"s" if len(cartoes) > 2 else ""}</summary>')
                for c in cartoes[1:]:
                    partes.append(janela_web._cartao(c, idx)); idx += 1
                partes.append("</details>")
            partes.append("</section>")
        return {"quando": quando, "html": "".join(partes)}

    def abrir(self, link: str) -> None:
        if link.startswith("https://"):
            webbrowser.open(link)

    def _foto(self, nome: str) -> str:
        return Estado(self._estado_path).cache_ler(f"imagem:{nome}") or ""

    def atualizar_imagens(self) -> dict:
        """Busca no Zoom a foto dos produtos que ainda não têm. Devolve {indice: url}."""
        cfg = carregar(self._config_path, self._segredos_path)
        estado, novas = Estado(self._estado_path), {}
        for i, item in enumerate(cfg.itens):
            if self._foto(item.nome) or not item.url:
                continue
            if novas:
                time.sleep(1)
            try:
                est = zoom.extrair_estado(self._baixar(item.url))
                if item.tipo == "produto":
                    fotos = [o.imagem for o in zoom.parse_produto(est, item.url).ofertas if o.imagem]
                else:
                    hits = [h for h in zoom.parse_busca(est) if h.imagem]
                    bons = [h for h in hits if passa_filtro_nome(h.nome, item)[0]]
                    fotos = [h.imagem for h in (bons or hits)]
            except Exception:  # noqa: BLE001 - sem foto não é erro
                continue
            if fotos:
                estado.cache_gravar(f"imagem:{item.nome}", fotos[0])
                novas[str(i)] = fotos[0]
        return novas

    def dados(self) -> dict:
        raw, seg = _ler(self._config_path), _ler(self._segredos_path)
        ia = raw.get("ia", {})
        return {
            "itens": [dict(form_de_item(i), imagem=self._foto(i.get("nome", ""))) for i in raw.get("itens", [])],
            "geral": {
                "tema": raw.get("aparencia", {}).get("tema", "sistema"),
                "ntfy_topico": seg.get("ntfy_topico", ""),
                "provedor": ia.get("provedor", "nenhum"),
                "limite_gasto_mensal": f'{ia.get("limite_gasto_mensal", 5):g}',
                "tem_chave_claude": bool(seg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")),
                "tem_chave_openai": bool(seg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")),
            },
        }

    def salvar_item(self, form: dict, indice: int | None) -> dict:
        raw = _ler(self._config_path)
        itens = raw.setdefault("itens", [])
        antigo = itens[indice] if indice is not None and 0 <= indice < len(itens) else None
        try:
            novo = item_do_form(form, antigo)
        except ValueError as e:
            return {"ok": False, "erro": str(e)}
        if antigo is not None:
            itens[indice] = novo
        else:
            itens.append(novo)
        _gravar(self._config_path, raw, CABECALHO)
        return {"ok": True, "dados": self.dados()}

    def excluir_item(self, indice: int) -> dict:
        raw = _ler(self._config_path)
        itens = raw.get("itens", [])
        if 0 <= indice < len(itens):
            itens.pop(indice)
            if not itens:
                raw.pop("itens")
            _gravar(self._config_path, raw, CABECALHO)
        return {"ok": True, "dados": self.dados()}

    def salvar_geral(self, form: dict) -> dict:
        raw, seg = _ler(self._config_path), _ler(self._segredos_path)
        try:
            limite = _numero(form.get("limite_gasto_mensal"), "limite de gasto")
        except ValueError as e:
            return {"ok": False, "erro": str(e)}
        if form.get("tema") in TEMAS:
            raw.setdefault("aparencia", {})["tema"] = form["tema"]
        ia = raw.setdefault("ia", {})
        ia["provedor"] = form.get("provedor") if form.get("provedor") in ("claude", "openai") else "nenhum"
        if limite is not None:
            ia["limite_gasto_mensal"] = limite
        topico = (form.get("ntfy_topico") or "").strip()
        if topico:
            seg["ntfy_topico"] = topico
        else:
            seg.pop("ntfy_topico", None)
        chave = (form.get("chave") or "").strip()
        if chave and ia["provedor"] != "nenhum":
            seg["anthropic_api_key" if ia["provedor"] == "claude" else "openai_api_key"] = chave
        _gravar(self._config_path, raw, CABECALHO)
        _gravar(self._segredos_path, seg, "# Seus dados. NÃO vai para o git.\n\n")
        return {"ok": True, "dados": self.dados()}

    def salvar_tema(self, tema: str) -> None:
        salvar_tema(PREF, tema)
        raw = _ler(self._config_path)
        raw.setdefault("aparencia", {})["tema"] = tema
        _gravar(self._config_path, raw, CABECALHO)

    def _rodar(self, *args) -> None:  # privado: não exposto à página
        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        subprocess.Popen([str(pyw if pyw.exists() else exe), "-m", "precos", *args], cwd=RAIZ,
                         creationflags=flags, close_fds=True)

    def verificar_agora(self) -> str:
        self._rodar()
        return "Verificando agora. Se aparecer oferta boa, a janela de aviso abre sozinha."

    def testar_aviso(self) -> str:
        self._rodar("--teste-aviso")
        return "Aviso de teste enviado. Confira o celular."


# ---------------------------------------------------------------- página

CSS = (
    CSS_CARTAO + ":root{" + _CLARO + "}"
    ':root[data-tema="escuro"]{' + _ESCURO + "}"
    '@media (prefers-color-scheme: dark){:root[data-tema="sistema"]{' + _ESCURO + "}}"
    + """
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--fundo);color:var(--texto);
  font:14px/1.45 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;
  display:flex;flex-direction:column;-webkit-font-smoothing:antialiased}
header{padding:20px 24px 0;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
h1{font-size:20px;font-weight:650;letter-spacing:-.01em}
header p{color:var(--suave);font-size:12.5px;margin-top:2px}
.temas{display:flex;gap:2px;background:var(--cartao);border:1px solid var(--borda);border-radius:999px;padding:3px}
.temas button{width:30px;height:30px;display:grid;place-items:center;border:0;border-radius:999px;
  background:transparent;color:var(--suave)}
.temas button:hover{color:var(--texto)}
.temas button[aria-pressed="true"]{background:var(--acento);color:var(--acento-texto)}
.ic{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
nav{display:flex;gap:20px;padding:14px 24px 0;border-bottom:1px solid var(--borda)}
nav button{background:none;border:0;padding:8px 0 10px;color:var(--suave);font-weight:600;
  border-bottom:2px solid transparent;margin-bottom:-1px;border-radius:0}
nav button[aria-selected="true"]{color:var(--texto);border-bottom-color:var(--acento)}
main{flex:1;overflow-y:auto;padding:18px 18px 24px 24px;scrollbar-gutter:stable}
main::-webkit-scrollbar{width:10px}
main::-webkit-scrollbar-thumb{background:var(--borda-forte);border-radius:999px;border:3px solid var(--fundo)}
main::-webkit-scrollbar-thumb:hover{background:var(--suave)}
.oculto{display:none!important}
.lista{display:flex;flex-direction:column;gap:10px}
.cartao{background:var(--cartao);border:1px solid var(--borda);border-radius:12px;padding:16px}
.prod{display:flex;align-items:center;gap:16px}
.prod .foto{width:64px;height:64px;flex:none;border-radius:8px;background:var(--foto);object-fit:contain;
  padding:4px;border:1px solid var(--borda)}
.prod .foto.vazia{display:grid;place-items:center;background:var(--fundo);color:var(--suave);
  font-size:22px;font-weight:650}
.prod .info{flex:1;min-width:0}
.prod h2{font-size:15px;font-weight:600}
.prod .busca{color:var(--suave);font-size:12.5px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.etiquetas{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.grupo+.grupo{margin-top:22px}
.grupo h3{font-size:13px;font-weight:650;color:var(--suave);text-transform:uppercase;
  letter-spacing:.05em;margin:0 0 8px 2px}
.nada{color:var(--suave);font-size:13px}
.mais{margin-top:8px;border:0;padding:0}
#ofertas .item{display:none}
#ofertas .nome{margin-top:0}
.mais summary{cursor:pointer;color:var(--suave);font-size:13px;font-weight:600;padding:4px 2px}
.mais .cartao{margin-top:8px}
.barra{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;
  color:var(--suave);font-size:12.5px}
.chip{font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;white-space:nowrap;
  background:var(--normal-bg);color:var(--normal-tx)}
.chip.verde{background:var(--bom-bg);color:var(--bom-tx)}
.chip.ia{background:var(--sem-bg);color:var(--sem-tx)}
.acoes{display:flex;gap:6px;flex:none}
button{font:inherit;cursor:pointer;border-radius:8px}
.btn{background:transparent;color:var(--texto);border:1px solid var(--borda);padding:7px 14px}
.btn:hover{background:var(--fundo)}
.btn.perigo:hover{color:var(--muito-tx);border-color:var(--muito-tx);background:var(--muito-bg)}
.btn.primario{background:var(--acento);color:var(--acento-texto);border-color:var(--acento);font-weight:600}
.btn.primario:hover{background:var(--acento-hover)}
.vazio{text-align:center;color:var(--suave);padding:40px 16px}
.vazio b{display:block;color:var(--texto);font-size:15px;margin-bottom:4px}
.adicionar{margin-top:14px}
form{display:flex;flex-direction:column;gap:16px}
form h2{font-size:16px;font-weight:650}
.campo{display:flex;flex-direction:column;gap:6px}
.campo label,.rotulo{font-size:13px;font-weight:600}
.campo small{color:var(--suave);font-size:12px}
input,textarea,select{font:inherit;color:var(--texto);background:var(--cartao);border:1px solid var(--borda-forte);
  border-radius:8px;padding:9px 12px;outline:none;width:100%}
input:focus,textarea:focus{border-color:var(--acento);box-shadow:0 0 0 3px var(--bom-bg)}
textarea{resize:vertical;min-height:64px}
.linha{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.seg{display:flex;background:var(--fundo);border:1px solid var(--borda);border-radius:10px;padding:3px;gap:3px}
.seg button{flex:1;border:0;background:transparent;color:var(--suave);padding:7px 10px;font-size:13px;font-weight:600}
.seg button[aria-pressed="true"]{background:var(--cartao);color:var(--texto);box-shadow:0 0 0 1px var(--borda)}
.check{display:flex;align-items:center;gap:8px;font-size:13px}
.check input{width:auto}
details{border-top:1px solid var(--borda);padding-top:14px}
summary{cursor:pointer;font-weight:600;font-size:13px;color:var(--suave)}
details[open] summary{margin-bottom:14px;color:var(--texto)}
details .grade{display:flex;flex-direction:column;gap:14px}
.erro{background:var(--muito-bg);color:var(--muito-tx);border-radius:8px;padding:9px 12px;font-size:13px}
.botoes{display:flex;justify-content:flex-end;gap:8px}
.secao{display:flex;flex-direction:column;gap:14px}
.secao+.secao{margin-top:14px}
.secao h3{font-size:14px;font-weight:650}
.secao p.dica{color:var(--suave);font-size:12.5px;margin-top:-8px}
.junto{display:flex;gap:8px}
.junto input{flex:1}
footer{padding:12px 24px 16px;border-top:1px solid var(--borda);display:flex;align-items:center;gap:12px}
footer .status{flex:1;color:var(--suave);font-size:12.5px}
.sk{display:block;background:var(--borda);border-radius:6px;animation:pulso 1.2s ease-in-out infinite}
@keyframes pulso{50%{opacity:.45}}
.sk-cartao+.sk-cartao{margin-top:12px}
.sk-topo{display:flex;gap:14px}
.sk-foto{width:64px;height:64px;border-radius:8px;flex:none}
.sk-linhas{flex:1;display:flex;flex-direction:column;gap:8px;padding-top:4px}
.sk-l1{height:10px;width:30%}
.sk-l2{height:14px;width:80%}
.sk-preco{height:26px;width:40%;margin-top:18px}
.sk-graf{height:44px;margin-top:18px}
.entrar{animation:aparecer .25s ease-out}
@keyframes aparecer{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion: reduce){.sk,.entrar{animation:none}}
"""
)

JS = r"""
const raiz = document.documentElement;
let D = null, editando = null, pausa = null;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = () => window.pywebview && window.pywebview.api;

function marcarTema(){ document.querySelectorAll('[data-escolha]').forEach(b =>
  b.setAttribute('aria-pressed', b.dataset.escolha === raiz.dataset.tema)); }

function seg(grupo, valor){ document.querySelectorAll(`[data-grupo="${grupo}"] button`).forEach(b =>
  b.setAttribute('aria-pressed', b.dataset.v === valor)); }
function segValor(grupo){ const b = document.querySelector(`[data-grupo="${grupo}"] button[aria-pressed="true"]`);
  return b ? b.dataset.v : ''; }

function chipsDe(it){
  const c = [];
  if (it.limite_total) c.push(`<span class="chip">Até R$ ${esc(it.limite_total)}</span>`);
  c.push(it.modo === 'mais_barato' ? '<span class="chip verde">Avisa o menor preço</span>'
                                   : '<span class="chip verde">Só promoção real</span>');
  if (it.ordem === 'parcelas') c.push('<span class="chip">10x primeiro</span>');
  if (it.pesquisa !== 'nenhuma') c.push(`<span class="chip ia">IA ${it.pesquisa === 'completa' ? 'completa' : 'econômica'}</span>`);
  return c.join('');
}

function render(){
  const n = D.itens.length;
  $('#resumo').textContent = n ? `${n} produto${n > 1 ? 's' : ''} monitorado${n > 1 ? 's' : ''}` : 'Nenhum produto ainda';
  $('#lista').innerHTML = n ? D.itens.map((it, i) => `
    <article class="cartao prod">
      ${it.imagem ? `<img class="foto" src="${esc(it.imagem)}" alt="">`
        : `<div class="foto vazia">${esc((it.nome || '?').trim()[0].toUpperCase())}</div>`}
      <div class="info"><h2>${esc(it.nome)}</h2>
        <p class="busca">${it.buscas ? 'Busca: ' + esc(it.buscas) : 'Produto específico'}</p>
        <div class="etiquetas">${chipsDe(it)}</div></div>
      <div class="acoes"><button class="btn" data-editar="${i}">Editar</button>
        <button class="btn perigo" data-excluir="${i}">Excluir</button></div>
    </article>`).join('')
    : '<div class="vazio"><b>Nada sendo monitorado</b>Adicione o primeiro produto para começar.</div>';
  const g = D.geral;
  $('#g-ntfy').value = g.ntfy_topico; $('#g-limite').value = g.limite_gasto_mensal;
  seg('provedor', g.provedor); atualizarChave();
}

function atualizarChave(){
  const p = segValor('provedor'), g = D.geral;
  $('#bloco-chave').classList.toggle('oculto', p === 'nenhum');
  const tem = p === 'claude' ? g.tem_chave_claude : g.tem_chave_openai;
  $('#g-chave').placeholder = tem ? 'Chave já salva (deixe em branco para manter)' : (p === 'claude' ? 'sk-ant-...' : 'sk-...');
}

function abrirForm(i){
  editando = i;
  const it = i === null ? {nome:'',buscas:'',limite_total:'',modo:'promocao',ordem:'menor_preco',pesquisa:'nenhuma',
    descricao:'',marcas:'',exigir:'',excluir:'',polegadas_min:'',polegadas_max:'',hz_min:'',produto_fixo:false} : D.itens[i];
  $('#f-titulo').textContent = i === null ? 'Novo produto' : 'Editar produto';
  for (const k of ['nome','buscas','limite_total','descricao','marcas','exigir','excluir','polegadas_min','polegadas_max','hz_min'])
    $('#f-' + k).value = it[k] || '';
  $('#f-fixo').classList.toggle('oculto', !it.produto_fixo);
  $('#f-palavras').checked = i === null;
  seg('modo', it.modo); seg('ordem', it.ordem); seg('pesquisa', it.pesquisa); atualizarIA();
  $('#f-erro').classList.add('oculto');
  $('#tela-lista').classList.add('oculto'); $('#tela-form').classList.remove('oculto');
  $('#f-nome').focus();
}
function fecharForm(){ $('#tela-form').classList.add('oculto'); $('#tela-lista').classList.remove('oculto'); }
function atualizarIA(){ $('#bloco-descricao').classList.toggle('oculto', segValor('pesquisa') === 'nenhuma'); }

function status(t){ $('#status').textContent = t; clearTimeout(pausa); pausa = setTimeout(() => $('#status').textContent = '', 6000); }

async function salvarForm(ev){
  ev.preventDefault();
  const f = {exigir_palavras: $('#f-palavras').checked, modo: segValor('modo'), ordem: segValor('ordem'), pesquisa: segValor('pesquisa')};
  for (const k of ['nome','buscas','limite_total','descricao','marcas','exigir','excluir','polegadas_min','polegadas_max','hz_min'])
    f[k] = $('#f-' + k).value;
  if (!api()) return;
  const r = await api().salvar_item(f, editando);
  if (!r.ok) { $('#f-erro').textContent = r.erro; $('#f-erro').classList.remove('oculto'); return; }
  D = r.dados; render(); fecharForm(); status('Produto salvo.');
  const novas = await api().atualizar_imagens();
  for (const [i, url] of Object.entries(novas)) if (D.itens[+i]) D.itens[+i].imagem = url;
  if (Object.keys(novas).length) render();
}

async function salvarGeral(ev){
  ev.preventDefault();
  if (!api()) return;
  const r = await api().salvar_geral({ntfy_topico: $('#g-ntfy').value, provedor: segValor('provedor'),
    chave: $('#g-chave').value, limite_gasto_mensal: $('#g-limite').value, tema: raiz.dataset.tema});
  if (!r.ok) { status(r.erro); return; }
  $('#g-chave').value = ''; D = r.dados; render(); status('Configurações salvas.');
}

document.addEventListener('click', async e => {
  const t = e.target.closest('[data-escolha]');
  if (t) { raiz.dataset.tema = t.dataset.escolha; marcarTema(); if (api()) api().salvar_tema(t.dataset.escolha); }
  const aba = e.target.closest('[data-aba]');
  if (aba) { document.querySelectorAll('[data-aba]').forEach(b => b.setAttribute('aria-selected', b === aba));
    for (const a of ['ofertas','produtos','config']) { const s = $('#aba-' + a);
      s.classList.toggle('oculto', aba.dataset.aba !== a); s.classList.remove('entrar');
      if (aba.dataset.aba === a) { void s.offsetWidth; s.classList.add('entrar'); } }
  }
  const sb = e.target.closest('.seg button');
  if (sb) { e.preventDefault(); seg(sb.parentElement.dataset.grupo, sb.dataset.v);
    if (sb.parentElement.dataset.grupo === 'pesquisa') atualizarIA();
    if (sb.parentElement.dataset.grupo === 'provedor') atualizarChave(); }
  const ed = e.target.closest('[data-editar]'); if (ed) abrirForm(+ed.dataset.editar);
  const ex = e.target.closest('[data-excluir]');
  if (ex) { if (ex.dataset.conf) { const r = await api().excluir_item(+ex.dataset.excluir); D = r.dados; render(); status('Produto excluído.'); }
            else { ex.dataset.conf = '1'; ex.textContent = 'Confirmar'; setTimeout(() => { delete ex.dataset.conf; ex.textContent = 'Excluir'; }, 3000); } }
  if (e.target.closest('#adicionar')) abrirForm(null);
  if (e.target.closest('#cancelar')) fecharForm();
  const lk = e.target.closest('[data-link]'); if (lk && api()) api().abrir(lk.dataset.link);
  if (e.target.closest('#verificar') && api()) { status(await api().verificar_agora()); acompanhar(); }
  if (e.target.closest('#testar') && api()) status(await api().testar_aviso());
});
$('#form-item').addEventListener('submit', salvarForm);
$('#form-geral').addEventListener('submit', salvarGeral);
marcarTema();

let ultimo = null;
async function carregarOfertas(){
  const r = api() ? await api().ofertas() : window.OFERTAS_DEMO; if (!r) return r;
  const o = $('#ofertas'); o.innerHTML = r.html; o.classList.remove('entrar'); void o.offsetWidth; o.classList.add('entrar');
  $('#quando').textContent = r.quando ? 'Última verificação: ' + r.quando : '';
  return r;
}
async function acompanhar(){  // depois de Verificar agora, atualiza quando a verificação terminar
  const antes = ultimo;
  for (let i = 0; i < 40; i++) { await new Promise(r => setTimeout(r, 5000));
    const r = await carregarOfertas(); if (r && r.quando && r.quando !== antes) { ultimo = r.quando; status('Preços atualizados.'); return; } }
}
async function iniciar(){
  const r = await carregarOfertas(); if (r) ultimo = r.quando;
  D = api() ? await api().dados() : window.DADOS_DEMO; if (!D) return; render();
  if (api() && D.itens.some(i => !i.imagem)) {
    const novas = await api().atualizar_imagens();
    for (const [i, url] of Object.entries(novas)) if (D.itens[+i]) D.itens[+i].imagem = url;
    if (Object.keys(novas).length) render();
  }
}
if (window.DADOS_DEMO) iniciar(); else window.addEventListener('pywebviewready', iniciar);
"""


def _seg(grupo: str, opcoes) -> str:
    return (f'<div class="seg" data-grupo="{grupo}">'
            + "".join(f'<button type="button" data-v="{v}">{escape(r)}</button>' for v, r in opcoes) + "</div>")


def _campo(id_: str, rotulo: str, dica: str = "", tipo: str = "input", ph: str = "") -> str:
    ctrl = (f'<textarea id="f-{id_}" placeholder="{escape(ph)}"></textarea>' if tipo == "textarea"
            else f'<input id="f-{id_}" placeholder="{escape(ph)}" autocomplete="off">')
    return (f'<div class="campo"><label for="f-{id_}">{escape(rotulo)}</label>{ctrl}'
            + (f"<small>{escape(dica)}</small>" if dica else "") + "</div>")


def html_cadastro(tema: str = "sistema", demo: dict | None = None, ofertas_demo: dict | None = None) -> str:
    tema = tema if tema in TEMAS else "sistema"
    seletor = "".join(
        f'<button data-escolha="{t}" aria-label="{r}" title="{r}">'
        f'<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">{ICONES[t]}</svg></button>'
        for t, r in (("sistema", "Seguir o sistema"), ("claro", "Tema claro"), ("escuro", "Tema escuro"))
    )
    form_item = (
        '<form id="form-item" class="cartao" novalidate><h2 id="f-titulo">Novo produto</h2>'
        '<p id="f-erro" class="erro oculto"></p>'
        + _campo("nome", "Nome", "Como ele aparece nos avisos.", ph="Ex.: Monitor 144Hz")
        + _campo("buscas", "O que buscar", "Escreva como você procuraria numa loja. Separe mais de uma busca com vírgula.",
                 ph="Ex.: monitor 144hz, monitor aoc 144hz")
        + '<p id="f-fixo" class="campo oculto"><small>Este produto está ligado a uma página específica. '
          "Deixe a busca em branco para manter assim.</small></p>"
        + '<label class="check"><input type="checkbox" id="f-palavras"> Só produtos com todas as palavras da primeira busca</label>'
        + _campo("limite_total", "Preço máximo no cartão (opcional)", "Total parcelado. Ex.: 1500", ph="Sem limite")
        + '<div class="campo"><span class="rotulo">Quando avisar</span>'
        + _seg("modo", (("promocao", "Só promoção real"), ("mais_barato", "Sempre que achar o menor preço"))) + "</div>"
        + '<div class="campo"><span class="rotulo">Ordem das ofertas</span>'
        + _seg("ordem", (("menor_preco", "Mais barato primeiro"), ("parcelas", "10x sem juros primeiro"))) + "</div>"
        + '<div class="campo"><span class="rotulo">Pesquisa com IA</span>'
        + _seg("pesquisa", (("nenhuma", "Desligada"), ("economica", "Econômica"), ("completa", "Completa")))
        + "<small>Econômica descarta produtos ruins (centavos por mês). Completa também lê avaliações na web.</small></div>"
        + '<div id="bloco-descricao">' + _campo("descricao", "O que você quer, com suas palavras",
                                                  tipo="textarea", ph="Ex.: air fryer boa até 500, fácil de limpar") + "</div>"
        + '<details><summary>Filtros avançados</summary><div class="grade">'
        + _campo("marcas", "Só estas marcas", "Separadas por vírgula. Vazio = qualquer marca.", ph="Ex.: LG, Samsung, AOC")
        + _campo("exigir", "Palavras obrigatórias no nome", ph="Ex.: Smart")
        + _campo("excluir", "Palavras que eliminam o anúncio", ph="Ex.: usado, recondicionado")
        + '<div class="linha">' + _campo("polegadas_min", "Polegadas mín.", ph="Ex.: 24")
        + _campo("polegadas_max", "Polegadas máx.", ph="Ex.: 27") + _campo("hz_min", "Hz mínimo", ph="Ex.: 144")
        + "</div></div></details>"
        '<div class="botoes"><button type="button" class="btn" id="cancelar">Cancelar</button>'
        '<button type="submit" class="btn primario">Salvar produto</button></div></form>'
    )
    form_geral = (
        '<form id="form-geral" class="cartao" novalidate>'
        '<div class="secao"><h3>Avisos no celular</h3>'
        '<p class="dica">Instale o app ntfy, toque em + e digite o mesmo nome de canal.</p>'
        '<div class="campo"><label for="g-ntfy">Canal do ntfy</label><div class="junto">'
        '<input id="g-ntfy" placeholder="Ex.: precos-k7x9q2" autocomplete="off">'
        '<button type="button" class="btn" id="testar">Enviar teste</button></div>'
        "<small>Use um nome difícil de adivinhar: quem souber o nome lê os avisos.</small></div></div>"
        '<div class="secao"><h3>Pesquisa com IA</h3>'
        '<div class="campo"><span class="rotulo">Provedor</span>'
        + _seg("provedor", (("nenhum", "Nenhum"), ("claude", "Claude"), ("openai", "OpenAI")))
        + '</div><div id="bloco-chave" class="campo"><label for="g-chave">Chave da API</label>'
        '<input id="g-chave" type="password" autocomplete="off"></div>'
        '<div class="campo"><label for="g-limite">Gasto máximo por mês (US$)</label>'
        '<input id="g-limite" inputmode="decimal" placeholder="5"><small>Ao chegar nele, a IA pausa até o mês virar.</small></div></div>'
        '<div class="botoes"><button type="submit" class="btn primario">Salvar configurações</button></div></form>'
    )
    demo_js = (f"<script>window.DADOS_DEMO={json.dumps(demo, ensure_ascii=False)};"
               f"window.OFERTAS_DEMO={json.dumps(ofertas_demo, ensure_ascii=False)};</script>") if demo else ""
    return (
        f'<!doctype html><html lang="pt-BR" data-tema="{tema}"><head><meta charset="utf-8">'
        f"<title>Monitor de preços</title><style>{CSS}</style></head><body>"
        '<header><div><h1>Monitor de preços</h1><p id="resumo">Carregando…</p></div>'
        f'<div class="temas" role="group" aria-label="Tema">{seletor}</div></header>'
        '<nav role="tablist"><button data-aba="ofertas" aria-selected="true">Ofertas</button>'
        '<button data-aba="produtos" aria-selected="false">Produtos</button>'
        '<button data-aba="config" aria-selected="false">Configurações</button></nav>'
        '<main><section id="aba-ofertas"><div class="barra"><span id="quando"></span></div>'
        '<div id="ofertas"><div class="cartao sk-cartao"><div class="sk-topo"><span class="sk sk-foto"></span><span class="sk-linhas"><span class="sk sk-l1"></span><span class="sk sk-l2"></span></span></div><span class="sk sk-preco"></span><span class="sk sk-graf"></span></div><div class="cartao sk-cartao"><div class="sk-topo"><span class="sk sk-foto"></span><span class="sk-linhas"><span class="sk sk-l1"></span><span class="sk sk-l2"></span></span></div><span class="sk sk-preco"></span><span class="sk sk-graf"></span></div></div></section>'
        '<section id="aba-produtos" class="oculto"><div id="tela-lista"><div id="lista" class="lista"></div>'
        '<button class="btn primario adicionar" id="adicionar">Adicionar produto</button></div>'
        f'<div id="tela-form" class="oculto">{form_item}</div></section>'
        f'<section id="aba-config" class="oculto">{form_geral}</section></main>'
        '<footer><span class="status" id="status"></span>'
        '<button class="btn" id="verificar">Verificar agora</button></footer>'
        f"{demo_js}<script>{JS}</script></body></html>"
    )


def abrir() -> None:
    import webview

    from .janela_web import ler_tema

    api = Api()
    tema = ler_tema(PREF, _ler(api._config_path).get("aparencia", {}).get("tema", "sistema"))
    webview.create_window("Monitor de preços", html=html_cadastro(tema), js_api=api,
                          width=760, height=820, min_size=(560, 520), background_color=cor_fundo(tema))
    webview.start()
