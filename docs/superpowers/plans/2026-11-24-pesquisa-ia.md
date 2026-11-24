# Pesquisa com IA (Claude ou OpenAI): plano

**Objetivo:** dar a cada item um nível de pesquisa com IA. O usuário escolhe o provedor (Claude ou OpenAI) e um teto de gasto por mês.

## Decisões
- **Configuração global** em `[ia]`:
  - `provedor`: `"claude"`, `"openai"` ou `"nenhum"` (padrão).
  - `limite_gasto_mensal`: em dólares, padrão 5.
  - `modelo_economico` e `modelo_completo`: opcionais.
  - `preco_entrada` e `preco_saida`: opcionais, em dólares por 1 milhão de tokens, para modelos que não estão na tabela.
- **Chaves:** `anthropic_api_key` e `openai_api_key` ficam em `segredos.toml`, ou nas variáveis `ANTHROPIC_API_KEY` e `OPENAI_API_KEY`.
- **Por item:** `pesquisa = "nenhuma" | "economica" | "completa"` (padrão `nenhuma`) e `descricao` (texto livre).
- **Modelos padrão:**
  - Claude: `claude-haiku-5-5` no econômico e `claude-opus-5-5` no completo, com busca na web `web_search_20260209` e fallback no servidor (`fallbacks="default"`).
  - OpenAI: `gpt-5-mini` e `gpt-5`, com a ferramenta `web_search` da API Responses. Os dois nomes podem ser trocados na configuração.
- **Nível econômico:**
  1. Quando o item tem `descricao`, a IA gera até 4 termos de busca uma vez só, e eles ficam guardados.
  2. A IA julga os nomes de produtos **novos** em lote (aprova ou reprova, com motivo). O resultado fica guardado por item e nome.
- **Nível completo:** tudo do econômico, mais uma pesquisa na web sobre cada finalista novo. Ela devolve nota de 0 a 10, um resumo e um veto, que também ficam guardados. Produto vetado não é avisado e dá lugar ao próximo.
- **Teto de gasto:** o gasto do mês fica no SQLite. Quando chega ao limite, a ferramenta para de chamar a IA e volta às regras fixas (julgar passa a aprovar tudo). Uma notificação é enviada uma vez por mês.
- **Falha da IA** (rede, chave, JSON inválido): é registrada no log e a ferramenta volta às regras. A rodada nunca cai por causa da IA.

## Arquivos
- `precos/ia.py`: `Resposta`, `custo()`, `Claude`, `OpenAIProv`, `criar(cfg_ia, nivel, segredos)`.
- `precos/pesquisa.py`: `Pesquisador` com `buscas_para`, `filtrar`, `avaliar`, controle de orçamento e cache via `Estado`.
- `precos/estado.py`: tabelas `ia_cache` e `gastos`.
- `precos/config.py`: `ConfigIA`, `Item.pesquisa` e `Item.descricao`, chaves.
- `precos/rodada.py`: recebe `pesquisador` opcional.
- `precos/__main__.py`: monta o pesquisador.

## Testes (provedor falso, sem rede)
- `custo`
- cache do julgamento
- sem orçamento: aprova tudo, não chama a IA e avisa uma vez
- geração e cache das buscas
- veto e cache da avaliação
- rodada que descarta reprovados
- rodada completa que pula o produto vetado
- configuração `[ia]`
- `criar` sem chave devolve None
- montagem da requisição do Claude e da OpenAI com clientes falsos
