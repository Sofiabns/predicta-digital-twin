# Sprint 4 — Documento Técnico

**Projeto:** Predicta — Digital Twin Industrial
**Disciplina / trilha:** RPA — FIAP 2026
**Tema:** Integração da solução e suporte operacional

| Integrante | RM |
| --- | --- |
| Sofia Bueris Netto de Souza | 565818 |
| Augusto Oliveira Codo de Sousa | 562080 |
| Gabriel Tonelli Avelino Dos Santos | 564705 |
| Vinícius Adrian Siqueira de Oliveira | 564962 |
| Felipe de Oliveira Cabral | 561720 |

---

## 1. Objetivo

Reunir em um único pipeline automatizado tudo o que foi construído nas sprints anteriores (coleta de telemetria, cadastro de ativos, catálogo técnico, detecção de anomalias, motor de decisão, base de conhecimento e assistente) e acrescentar o que faltava para o suporte operacional ficar completo: **sincronizar o status dos motores, direcionar o procedimento correto para cada alerta, alimentar o assistente com dados reais e registrar o ciclo de vida de cada falha até o encerramento**.

## 2. Ponto de partida: o que encontramos no projeto da Sprint 3

Antes de integrar, revisamos o código existente. Para a automação ser confiável de ponta a ponta, foi preciso corrigir lacunas que apareciam apenas quando tudo rodava junto:

| # | Problema encontrado | Efeito | Correção na Sprint 4 |
| --- | --- | --- | --- |
| 1 | Eventos eram abertos, mas nenhum fluxo os encerrava | Motor ficava `critico` para sempre | Ciclo de vida com resolução automática e manual |
| 2 | A cada 20 s uma nova ordem de manutenção e um novo evento eram criados para a mesma falha | Dezenas de OS duplicadas | Um evento aberto por ativo; recorrência apenas conta ocorrências |
| 3 | O catálogo usa "W22" e a placa traz "W22 IE3 Premium"; o `JOIN` por igualdade nunca casava | Todos os motores usavam limites padrão | Resolvedor de limites por fabricante + modelo contido no nome |
| 4 | `salvar_especificacao` inseria uma linha nova a cada coleta | Catálogo crescia sem parar | Atualização (upsert) por fabricante e modelo |
| 5 | O chat do dashboard consultava colunas que não existem na view | Assistente sempre falhava na consulta | Contexto vindo de documentos RAG exportados pela automação |
| 6 | O ETL tratava `cadastro_ativos.csv` como telemetria | Erro a cada execução | Coleta restrita a `leituras_*.csv` |
| 7 | Importação obrigatória de `ollama`, `faiss` e `scrapling` | Qualquer ausência impedia o sistema de iniciar | Importações tardias com alternativa automática |
| 8 | Arquivos inválidos permaneciam na pasta de entrada | Mesmo erro repetido em todo ciclo | Quarentena com registro do motivo |
| 9 | Scripts de inicialização chamavam `limpar_banco.py` sem argumentos (menu interativo) | Script travava esperando entrada | Inicialização passou a usar a demonstração integrada |

## 3. Arquitetura

```
 data/raw (CSV, placas JSON)          catálogo (web ou local)        data/manuais
        │                                      │                           │
        ▼                                      ▼                           ▼
 ┌──────────────────────────  Orquestrador (src/integracao/orquestrador.py)  ──────────────┐
 │ preparo → [telemetria simulada] → cadastro → catálogo → coleta → análise                │
 │        → avaliação dos ativos → contexto do assistente → registro do ciclo               │
 └──────────────────────────────────────────────────────────────────────────────────────────┘
        │                │                 │                  │                   │
        ▼                ▼                 ▼                  ▼                   ▼
   SQLite (leituras, associacoes_ativos, eventos_operacionais, historico_eventos, manutencoes,
           auditoria_operacional, execucoes_pipeline, execucoes_etapas)
        │                                   │                                      │
        ▼                                   ▼                                      ▼
   Dashboard (Gradio)           data/rag/operacional/*.md ──► Base de conhecimento ──► Assistente / MCP
```

### 3.1 Módulos novos

| Módulo | Responsabilidade |
| --- | --- |
| `config.py` | Todos os parâmetros, lidos do ambiente |
| `orquestrador.py` | Sequência das etapas, isolamento de falhas, laço contínuo, registro do ciclo |
| `processador_ativos.py` | Tabela de decisão por ativo e transação única |
| `ciclo_vida_eventos.py` | Estados do evento, histórico, OS, auditoria encadeada, ações humanas |
| `avaliacao.py` | Regras de severidade (temperatura, vibração, corrente, tensão) |
| `limites.py` | Limites por motor a partir do catálogo, com padrão e origem registrada |
| `suporte_operacional.py` | Recomendação: regras + manuais + catálogo + IA opcional |
| `playbook.py` | Procedimentos por tipo de desvio, com referência ao manual |
| `contexto_rag.py` | Exportação dos dados operacionais para o assistente |
| `resiliencia.py` | Nova tentativa, disjuntor, etapa protegida |
| `log_estruturado.py` | Log JSON Lines |
| `migracao.py` | Esquema novo, compatível com bancos já existentes |
| `simulador.py`, `demo.py` | Telemetria simulada e roteiro reproduzível |
| `evidencias.py`, `validacao.py` | Geração das evidências e verificações de integridade |

## 4. Fluxo de um ciclo

1. **Preparo.** Garante o esquema do banco (aplica só o que falta) e cadastra os motores se o banco estiver vazio. Se falhar, o ciclo é abortado e repetido no próximo intervalo.
2. **Telemetria** (apenas no modo simulado). Gera um CSV por motor.
3. **Cadastro.** Processa `cadastro_ativos.csv` e os JSON de placa, quando existirem (TAG, localização, dados nominais).
4. **Catálogo.** Se não há coleta dentro da validade (24 h), consulta clima e catálogo, com nova tentativa; se tudo falhar, usa o catálogo local.
5. **Coleta.** Processa cada `leituras_*.csv`. O que não for válido vai para quarentena.
6. **Análise.** Executa a detecção estatística das sprints anteriores e persiste anomalias.
7. **Avaliação.** Para cada ativo com leitura nova: classifica, decide, atualiza status, evento, OS e histórico (uma transação) e, se for o caso, notifica.
8. **Contexto do assistente.** Reexporta os documentos que mudaram e reindexa.
9. **Registro.** Grava o resultado do ciclo e de cada etapa no banco e no log.

### 4.1 Tabela de decisão por ativo

| Severidade da leitura | Evento aberto? | Ação |
| --- | --- | --- |
| Normal | não | Sincroniza o status para `operacional`, se estava divergente |
| Normal | sim | Conta uma leitura normal; ao atingir 3 (e sem atendimento humano), resolve o evento e volta o status para `operacional` |
| Alerta ou crítica | não | Atualiza o status, abre o evento, gera a recomendação, cria a OS, encaminha à manutenção; notifica se crítica |
| Alerta ou crítica | sim, mesma severidade | Conta a ocorrência (sem duplicar nada) |
| Crítica | sim, era alerta | Escalonamento: refaz a recomendação, converte a OS para corretiva urgente, atualiza status, notifica |
| Alerta | sim, era crítica | Reclassificação para alerta e ajuste do status |

Exceção para todas as linhas: se o ativo está em `manutencao` ou `parado`, o status **não** é alterado pela automação.

## 5. Modelo de dados (acréscimos)

**Tabelas novas:** `historico_eventos` (uma linha por transição), `execucoes_pipeline` (um registro por ciclo) e `execucoes_etapas` (um registro por etapa e ciclo).

**Colunas novas:**

- `eventos_operacionais`: `leitura_id`, `manutencao_id`, `ocorrencias`, `ciclos_normais`, `procedimentos_json`, `referencias_json`, `origem_recomendacao`, `prioridade`, `prazo_horas`, `run_id`, `atualizado_em`, `encerrado_em`, `resolucao`, `encerrado_por`, `encaminhado_para`
- `associacoes_ativos`: `ultima_leitura_avaliada_id`, `ultima_avaliacao_em`
- `manutencoes`: `evento_id`

**Views novas:** `vw_eventos_abertos`, `vw_trilha_eventos`.

A migração é idempotente: roda em banco novo ou antigo e só acrescenta o que falta.

## 6. Suporte operacional (recomendação técnica)

Para cada alerta, a recomendação é composta em três camadas:

1. **Playbook.** Passos corretivos e preventivos por tipo de desvio, extraídos dos manuais do projeto, cada um com a referência (arquivo e seção). Quando temperatura e vibração sobem juntas, entra o passo de parada, relubrificação e alinhamento descrito na seção de diagnóstico integrado do manual normativo.
2. **Recuperação nos manuais.** Os trechos mais relevantes são buscados (embeddings + FAISS quando disponíveis; BM25 caso contrário) e anexados como referências. O guia do fabricante vindo do catálogo também entra.
3. **Texto do diagnóstico.** Se o Ollama responde dentro do tempo, ele redige o diagnóstico com base nos trechos e nos passos. Se não responde, o texto é montado a partir das regras. Um **disjuntor** evita esperar o tempo limite a cada ativo quando a IA está fora.

O campo `origem_recomendacao` guarda `llm+rag`, `regras+rag` ou `regras`.

## 7. Fornecimento de dados ao assistente (RAG)

A cada ciclo, para cada ativo, é gerado um documento `data/rag/operacional/<TAG>.md` com perfil e limites, estado atual, estatísticas das últimas 100 leituras, últimos 5 eventos (diagnóstico, ação, resolução) e últimas 5 ordens de manutenção. Também são gerados `resumo_planta.md` e `contexto_operacional.jsonl`. A escrita é atômica (arquivo temporário + troca) e só ocorre se o conteúdo mudou.

Esses documentos entram em uma coleção separada da dos manuais. O chat do dashboard e as ferramentas MCP (`listar_eventos_abertos`, `consultar_historico_ativo`, `buscar_procedimento_tecnico`, `consultar_contexto_ativo`) consultam essas duas coleções. Quando o Ollama não está disponível, o chat devolve o que foi recuperado, em vez de uma mensagem de erro.

## 8. Rastreabilidade e governança

- **Histórico por evento:** cada transição guarda estado anterior e novo, ação, responsável (`RPA_PREDICTA` ou `tecnico:<nome>`), observação, status do ativo antes e depois e o `run_id`.
- **Auditoria com hash encadeado:** cada registro inclui o SHA-256 calculado sobre o conteúdo e o hash do registro anterior. `verificar_cadeia_auditoria` refaz o cálculo e acusa qualquer registro alterado (há teste que adultera um registro e confirma a detecção).
- **Ligação evento ↔ ordem de manutenção ↔ leitura** por chaves no banco.
- **Encerramento:** resolução automática (normalização confirmada) ou manual (técnico, com texto da solução). A OS é concluída junto.

## 9. Tratamento de exceções

O princípio adotado foi **isolar a falha no menor escopo possível e sempre registrá-la**:

| Escopo | Mecanismo |
| --- | --- |
| Ciclo | `executar_etapa` captura qualquer exceção de cada etapa e devolve `ok`, `degradado` ou `falha` |
| Ativo | O laço de avaliação captura exceções por ativo |
| Dado | Transação única por ativo (tudo ou nada) |
| Arquivo | Quarentena com `.motivo.json` |
| Rede | `com_retry` com espera exponencial; depois, alternativa local |
| IA | `Disjuntor` (2 falhas abrem por 3 minutos) e texto por regras |
| Laço contínuo | Exceção não tratada vira ciclo `falha`; backoff crescente até 300 s; Ctrl+C encerra com segurança |

## 10. Verificações e testes

- `scripts/validar_cs04.py`: 10 verificações sobre o banco e o log (evento com recomendação e histórico, sem evento duplicado por ativo, sem divergência entre status e eventos, sem OS repetida, cadeia de auditoria íntegra etc.).
- `tests/`: 42 testes. Os 25 novos cobrem as regras de severidade, resolução de limites, recomendação com e sem base de conhecimento, fluxo alerta→status→evento→OS→notificação, sincronização de status, preservação de `manutencao`, anomalia persistente sem duplicidade, resolução automática, bloqueio da resolução automática durante atendimento humano, escalonamento, detecção de adulteração na auditoria, falha de etapa, quarentena, falha de um ativo isolada, banco indisponível, laço contínuo com exceção e a demonstração completa.

## 11. Evidência de execução

`python scripts/executar_rpa_integrado.py --demo` roda 14 ciclos (mais a carga histórica no ciclo 0). Resultado esperado e registrado em `evidencias/`:

| Ativo | O que acontece | Resultado |
| --- | --- | --- |
| MTR-L01-BOM-001 | Já inicia crítico (88,1 °C, 5,03 mm/s). Evento aberto, OS corretiva urgente, e-mail. Técnico assume no ciclo 3 e conclui no ciclo 5. | Resolvido por técnico, status `operacional` |
| MTR-L01-EST-002 | Pico de temperatura (80,2 °C) no ciclo 3 | Alerta, OS preventiva; resolvido automaticamente após 3 leituras normais |
| MTR-UTIL-EXA-004 | Vibração sobe: alerta (ciclo 5), depois crítica (ciclo 6) | Escalonamento, OS vira corretiva urgente; resolvido automaticamente |
| MTR-ENV-TRP-005 | Começa com status `critico` no cadastro, mas a leitura é normal. Depois, queda de tensão (352 V) nos ciclos 9 e 10 | Status sincronizado no início; alerta elétrico resolvido automaticamente |
| MTR-L02-CMP-003 | Em `manutencao` desde o cadastro | Status preservado em toda a execução |

Falhas injetadas: ciclo 6 (arquivo corrompido e motor não cadastrado → quarentena), ciclo 7 (etapa de análise falha → ciclo `parcial`, avaliação continua), ciclo 8 (sensor sem sinal → ativo não conta leitura normal).

## 12. Como reproduzir

Veja o [README](../README.md#como-executar). Em resumo: `pip install -r requirements-core.txt`, `python scripts/executar_rpa_integrado.py --demo`, `python scripts/validar_cs04.py`, `python -m pytest tests -q`.

## 13. Limitações e próximos passos

- Classificação baseada na leitura mais recente; tendência (regressão sobre a janela) poderia antecipar alertas.
- O e-mail é simulado (arquivo HTML). A troca por SMTP ou por um webhook de Teams/Slack é localizada em `notificacao_service.py`.
- O catálogo local é uma amostra; três modelos têm valores ilustrativos.
- As evidências do repositório foram geradas com Ollama e busca semântica. O modo sem IA também foi testado (testes automatizados e execução anterior) e produz recomendações por regras e manuais.
- A atribuição de ordens a técnicos específicos e a integração com um sistema de manutenção (CMMS) ficam como evolução.
