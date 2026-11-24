# Monitor de preços

Acompanha o preço do que você quer comprar em várias lojas, confere no histórico se a promoção é **de verdade** e te avisa **na tela do PC e no celular**.

Você escreve o que buscaria numa loja (ex.: `smart tv 32`, `monitor 144hz`, `ryzen 7 5700x`), sem colar link. O monitor procura no [Zoom](https://www.zoom.com.br) (com o Buscapé de reserva), compara as lojas e avisa só quando vale a pena.

## O que ele faz

- **Afunila a busca sozinho.** A partir do que você escreveu, descobre a categoria do produto no Zoom e usa as páginas com filtro do próprio site (ex.: TVs de 32", monitores de 144 Hz), do mais barato ao mais caro. É ali que estão os produtos de catálogo, que têm histórico de preço.
- **Separa promoção de verdade de desconto maquiado.**
  - **Promoção real:** pelo menos 10% abaixo da mediana dos últimos 90 dias e perto do menor preço do período.
  - **Desconto maquiado:** 5% ou mais acima do normal. É o truque de subir o preço antes do "desconto", e **nunca** gera aviso.
- **Compara pelo preço no cartão parcelado**, não pelo PIX, e só com parcelamento sem juros. O limite de preço vale para o total parcelado.
- **Só a própria loja:** anúncios de vendedores de marketplace ficam de fora.
- **Liga anúncios soltos ao produto certo** pelo código do modelo, aceitando só código idêntico (24U411B não é 24U511SB). Para modelos que não estão no catálogo, monta um **histórico próprio** a cada verificação.
- **Não repete aviso:** a mesma oferta só é avisada de novo se cair pelo menos 2%.

## Como ele avisa

- **Janela no PC:** fica por cima até você fechar. Mostra a foto, o preço, o veredito e um gráfico de 90 dias (verde abaixo do normal, laranja acima, vermelho muito acima).
- **Notificação no celular** pelo app gratuito [ntfy](https://ntfy.sh) (iPhone e Android), sem cadastro.
- **WhatsApp** (opcional), via [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/).

## Instalação (Windows 10/11)

Precisa do Python 3.11 ou mais novo. A janela usa o Edge WebView2, que já vem no Windows 10/11.

```powershell
git clone <endereço deste repositório> monitor-precos
cd monitor-precos
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File criar_atalho.ps1    # cria o atalho "Monitor de precos" na área de trabalho
```

## Primeiro uso

Abra pelo atalho ou com `.venv\Scripts\python.exe -m precos --cadastro`. O app tem três abas:

1. **Ofertas:** a melhor oferta atual de cada produto. Na primeira vez, mostra uma tela de boas-vindas.
2. **Produtos:**
   - clique em **Adicionar produto** e escreva o que buscaria numa loja;
   - a seção **"Como escrever para ter um bom resultado"** tem exemplos;
   - tamanho, Hz, marcas e preço máximo ficam nos filtros.
3. **Configurações:**
   - **Avisos no celular:** passo a passo do ntfy, com botão para gerar um nome de canal e enviar um teste.
   - **Verificação automática:** 5 min, 10 min, 30 min, 1 hora, personalizado (1 a 1440 min) ou desligada. Usa o Agendador de Tarefas do Windows e roda em prioridade baixa, mesmo com o app fechado.
   - **Pesquisa com IA** (opcional, veja abaixo).

O botão **Verificar agora** faz uma busca na hora. Leva de 1 a 2 minutos, porque o monitor espera alguns segundos entre uma página e outra.

## Pesquisa com IA (opcional)

A IA descarta produtos ruins e, no nível completo, lê avaliações na web e dá nota ou veto. Você escolhe por produto:

| Nível | O que faz |
|---|---|
| Desligada (padrão) | Só as regras do cadastro. Custo zero. |
| Econômica | Descarta produtos ruins. Só os produtos **novos** vão para a IA; o resto fica em cache. |
| Completa | Também pesquisa avaliações e defeitos conhecidos de cada finalista e dá nota de 0 a 10. Produto com defeito crônico é vetado. |

Formas de conectar, em Configurações → Pesquisa com IA:
- **Claude Code** ou **Codex:** usam **o plano que você já paga** (Claude ou ChatGPT), pelo programa instalado no PC. O botão **Conectar** abre o login do próprio programa no navegador. O monitor nunca vê a sua senha.
- **Chave de API** (Anthropic ou OpenAI): pago por uso, com teto de gasto mensal.

Você pode ligar mais de uma, em ordem de prioridade. Se o limite do plano acabar na primeira, o monitor passa para a próxima e te avisa. Em cada conexão dá para escolher o modelo, com a consequência explicada: modelos menores são mais rápidos e gastam menos, mas erram mais.

## Seus dados

Tudo fica no seu PC: `config.toml` (produtos e preferências), `segredos.toml` (canal do ntfy, CEP, chaves) e a pasta `dados/` (memória de avisos, histórico próprio, log). Esses arquivos estão no `.gitignore`. Quem souber o nome do seu canal do ntfy consegue ler os avisos, então use um nome difícil de adivinhar (o app gera um).

## Linha de comando

```powershell
.venv\Scripts\python.exe -m precos                 # uma verificação agora
.venv\Scripts\python.exe -m precos --teste-aviso   # aviso de teste (janela + celular)
.venv\Scripts\python.exe -m precos --cadastro      # abre o app
powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1 -Minutos 30   # agendamento automático
powershell -ExecutionPolicy Bypass -File desinstalar_tarefa.ps1            # remove o agendamento
```

Quem preferir pode editar o `config.toml` à mão: o `config.exemplo.toml` explica todos os campos.

## Limitações

- **Frete:** ainda não é calculado (o CEP fica guardado para isso). O aviso diz "Frete: confira na loja", exceto no Mercado Livre ("Frete grátis (Meli+)").
- **Histórico:** vem do Zoom, que costuma guardar uns 40 dias. Modelos fora do catálogo dependem do histórico próprio, que precisa de 14 dias de verificações para dar veredito.
- **Sem juros:** o monitor confia no parcelamento que a loja mostra. Acima de 12x, o aviso pede para conferir na loja.
- **Só Windows:** a janela e o agendamento usam recursos do Windows.

## Uso responsável

Projeto para **uso pessoal**. Ele lê páginas públicas com intervalo entre os pedidos. Dá para verificar até a cada 1 minuto, mas abaixo de 15 minutos o Zoom pode bloquear temporariamente e as verificações emendam umas nas outras. Não use para coletar dados em massa. Os termos de uso dos sites continuam valendo.

## Desenvolvimento

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Os testes usam dados reais do Zoom salvos em `tests/fixtures` e não acessam a internet.

## Licença

MIT
