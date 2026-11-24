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

## Configuração

### `config.toml`: o que você quer comprar
Cada bloco `[[itens]]` é um produto. Os campos estão explicados no próprio arquivo.

- **`tipo = "produto"`:** abra o produto no zoom.com.br e cole o endereço da página em `url`.
- **`tipo = "busca"`:** faça a busca no zoom.com.br e cole o endereço da busca. Para cobrir mais anúncios, coloque buscas extras em `urls`. Depois use os filtros (`marcas`, `polegadas_min`, `hz_min`, `exigir`, `excluir`) para tirar o que não presta.
- **`modo = "mais_barato"`:** avisa também quando aparece o menor preço já visto.
- **`modo = "promocao"`:** só avisa promoção real ou oferta sem histórico.

### `segredos.toml`: seus dados (não vai para o git)
- **`ntfy_topico`:** o nome do seu canal de avisos. Escolha algo difícil de adivinhar, como `precos-k7x9q2m4ab`, porque quem souber o nome consegue ler os avisos.
- **`callmebot_fone`** e **`callmebot_apikey`:** opcionais, para receber pelo WhatsApp.

### Avisos no celular (ntfy)
1. Instale o app **ntfy** (App Store ou Google Play).
2. Toque em **+** e digite o mesmo nome que está em `ntfy_topico`.
3. Quando o app pedir permissão de notificação, aceite.
4. Para testar, rode `.venv\Scripts\python.exe -m precos --teste-aviso`. A janela deve abrir no PC e a notificação deve chegar no celular.

## Rodar

```powershell
.venv\Scripts\python.exe -m precos                # uma verificação agora
powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1    # agenda: ao entrar no Windows e a cada 3h
powershell -ExecutionPolicy Bypass -File desinstalar_tarefa.ps1 # remove o agendamento
```

O log fica em `dados/precos.log`. O programa roda com prioridade baixa e espera alguns segundos entre uma página e outra, para não pesar no PC nem no site.

## Limitações da v1

- **Frete:** não é calculado. O aviso diz "confira na loja", exceto no Mercado Livre, que conta como frete grátis (Meli+).
- **Histórico:** vem do Zoom, que costuma ter uns 40 dias. A comparação usa o preço à vista do histórico.
- **Anúncios soltos da busca** (link `/lead?`) não têm histórico e chegam marcados como "sem histórico".
- **Monitores:** o tipo de painel só é conferido pelo nome do anúncio. Quando o nome não diz, a oferta vem marcada como "painel não confirmado".

## Uso responsável

Este projeto é para **uso pessoal**. Ele lê páginas públicas em baixa frequência (a cada 3 horas). Não diminua esse intervalo e não use o projeto para coletar dados em massa. Os termos de uso dos sites continuam valendo.

## Licença

MIT
