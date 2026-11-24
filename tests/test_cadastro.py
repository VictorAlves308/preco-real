import tomllib

import pytest

from precos.cadastro import Api, form_de_item, html_cadastro, item_do_form, para_toml
from precos.config import carregar, url_busca


def test_url_busca():
    assert url_busca("ryzen 7 5700x") == "https://www.zoom.com.br/search?q=ryzen%207%205700x"


def test_carregar_item_com_buscas(tmp_path):
    c = tmp_path / "c.toml"
    c.write_text('[[itens]]\nnome = "CPU"\nbuscas = ["ryzen 7 5700x", "5700x box"]\n', encoding="utf-8")
    item = carregar(c, tmp_path / "s.toml").itens[0]
    assert item.tipo == "busca"
    assert item.url == url_busca("ryzen 7 5700x")
    assert item.urls == [url_busca("5700x box")]


def test_para_toml_ida_e_volta():
    dados = {
        "aparencia": {"tema": "escuro"},
        "ia": {"provedor": "claude", "limite_gasto_mensal": 5.0},
        "itens": [
            {"nome": 'TV "boa"', "buscas": ["smart tv 32"], "limite_total": 1500.0, "polegadas_min": 32},
            {"nome": "Ação ç", "url": "https://www.zoom.com.br/x", "tipo": "produto"},
        ],
    }
    assert tomllib.loads(para_toml(dados)) == dados


def test_item_do_form_valida():
    with pytest.raises(ValueError, match="nome"):
        item_do_form({"nome": " ", "buscas": "x"})
    with pytest.raises(ValueError, match="buscar"):
        item_do_form({"nome": "CPU", "buscas": ""})
    with pytest.raises(ValueError, match="preço"):
        item_do_form({"nome": "CPU", "buscas": "x", "limite_total": "abc"})


def test_item_do_form_converte():
    it = item_do_form({"nome": "TV", "buscas": "smart tv 32, smart tv 40", "limite_total": "1.500,00",
                       "modo": "promocao", "ordem": "parcelas", "pesquisa": "nenhuma",
                       "marcas": "Samsung, LG", "polegadas_min": "32", "polegadas_max": "40",
                       "hz_min": "", "exigir_palavras": True})
    assert it == {"nome": "TV", "buscas": ["smart tv 32", "smart tv 40"], "limite_total": 1500.0,
                  "modo": "promocao", "ordem": "parcelas", "marcas": ["Samsung", "LG"],
                  "exigir": ["smart", "tv", "32"], "polegadas_min": 32.0, "polegadas_max": 40.0}


def test_form_de_item_deriva_termos_do_link():
    f = form_de_item({"nome": "Monitor", "url": url_busca("monitor 144hz"), "urls": [url_busca("monitor aoc")]})
    assert f["buscas"] == "monitor 144hz, monitor aoc"
    f = form_de_item({"nome": "CPU", "url": "https://www.zoom.com.br/processador/x", "tipo": "produto"})
    assert f["buscas"] == "" and f["produto_fixo"] is True


def test_item_de_produto_fixo_mantem_link_se_busca_vazia():
    antigo = {"nome": "CPU", "url": "https://www.zoom.com.br/processador/x", "tipo": "produto", "modo": "mais_barato"}
    it = item_do_form({"nome": "CPU", "buscas": "", "modo": "mais_barato"}, antigo)
    assert it["url"] == antigo["url"] and it["tipo"] == "produto"


def _api(tmp_path):
    (tmp_path / "config.toml").write_text("", encoding="utf-8")
    (tmp_path / "segredos.toml").write_text('cep = "00000-000"\nanthropic_api_key = "sk-velha"\n', encoding="utf-8")
    return Api(tmp_path / "config.toml", tmp_path / "segredos.toml")


def test_api_salvar_editar_excluir(tmp_path):
    api = _api(tmp_path)
    r = api.salvar_item({"nome": "CPU", "buscas": "ryzen 7 5700x", "modo": "mais_barato"}, None)
    assert r["ok"] and len(r["dados"]["itens"]) == 1
    r = api.salvar_item({"nome": "CPU 2", "buscas": "ryzen 7 5700x", "modo": "mais_barato"}, 0)
    assert r["dados"]["itens"][0]["nome"] == "CPU 2"
    assert carregar(tmp_path / "config.toml", tmp_path / "x").itens[0].nome == "CPU 2"
    assert api.salvar_item({"nome": "", "buscas": "x"}, None) == {"ok": False, "erro": "Dê um nome ao produto."}
    assert api.excluir_item(0)["dados"]["itens"] == []


def test_api_config_geral_nao_vaza_nem_apaga_chave(tmp_path):
    api = _api(tmp_path)
    d = api.dados()
    assert "sk-velha" not in str(d)
    assert d["geral"]["tem_chave_claude"] is True
    api.salvar_geral({"ntfy_topico": "precos-abc", "provedor": "claude", "chave": "", "limite_gasto_mensal": "3",
                      "tema": "claro"})
    seg = tomllib.loads((tmp_path / "segredos.toml").read_text(encoding="utf-8"))
    assert seg == {"cep": "00000-000", "anthropic_api_key": "sk-velha", "ntfy_topico": "precos-abc"}
    cfg = carregar(tmp_path / "config.toml", tmp_path / "segredos.toml")
    assert cfg.ia.provedor == "claude" and cfg.ia.limite_gasto_mensal == 3.0 and cfg.tema == "claro"


def test_html_cadastro():
    html = html_cadastro()
    for trecho in ('data-aba="produtos"', 'data-aba="config"', 'id="f-buscas"', 'id="verificar"',
                   'aria-label="Tema escuro"'):
        assert trecho in html


def test_api_fotos(tmp_path):
    from precos.estado import Estado
    from util_html import estado as fixture, html_de
    (tmp_path / "config.toml").write_text(
        '[[itens]]\nnome = "Monitor"\nbuscas = ["monitor 144hz"]\n\n[[itens]]\nnome = "Sem foto"\nbuscas = ["x"]\n',
        encoding="utf-8")
    Estado(tmp_path / "e.db").cache_gravar("imagem:Sem foto", "")
    pedidos = []

    def baixar(u):
        pedidos.append(u)
        return html_de(fixture("zoom_busca_monitor.json"))

    api = Api(tmp_path / "config.toml", tmp_path / "s.toml", tmp_path / "e.db", baixar=baixar)
    assert api.dados()["itens"][0]["imagem"] == ""
    fotos = api.atualizar_imagens()
    assert fotos["0"].startswith("https://")
    assert api.dados()["itens"][0]["imagem"] == fotos["0"]
    assert api.atualizar_imagens() == {}  # já tem: não baixa de novo
    assert len(pedidos) == 2


def test_api_ofertas_html(tmp_path):
    import json
    (tmp_path / "config.toml").write_text('[[itens]]\nnome = "CPU"\nbuscas = ["x"]\n\n[[itens]]\nnome = "TV"\nbuscas = ["y"]\n',
                                          encoding="utf-8")
    api = Api(tmp_path / "config.toml", tmp_path / "s.toml", tmp_path / "e.db", instantaneo=tmp_path / "u.json")
    vazio = api.ofertas()
    assert vazio["quando"] == "" and "Ainda não verifiquei" in vazio["html"]
    cartao = {"item": "CPU", "nome": "Ryzen", "loja": "KaBuM!", "preco": "R$ 1,00", "parcelas": "em 10x sem juros",
              "pix": "PIX R$ 1,00", "veredito": "maquiada", "rotulo": "Desconto maquiado", "tags": [],
              "frete": "f", "link": "https://x", "imagem": "", "historico": [], "minimo": "", "mediana": ""}
    (tmp_path / "u.json").write_text(json.dumps({"quando": "2026-11-24T13:40:00", "itens": {"CPU": [cartao]}}),
                                     encoding="utf-8")
    r = api.ofertas()
    assert r["quando"] == "24/11 às 13:40"
    assert r["html"].count('class="cartao"') == 1
    assert "TV" in r["html"] and "Ainda não verificado" in r["html"]
    (tmp_path / "u.json").write_text(json.dumps({"quando": "2026-11-24T13:40:00", "itens": {"CPU": [cartao], "TV": []}}),
                                     encoding="utf-8")
    assert "Nenhuma oferta passou nos seus filtros" in api.ofertas()["html"]


def test_app_abre_em_ofertas():
    html = html_cadastro()
    assert '<button data-aba="ofertas" aria-selected="true">' in html
    assert 'id="aba-ofertas"' in html


def test_app_abre_com_skeleton():
    html = html_cadastro()
    inicio = html.split('id="ofertas">')[1][:400]
    assert 'class="sk' in inicio
    assert "@keyframes pulso" in html and "linear-gradient" not in html


def test_cor_de_fundo_inicial():
    from precos.cadastro import cor_fundo
    assert cor_fundo("escuro") == "#161615" and cor_fundo("claro") == "#F6F5F2"


def _api_ia(tmp_path, localizar, runner=None):
    (tmp_path / "config.toml").write_text('[ia]\nprovedor = "codex"\n', encoding="utf-8")
    return Api(tmp_path / "config.toml", tmp_path / "s.toml", tmp_path / "e.db", instantaneo=tmp_path / "u.json",
               localizar=localizar, rodar_cmd=runner or (lambda cmd, entrada, timeout, cwd: (0, "codex-cli 9.9", "")))


def test_status_ia_lista_conexoes(tmp_path):
    api = _api_ia(tmp_path, lambda n: "C:/bin/codex.cmd" if n == "codex" else None)
    st = api.status_ia()
    assert st["ligados"] == ["codex"]
    por_id = {c["id"]: c for c in st["conexoes"]}
    assert por_id["codex"]["instalado"] and "9.9" in por_id["codex"]["versao"]
    assert not por_id["claude_code"]["instalado"]
    assert por_id["claude_code"]["instalar"] == "npm install -g @anthropic-ai/claude-code"
    assert por_id["api"]["tipo"] == "api"


def test_testar_ia_ok_e_limite(tmp_path):
    import json as _json
    resp = {"r": (0, _json.dumps({"is_error": False, "result": "OK"}), "")}
    api = _api_ia(tmp_path, lambda n: f"C:/bin/{n}.cmd", lambda cmd, entrada, timeout, cwd: resp["r"])
    r = api.testar_ia("claude_code")
    assert r["ok"] and r["tipo"] == "ok" and r["mensagem"].startswith("Conectado")
    resp["r"] = (1, _json.dumps({"is_error": True, "result": "Claude AI usage limit reached"}), "")
    r = api.testar_ia("claude_code")
    assert not r["ok"] and r["tipo"] == "limite"
    assert api.status_ia()["status"]["claude_code"]["tipo"] == "limite"


def test_testar_ia_nao_instalado(tmp_path):
    r = _api_ia(tmp_path, lambda n: None).testar_ia("claude_code")
    assert r == {"ok": False, "tipo": "nao_instalado", "mensagem": "Claude Code não está instalado neste PC."}


def test_ligar_varias_ias_em_ordem(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)  # config começa com provedor = "codex"
    api._gravar_status("claude_code", "ok", "Conectado.")
    api.ligar_ia("claude_code", True)
    cfg = carregar(tmp_path / "config.toml", tmp_path / "s.toml")
    assert cfg.ia.ligadas() == ["codex", "claude_code"]  # ligar um não desliga o outro
    api.priorizar_ia("claude_code")
    assert carregar(tmp_path / "config.toml", tmp_path / "s.toml").ia.ligadas() == ["claude_code", "codex"]
    assert api.status_ia()["ligados"] == ["claude_code", "codex"]
    api.ligar_ia("codex", False)
    api.ligar_ia("claude_code", False)
    cfg = carregar(tmp_path / "config.toml", tmp_path / "s.toml")
    assert cfg.ia.ligadas() == [] and cfg.ia.provedor == "nenhum"


def test_salvar_geral_sem_provedor_nao_mexe_na_ia(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    api.salvar_geral({"ntfy_topico": "precos-x"})
    assert carregar(tmp_path / "config.toml", tmp_path / "s.toml").ia.provedor == "codex"


def test_faixa_de_erro_da_ia_nas_ofertas(tmp_path):
    import json as _json
    from precos.estado import Estado
    api = _api_ia(tmp_path, lambda n: None)
    Estado(tmp_path / "e.db").cache_gravar("ia_status:codex", _json.dumps(
        {"tipo": "limite", "mensagem": "Codex: o limite de uso do seu plano acabou.", "provedor": "codex"}))
    html = api.ofertas()["html"]
    assert 'class="faixa limite"' in html and "limite de uso do seu plano" in html and 'data-ir="config"' in html
    assert "sigo só com as regras" in html  # nenhuma reserva ligada


def test_faixa_mostra_reserva_em_uso(tmp_path):
    import json as _json
    from precos.estado import Estado
    api = _api_ia(tmp_path, lambda n: None)
    api._gravar_status("claude_code", "ok", "Conectado.")
    api.ligar_ia("claude_code", True)  # codex (1º) e claude_code (2º)
    Estado(tmp_path / "e.db").cache_gravar("ia_status:codex", _json.dumps(
        {"tipo": "limite", "mensagem": "Codex: o limite de uso do seu plano acabou.", "provedor": "codex"}))
    html = api.ofertas()["html"]
    assert "Usando Claude Code enquanto isso" in html


def test_html_conexoes_ia():
    html = html_cadastro()
    assert 'id="conexoes-ia"' in html and 'id="verificar-ia"' in html


def test_modelos_na_tela(tmp_path):
    api = _api_ia(tmp_path, lambda n: f"C:/bin/{n}.cmd")
    cc = next(c for c in api.status_ia()["conexoes"] if c["id"] == "claude_code")
    valores = [o["valor"] for o in cc["opcoes"]]
    assert valores[:4] == ["", "haiku", "sonnet", "opus"]
    assert all(o["efeito"] for o in cc["opcoes"])
    assert cc["modelos"] == {"economica": "haiku", "completa": ""}  # padrões atuais
    api.salvar_modelo("claude_code", "completa", "opus")
    cc = next(c for c in api.status_ia()["conexoes"] if c["id"] == "claude_code")
    assert cc["modelos"]["completa"] == "opus"
    assert carregar(tmp_path / "config.toml", tmp_path / "s.toml").ia.modelos["claude_code"]["completa"] == "opus"
    api.salvar_modelo("claude_code", "completa", "")
    assert carregar(tmp_path / "config.toml", tmp_path / "s.toml").ia.modelos.get("claude_code", {}).get("completa") is None


def test_modelos_api_por_provedor(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    conx = next(c for c in api.status_ia()["conexoes"] if c["id"] == "api")
    assert {o["valor"] for o in conx["opcoes_claude"]} >= {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"}
    assert any(o["valor"] == "outro" for o in conx["opcoes_openai"])


class Terminal:
    def __init__(self):
        self.abertos = []

    def __call__(self, cmd):
        self.abertos.append(cmd)


def _runner_login(logado, resposta_ok=True):
    import json as _json

    def r(cmd, entrada, timeout, cwd):
        if cmd[1:3] == ["auth", "status"]:
            return (0 if logado["claude"] else 1), _json.dumps(
                {"loggedIn": logado["claude"], "subscriptionType": "team", "orgName": "Empresa Exemplo",
                 "email": "a@b.com"}), ""
        if cmd[1:3] == ["login", "status"]:
            return (0, "Logged in using ChatGPT", "") if logado["codex"] else (1, "", "Not logged in")
        if "auth" in cmd and "logout" in cmd:
            logado["claude"] = False
            return 0, "", ""
        if cmd[1:] == ["logout"]:
            logado["codex"] = False
            return 0, "", ""
        if "-p" in cmd:
            return 0, _json.dumps({"is_error": False, "result": "OK"}), ""
        if "exec" in cmd:
            from pathlib import Path as _P
            _P(cmd[cmd.index("-o") + 1]).write_text("OK", encoding="utf-8")
            return 0, "", ""
        return 0, "v1.0", ""
    return r


def test_conectar_sem_login_abre_navegador(tmp_path):
    logado = {"claude": False, "codex": False}
    api = _api_ia(tmp_path, lambda n: f"C:/bin/{n}.cmd", _runner_login(logado))
    term = Terminal()
    api._abrir_terminal = term
    r = api.conectar_ia("codex")
    assert r["tipo"] == "aguardando_login" and "navegador" in r["mensagem"]
    assert term.abertos == [["C:/bin/codex.cmd", "login"]]
    assert api.estado_login("codex")["logado"] is False
    logado["codex"] = True  # pessoa terminou o login no navegador
    assert api.estado_login("codex")["logado"] is True
    r = api.conectar_ia("codex")
    assert r["ok"] and r["tipo"] == "ok" and "ChatGPT" in r["mensagem"]
    assert api.status_ia()["ligados"] == ["codex"]  # conectar liga a chave


def test_conectar_claude_mostra_plano(tmp_path):
    logado = {"claude": True, "codex": True}
    api = _api_ia(tmp_path, lambda n: f"C:/bin/{n}.cmd", _runner_login(logado))
    r = api.conectar_ia("claude_code")
    assert r["ok"] and "Plano Team" in r["mensagem"] and "Empresa Exemplo" in r["mensagem"]


def test_desconectar(tmp_path):
    logado = {"claude": True, "codex": True}
    api = _api_ia(tmp_path, lambda n: f"C:/bin/{n}.cmd", _runner_login(logado))
    api.conectar_ia("codex")
    st = api.desconectar_ia("codex")
    assert logado["codex"] is False and st["ligados"] == []


def test_para_toml_tabela_dentro_de_tabela():
    dados = {"ia": {"provedor": "codex", "modelos": {"claude_code": {"completa": "opus"}, "codex": {"economica": "x"}}},
             "itens": [{"nome": "A", "buscas": ["a"]}]}
    assert tomllib.loads(para_toml(dados)) == dados


def test_nao_liga_ia_sem_conectar(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    r = api.ligar_ia("claude_code", True)
    assert r["ligados"] == ["codex"] and "Conecte" in r["erro"]
    api._gravar_status("claude_code", "login", "sem login")
    assert api.ligar_ia("claude_code", True)["ligados"] == ["codex"]


def test_chave_desabilitada_sem_conexao_no_js():
    assert "Conecte primeiro" in html_cadastro()


def test_agendamento_mostrado(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    api._ler_tarefa = lambda: {"existe": True, "estado": "Ready", "intervalo": "PT30M", "proxima": "2026-11-24T14:18:00"}
    assert api.agendamento() == {"ativo": True, "intervalo_min": 30, "proxima": "14:18",
                                 "texto": "Próxima verificação automática às 14:18 (a cada 30 min)."}
    api._ler_tarefa = lambda: {"existe": True, "estado": "Ready", "intervalo": "PT3H", "proxima": "2026-11-24T17:00:00"}
    assert api.agendamento()["intervalo_min"] == 180 and "a cada 3 h" in api.agendamento()["texto"]
    api._ler_tarefa = lambda: {"existe": False}
    assert api.agendamento()["ativo"] is False and "desligada" in api.agendamento()["texto"]


def test_mudar_intervalo(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    chamadas = []
    api._rodar_script = lambda nome, *args: chamadas.append((nome, args))
    api._ler_tarefa = lambda: {"existe": False}
    api.mudar_intervalo(60)
    api.mudar_intervalo(0)
    assert chamadas == [("instalar_tarefa.ps1", ("-Minutos", "60")), ("desinstalar_tarefa.ps1", ())]


def test_html_intervalo():
    assert 'data-grupo="intervalo"' in html_cadastro()


def test_intervalo_personalizado_ate_1_minuto(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    chamadas = []
    api._rodar_script = lambda nome, *args: chamadas.append((nome, args))
    api._ler_tarefa = lambda: {"existe": False}
    api.mudar_intervalo(1)
    api.mudar_intervalo(7)
    assert chamadas == [("instalar_tarefa.ps1", ("-Minutos", "1")), ("instalar_tarefa.ps1", ("-Minutos", "7"))]


def test_html_intervalos():
    html = html_cadastro()
    for v in ('data-v="5"', 'data-v="10"', 'data-v="personalizado"', 'id="intervalo-min"'):
        assert v in html
    assert "bloquear" in html  # aviso sobre intervalos curtos


def test_cep_configuravel(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    assert api.salvar_geral({"cep": "01310100"})["ok"]
    assert carregar(tmp_path / "config.toml", tmp_path / "s.toml").cep == "01310-100"
    assert api.dados()["geral"]["cep"] == "01310-100"
    assert api.salvar_geral({"cep": "123"}) == {"ok": False, "erro": "CEP inválido: use 8 números, ex.: 01310-100."}
    api.salvar_geral({"cep": ""})
    assert carregar(tmp_path / "config.toml", tmp_path / "s.toml").cep is None
    assert 'id="g-cep"' in html_cadastro()


@pytest.mark.parametrize("digitado,topico", [
    ("ntfy.sh/promo-exemplo-123", "promo-exemplo-123"),
    ("https://ntfy.sh/promo-exemplo-123", "promo-exemplo-123"),
    ("  promo-exemplo-123  ", "promo-exemplo-123"),
    ("promo exemplo", None),
])
def test_normaliza_topico(digitado, topico):
    from precos.cadastro import normalizar_topico
    assert normalizar_topico(digitado) == topico


def test_enviar_teste_usa_o_campo_e_salva(tmp_path):
    api = _api_ia(tmp_path, lambda n: None)
    enviados = []
    api._enviar_ntfy = lambda cfg, titulo, corpo, link: (enviados.append(cfg.ntfy_topico), True)[1]
    r = api.testar_aviso("ntfy.sh/promo-exemplo-123")
    assert r["ok"] and enviados == ["promo-exemplo-123"]
    assert carregar(tmp_path / "config.toml", tmp_path / "s.toml").ntfy_topico == "promo-exemplo-123"
    api._enviar_ntfy = lambda *a: False
    assert api.testar_aviso("promo-exemplo-123")["ok"] is False
    assert api.testar_aviso("canal com espaço")["ok"] is False


def test_dicas_de_busca_no_cadastro():
    html = html_cadastro()
    assert 'class="dicas"' in html and "smart tv 32 polegadas" in html and "Preço máximo" in html


def test_ntfy_explicado_passo_a_passo():
    html = html_cadastro()
    assert 'class="prefixo">ntfy.sh/</span>' in html
    assert 'id="gerar-canal"' in html and 'id="copiar-canal"' in html
    assert html.count('class="passo"') == 4
    assert 'id="canal-aviso"' in html


def test_primeiro_uso_guia_o_cadastro(tmp_path):
    (tmp_path / "config.toml").write_text("", encoding="utf-8")
    api = Api(tmp_path / "config.toml", tmp_path / "s.toml", tmp_path / "e.db", instantaneo=tmp_path / "u.json")
    html = api.ofertas()["html"]
    assert "Bem-vindo" in html and 'data-novo-produto' in html
    assert "ntfy" in html  # lembra de configurar o aviso no celular
