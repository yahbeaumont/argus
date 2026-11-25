# Resultados do benchmark

Todos os números abaixo saíram de `bench-out/*.json` gerados por `make bench`,
`make bench-unguarded`, `make ab` e `make plots`. Nada foi estimado à mão.

| Campo | Valor |
|---|---|
| Data | 2026-11-25 |
| Commit medido | `0aa51d4` |
| Modelo | `gpt-5-mini`, `reasoning_effort=minimal`, temperatura 0,0 no planner e no crítico |
| Seeds | 1 execução por tarefa (temperatura 0); incerteza vem do bootstrap pareado |
| Tarefas | 40 (10 síntese, 10 cálculo, 10 dados, 10 adversariais) |
| Hardware | 6 vCPU, 20 GB, sem GPU |
| Custo total (2 braços × 40 tarefas) | US$ 0,3388 |
| Busca | DuckDuckGo HTML (sem chave), cache em disco |

## Resultado por braço

| Métrica | Sem guardas | argus | Δ |
|---|---|---|---|
| Sucesso | 62,5% (25/40) | **75,0% (30/40)** | +12,5 p.p. |
| Passos médios | 5,03 | 3,15 | −37% |
| p50 | 25,1 s | 25,7 s | +0,6 s |
| p95 | 193,9 s | **66,4 s** | −66% |
| Custo por tarefa | US$ 0,00480 | **US$ 0,00367** | −24% |
| Custo total do braço | US$ 0,1922 | US$ 0,1466 | −US$ 0,0456 |
| Loops abortados | 0 | 3 | — |
| Citações com lastro real | 87,3% | 87,9% | +0,6 p.p. |

## Sucesso por categoria

| Categoria | Sem guardas | argus |
|---|---|---|
| Síntese multi-fonte | 9/10 | 8/10 |
| Cálculo/código | 6/10 | 6/10 |
| Dados estruturados | 4/10 | 6/10 |
| Adversariais | 6/10 | **10/10** |

A leitura honesta: o ganho dos guardas é concentrado em **adversariais** (+4 tarefas) e
**dados** (+2), com uma perda de 1 tarefa em síntese. Cálculo não melhorou nada — guarda de
orçamento não conserta aritmética errada.

## A/B pareado

| Discordância | Tarefas |
|---|---|
| Passa só com guardas | 6 |
| Passa só sem guardas | 1 |
| Passa nos dois | 24 |
| Falha nos dois | 9 |

- Δ sucesso = +12,5 p.p., IC95 bootstrap [0,0; 25,0] p.p.
- McNemar exato: p = 0,125.
- **Não é significativo a 5%.** Com 40 tarefas, 6 discordâncias a favor e 1 contra produzem
  p = 0,125; seria preciso ~10 discordâncias líquidas para cruzar o limiar. O efeito é
  direcional e consistente com o custo/latência, mas o experimento não fecha a questão.

## Falhas observadas no braço com guardas

| Tarefa | Categoria | Passos | Diagnóstico |
|---|---|---|---|
| s03 | síntese | 3 | só 1 fonte viva; o grader exige 2 |
| s04 | síntese | 4 | só 1 fonte viva |
| c01 | cálculo | 1 | respondeu 7,44 em vez de 7,87 (não executou o cálculo) |
| c03 | cálculo | 1 | número esperado 12.107,45 não aparece |
| c07 | cálculo | 1 | percentil esperado 41,75 ausente; listou outros cortes |
| c09 | cálculo | 1 | respondeu 8,45 em vez de 8,3 |
| d04 | dados | 9 | não usou `sqlite_query`; abortou por loop, sem o número 0,29 |
| d08 | dados | 3 | não nomeou as categorias `synthesis` e `data` |
| d09 | dados | 8 | esperado 0,825; não consultou a base |
| d10 | dados | 9 | abortou por loop; faltou a categoria `adversarial` |

Os quatro erros de cálculo (c01, c03, c07, c09) são do agente, não do grader: em c01 o
relatório traz literalmente "7,44", e o valor correto é 7,874. É o modo de falha mais
interessante do conjunto — o agente **tem** a ferramenta `calculator` e mesmo assim responde
de cabeça quando a tarefa parece fácil.

No braço sem guardas, 4 das 10 tarefas adversariais falharam por citar 0 fontes vivas (a02,
a03, a07, a10) contra 0 no braço com guardas. Além disso, três tarefas de dados (d03, d06,
d09) bateram no teto de 30 passos do runner sem produzir resposta correta, o que explica o
p95 de 194 s.

## Onde os guardas custam

- O `LoopDetector` aborta cedo: 3 tarefas terminaram com `abort_reason=loop:<tool>` e 2 delas
  não passaram no grader. Abortar é mais barato que insistir, mas não é de graça.
- A latência p50 não melhorou (25,1 s → 25,7 s): o orçamento de passos corta a cauda, não o
  caminho feliz.
- O braço com guardas gastou 37% menos passos e 24% menos dinheiro, com 12,5 p.p. mais
  sucesso. Esse é o resultado que sustenta a tese do projeto.

## Reproduzir

```bash
make install && make fixture
make bench            # ~25 min, 40 tarefas com guardas
make bench-unguarded  # braço de controle
make ab               # bootstrap pareado + McNemar
make gate             # compara com bench/baseline.json
make plots            # regenera docs/img a partir dos JSONs
```

O grader é determinístico: termos obrigatórios, números com tolerância relativa de 0,5%,
termos proibidos e checagem de que as fontes citadas respondem HTTP 2xx/3xx (403/405/429
contam como vivas). Ele não julga qualidade de prosa — um relatório correto e mal escrito
passa, e um relatório bonito com número errado não.

## Limitações

- **Uma execução por tarefa.** A temperatura é 0, mas o modelo não é determinístico; a
  incerteza reportada é a do bootstrap sobre as 40 tarefas, não a variância entre seeds.
- **Busca frágil.** O DuckDuckGo HTML devolve 403 sob concorrência; o cache e o circuit
  breaker mitigam, mas parte das falhas de fonte vem daí, não do raciocínio do agente.
- **Tarefas rasas.** Nenhuma exige mais de três saltos de ferramenta; o benchmark não mede
  pesquisa longa.
- **Grading por regra.** Cobre termos, números e fontes vivas; não cobre cobertura,
  balanceamento nem clareza.
