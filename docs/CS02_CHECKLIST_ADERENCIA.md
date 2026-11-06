# 📋 Checklist de Aderência — Sprint 2
**Predicta — RPA Industrial (FIAP 2026)**

Este documento mapeia os requisitos exigidos no enunciado da Sprint 2 com os respectivos arquivos e lógicas implementadas no repositório.

| Requisito / Entregável solicitado | Arquivo / Componente no Repositório | Descrição da Implementação |
|:---|:---|:---|
| **Estrutura de Navegação** (hierarquia) | `src/persistencia/planta_repository.py`<br>`src/dashboard/data_service.py` | Lógica de consulta aninhada para obter Plantas ➔ Áreas ➔ Linhas ➔ TAGs na interface gráfica do Gradio. |
| **Associação Automatizada (RPA)** | `src/cadastro_ativo/ativo_association_pipeline.py`<br>`scripts/atualizar_associacoes_ativos.py` | RPA que consome `cadastro_ativos.csv`, cria a árvore hierárquica, associa o motor à sua TAG e salva no SQLite. |
| **Visualização de Dados** (atuais/históricos) | `src/dashboard/operational_view.py` | Exibição de KPIs dinâmicos (HTML/CSS) com a última leitura do sensor e gráficos temporais via Plotly. |
| **Interface de Consulta** (Real-Time) | `src/dashboard/operational_view.py` | Aba "Digital Twin Operacional" no Gradio contendo navegação hierárquica e busca por string de TAG. |
| **Integração de Dados Técnicos** | `src/cadastro_ativo/placa_pipeline.py`<br>`scripts/processar_placas_motores.py` | Pipeline de OCR simulado que lê arquivos JSON extraídos de placas, valida dados e associa ao motor. |
| **Garantia de Rastreabilidade** | `src/persistencia/auditoria_repository.py` | Tabela `auditoria_operacional` preenchida automaticamente a cada alteração de dados do ativo. |
| **Preparação para Machine Learning** | `src/persistencia/leitura_repository.py` | Histórico de leituras estruturado em banco SQLite adequado para treinamento futuro de modelos. |
