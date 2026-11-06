# Sprint 4 — Checklist de aderência ao enunciado

Cada item indica onde pode ser conferido.

## Pilar 1 — Consolidação do fluxo de automação (RPA end-to-end)

| Requisito | Status | Como conferir |
| --- | --- | --- |
| Integrar as automações das sprints anteriores (captura, regras, atualização de registros) sem intervenção manual | Atendido | `src/integracao/orquestrador.py` (etapas cadastro, catálogo, coleta, análise, avaliação); `evidencias/execucoes_etapas.csv` |
| Sincronização contínua | Atendido | Modo `--continuo`; só avalia ativos com leitura nova; `scripts/executar_rpa_integrado.py` |
| Estados dos motores sincronizados entre banco, histórico e interface | Atendido | Status e evento gravados na mesma transação (`processador_ativos.py`); dashboard lê as mesmas tabelas (`data_service.py`); verificação "nenhum ativo em atenção/crítico sem evento aberto" em `validar_cs04.py` |
| Status divergente é corrigido sozinho | Atendido | MTR-005 começa `critico` no cadastro e é sincronizado (teste `test_status_inconsistente_e_sincronizado...`) |

## Pilar 2 — Suporte operacional e troubleshooting

| Requisito | Status | Como conferir |
| --- | --- | --- |
| Direcionar procedimentos corretivos/preventivos a partir da anomalia, cruzando com a base técnica | Atendido | `suporte_operacional.py` + `playbook.py`; campos `procedimentos_json` e `referencias_json` no evento; seção 3 de cada evento no relatório |
| Fornecer dados operacionais e históricos para o assistente/RAG | Atendido | `contexto_rag.py`; `evidencias/contexto_rag/`; chat do dashboard e ferramentas MCP |
| Registro automatizado de resolução ou encaminhamento | Atendido | `ciclo_vida_eventos.py`; `historico_eventos`; `scripts/gerenciar_eventos.py` |
| Rastreabilidade e governança do ciclo de vida | Atendido | Histórico por transição, auditoria com hash encadeado, ligação evento ↔ OS ↔ leitura |

## Entregáveis oficiais

| Entregável | Status | Local |
| --- | --- | --- |
| Projeto final estruturado (GitHub) | Atendido | Este repositório |
| Notebook executável (Google Colab) | Atendido | `notebooks/Predicta_Sprint4_Colab.ipynb` |
| Pipeline integrado de RPA cobrindo atualização de status, registro de eventos e acionamento de suporte | Atendido | `src/integracao/`, `scripts/executar_rpa_integrado.py` |
| Evidência de execução ponta a ponta (alerta → status → recomendação) | Atendido | `evidencias/RELATORIO_EVIDENCIAS.md`, `trilha_ponta_a_ponta.csv`, `logs/execucao.jsonl`, `predicta_evidencia.db` |

## Critérios de avaliação

| Critério | Status | Argumentos |
| --- | --- | --- |
| Integração de ponta a ponta | Atendido | Um orquestrador conduz dados, regras de negócio, recomendação, rastreabilidade e assistente no mesmo banco |
| Autonomia e resiliência (Try/Catch) | Atendido | Isolamento por etapa e por ativo, transação única, retry, disjuntor, quarentena, backoff; 10 testes de falha em `tests/test_cs04_ciclo_vida.py` |
| Qualidade e organização do código | Atendido | Módulos por responsabilidade, regras em um só lugar, configuração por ambiente, migração compatível, 42 testes, documentação |

## Falhas injetadas na demonstração (prova de resiliência)

| Ciclo | Falha | Resposta observada |
| --- | --- | --- |
| 6 | Arquivo de sensor corrompido (MTR-003) e arquivo de motor não cadastrado (MTR-099) | Dois arquivos em `quarentena`; ciclo `parcial`; demais ativos avaliados |
| 7 | Exceção na etapa de análise | Etapa `falha`; avaliação e contexto seguem; ciclo `parcial` |
| 8 | Sensor do MTR-005 sem sinal | "sem leitura nova": ativo não conta como leitura normal |
| 0 | API de clima indisponível (ambiente sem internet) | Etapa `degradado`; catálogo local usado |
| Todos | Ollama indisponível | Recomendação por regras + manuais (`regras+rag`) |
