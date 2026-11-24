# Monitor de preços

Acompanha preços de produtos no [Zoom](https://www.zoom.com.br) (com o Buscapé de reserva), confere no histórico se a promoção é de verdade e te avisa:

- com uma **janela na tela do PC**, que fica por cima de tudo até você fechar;
- com uma **notificação no celular** pelo app [ntfy](https://ntfy.sh) (iPhone e Android, grátis, sem cadastro);
- opcionalmente pelo **WhatsApp**, via [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/).

## O que ele considera

- **Preço no cartão parcelado**, nunca o do PIX. O limite de preço vale para o total parcelado.
- **Parcelado sem juros**, com preferência para 10x.
- **Só a própria loja**: anúncios de vendedores de marketplace ficam de fora.
- **Promoção real**: o preço está pelo menos 10% abaixo da mediana dos últimos 90 dias e até 3% acima do menor preço do período.
- **Maquiada**: o preço está 5% ou mais acima do normal. Esse caso **nunca** gera aviso, porque é o truque de subir o preço antes do "desconto".
- **Sem histórico**: a oferta é avisada, mas marcada como "não confirmado".
- **Sem repetição**: a mesma oferta só é avisada de novo se cair pelo menos 2%.

## Instalação (Windows)

Precisa do Python 3.11 ou mais novo.

```powershell
git clone <este repositório> monitor-precos
cd monitor-precos
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.exemplo.toml config.toml
copy segredos.exemplo.toml segredos.toml
```

## Cadastro de produtos (tela)

O jeito mais fácil é pela tela de cadastro:

```powershell
.venv\Scripts\python.exe -m precos --cadastro
powershell -ExecutionPolicy Bypass -File criar_atalho.ps1   # cria um atalho na área de trabalho
```

Nela você adiciona, edita e exclui produtos. Não precisa de link: é só escrever o que buscaria numa loja
(ex.: `ryzen 7 5700x`). Também configura o canal do ntfy, a IA e o tema, e pode mandar verificar na hora.
Tudo é salvo no `config.toml` e no `segredos.toml`. Na primeira vez que a tela salva, ela guarda o arquivo
original em `config.toml.bak`.

## Configuração

### `config.toml`: o que você quer comprar
Cada bloco `[[itens]]` é um produto. Os campos estão explicados no próprio arquivo.

- **`buscas = ["termo", ...]`:** o jeito mais simples: termos de busca, como numa loja. Dispensa `url` e `tipo`.
- **`tipo = "produto"`:** abra o produto no zoom.com.br e cole o endereço da página em `url`.
- **`tipo = "busca"`:** faça a busca no zoom.com.br e cole o endereço da busca. Para cobrir mais anúncios, coloque buscas extras em `urls`. Depois use os filtros (`marcas`, `polegadas_min`, `hz_min`, `exigir`, `excluir`) para tirar o que não presta.
- **`modo = "mais_barato"`:** avisa também quando aparece o menor preço já visto.
- **`modo = "promocao"`:** só avisa promoção real ou oferta sem histórico.
- **`ordem = "menor_preco"`** (padrão): no aviso, o mais barato vem primeiro.
- **`ordem = "parcelas"`:** ofertas em 10x ou mais vêm primeiro e, entre elas, a mais barata.

### Pesquisa com IA (opcional)
Dá para usar **Claude** (Anthropic) ou **OpenAI**. Você escolhe quanto quer gastar.

| `pesquisa` | O que faz | Custo típico |
|---|---|---|
| `"nenhuma"` (padrão) | Só as regras do item. | zero |
| `"economica"` | A partir da `descricao`, a IA monta as buscas uma vez só e descarta produtos ruins. Ela só avalia os produtos **novos**. | centavos por mês |
| `"completa"` | Tudo do econômico, mais uma pesquisa na web sobre cada finalista novo. O aviso traz uma nota de 0 a 10, e produto com defeito crônico é vetado. | alguns dólares por mês |

Como ligar:
1. Em `config.toml`, adicione a seção `[ia]` com `provedor` e `limite_gasto_mensal`.
2. Coloque a chave em `segredos.toml`.
3. Em cada item, defina `pesquisa` e `descricao`.

Detalhes:
- Tudo fica em cache. Um produto já avaliado não é cobrado de novo.
- Ao atingir o limite do mês, a ferramenta volta às regras fixas e te avisa uma vez.
- Se a IA falhar, a verificação continua só com as regras.

### `segredos.toml`: seus dados (não vai para o git)
- **`ntfy_topico`:** o nome do seu canal de avisos. Escolha algo difícil de adivinhar, como `precos-k7x9q2m4ab`, porque quem souber o nome consegue ler os avisos.
- **`callmebot_fone`** e **`callmebot_apikey`:** opcionais, para receber pelo WhatsApp.
- **`anthropic_api_key`** ou **`openai_api_key`:** opcionais, para a pesquisa com IA.

### Avisos no celular (ntfy)
1. Instale o app **ntfy** (App Store ou Google Play).
2. Toque em **+** e digite o mesmo nome que está em `ntfy_topico`.
3. Quando o app pedir permissão de notificação, aceite.
4. Para testar, rode `.venv\Scripts\python.exe -m precos --teste-aviso`. A janela deve abrir no PC e a notificação deve chegar no celular.

## Rodar

```powershell
.venv\Scripts\python.exe -m precos                # uma verificação agora
powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1    # agenda: ao entrar no Windows e a cada 3h
powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1 -Minutos 30  # mais frequente (ex.: Black Friday)
powershell -ExecutionPolicy Bypass -File desinstalar_tarefa.ps1 # remove o agendamento
```

O log fica em `dados/precos.log`. O programa roda com prioridade baixa e espera alguns segundos entre uma página e outra, para não pesar no PC nem no site.

## Limitações da v1

- **Frete:** não é calculado. O aviso diz "confira na loja", exceto no Mercado Livre, que conta como frete grátis (Meli+).
- **Histórico:** vem do Zoom, que costuma ter uns 40 dias. A comparação usa o preço à vista do histórico.
- **Anúncios soltos da busca** (link `/lead?`) não têm histórico e chegam marcados como "sem histórico".
- **Monitores:** o tipo de painel só é conferido pelo nome do anúncio. Quando o nome não diz, a oferta vem marcada como "painel não confirmado".

## Uso responsável

Este projeto é para **uso pessoal**. Ele lê páginas públicas em baixa frequência (a cada 3 horas por padrão). Dá para baixar até 1 minuto, mas abaixo de 15 minutos o Zoom pode bloquear temporariamente e as verificações emendam umas nas outras. Não use o projeto para coletar dados em massa. Os termos de uso dos sites continuam valendo.

## Licença

MIT
