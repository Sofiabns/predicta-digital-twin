# Evidências de execução ponta a ponta - Sprint 4

Gerado em 06/11/2026 18:29:36 a partir do banco `predicta_evidencia.db` e do log `logs/execucao.jsonl`.

## 1. Resultado das verificações de integridade

| Verificação | Resultado | Detalhe |
|---|---|---|
| Existe ao menos um evento registrado | OK | 4 evento(s) |
| Todo evento tem diagnóstico, ação e procedimentos | OK | 0 sem recomendação |
| Todo evento tem histórico de transições | OK | 0 sem histórico |
| No máximo um evento aberto por ativo | OK | 0 ativo(s) com duplicidade |
| Todo evento resolvido tem data e descrição de encerramento | OK | 0 inconsistente(s) |
| Nenhum ativo em 'atenção/crítico' sem evento aberto | OK | 0 divergência(s) entre status e eventos |
| Uma ordem de manutenção por evento (sem duplicidade) | OK | 0 evento(s) com OS repetida |
| Cadeia de hashes da auditoria íntegra | OK | 26 registro(s) verificados: ok |
| Execuções de ciclo registradas no banco | OK | 15 ciclo(s) |
| Log estruturado contém o fluxo alerta → status → recomendação | OK | 378 linhas JSON |

## 2. Fluxo alerta → status → recomendação, por evento

### Evento 1 - MTR-L01-BOM-001 (CRITICO, resolvido)

1. **Alerta detectado** em 2026-11-06 18:27:55. Leitura que motivou a classificação: 2026-08-25 06:30:00 | 88.11 °C | 5.03 mm/s | 15.07 A | 384.72 V.
   Temperatura 88.1°C excede o limite de 85°C. Vibração 5.03 mm/s excede o limite de 2.8 mm/s (zona D da ISO 10816-3).
2. **Status do ativo:** operacional→critico; critico→manutencao; manutencao→operacional.
3. **Recomendação técnica** (origem: llm+rag; 9 procedimentos, 4 referências):
   - Diagnóstico: Alta Temperatura (acima da classe) combinada com Vibração alta, indicando sobrecarga severa com desalinhamento ou falta grave de lubrificação nos mancais.
   - Ação: Parar a máquina, drenar a graxa velha, re-lubrificar mancais e checar alinhamento a laser.
4. **Encaminhamento:** ordem #1 (corretiva, urgente) para Equipe de Manutenção.
5. **Encerramento:** 2026-11-06 18:28:40, por tecnico:tecnico.turno_a. Resolvido por tecnico.turno_a: Realinhado o eixo a laser e trocado o rolamento do lado acoplado; vibração normalizada.
   Linha do tempo: abertura(pendente) > encaminhamento(encaminhado) > atendimento(em_atendimento) > resolucao(resolvido).

### Evento 2 - MTR-L01-EST-002 (ALERTA, resolvido)

1. **Alerta detectado** em 2026-11-06 18:28:18. Leitura que motivou a classificação: 2026-11-06 16:36:00 | 80.2 °C | 1.74 mm/s | 14.49 A | 384.48 V.
   Temperatura 80.2°C está próxima do limite de 85°C.
2. **Status do ativo:** operacional→atencao; atencao→operacional.
3. **Recomendação técnica** (origem: llm+rag; 4 procedimentos, 4 referências):
   - Diagnóstico: Carga demandada no eixo é superior à nominal, causando o aquecimento anormal.
   - Ação: Reduzir a carga operacional e confirmar se a corrente está acima da nominal da placa.
4. **Encaminhamento:** ordem #2 (preventiva, media) para Equipe de Manutenção.
5. **Encerramento:** 2026-11-06 18:28:42, por RPA_PREDICTA. Normalizado automaticamente após 3 leituras consecutivas dentro dos limites.
   Linha do tempo: abertura(pendente) > encaminhamento(encaminhado) > resolucao(resolvido).

### Evento 3 - MTR-UTIL-EXA-004 (CRITICO, resolvido)

1. **Alerta detectado** em 2026-11-06 18:28:36. Leitura que motivou a classificação: 2026-11-06 17:06:00 | 71.0 °C | 2.78 mm/s | 14.19 A | 382.51 V.
   Vibração 2.78 mm/s excede o limite de 2.5 mm/s (zona B da ISO 10816-3).
2. **Status do ativo:** operacional→atencao; atencao→critico; critico→operacional.
3. **Recomendação técnica** (origem: llm+rag; 4 procedimentos, 4 referências):
   - Diagnóstico: Desalinhamento mecânico do eixo com a carga.
   - Ação: Usar alinhador a laser para corrigir alinhamento de base.
4. **Encaminhamento:** ordem #3 (corretiva, urgente) para Equipe de Manutenção.
5. **Encerramento:** 2026-11-06 18:29:14, por RPA_PREDICTA. Normalizado automaticamente após 3 leituras consecutivas dentro dos limites.
   Linha do tempo: abertura(pendente) > encaminhamento(encaminhado) > escalonamento(encaminhado) > resolucao(resolvido).

### Evento 4 - MTR-ENV-TRP-005 (ALERTA, resolvido)

1. **Alerta detectado** em 2026-11-06 18:29:09. Leitura que motivou a classificação: 2026-11-06 17:36:00 | 64.61 °C | 1.19 mm/s | 15.73 A | 352.0 V.
   Tensão 352.0 V fora da faixa de 361–399 V (desvio de 7.4% sobre a nominal de 380 V).
2. **Status do ativo:** operacional→atencao; atencao→operacional.
3. **Recomendação técnica** (origem: llm+rag; 3 procedimentos, 4 referências):
   - Diagnóstico: Desvio de tensão na entrada do motor, tendo a tensão 352,0 V fora da faixa de 361–399 V, com desvio de 7,4% sobre a nominal de 380 V.
   - Ação: A equipe elétrica deve verificar a rede para subtensão ou sobretensão.
4. **Encaminhamento:** ordem #4 (preventiva, media) para Equipe de Manutenção.
5. **Encerramento:** 2026-11-06 18:29:28, por RPA_PREDICTA. Normalizado automaticamente após 3 leituras consecutivas dentro dos limites.
   Linha do tempo: abertura(pendente) > encaminhamento(encaminhado) > resolucao(resolvido).

## 3. Status final dos ativos

| TAG | Motor | Status | Atualizado por | Temp. (°C) | Vibr. (mm/s) |
|---|---|---|---|---|---|
| MTR-ENV-TRP-005 | MTR-005 | operacional | RPA_PREDICTA | 65.92 | 1.22 |
| MTR-L01-BOM-001 | MTR-001 | operacional | tecnico:tecnico.turno_a | 72.79 | 1.75 |
| MTR-L01-EST-002 | MTR-002 | operacional | RPA_PREDICTA | 70.6 | 1.77 |
| MTR-L02-CMP-003 | MTR-003 | manutencao | rpa_integrado_cadastro | 64.06 | 1.18 |
| MTR-UTIL-EXA-004 | MTR-004 | operacional | RPA_PREDICTA | 64.19 | 1.2 |

## 4. Ciclos executados

| Ciclo | Status | Etapas com ressalva ou falha |
|---|---|---|
| 0 | sucesso | - |
| 1 | sucesso | - |
| 2 | sucesso | - |
| 3 | sucesso | - |
| 4 | sucesso | - |
| 5 | sucesso | - |
| 6 | parcial | coleta: degradado |
| 7 | parcial | analise: falha |
| 8 | sucesso | - |
| 9 | sucesso | - |
| 10 | sucesso | - |
| 11 | sucesso | - |
| 12 | sucesso | - |
| 13 | sucesso | - |
| 14 | sucesso | - |

## 5. Tratamento de exceções observado

- Ciclo 7 / analise: Etapa 'analise' falhou: RuntimeError: falha simulada na etapa 'analise' (teste de resiliência)
- Ciclo 7 / analise: Etapa 'analise' terminou com status falha
- Ciclo 6 / coleta: leituras_MTR-003.csv não pôde ser processado (sem_registros_validos); movido para quarentena
- Ciclo 6 / coleta: leituras_MTR-099.csv não pôde ser processado (motor_nao_cadastrado); movido para quarentena
- Ciclo 6 / avaliacao: Nenhuma leitura nova; ativo mantido como está
- Ciclo 8 / avaliacao: Nenhuma leitura nova; ativo mantido como está

## 6. Modo de execução

- Recomendações geradas: 5 (llm+rag)
- Busca na base de conhecimento: semantico
- Contexto climático: obtido

## 7. Arquivos desta pasta

- `trilha_ponta_a_ponta.csv`: uma linha por evento, do alerta ao encerramento
- `eventos_operacionais.csv`, `historico_eventos.csv`, `manutencoes.csv`, `auditoria_operacional.csv`
- `execucoes_etapas.csv`: duração e resultado de cada etapa em cada ciclo
- `status_final_ativos.csv`: estado dos motores ao final
- `logs/execucao.jsonl`: log estruturado (uma linha JSON por registro)
- `notificacoes/`: e-mails de alerta simulados
- `contexto_rag/`: documentos entregues ao assistente
- `predicta_evidencia.db`: cópia do banco SQLite ao final da execução
