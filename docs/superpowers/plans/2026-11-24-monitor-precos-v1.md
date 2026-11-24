# Monitor de preços v1 — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python tool that, every 3 hours (and at logon), reads offers and price history from Zoom (fallback Buscapé) for configured items. It applies the card-price, interest-free, seller and real-promotion rules, and alerts with a topmost window on the PC plus an ntfy push to the phone.

**Architecture:**
- Zoom and Buscapé pages embed all their data as Next.js JSON in `<script id="__NEXT_DATA__">`.
- Parsing works on that JSON only, never HTML. Fetching is kept separate from parsing so parsing is tested with saved fixtures.
- A small SQLite file stores what was already alerted and the lowest price seen.
- It is an open-source repo: everything personal lives in `config.toml` / `segredos.toml`, which are gitignored. Example files are committed.

**Tech Stack:** Python 3.13 (stdlib `tomllib`, `sqlite3`, `tkinter`, `statistics`), `requests`, `pytest`. Windows Task Scheduler for scheduling.

**Spec:** `C:\Users\<usuario>\Desktop\monitor-precos\docs\2026-11-24-monitor-precos-design.md`

## Global Constraints
- Project root: `C:\Users\<usuario>\Desktop\monitor-precos`. Package `precos/`, tests `tests/`, venv `.venv` created from the system Python 3.13.
- Python on this machine: the `python` on PATH is the WindowsApps one. Bash's Python prints nothing, so run Python commands through PowerShell with `.venv\Scripts\python.exe`.
- User-facing text (alerts, README, config comments): Brazilian Portuguese.
- Compare and limit by the **card installment total** (`totalParceledValue`), never the PIX/cash price.
- Interest-free rule: Zoom's `hasInterest` is **not** an interest flag.
  - Example: KaBuM 10x is sem juros on kabum.com.br (`hasFee:false`), but Zoom says `hasInterest:true` for the same offer. On Zoom it only means "parcelado > à vista".
  - Zoom lists the store's standard installment plan, which BR stores show as their maximum interest-free plan. So `sem_juros = parcelas is not None and parcelas >= 1 and total_parcelado is not None`, ignoring `hasInterest`.
  - Missing parcelas or total → not eligible.
  - When parcelas > 12, the alert says "em Nx (confira sem juros na loja)".
- Offers with `numParcels >= 10` sort first. Within each group, sort by installment total ascending.
- Seller rule: `sellerIsMarketplace == False` only. (Amazon/Magalu own-stock and ML official/Full show up on Zoom as non-marketplace merchants.)
- Verdict uses Zoom's daily price history. That history is the cash price, so the cash `price` is compared against it. The window is up to 90 days of whatever is available.
  - `real`: price ≤ 0.90 × median **and** price ≤ 1.03 × min
  - `maquiada`: price ≥ 1.05 × median. (This simplifies the spec's "subiu antes do desconto"; it catches the Kabum 5700X case: R$ 1.299,99 vs median ≈ R$ 1.100.)
  - `sem_historico`: fewer than 14 history days
  - `normal`: everything else
- Alerts:
  - At most 3 offers per item.
  - `real` and `sem_historico` (labelled "sem histórico, não confirmado") alert.
  - `normal` alerts only for items with `modo = "mais_barato"` and only when the price is below the lowest installment total ever stored for that item.
  - `maquiada` never alerts.
- Dedupe: an offer (`item`, `offer_id`) is re-alerted only if its installment total is ≤ 0.98 × the last alerted total.
- Personal values never go in code or committed files:
  - CEP `00000-000` and the ntfy topic go in `segredos.toml`.
  - The TV limit of R$ 1.500 goes in `config.toml`.
- Low impact on the PC:
  - Process priority BELOW_NORMAL (`ctypes.windll.kernel32.SetPriorityClass(handle, 0x4000)` on Windows).
  - 3–6 s random sleep between HTTP requests.
  - At most 8 product pages per category item per run.
- Shipping in v1: Zoom does not expose shipping. Alerts say "frete: confira na loja", except when the merchant name contains "Mercado Livre", which reads "frete grátis (Meli+)".

## Review Focus
1. Zoom returns 403, a captcha page, or HTML without `__NEXT_DATA__`. Expected: retry the same path on `www.buscape.com.br`. If both fail, log it, skip that item and continue with the others, with no crash and no alert. (Task 2 test `test_fetch_fallback_buscape`, Task 6 test `test_item_com_erro_nao_derruba`)
2. An offer with `numParcels` or `totalParceledValue` missing/0. Expected: excluded, never crashes. (Task 3 test `test_juros_ausente_exclui`)
3. ntfy unreachable, or no topic configured. Expected: the window still shows, the error is logged, and the run is still recorded as alerted. (Task 5 test `test_ntfy_falha_nao_derruba`)
4. The same offer at the same price across many runs, for example with the PC left on all week. Expected: exactly one alert. (Task 4 test `test_dedupe_mesmo_preco`)
5. A category search where no hit passes the filters. Expected: nothing alerts, the item is logged as "nenhuma oferta elegível", and there is no empty window. (Task 6 test `test_sem_ofertas_sem_janela`)

---

### Task 1: Scaffold, config loading

**Files:**
- Create: `requirements.txt` (`requests`, `pytest`)
- Create: `.gitignore` (`.venv/`, `config.toml`, `segredos.toml`, `dados/`, `__pycache__/`, `*.log`)
- Create: `config.exemplo.toml`, `segredos.exemplo.toml`, `LICENSE` (MIT)
- Create: `precos/__init__.py`, `precos/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass Item(nome: str, url: str, tipo: Literal["produto","busca"], modo: Literal["promocao","mais_barato"], limite_total: float | None, polegadas_min: float | None, polegadas_max: float | None, hz_min: int | None, marcas: list[str], exigir: list[str], excluir: list[str])`
  - `@dataclass Config(itens: list[Item], ntfy_topico: str | None, ntfy_servidor: str, cep: str | None, callmebot_fone: str | None, callmebot_apikey: str | None)`
  - `carregar(config_path: Path, segredos_path: Path) -> Config`
- Defaults:
  - `ntfy_servidor="https://ntfy.sh"`
  - An empty list for the list fields.
  - A missing `segredos.toml` gives all secrets as None.
- `config.exemplo.toml` carries the three real items:
  - **Ryzen 7 5700X:** `tipo="produto"`, url `https://www.zoom.com.br/processador/processador-amd-ryzen-7-5700x-3-4ghz-4-6ghz-turbo-am4`, `modo="mais_barato"`.
  - **Monitor 144Hz:** `tipo="busca"`, url `https://www.zoom.com.br/search?q=monitor%20144hz`, `modo="mais_barato"`, polegadas 23.8–27, `hz_min=144`.
    - marcas: LG, Samsung, AOC, Dell, ASUS, Acer, Gigabyte, MSI, Philips, Pichau
    - excluir: `["TN","Portátil","Portatil"]`
  - **TV 32-40:** `tipo="busca"`, url `https://www.zoom.com.br/search?q=smart%20tv%2032`, `modo="promocao"`, polegadas 32–40, `limite_total=1500`.
    - marcas: Samsung, LG, TCL, Philips, AOC
    - exigir: `["Smart"]`
  - Add a second TV search url, `smart tv 40`, as another item named "TV 32-40 (40pol)".

- [ ] **Step 1:** Create the venv: `& "C:\Users\<usuario>\AppData\Local\Microsoft\WindowsApps\python.exe" -m venv .venv`. Then run `.venv\Scripts\python.exe -m pip install -r requirements.txt`. Expected: pip succeeds.
- [ ] **Step 2:** `git init`. Write `tests/test_config.py`:
  - `test_carrega_exemplo`: loading `config.exemplo.toml` + `segredos.exemplo.toml` gives 4 items. The item `"Ryzen 7 5700X"` has `tipo == "produto"`. The TV item has `limite_total == 1500.0`.
  - `test_sem_segredos`: a nonexistent segredos path gives `cfg.ntfy_topico is None` and `cfg.ntfy_servidor == "https://ntfy.sh"`.
- [ ] **Step 3:** Run `.venv\Scripts\python.exe -m pytest tests/test_config.py -v`. Expected: FAIL (module missing).
- [ ] **Step 4:** Implement `precos/config.py` with `tomllib`.
- [ ] **Step 5:** Rerun. Expected: PASS.
- [ ] **Step 6:** Commit: `git add -A; git commit -m "feat: scaffold and config loading"`.

### Task 2: Zoom/Buscapé fetch and parse

**Files:**
- Create: `precos/zoom.py`
- Create: `tests/fixtures/zoom_produto_5700x.json`, `tests/fixtures/zoom_busca_monitor.json`. Each is only `props.initialReduxState` → keys `offers`, `priceHistory`, `hits`, extracted from the recon pages at `<pasta-temporaria>\zoom_prod.html` and `zoom_mon.html` with a throwaway script.
- Test: `tests/test_zoom.py`

**Interfaces:**
- Produces:
  - `@dataclass Oferta(offer_id: str, nome: str, loja: str, preco_vista: float, total_parcelado: float | None, parcelas: int | None, valor_parcela: float | None, sem_juros: bool, marketplace: bool, link: str)`
  - `@dataclass Produto(produto_id: str, nome: str, url: str, ofertas: list[Oferta], historico: list[tuple[date, float]])`
  - `@dataclass Hit(nome: str, url: str, tipo: str, preco_vista: float, total_parcelado: float | None, parcelas: int | None, sem_juros: bool, marketplace: bool)`
  - `extrair_estado(html: str) -> dict`: the `initialReduxState`. Raises `SemDados` if `__NEXT_DATA__` is absent.
  - `parse_produto(estado: dict, url: str) -> Produto`
  - `parse_busca(estado: dict) -> list[Hit]`
  - `baixar(url: str, sessao: requests.Session | None = None) -> str`: on a status ≠ 200 or `SemDados`, retries once with the host swapped `www.zoom.com.br` → `www.buscape.com.br`. If both fail, raises `SemDados`.
- Field mapping:
  - **`parse_produto`:** reads `estado["offers"]["offerList"]`.
    - `offer_id=id`, `loja=sellerName`, `preco_vista=price`, `total_parcelado=totalParceledValue`, `parcelas=numParcels`, `valor_parcela=parcelValue`
    - `sem_juros` per the Global Constraints rule (ignore `hasInterest`), `marketplace = bool(sellerIsMarketplace)`
    - `link = "https://www.zoom.com.br/lead?oid=" + id`
    - History comes from `estado["priceHistory"]["priceHistory"][produto_id]["days"]`, keeping the **minimum price per date**.
  - **`parse_busca`:** reads `estado["hits"]["hits"]`.
    - `installments.total_value` / `amount_months`
    - `sem_juros` per the Global Constraints rule, `marketplace = bool(marketplace)`
    - `url` is made absolute against `https://www.zoom.com.br`.
- Requests use a desktop Chrome User-Agent and a timeout of 20 s.

- [ ] **Step 1:** Build the two fixture JSONs from the recon HTML.
- [ ] **Step 2:** Write the tests:
  - `test_parse_produto_5700x`: ≥1 oferta. The KaBuM! oferta has `preco_vista == 1299.99`, `total_parcelado == 1529.4`, `parcelas == 10`, `sem_juros is True`, `marketplace is False`. The historico has ≥30 entries, and the entry for `date(2026,11,10)` has price `929.99`.
  - `test_parse_busca_monitor`: 12 hits. The first hit's name contains "GS25F14", `parcelas == 7`, `total_parcelado == 895.44`.
  - `test_extrair_sem_next_data`: `extrair_estado("<html></html>")` raises `SemDados`.
  - `test_fetch_fallback_buscape`: with a fake session whose `get` returns 403 for zoom and fixture-derived HTML for buscape, `baixar` returns the buscape HTML and the second call's URL host is `www.buscape.com.br`.
- [ ] **Step 3:** Run `.venv\Scripts\python.exe -m pytest tests/test_zoom.py -v`. Expected: FAIL.
- [ ] **Step 4:** Implement `precos/zoom.py`.
- [ ] **Step 5:** Rerun. Expected: PASS.
- [ ] **Step 6:** Commit `feat: zoom/buscape fetch and parse`.

### Task 3: Rules (filters, eligibility, verdict, ranking)

**Files:**
- Create: `precos/regras.py`
- Test: `tests/test_regras.py`

**Interfaces:**
- Consumes: `Item` (Task 1), `Oferta`, `Hit` (Task 2)
- Produces:
  - `passa_filtro_nome(nome: str, item: Item) -> tuple[bool, list[str]]`. Returns (passes, tags).
    - Size: parse `(\d{2}(?:[.,]\d)?)\s*(?:"|''|pol|polegadas|”)` or a bare `\b(2[3-9]|3\d|4\d)(?:[.,]\d)?\b` after the word Monitor/TV. It must fall within min/max when they are set. Unknown size → fails.
    - Hz: `(\d{2,3})\s*hz`, case-insensitive. It must be ≥ `hz_min`, and unknown → fails when `hz_min` is set.
    - Brand: `marcas`, case-insensitive word match. Empty list = any.
    - `exigir`: all words must be present. `excluir`: none may be present, matched as whole words, case-insensitive.
    - Panel: if the name contains IPS or VA, no tag. Otherwise tag `"painel não confirmado"` (only when `hz_min` is set, i.e. monitors).
  - `elegivel(o: Oferta, item: Item) -> bool`: `sem_juros and not marketplace and parcelas and total_parcelado`, plus `total_parcelado <= limite_total` when a limit is set.
  - `veredito(preco_vista: float, historico: list[tuple[date, float]], hoje: date) -> Literal["real","maquiada","normal","sem_historico"]`: per Global Constraints, over history entries within 90 days before `hoje`.
  - `ordenar(ofertas: list[Oferta]) -> list[Oferta]`: key `(parcelas < 10, total_parcelado)`.

- [ ] **Step 1:** Write the tests:
  - `test_filtro_monitor_ok`: `"Monitor LG 24\" IPS 144HZ 1MS 24U411B-B.AWZM"` with the monitor item gives `(True, [])`.
  - `test_filtro_monitor_portatil`: `"Monitor Portátil Full HD 144hz Gamer 1080p 16.1 Polegadas - Arzopa"` gives False.
  - `test_filtro_monitor_sem_painel`: `"Monitor Gamer Gigabyte GS24F14A 23.8 1080p FHD 144Hz Preto"` gives `(True, ["painel não confirmado"])`.
  - `test_filtro_marca_fora`: `"Monitor Duex Led 24 144Hz Hdmi Gamer Dx240Zg"` gives False.
  - `test_filtro_tv`: `'Smart TV 32" LG HD webOS 32LB650BPSA'` with the TV item gives True. `'Smart TV 50" Samsung 4K'` gives False.
  - `test_juros_ausente_exclui`: a hit dict without `installments`, parsed by `parse_busca`, gives `sem_juros is False` and is not eligible. An Oferta with `parcelas=None` → not eligible.
  - `test_limite_total`: with the TV item (limit 1500), `total_parcelado=1590` → not eligible, `1499` → eligible.
  - `test_veredito_maquiada_5700x`: using the fixture history from Task 2 with `hoje=date(2026,11,24)`, `veredito(1299.99, ...) == "maquiada"`.
  - `test_veredito_real`: history of 30 days at 1000 plus 1 day at 880, then `veredito(890, ...)` gives `"real"`.
  - `test_veredito_sem_historico`: 10 days → `"sem_historico"`.
  - `test_ordenar`: offers (8x, 600), (10x, 700), (10x, 650) are ordered 650, 700, 600.
- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_regras.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `precos/regras.py` (use `statistics.median`).
- [ ] **Step 4:** Rerun. Expected: PASS.
- [ ] **Step 5:** Commit `feat: price rules`.

### Task 4: State store (dedupe and lowest seen)

**Files:**
- Create: `precos/estado.py`
- Test: `tests/test_estado.py`

**Interfaces:**
- Produces: `class Estado(path: Path)` with:
  - `ja_avisado(item: str, offer_id: str, total: float) -> bool`. True if a previous alert exists with `total > last_total * 0.98`. Same price or a small drop → True.
  - `registrar_aviso(item: str, offer_id: str, total: float) -> None`
  - `menor_visto(item: str) -> float | None`
  - `registrar_preco(item: str, total: float) -> None`: keeps the minimum.
- Storage: SQLite at `dados/estado.db`. Tables are created on open.

- [ ] **Step 1:** Write the tests:
  - `test_dedupe_mesmo_preco`: register (i, o1, 700). Then `ja_avisado(i, o1, 700)` and `(i, o1, 690)` are True, and `(i, o1, 680)` is False.
  - `test_menor_visto`: register 800 then 750 then 900 → `menor_visto == 750`. An unknown item → None.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: state store`.

### Task 5: Alerts (message, ntfy, topmost window)

**Files:**
- Create: `precos/avisos.py`, `precos/janela.py`
- Test: `tests/test_avisos.py`

**Interfaces:**
- Consumes: `Oferta` (Task 2), `Config` (Task 1)
- Produces:
  - `@dataclass Achado(item: str, oferta: Oferta, veredito: str, tags: list[str])`
  - `formatar(achados: list[Achado]) -> tuple[str, str]`: returns (title, body). The body has one block per achado:
    `"{item}: {oferta.nome}\n{loja} — R$ {total} em {parcelas}x sem juros (PIX R$ {vista})\n{rotulo_veredito}{tags}\n{frete}\n{link}"`
    - Money is formatted pt-BR: `R$ 1.529,40`.
    - Labels: `real` → "✅ promoção real", `sem_historico` → "⚠️ sem histórico, não confirmado", `normal` → "menor preço já visto".
    - Frete text per Global Constraints.
  - `enviar_ntfy(cfg: Config, titulo: str, corpo: str, link: str | None, sessao=None) -> bool`: POSTs JSON `{"topic","title","message","click","tags":["moneybag"]}` to `cfg.ntfy_servidor`. Returns False when no topic is set or on any exception (logged).
  - `enviar_whatsapp(cfg, corpo, sessao=None) -> bool`: CallMeBot GET `https://api.callmebot.com/whatsapp.php?phone=&text=&apikey=`. No-op False when it isn't configured.
  - `abrir_janela(titulo: str, corpo: str, links: list[str]) -> None`: launches `pythonw -m precos.janela <json-file>` detached (`subprocess.Popen` with `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`) so the run does not block.
  - `precos/janela.py`:
    - A tkinter window: `attributes("-topmost", True)`, title, a read-only scrollable text body, one clickable button per link (`webbrowser.open`), and a "Fechar" button.
    - It does not auto-close.
    - The JSON temp file is deleted after it is read.

- [ ] **Step 1:** Write the tests:
  - `test_formatar`: one Achado (KaBuM!, total 1529.4, 10x, vista 1299.99, veredito `sem_historico`). The body contains `"R$ 1.529,40 em 10x sem juros"`, `"PIX R$ 1.299,99"` and `"sem histórico, não confirmado"`.
  - `test_ntfy_payload`: with a fake session capturing `post`, the JSON has `topic == "t"`, a `click` link, and `message` equal to the body.
  - `test_ntfy_falha_nao_derruba`: a fake session raising `ConnectionError` → returns False, no exception.
  - `test_ntfy_sem_topico`: `ntfy_topico=None` → False, and the session is not called.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement both files.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Manually check the window with `.venv\Scripts\python.exe -c "from precos.avisos import abrir_janela; abrir_janela('Teste','Corpo de teste',['https://www.zoom.com.br'])"`. Expected: the window stays on top until "Fechar" is pressed.
- [ ] **Step 6:** Commit `feat: alerts (ntfy, window, whatsapp)`.

### Task 6: Run orchestration, entry point, logging

**Files:**
- Create: `precos/__main__.py`, `precos/rodada.py`
- Test: `tests/test_rodada.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `rodar(cfg: Config, estado: Estado, baixar=zoom.baixar, avisar=None, hoje: date | None = None, dormir=time.sleep) -> list[Achado]`.
  - For each item, in a `try`. On an exception, log `"{item}: erro {e}"` and continue.
  - **`produto`:** download, then `parse_produto`, filter `elegivel`, `ordenar`, take the verdict on each oferta's `preco_vista` against the product history.
  - **`busca`:** download, then `parse_busca`. Keep hits whose name passes `passa_filtro_nome`, sorted by `total_parcelado`, first 8.
    - For hits whose url is a product page (not `/lead?`), download that product page (sleep 3–6 s between pages) and process it as `produto` (tags carried over).
    - For `/lead?` hits, build an Oferta from the Hit with `veredito="sem_historico"`.
  - Apply the alert selection from Global Constraints (`modo`, `menor_visto`, dedupe), top 3 per item. Call `estado.registrar_preco` with the item's best eligible total, after comparing against `menor_visto`.
  - If any achados exist, call `avisar(achados)`. The default sends `formatar`, then `abrir_janela` + `enviar_ntfy` + `enviar_whatsapp`. Then `registrar_aviso` for each one.
- `__main__.py`:
  - Set BELOW_NORMAL priority.
  - Log to `dados/precos.log` (rotating, 1 MB).
  - Load `config.toml` + `segredos.toml` from the project root.
  - Print `"OK: N achados"`.
  - `--teste-aviso` sends a fake achado to all channels.

- [ ] **Step 1:** Write the tests, using fake `baixar` returning fixture HTML and a fake `avisar` capturing achados:
  - `test_produto_maquiado_nao_avisa`: the 5700X item in `modo="promocao"` gives 0 achados.
  - `test_sem_historico_avisa_uma_vez`: the 5700X fixture with its `priceHistory` days emptied gives 1 achado with veredito `sem_historico`. A second `rodar` with the same Estado gives 0 (dedupe).
  - `test_item_com_erro_nao_derruba`: the first item's `baixar` raises `SemDados`, the second item still yields its achados.
  - `test_sem_ofertas_sem_janela`: no eligible offers → `avisar` is never called.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite `.venv\Scripts\python.exe -m pytest -v`. Expected: all PASS.
- [ ] **Step 5:** Live smoke test: copy the example configs to `config.toml` / `segredos.toml` (topic: generate `precos-` + 10 random lowercase/digit chars). Run `.venv\Scripts\python.exe -m precos`. Expected: `OK: N achados` and no traceback. Check `dados/precos.log`. If N>0, a window appears.
- [ ] **Step 6:** Commit `feat: run orchestration`.

### Task 7: Scheduling, README

**Files:**
- Create: `instalar_tarefa.ps1`, `desinstalar_tarefa.ps1`, `README.md`

**Interfaces:**
- `instalar_tarefa.ps1` registers the task "Monitor de precos":
  - Action: `.venv\Scripts\pythonw.exe -m precos`, with WorkingDirectory set to the project root.
  - Triggers: `-AtLogOn` for the current user, plus `-Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 3)`.
  - Settings: `-Priority 7 -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)`.
  - Principal: the interactive current user, LogonType Interactive, so the window can show.
- The README is in pt-BR and covers:
  - what it does
  - install (venv, pip)
  - configure (copy the example files, the item fields, how to pick a Zoom URL)
  - ntfy on iPhone/Android (install the app, subscribe to the topic, allow notifications)
  - optional WhatsApp via CallMeBot
  - schedule
  - a note that it is for personal use with a low request rate
  - known v1 limits: shipping not checked except ML, history comes from Zoom (~40 days), the verdict compares cash prices

- [ ] **Step 1:** Write the scripts and the README.
- [ ] **Step 2:** Run `powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1`, then `Get-ScheduledTask "Monitor de precos" | Select TaskName,State`. Expected: Ready. Then `Start-ScheduledTask "Monitor de precos"`, wait, and check `dados/precos.log` for a new "OK" line.
- [ ] **Step 3:** Run `.venv\Scripts\python.exe -m precos --teste-aviso`. Expected: the window shows, and the ntfy message arrives on the topic (verify with `curl.exe -s "https://ntfy.sh/<topic>/json?poll=1"`).
- [ ] **Step 4:** Commit `feat: scheduling and README`.
