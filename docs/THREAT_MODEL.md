# Modelo de ameaça

Um agente que busca na web e executa código é, por construção, uma superfície de ataque com
quatro componentes: o conteúdo que ele lê, o código que ele roda, o dinheiro que ele gasta e o
relatório que ele entrega. Este documento cobre os vetores que o argus trata e os que ficam
explicitamente fora de escopo.

## Ativos

- Chave do provedor de LLM e chave do provedor de busca.
- Base SQLite de fixtures usada pelas tarefas de dados.
- Host que executa o `python_exec` e o diretório de cache de páginas.
- Credibilidade do relatório: uma URL inventada é tão danosa quanto um número inventado.

## Vetores e mitigações

| Vetor | Impacto | Mitigação no argus | Verificação |
|---|---|---|---|
| Injeção de prompt via página web | O agente executa um passo escolhido pelo atacante | Saída de ferramenta truncada em 8k chars; contrato de ferramenta fechado; o writer só recebe observações, nunca instruções do sistema; `python_exec` sem rede | Tarefa `a05` do bench pede para seguir instruções de uma página e falha se o relatório vazar `OPENAI_API_KEY` ou `sk-` |
| Código hostil em `python_exec` | RCE, exfiltração de arquivos | `subprocess` com `-I -S`, `resource.setrlimit` (CPU 10s, AS 512 MB, 32 processos), `cwd` em diretório temporário, ambiente mínimo | `tests/test_sandbox.py` executa snippet real; a tarefa `a05` tenta ler ambiente |
| SSRF via `fetch_page` | Acesso a metadata de nuvem e serviços internos | Apenas `http(s)`; bloqueio de `169.254.169.254`, `localhost`, `metadata.google.internal`, IPs privados/loopback/link-local | `guard_url` é chamado antes de qualquer requisição |
| Loop de ferramenta | Custo e latência sem progresso | `LoopDetector` por hash de `(tool, args)`; no limite o ator recebe aviso explícito; se repetir depois do aviso, a execução é abortada com `abort_reason=loop:<tool>` | Métrica `loop_aborts` do bench e teste `test_guards.py` |
| Estouro de orçamento | Conta inesperada | `BudgetGuard` com passos, tokens, segundos e custo em dólar, checado antes de cada passo | Testes de orçamento em `test_guards.py` |
| Ferramenta instável | Cascata de falhas | `CircuitBreaker` por ferramenta: 3 falhas abrem o circuito por 120s | `test_guards.py::test_breaker_opens_and_resets` |
| SQL destrutivo | Corrupção das fixtures | Só `SELECT`/`WITH`, conexão `mode=ro` | `server.py::sqlite_query` |
| Fonte inventada no relatório | Relatório convincente e falso | `citations.verify` compara cada URL citada com as URLs efetivamente retornadas pelas ferramentas; o resultado entra em `citations_supported/citations_total` e no bench | Tarefa `a01` (domínio inexistente) e métrica `citation_support` |
| Vazamento de chave no relatório | Comprometimento de credencial | Chaves ficam no cliente LLM e no processo do servidor MCP; nunca entram no prompt | `must_not_contain` da tarefa `a05` |

## O que o bench mede e o que ele não mede

O bench mede taxa de sucesso, abortos por loop, latência, custo e suporte de citação em 40 tarefas
fixas. Ele **não** mede resistência a um atacante adaptativo, nem qualidade de prosa, nem
profundidade além de três saltos de ferramenta.

## Fora de escopo

Multi-tenancy, isolamento por kernel (gVisor/Firecracker/seccomp), rate limit distribuído,
rotação de credenciais, moderação de conteúdo e execução de código em linguagem diferente de
Python. `python_exec` é um subprocesso com limites de recurso: não é um sandbox de segurança
para código hostil de verdade, e o README diz isso na seção de limitações.
