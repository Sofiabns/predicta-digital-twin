# 🏭 Predicta — Digital Twin Industrial (FIAP 2026)

> **Sprint 4 · Integração da Solução e Suporte Operacional (RPA)**
> Pipeline único que liga sensores, regras de negócio, histórico, base de conhecimento técnica e assistente de diagnóstico, com rastreabilidade completa de cada falha, do alerta ao encerramento.

---

## 👥 Equipe Predicta

| Nome completo                          | RM     |
| -------------------------------------- | ------ |
| Sofia Bueris Netto de Souza            | 565818 |
| Augusto Oliveira Codo de Sousa         | 562080 |
| Gabriel Tonelli Avelino Dos Santos     | 564705 |
| Vinícius Adrian Siqueira de Oliveira   | 564962 |
| Felipe de Oliveira Cabral              | 561720 |

---

## 📑 Sumário

1. [Em uma frase](#em-uma-frase)
2. [Como avaliar em 2 minutos](#como-avaliar-em-2-minutos)
3. [O que a Sprint 4 entrega](#o-que-a-sprint-4-entrega)
4. [Como o pipeline funciona](#como-o-pipeline-funciona)
5. [Ciclo de vida de um evento](#ciclo-de-vida-de-um-evento)
6. [Regras de negócio](#regras-de-negócio)
7. [Autonomia e resiliência](#autonomia-e-resiliência)
8. [Como executar](#como-executar)
9. [Evidências de execução](#evidências-de-execução)
10. [Estrutura do repositório](#estrutura-do-repositório)
11. [Mapeamento com o enunciado](#mapeamento-com-o-enunciado)
12. [Decisões e limitações](#decisões-e-limitações)
13. [Sprints anteriores](#sprints-anteriores)

---

## Em uma frase

A cada ciclo, o Predicta lê a telemetria dos motores, aplica as regras, **atualiza o status do ativo**, **abre (ou atualiza) o evento**, **busca nos manuais o que fazer**, **gera a ordem de manutenção**, avisa a equipe, **mantém tudo registrado** e entrega ao assistente o histórico atualizado. Sem ninguém clicar em nada.

---

## Como avaliar em 2 minutos

Não é preciso instalar Ollama, FAISS nem o dashboard para ver o fluxo completo.

**Opção A, Google Colab:** abra `notebooks/Predicta_Sprint4_Colab.ipynb` e execute as células em ordem. O notebook já está salvo com as saídas de uma execução.

**Opção B, computador local:**

```bash
pip install -r requirements-core.txt
python scripts/executar_rpa_integrado.py --demo     # ~1 minuto, 14 ciclos
python scripts/validar_cs04.py                      # confere a integridade
python -m pytest tests -q                           # 42 testes
```

Depois, abra `evidencias/RELATORIO_EVIDENCIAS.md`. Ele mostra, para cada falha, o caminho **alerta detectado → status atualizado → recomendação técnica registrada → encaminhamento → encerramento**.

Para ver o dashboard com os dados da demonstração: `./run_unix.sh` (Mac/Linux) ou `run_windows.bat` (Windows).

---

## O que a Sprint 4 entrega

| Pilar do enunciado | O que foi feito | Onde |
| --- | --- | --- |
| **Sincronização contínua** | Um orquestrador executa, em cada ciclo, cadastro → catálogo → coleta → análise → avaliação → contexto do assistente. Só avalia ativos com leitura nova. | `src/integracao/orquestrador.py` |
| **Status em tempo real** | O status do motor é atualizado no mesmo instante em que o evento é aberto, escalado ou resolvido, tudo em uma única transação. Dashboard, histórico e banco leem da mesma fonte. | `src/integracao/processador_ativos.py` |
| **Direcionar procedimentos** | Cada alerta é cruzado com os manuais e com o catálogo do fabricante. O resultado é uma lista de passos corretivos e preventivos, cada um com a seção do manual de onde veio. | `src/integracao/suporte_operacional.py`, `playbook.py` |
| **Dados para o assistente (RAG)** | A cada ciclo, estado atual, estatísticas, eventos e manutenções de cada ativo viram documentos indexados junto com os manuais. | `src/integracao/contexto_rag.py` |
| **Encerramento e rastreabilidade** | Estados `pendente → encaminhado → em_atendimento → resolvido`, histórico de cada transição e auditoria com hash encadeado (qualquer adulteração é detectada). | `src/integracao/ciclo_vida_eventos.py` |
| **Tratamento de exceções** | Try/Catch por etapa e por ativo, nova tentativa com espera, disjuntor para a IA, quarentena de arquivos ruins e laço contínuo que não morre. | `src/integracao/resiliencia.py` |
| **Evidências** | Log JSON Lines, banco SQLite, CSVs e relatório gerados por uma execução real. | `evidencias/` |

---

## Como o pipeline funciona

```
                          ┌──────────────── a cada ciclo ────────────────┐
 CSV dos sensores ──►  1. cadastro   (TAG, localização, placa do motor)
 (ou simulador)        2. catálogo   (limites do fabricante, validade de 24 h)
                       3. coleta     (ETL; arquivo inválido vai para quarentena)
                       4. análise    (anomalias estatísticas da Sprint 1)
                       5. avaliação  ──► regra ──► status ──► evento ──► recomendação
                       │                                         │            │
                       │                                         ▼            ▼
                       │                                   ordem de      e-mail de
                       │                                   manutenção    alerta
                       6. contexto do assistente (documentos RAG atualizados)
                       7. registro do ciclo (banco + log estruturado)
                          └───────────────────────────────────────────────┘
```

Cada etapa roda isolada: se uma falhar, o erro é registrado e as demais continuam. O ciclo termina como `sucesso`, `parcial` (alguma etapa com ressalva ou falha) ou `falha` (banco indisponível).

---

## Ciclo de vida de um evento

```
 anomalia detectada
        │
        ▼
   pendente ──(RPA gera OS)──► encaminhado ──(técnico assume)──► em_atendimento
        │                           │                                  │
        └──── leituras normais ─────┴──► resolvido ◄──(técnico conclui)┘
              (3 seguidas, só sem atendimento humano)
```

- **Um evento aberto por ativo.** Se a anomalia continua, o evento só conta mais uma ocorrência: não duplica evento, OS nem e-mail.
- **Escalonamento.** Se uma situação de alerta piora para crítica, o evento é reclassificado, a recomendação é refeita, a OS vira corretiva urgente e a equipe é avisada.
- **Atendimento humano manda.** Quando o técnico assume, o ativo passa a `manutencao` e a automação não sobrescreve esse status nem encerra o evento sozinha.
- **Toda mudança fica registrada** em `historico_eventos` (quem, quando, de qual estado para qual) e na auditoria com hash encadeado.

---

## Regras de negócio

| Grandeza | ALERTA | CRÍTICO | Fonte do limite |
| --- | --- | --- | --- |
| Temperatura | ≥ 90% do limite | acima do limite | catálogo do fabricante (ou padrão do manual: 80 °C) |
| Vibração | ≥ 90% do limite | acima do limite | catálogo do fabricante (ou padrão: 2,8 mm/s, ISO 10816-3) |
| Corrente | ≥ 90% de 110% da nominal | acima de 110% da nominal | placa do motor |
| Tensão | desvio > 5% da nominal | desvio > 10% | placa (ou 380 V quando não há placa) |

| Severidade | Status do ativo | Ordem de manutenção | Prazo | E-mail |
| --- | --- | --- | --- | --- |
| ALERTA | `atencao` | preventiva, prioridade média | 72 h | não |
| CRÍTICO | `critico` | corretiva, urgente | 4 h | sim |
| Normal sem evento | `operacional` (sincroniza se estava divergente) | | | |

Os status `manutencao` e `parado` são definidos por pessoas e nunca são sobrescritos pela automação. Todos os parâmetros podem ser mudados por variável de ambiente (veja `.env.example`).

---

## Autonomia e resiliência

| Situação | Como o pipeline reage |
| --- | --- |
| Arquivo de sensor corrompido ou de motor não cadastrado | Vai para `data/quarentena/` com um `.motivo.json`; o ciclo segue |
| Uma etapa lança exceção | Registrada no log; as demais etapas executam; ciclo marcado como `parcial` |
| Falha ao processar um ativo | Só aquele ativo é pulado; os outros são avaliados |
| Escrita no banco falha no meio de um ativo | A transação desfaz tudo daquele ativo (status, evento, histórico, auditoria) |
| Ollama indisponível | Disjuntor pula a IA por alguns minutos; recomendação sai das regras + manuais |
| FAISS/modelo de embeddings ausentes | Busca léxica BM25 assume automaticamente |
| API de clima ou catálogo online fora do ar | Nova tentativa com espera crescente; depois, catálogo local e valor padrão |
| Sensor sem sinal | O ativo é marcado como "sem leitura nova" e **não** conta como leitura normal |
| Falha de e-mail | Registrada; o evento já está salvo |
| Falhas seguidas de ciclo inteiro | Espera crescente (backoff) até 5 minutos |
| Ctrl+C / SIGTERM | Termina o ciclo atual e encerra |

---

## Como executar

### Dependências

```bash
pip install -r requirements-core.txt     # pipeline, testes, demonstração
pip install -r requirements.txt          # completo: dashboard, FAISS, Ollama, MCP
```

### Demonstração reproduzível

```bash
python scripts/executar_rpa_integrado.py --demo
```

Recria o banco e roda 14 ciclos com um roteiro fixo: um alerta crítico atendido por técnico, um alerta leve que se resolve sozinho, uma vibração que escala de alerta para crítica, uma queda de tensão, arquivos corrompidos, um sensor sem sinal e uma etapa que falha de propósito. Ao final, gera a pasta `evidencias/`.

### Modo contínuo (produção simulada)

```bash
python scripts/executar_rpa_integrado.py --continuo --simular --intervalo 20
```

Sem `--simular`, o orquestrador lê os CSV que chegarem em `data/raw/`. Com Docker: `docker compose up`.

### Um único ciclo

```bash
python scripts/executar_rpa_integrado.py --unico
```

### Ações da equipe de manutenção

```bash
python scripts/gerenciar_eventos.py listar
python scripts/gerenciar_eventos.py assumir  MTR-L01-BOM-001 --tecnico maria.silva
python scripts/gerenciar_eventos.py resolver MTR-L01-BOM-001 --tecnico maria.silva --resolucao "Rolamento trocado"
python scripts/gerenciar_eventos.py historico MTR-L01-BOM-001
```

### Com IA generativa (opcional)

```bash
ollama pull llama3.2 && ollama serve
python scripts/executar_rpa_integrado.py --demo      # a origem passa a ser llm+rag
```

Para forçar o modo sem IA: `--sem-llm`.

### Validação e testes

```bash
python scripts/validar_cs04.py          # 10 verificações de integridade
python -m pytest tests -q               # 42 testes (25 novos da Sprint 4: 8 de regras e 17 de ciclo de vida, resiliência e ponta a ponta)
```

---

## Evidências de execução

Pasta `evidencias/`, gerada por uma execução real da demonstração:

| Arquivo | Conteúdo |
| --- | --- |
| `RELATORIO_EVIDENCIAS.md` | Leitura humana: verificações, fluxo de cada evento, ciclos, exceções tratadas |
| `trilha_ponta_a_ponta.csv` | Uma linha por evento: alerta → status → recomendação → OS → encerramento |
| `logs/execucao.jsonl` | Log estruturado (uma linha JSON por registro, com `run_id`, ciclo, etapa e ativo) |
| `predicta_evidencia.db` | Cópia do banco SQLite ao final da execução |
| `historico_eventos.csv`, `eventos_operacionais.csv`, `manutencoes.csv`, `auditoria_operacional.csv` | Tabelas do banco |
| `execucoes_etapas.csv` | Duração e resultado de cada etapa em cada ciclo |
| `notificacoes/` | E-mails de alerta simulados (HTML) |
| `contexto_rag/` | Documentos entregues ao assistente |

---

## Estrutura do repositório

```
├── src/
│   ├── integracao/                 ← NOVO (Sprint 4)
│   │   ├── orquestrador.py         ciclo e laço contínuo
│   │   ├── processador_ativos.py   regra → status → evento → recomendação → OS
│   │   ├── ciclo_vida_eventos.py   estados, histórico, auditoria encadeada
│   │   ├── avaliacao.py            regras de severidade (única fonte)
│   │   ├── suporte_operacional.py  recomendação (regras + RAG + IA opcional)
│   │   ├── playbook.py             procedimentos extraídos dos manuais
│   │   ├── contexto_rag.py         dados operacionais para o assistente
│   │   ├── limites.py              limites por motor (catálogo ou padrão)
│   │   ├── resiliencia.py          retry, disjuntor, etapa protegida
│   │   ├── log_estruturado.py      JSON Lines
│   │   ├── migracao.py             esquema novo, compatível com bancos antigos
│   │   ├── simulador.py, demo.py   telemetria simulada e roteiro da demonstração
│   │   └── evidencias.py, validacao.py
│   ├── analise/                    base de conhecimento (agora com fallback léxico), motor de decisão
│   ├── automacao/, cadastro_ativo/, coleta/, persistencia/, scraping/, dashboard/, mcp/   (sprints anteriores, ajustados)
├── scripts/                        executar_rpa_integrado, gerenciar_eventos, validar_cs04, gerar_evidencias_cs04, ...
├── database/                       schema.sql + schema_cs04.sql
├── data/                           manuais, amostras, catálogo de exemplo
├── docs/                           CS04_DOCUMENTO_TECNICO.md, CS04_CHECKLIST_ADERENCIA.md (+ CS02)
├── notebooks/                      Predicta_Sprint4_Colab.ipynb
├── evidencias/                     saída da execução ponta a ponta
└── tests/                          42 testes
```

---

## Mapeamento com o enunciado

| Entregável / critério | Atendido por |
| --- | --- |
| Pipeline integrado de RPA (atualização de status, registro de eventos, acionamento de suporte) | `src/integracao/` + `scripts/executar_rpa_integrado.py` |
| Evidência de execução ponta a ponta | `evidencias/` (alerta → status → recomendação) |
| Integração de ponta a ponta | Orquestrador chama as automações das sprints 1 a 3 e as novas, na mesma sequência e no mesmo banco |
| Autonomia e resiliência (Try/Catch) | Seção [Autonomia e resiliência](#autonomia-e-resiliência), testes em `tests/test_cs04_ciclo_vida.py` |
| Qualidade e organização do código | Módulos pequenos com uma responsabilidade, regras em um só lugar, configuração por ambiente, 42 testes |

O checklist detalhado está em [`docs/CS04_CHECKLIST_ADERENCIA.md`](docs/CS04_CHECKLIST_ADERENCIA.md) e o documento técnico em [`docs/CS04_DOCUMENTO_TECNICO.md`](docs/CS04_DOCUMENTO_TECNICO.md).

---

## Decisões e limitações

- **IA generativa é opcional.** O Ollama melhora a redação do diagnóstico, mas a recomendação (passos, prazos e referências) vem das regras e dos manuais. Assim, o fluxo nunca fica parado por causa da IA e a origem de cada recomendação fica gravada (`llm+rag`, `regras+rag` ou `regras`).
- **As evidências incluídas no repositório** foram geradas com Ollama (llama3.2) e busca semântica (FAISS + all-MiniLM-L6-v2). Sem esses recursos, o pipeline continua funcionando com regras e busca léxica, e a origem de cada recomendação fica registrada.
- **Catálogo do fabricante.** O catálogo local é uma amostra didática; os valores de ABB M3AA, Siemens SIMOTICS SD e Baldor Super-E foram acrescentados para cobrir todos os motores da planta e são ilustrativos. Em produção, aponte `CATALOGO_URL` para a fonte real.
- **Status por leitura mais recente.** A classificação usa a última leitura de cada ativo. Para reduzir alarmes falsos, o encerramento exige 3 leituras normais seguidas (configurável).
- **E-mail simulado.** O envio grava um HTML em `logs/notificacoes/`. Trocar por SMTP exige mexer só em `notificacao_service.py`.
- **MCP somente leitura.** As ferramentas MCP consultam eventos, histórico, manuais e contexto, mas não fecham eventos: o encerramento é sempre uma ação de pessoa (CLI) ou da regra de normalização.
- **Problemas do legado corrigidos nesta sprint:** eventos que nunca fechavam, ordem de serviço repetida a cada ciclo, limites do catálogo ignorados por diferença de nome do modelo, catálogo duplicado a cada coleta, chat do dashboard consultando colunas inexistentes e `cadastro_ativos.csv` tratado como telemetria.

---

## Sprints anteriores

Os detalhes das Sprints 1 a 3 continuam abaixo e permanecem válidos.

<a id="cs01-baseline"></a>
<details>
<summary><strong>Challenge Sprint 01 — Baseline</strong> (telemetria, persistência, anomalias, dashboard original)</summary>

### Objetivo da Sprint 01

Automatizar o fluxo **CSV → validação → SQLite → análise de anomalias → dashboard**, simulando ingestão de sensores IoT em motores elétricos industriais.

### Visão geral

- **Coleta** de dados em CSV (`leituras_<CODIGO_MOTOR>.csv`)
- **Validação e normalização** das leituras
- **Persistência** em SQLite
- **Detecção e classificação** de anomalias (severidade)
- **Dashboard** Gradio (abas: Visão Geral, Motores, Telemetria, Anomalias)
- **Logs** estruturados

### Problema de negócio

Motores industriais param sem aviso prévio, causando prejuízos em linhas de produção. Manutenção preditiva exige *pipeline* robusto e auditável.

### Solução (CS01)

*Pipeline* RPA modular em Python: do CSV bruto ao dashboard, com histórico em banco e rastreabilidade via logs.

### Arquitetura (CS01)

```text
┌────────────────────────────────────────────┐
│  data/raw/*.csv  (CSVs de entrada)         │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  PIPELINE RPA (src/coleta/pipeline.py)     │
│   Extract → Transform → Load               │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  SQLite (database/motores.db)              │
│  + data/processed/  (CSVs já ingeridos)    │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  ANÁLISE (src/analise/analisador.py)       │
│   Detecção e classificação de anomalias   │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  Dashboard Gradio + Logs estruturados      │
└────────────────────────────────────────────┘
```

### Stack técnica

| Camada               | Tecnologia          |
| -------------------- | ------------------- |
| Linguagem            | Python 3.12         |
| Banco de Dados       | SQLite 3            |
| Manipulação de dados | Pandas              |
| Dashboard            | Gradio + Plotly     |
| Logs                 | `logging` (stdlib)  |

### Como executar (somente fluxo CS01)

**Pré-requisitos:** Python 3.12+, Git.

**1. Clone e ambiente virtual**

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**2. Dependências e banco**

```bash
pip install -r requirements.txt
python scripts/init_db.py
python scripts/cadastrar_motores.py
```

**3. Dados de telemetria (apenas leituras)**

**Windows (PowerShell):** `Copy-Item data/samples/leituras_*.csv data/raw/`  
**Linux / macOS:** `cp data/samples/leituras_*.csv data/raw/`

> O *pipeline* espera arquivos `leituras_<CODIGO_MOTOR>.csv` em `data/raw/`. Após processar, move para `data/processed/` com *timestamp*.

**4. Pipeline, análise e dashboard**

```bash
python scripts/executar_pipeline.py
python scripts/analisar_leituras.py
python scripts/run_dashboard.py
```

Abra **http://localhost:7860** e utilize as quatro abas originais.


### Estrutura relevante (visão CS01)

```text
rpa-cs01/
├── data/raw|processed|samples/
├── database/schema.sql
├── scripts/
│   ├── init_db.py
│   ├── cadastrar_motores.py
│   ├── executar_pipeline.py
│   ├── analisar_leituras.py
│   ├── run_dashboard.py
│   ├── diagnostico_banco.py
│   ├── inspecionar_db.py
│   ├── limpar_banco.py
│   └── validar_deteccao.py
└── src/
    ├── analise/
    ├── coleta/
    ├── dashboard/   (app.py, data_service.py, theme.py)
    └── persistencia/ (database, motor, leitura, anomalia)
```

### Decisões técnicas (CS01)

- SQLite embarcado; arquitetura em camadas; *repository pattern*; convenção `leituras_<CODIGO>.csv`; logs em `logs/`; dados gerados localmente conforme `.gitignore`.

### Funcionalidades do dashboard (CS01)

- **Visão Geral**, **Motores**, **Telemetria**, **Anomalias** (aba Digital Twin é **CS02** — ver seção dobrável seguinte).

### Scripts utilitários (CS01)

| Script | Função |
|--------|--------|
| `scripts/diagnostico_banco.py` | Diagnóstico do banco |
| `scripts/inspecionar_db.py` | Inspeção rápida |
| `scripts/limpar_banco.py` | Reset para testes |
| `scripts/validar_deteccao.py` | Testes da lógica de detecção |

</details>

<a id="cs02-evolucao"></a>
<details>
<summary><strong>Challenge Sprint 02 — Evolução</strong> (TAG, planta, placa simulada, Digital Twin, auditoria)</summary>

### Objetivo da Sprint 02

Contextualizar o ativo na planta industrial: **hierarquia** (planta → área → linha → localização), **TAG única**, **coordenadas** para mapa, **dados técnicos da placa** (via JSON pós-OCR simulado), **auditoria** e **aba Digital Twin Operacional** no Gradio — **sem remover** as funcionalidades da CS01.

### O que a CS02 adiciona

- Tabelas: `plantas`, `areas`, `linhas`, `localizacoes`, `associacoes_ativos`, `dados_placa_motor`, `auditoria_operacional` + *views* `vw_*` (ver `database/schema.sql`).
- Scripts: `atualizar_associacoes_ativos.py`, `processar_placas_motores.py`, `validar_cs02.py`.
- Módulos: `src/cadastro_ativo/`, repositórios adicionais em `src/persistencia/`, `src/dashboard/operational_view.py`.

### Arquitetura (CS01 + CS02)

```text
data/raw/*.csv (telemetria)          data/raw/cadastro_ativos.csv
         │                                    │
         ▼                                    ▼
  Pipeline CS01 (coleta)            RPA associação CS02
         │                                    │
         └──────────────┬─────────────────────┘
                        ▼
                 SQLite (motores + leituras + hierarquia CS02 + placa + auditoria)
                        ▼
            Análise (anomalias) + Dashboard (4 abas CS01 + Digital Twin CS02)
```

### Como executar (fluxo completo para demonstração CS02)

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/init_db.py
python scripts/cadastrar_motores.py

mkdir -p data/raw/placas_extraidas
cp data/samples/leituras_*.csv data/raw/
cp data/samples/cadastro_ativos_sample.csv data/raw/cadastro_ativos.csv
cp data/samples/placas_extraidas/*.json data/raw/placas_extraidas/

python scripts/executar_pipeline.py
python scripts/atualizar_associacoes_ativos.py
python scripts/processar_placas_motores.py
python scripts/analisar_leituras.py
python scripts/validar_cs02.py
python scripts/run_dashboard.py
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts/init_db.py
python scripts/cadastrar_motores.py

New-Item -ItemType Directory -Force data\raw\placas_extraidas
Copy-Item data\samples\leituras_*.csv data\raw\
Copy-Item data\samples\cadastro_ativos_sample.csv data\raw\cadastro_ativos.csv
Copy-Item data\samples\placas_extraidas\*.json data\raw\placas_extraidas\

python scripts/executar_pipeline.py
python scripts/atualizar_associacoes_ativos.py
python scripts/processar_placas_motores.py
python scripts/analisar_leituras.py
python scripts/validar_cs02.py
python scripts/run_dashboard.py
```

**Dashboard:** http://localhost:7860

### Aba “Digital Twin Operacional”

1. Navegue **Planta → Área → Linha → TAG** ou use **Buscar TAG**.  
2. Veja **status visual**, **última leitura** (temperatura, vibração, corrente, tensão, RPM) e **dados da placa** (quando existirem).  
3. Altere a **métrica** do histórico e o **mapa** (*scatter* com coordenadas).  
4. Perfis **manutenção / engenharia / admin** são **demonstrativos** (sem autenticação real).

### TAGs de exemplo

- `MTR-L01-BOM-001` (motor `MTR-001`)  
- `MTR-L01-EST-002` (`MTR-002`)  
- `MTR-L02-CMP-003` (`MTR-003`)  
- `MTR-UTIL-EXA-004` (`MTR-004`)  
- `MTR-ENV-TRP-005` (`MTR-005`)

### Testes e validação

```bash
pytest tests/ -q
python scripts/validar_cs02.py
```

### Documentação CS02 (Markdown + Word)

| Arquivo | Uso |
|---------|-----|
| `docs/CS02_DOCUMENTO_TECNICO.md` | Fonte versionável (*markdown*) |
| `docs/CS02_DOCUMENTO_TECNICO_PARA_WORD.txt` | Colar no Word/Google Docs → exportar PDF |
| `docs/CS02_ROTEIRO_VIDEO.md` | Roteiro 3–5 min com tempos e comandos |
| `docs/CS02_CHECKLIST_ADERENCIA.md` | Matriz enunciado × implementação |

### Entregáveis CS02 (mapeamento)

| Entregável | Onde |
|------------|------|
| RPA associação | `src/cadastro_ativo/`, `scripts/atualizar_associacoes_ativos.py` |
| RPA placa (JSON) | `src/cadastro_ativo/placa_pipeline.py`, `scripts/processar_placas_motores.py` |
| Digital Twin | `src/dashboard/operational_view.py` |
| Validação | `scripts/validar_cs02.py` |

### Limitações (CS02)

- OCR real **não** está no repositório; usa-se JSON estruturado.  
- Controle de perfis na UI é **acadêmico**, não segurança de produção.

### Estrutura completa do repositório (pós-CS02)

```text
rpa-cs01/
├── data/
├── database/
├── docs/
├── logs/
├── scripts/   (+ atualizar_associacoes_ativos, processar_placas_motores, validar_cs02)
└── src/
    ├── analise/
    ├── cadastro_ativo/
    ├── coleta/
    ├── dashboard/   (+ operational_view.py)
    └── persistencia/ (+ repositórios CS02)
```

*(Árvore resumida; detalhes nos arquivos fonte.)*

</details>

<a id="cs03-inteligencia"></a>
<details>
<summary><strong>Challenge Sprint 03 — Inteligência & Automação Avançada</strong> (Agentes de IA, RAG, Web Scraping e MCP)</summary>

### Objetivo da Sprint 03

Elevar o sistema a um **Nível 4 de Maturidade Digital Industrial**. Transformamos o sistema reativo em um ecossistema inteligente, capaz de analisar manuais, prever ações com IA Generativa, buscar contexto climático da planta em tempo real e orquestrar eventos sem interferência humana.

### O que a CS03 adiciona

- **Agentic RPA com Llama 3.2 (Ollama):** O sistema não apenas detecta o problema; ele emite diagnósticos profundos de engenharia para falhas nos motores usando IA local.
- **RAG com FAISS e Sentence-Transformers:** O modelo embasa as decisões de manutenção lendo manuais operacionais reais através da Busca Semântica em banco de dados vetorial.
- **Web Scraping Avançado (Scrapling + Fallback Automático):** Os dados técnicos dos motores (RPM, correntes, tensão) são atualizados em tempo real via scraping de um catálogo web normativo.
- **Model Context Protocol (MCP):** Arquitetura moderna de abstração para conexão e escalabilidade segura de ferramentas do sistema via protocolos padronizados de IA.
- **Integração Open-Meteo:** O motor de contexto ganha ciência de fatores ambientais locais (temperatura da planta, clima) que influenciam a operação.
- **Ecossistema Vivo e Assíncrono:** O `simulador_iot_stream.py` com o `orquestrador_eventos.py` rodam um ciclo contínuo ininterrupto.
- **Aba '🧠 IA & Decisão':** O Gradio recebe a nova aba contendo Painel de Eventos, Chatbot integrado aos manuais da planta e alertas em tempo real.

### Arquitetura (CS01 + CS02 + CS03)

```text
 ┌──────────────────────────────────────────────┐
 │                  Scrapling                   │  <-- Atualiza specs (Scraping)
 └──────────────────────┬───────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────┐
 │             Simulador IoT Stream             │  <-- Telemetria Real-Time
 └──────────────────────┬───────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────┐
 │                Banco de Dados                │  <-- SQL Relacional (CRUD Autônomo)
 └──────────────────────┬───────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────┐
 │        Orquestrador de Eventos (RPA)         │  <-- Transacional (Eventos)
 └──────────────────────┬───────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────┐
 │            Motor de Decisão (IA)             │  <-- Ollama + FAISS RAG
 └──────────────────────┬───────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────┐
 │        Dashboard Operacional (Gradio)        │  <-- Visões + Dossiê de IA
 └──────────────────────────────────────────────┘
```

### Como executar (fluxo completo para demonstração CS03)

**macOS / Linux**

```bash
# 1. Ative seu ambiente e instale dependências da CS03
source .venv/bin/activate
pip install -r requirements.txt

# 2. Inicialize o banco limpo e cadastre motores base
python scripts/limpar_banco.py
python scripts/init_db.py
python scripts/cadastrar_motores.py
python scripts/atualizar_associacoes_ativos.py

# 3. Inicialize os serviços de base (Opcional, porém recomendado para rodar IA)
# Garanta que a API local do Ollama está ativa com o modelo Llama 3.2:
# ollama run llama3.2

# 4. Rode a esteira completa End-to-End da CS03 (Validação e Inicialização)
python scripts/validar_cs03.py

# 5. Inicie o Stream de IoT Autônomo em um terminal
python scripts/simulador_iot_stream.py

# 6. Em outro terminal, suba o Painel de Controle Integrado
python scripts/run_dashboard.py
```

**Dashboard:** Abra no navegador http://localhost:7860

Navegue para a nova aba **"🧠 IA & Decisão"**:
1. Veja o painel de **Diagnóstico Autônomo de Engenharia**, mostrando a severidade e causa raiz calculada pelo Ollama.
2. Interaja com o **Chatbot Mestre de Manutenção**, que tem o contexto completo da planta via RAG (FAISS) e MCP.
3. Observe como os alertas de telemetria pipocam via **Painel Operacional**.

### Valor de Negócio CS03

Esse pipeline foi pensado de forma aderente à **Industria 4.0**. O RAG permite que a IA tome decisões restritas ao manual de catálogo daquele modelo de motor específico, reduzindo alucinações (Zero Hallucination Tolerance). A camada Open-Meteo evita falsos-positivos termográficos ao levar em conta frentes frias ou ondas de calor na planta.

</details>

---

## 📄 Licença

Trabalho acadêmico — **FIAP 2026**. Uso educacional.
