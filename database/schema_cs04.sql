-- ============================================================
-- Sprint 4 - Integração da solução e suporte operacional
-- Objetos novos (idempotente). As colunas adicionadas em tabelas
-- existentes ficam em src/integracao/migracao.py (ALTER TABLE).
-- ============================================================

-- Histórico de cada mudança de estado de um evento (rastreabilidade)
CREATE TABLE IF NOT EXISTS historico_eventos (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id             INTEGER NOT NULL,
    status_anterior       TEXT,
    status_novo           TEXT    NOT NULL,
    acao                  TEXT    NOT NULL,
    ator                  TEXT    NOT NULL,
    observacao            TEXT,
    status_ativo_anterior TEXT,
    status_ativo_novo     TEXT,
    run_id                TEXT,
    criado_em             TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evento_id) REFERENCES eventos_operacionais(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_hist_evento ON historico_eventos(evento_id, id);

-- Uma linha por ciclo de execução da automação
CREATE TABLE IF NOT EXISTS execucoes_pipeline (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT    NOT NULL,
    ciclo       INTEGER NOT NULL,
    modo        TEXT,
    inicio      TEXT    NOT NULL,
    fim         TEXT,
    status      TEXT,
    resumo_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_run ON execucoes_pipeline(run_id, ciclo);

-- Uma linha por etapa de cada ciclo
CREATE TABLE IF NOT EXISTS execucoes_etapas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT    NOT NULL,
    ciclo         INTEGER NOT NULL,
    etapa         TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    duracao_ms    INTEGER,
    detalhes_json TEXT,
    erro          TEXT,
    criado_em     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_etapas_run ON execucoes_etapas(run_id, ciclo);

DROP VIEW IF EXISTS vw_eventos_abertos;
CREATE VIEW vw_eventos_abertos AS
SELECT
    e.id AS evento_id, e.tag_ativo, e.codigo_motor, e.severidade,
    e.status_resolucao, e.ocorrencias, e.ciclos_normais, e.prioridade,
    e.prazo_horas, e.origem_recomendacao, e.descricao_anomalia,
    e.diagnostico_ia, e.acao_recomendada, e.manutencao_id,
    e.created_at AS aberto_em, e.atualizado_em
FROM eventos_operacionais e
WHERE e.status_resolucao IN ('pendente', 'encaminhado', 'em_atendimento');

DROP VIEW IF EXISTS vw_trilha_eventos;
CREATE VIEW vw_trilha_eventos AS
SELECT
    e.id AS evento_id, e.tag_ativo, e.codigo_motor, e.severidade,
    e.status_resolucao, e.ocorrencias, e.origem_recomendacao,
    e.created_at AS aberto_em, e.encerrado_em, e.encerrado_por, e.resolucao,
    e.manutencao_id, m.tipo AS os_tipo, m.status AS os_status,
    m.prioridade AS os_prioridade,
    (SELECT COUNT(*) FROM historico_eventos h WHERE h.evento_id = e.id) AS transicoes
FROM eventos_operacionais e
LEFT JOIN manutencoes m ON m.id = e.manutencao_id;
