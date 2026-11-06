# 🏭 Relatório Técnico — Digital Twin & RPA (Sprint 2)
**Predicta — RPA Industrial (FIAP 2026)**

---

## 1. Mapeamento da Associação Ativo-TAG-Localização

O modelo de dados implementado no SQLite (`database/motores.db`) visa contextualizar os ativos industriais (`motores`) dentro da estrutura física da planta.

### Estrutura Hierárquica da Planta
A hierarquia física foi modelada com as seguintes tabelas de suporte:
1. **Plantas (`plantas`)**: Identifica a unidade fabril (ex: `PLT-PRD-01`).
2. **Áreas (`areas`)**: Divisões internas da planta (ex: `AR-PINT`, `AR-MONT`).
3. **Linhas (`linhas`)**: Linhas de produção ou utilidades dentro da área (ex: `LIN-TRP`).
4. **Localizações (`localizacoes`)**: Ponto geográfico específico contendo as coordenadas `coordenada_x` e `coordenada_y`.

### Associação Automatizada (RPA)
A tabela `associacoes_ativos` vincula a entidade física `motores` à sua respectiva identificação lógica (`tag`) e espacial (`localizacao_id`).
- **Idempotência**: O pipeline de RPA em `src/cadastro_ativo/ativo_association_pipeline.py` lê os cadastros de `data/raw/cadastro_ativos.csv`. Se as informações não mudaram, a associação é mantida como `inalterada`. Caso haja modificação espacial ou de TAG, o registro é atualizado, gerando rastreabilidade.
- **Auditoria Operacional**: Qualquer mudança de associação gera uma entrada na tabela `auditoria_operacional`, contendo o usuário/origem da ação, data, ação realizada (criação/atualização) e o estado do registro.

---

## 2. Processo de Integração dos Dados da Placa no Cadastro

Para evitar digitação manual dos dados técnicos das placas de motores (potência, corrente nominal, tensão, RPM, fabricante), foi desenvolvido um pipeline de integração que simula um sistema OCR.

### Pipeline de Dados
```text
[Imagem da Placa] ──> (OCR / Processamento Externo) ──> [JSON estruturado em data/raw/placas_extraidas/]
                                                                │
                                                                ▼
                                                [scripts/processar_placas_motores.py]
                                                                │
                                                                ▼
                                                [Validação técnica (placa_validator.py)]
                                                                │
                                                                ▼
                                                [Persistência SQLite (dados_placa_motor)]
```

1. **Geração**: Os dados extraídos da imagem da placa são armazenados em formato JSON na pasta `data/raw/placas_extraidas/`.
2. **Validação**: O script `src/cadastro_ativo/placa_validator.py` verifica a integridade do JSON, assegurando que os campos como `codigo_motor`, `tensao_nominal`, `corrente_nominal`, `rpm_nominal` e `confianca_extracao` estejam preenchidos e válidos.
3. **Persistência**: O repositório `placa_motor_repository.py` realiza um *upsert* na tabela `dados_placa_motor`.
4. **Arquivamento**: O arquivo JSON processado é movido com um *timestamp* para a pasta `data/processed/placas_extraidas/` para evitar reprocessamento e manter o histórico.
