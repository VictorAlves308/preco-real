# Monitor de preços — design

Data: 24/11/2026

## Para que serve

O usuário quer comprar três coisas pelo menor preço real, sem cair em promoção falsa. A Black Friday é em 27/11/2026 e é quando mais aparece desconto inflado. A ferramenta pesquisa os produtos por categoria, compara as lojas, confere no histórico de 3 meses se o desconto é verdadeiro e avisa quando aparece uma oferta boa.

## Itens monitorados

| Item | O que procurar | Limite |
|---|---|---|
| Processador | Exatamente o **AMD Ryzen 7 5700X** (box). Só o preço importa. | sem limite definido; só aponta o menor preço real |
| Monitor | 144Hz ou mais, **o mais barato que não seja ruim** | sem limite definido; o objetivo é o mais barato |
| TV | 32 a 40 polegadas, Smart TV, uso básico (streaming) para a mãe | **R$ 1.500 no total parcelado** |

### O que é "não ruim" (decisão minha, pode corrigir)
- **Monitor:**
  - 23,8" a 27", 1080p, 144Hz ou mais, painel IPS ou VA (TN fica de fora).
  - Marcas: LG, Samsung, AOC, Dell, ASUS, Acer, Gigabyte, MSI, Philips, Pichau.
  - Nota de 4,5 ou mais, com pelo menos 50 avaliações, quando a fonte mostrar a nota.
  - Na lista final, ordena pelo preço.
- **TV:**
  - Smart TV com Google TV, Tizen, webOS ou Roku.
  - Marcas: Samsung, LG, TCL, Philips, AOC.
  - Mesma regra de nota.

## Regra de preço
- **Sempre comparar pelo preço no cartão parcelado**, nunca pelo preço do PIX.
- **Só vale parcelamento sem juros.** Ofertas com **10x sem juros** são preferidas e aparecem primeiro. Ofertas com menos parcelas sem juros entram marcadas como "menos de 10x". Decisão minha, porque o pedido foi "preferência 10x", e não "só 10x".
- No limite da TV, a conta é o total parcelado: R$ 1.500.

## Promoção real ou falsa (decisão minha, pode corrigir)
Usa o histórico de 90 dias da fonte (Zoom/Buscapé).
- **Promoção real:** o preço atual é pelo menos 10% menor que a mediana dos 90 dias, e no máximo 3% acima do menor preço desses 90 dias.
- **Falsa / maquiada:** o preço subiu mais de 10% nos 30 dias antes do "desconto", ou o "de/por" da loja usa um "de" que nunca foi praticado.
- **Preço normal:** os demais casos. Não gera aviso.
- Se a fonte não tiver histórico, a oferta aparece como "sem histórico" e não conta como promoção real.

## Frete
- **Preferência por frete grátis.** O usuário tem o plano do Mercado Livre (Meli+), então os produtos Full/lojas oficiais do ML contam como frete grátis.
- Nas outras lojas, se o frete for pago para o CEP **00000-000**, o frete entra no preço comparado e a oferta é marcada "frete pago". Para a TV, o frete conta dentro do limite de R$ 1.500.
- Na v1, o frete é lido do selo "frete grátis" da listagem. A simulação por CEP fica só para as ofertas finalistas.

## Prazo: v1 hoje (24/11)
O usuário quer a ferramenta funcionando hoje, por causa da Black Friday.
- **v1 enxuta:**
  - Começa pelas fontes que respondem mais fácil (Kabum, Mercado Livre e o histórico do Zoom/Buscapé, se não bloquearem). As demais lojas entram quando funcionarem.
  - Já tem a janela na tela, o WhatsApp, o agendamento e a regra de promoção.
- **Depois:** completar as lojas, simular frete por CEP em todas e refinar os filtros.

## Lojas e fontes
- **Lojas:** Kabum, Pichau, Terabyte, Amazon, Mercado Livre (só vendas oficiais/Full), Magalu.
- **Histórico e comparação:** Zoom e Buscapé.
- O preço a prazo e as parcelas vêm da página da loja quando o agregador não mostrar.

## Avisos
- Quando aparece uma oferta nova que passa nas regras, ou quando uma oferta já avisada fica mais barata:
  1. **Janela na tela:** fica por cima de tudo e só some quando é fechada. Mostra produto, loja, preço parcelado, número de parcelas, comparação com o histórico e o link.
  2. **WhatsApp via CallMeBot:** mensagem curta com os mesmos dados e o link.
- **Sem repetir:** a mesma oferta, pelo mesmo preço, não é avisada de novo. Só avisa de novo se o preço cair pelo menos 2%. (decisão minha)
- **Quantos avisos (decisão minha):**
  - Cada aviso traz no máximo as **3 melhores ofertas de cada item**, não uma mensagem por oferta.
  - Ofertas "promoção real" avisam na hora.
  - Ofertas "sem histórico" também avisam, marcadas como **"sem histórico, não confirmado"**. Sem isso, a ferramenta ficaria muda na Black Friday enquanto o histórico próprio ainda é curto.
  - Ofertas "maquiadas" nunca avisam.
  - O processador e o monitor avisam também quando aparece um preço menor que o menor já visto, mesmo que não seja promoção pela regra dos 90 dias, porque o objetivo ali é o mais barato.

## Vendedores (decisão minha)
- **Amazon e Magalu:** só produtos vendidos ou entregues pela própria loja.
- **Mercado Livre:** lojas oficiais **ou** produtos Full.
- Vendedor terceiro sem essas condições fica de fora.

## Especificação faltando (decisão minha)
- Se o anúncio não mostra o tipo de painel, a frequência ou o sistema da TV, a ferramenta consulta a ficha técnica do produto, uma vez por modelo, e guarda o resultado.
- Se mesmo assim não achar, a oferta aparece com a marca "não confirmado".
- Painel TN confirmado é sempre descartado.

## Como roda (opção A, escolhida pelo usuário)
- Fica no PC do usuário: script Python agendado no Agendador de Tarefas do Windows.
  - Roda a cada 3 horas e também ao ligar o PC.
  - Roda com prioridade baixa, porque o usuário usa o PC para outras coisas.
- Os dados ficam numa pasta local: histórico das buscas e ofertas já avisadas.
- A configuração fica num arquivo editável: itens, filtros, limites e lojas. O número de WhatsApp e a chave do CallMeBot ficam num arquivo separado, fora do código.
- Antes de a ferramenta ficar pronta, faço uma varredura manual dos três itens, já para a Black Friday.

## Opções consideradas
- **A) Script local agendado, com pesquisa por categoria.** ESCOLHIDA. É a única que tem a janela na tela, o WhatsApp e a pesquisa sozinha. Limitação: só verifica com o PC ligado.
- **B) Nuvem (GitHub Actions).** Verifica com o PC desligado, mas não tem a janela na tela.
- **C) Lista fixa de modelos escolhida por mim.** É a que menos quebra, mas não descobre modelos novos, e o pedido foi que a ferramenta pesquisasse.

## Fora do escopo
- Comprar automaticamente.
- Aplicativo de celular ou site.
- Produtos usados e vendedores de marketplace sem reputação.

## Seria um fracasso se
- Avisasse preço do PIX como se fosse o do cartão.
- Chamasse de promoção um desconto maquiado.
- Lotasse de avisos repetidos.
- Pesasse no PC.

## Fica a critério de quem constrói
- Como raspar cada fonte: API JSON, HTML ou navegador headless.
- Se Zoom ou Buscapé bloquearem o acesso, cair para o histórico guardado pela própria ferramenta e para as páginas das lojas.
- Formato dos arquivos de dados.
- Visual da janela, desde que fique por cima e seja legível.
