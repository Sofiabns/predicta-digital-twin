-- ============================================================
-- RPA-CS01 Predicta - Schema do Banco de Dados
-- SGBD: SQLite 3
-- Autor: Felipe de Oliveira Cabral e grupo
-- ============================================================

-- Habilita integridade referencial (FK)
PRAGMA foreign_keys = ON;

-- ============================================================
-- TABELA: motores
-- Cadastro dos motores industriais monitorados
-- ============================================================
CREATE TABLE IF NOT EXISTS motores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT    NOT NULL UNIQUE,
    modelo          TEXT    NOT NULL,
    fabricante      TEXT,
    localizacao     TEXT    NOT NULL,
    potencia_kw     REAL    CHECK (potencia_kw > 0),
    data_instalacao TEXT,
    status          TEXT    NOT NULL DEFAULT 'ativo'
                    CHECK (status IN ('ativo', 'inativo', 'manutencao')),
    criado_em       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_motores_codigo ON motores(codigo);
CREATE INDEX IF NOT EXISTS idx_motores_status ON motores(status);

-- ============================================================
-- TABELA: leituras
-- Dados telemétricos coletados dos motores
-- ============================================================
CREATE TABLE IF NOT EXISTS leituras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    motor_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    tensao REAL CHECK (tensao IS NULL OR tensao >= 0),
    temperatura REAL,
    vibracao REAL CHECK (vibracao IS NULL OR vibracao >= 0),
    corrente REAL CHECK (corrente IS NULL OR corrente >= 0),
    rpm REAL CHECK (rpm IS NULL OR rpm >= 0),
    label_origem INTEGER CHECK (label_origem IN (0, 1) OR label_origem IS NULL),
    classe_origem TEXT CHECK (classe_origem IN ('normal', 'alerta', 'critico') OR classe_origem IS NULL),
    processado INTEGER DEFAULT 0,
    criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (motor_id) REFERENCES motores(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_leituras_motor     ON leituras(motor_id);
CREATE INDEX IF NOT EXISTS idx_leituras_timestamp ON leituras(timestamp);
CREATE INDEX IF NOT EXISTS idx_leituras_proc      ON leituras(processado);

-- ============================================================
-- TABELA: anomalias
-- Anomalias detectadas a partir das leituras
-- ============================================================
CREATE TABLE IF NOT EXISTS anomalias (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    motor_id       INTEGER NOT NULL,
    leitura_id     INTEGER NOT NULL,
    tipo           TEXT    NOT NULL
                   CHECK (tipo IN ('temperatura', 'vibracao', 'corrente', 'multipla', 'outlier_estatistico')),
    severidade     TEXT    NOT NULL
                   CHECK (severidade IN ('baixa', 'media', 'alta', 'critica')),
    valor_medido   REAL    NOT NULL,
    valor_limite   REAL    NOT NULL,
    descricao      TEXT,
    detectado_em   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notificado     INTEGER NOT NULL DEFAULT 0 CHECK (notificado IN (0, 1)),
    FOREIGN KEY (motor_id)   REFERENCES motores(id)  ON DELETE CASCADE,
    FOREIGN KEY (leitura_id) REFERENCES leituras(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_anomalias_motor      ON anomalias(motor_id);
CREATE INDEX IF NOT EXISTS idx_anomalias_severidade ON anomalias(severidade);
CREATE INDEX IF NOT EXISTS idx_anomalias_detectado  ON anomalias(detectado_em);

-- ============================================================
-- TABELA: manutencoes
-- Ordens de manutenção preditiva/corretiva
-- ============================================================
CREATE TABLE IF NOT EXISTS manutencoes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    motor_id        INTEGER NOT NULL,
    anomalia_id     INTEGER,
    tipo            TEXT    NOT NULL
                    CHECK (tipo IN ('preditiva', 'preventiva', 'corretiva')),
    status          TEXT    NOT NULL DEFAULT 'pendente'
                    CHECK (status IN ('pendente', 'agendada', 'em_andamento', 'concluida', 'cancelada')),
    prioridade      TEXT    NOT NULL DEFAULT 'media'
                    CHECK (prioridade IN ('baixa', 'media', 'alta', 'urgente')),
    descricao       TEXT    NOT NULL,
    data_prevista   TEXT,
    data_conclusao  TEXT,
    tecnico         TEXT,
    custo_estimado  REAL    CHECK (custo_estimado >= 0),
    criado_em       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (motor_id)    REFERENCES motores(id)   ON DELETE CASCADE,
    FOREIGN KEY (anomalia_id) REFERENCES anomalias(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_manutencoes_motor    ON manutencoes(motor_id);
CREATE INDEX IF NOT EXISTS idx_manutencoes_status   ON manutencoes(status);
CREATE INDEX IF NOT EXISTS idx_manutencoes_prio     ON manutencoes(prioridade);

-- ============================================================
-- VIEW: v_resumo_motores
-- Visão consolidada dos motores com estatísticas
-- ============================================================
CREATE VIEW IF NOT EXISTS v_resumo_motores AS
SELECT
    m.id,
    m.codigo,
    m.modelo,
    m.localizacao,
    m.status,
    COUNT(DISTINCT l.id)                                    AS total_leituras,
    COUNT(DISTINCT a.id)                                    AS total_anomalias,
    COUNT(DISTINCT CASE WHEN a.severidade = 'critica'
                        THEN a.id END)                      AS anomalias_criticas,
    COUNT(DISTINCT CASE WHEN mt.status = 'pendente'
                        THEN mt.id END)                     AS manutencoes_pendentes,
    MAX(l.timestamp)                                        AS ultima_leitura
FROM motores m
LEFT JOIN leituras    l  ON l.motor_id  = m.id
LEFT JOIN anomalias   a  ON a.motor_id  = m.id
LEFT JOIN manutencoes mt ON mt.motor_id = m.id
GROUP BY m.id, m.codigo, m.modelo, m.localizacao, m.status;

-- ============================================================
-- CS02 — Modelo operacional (planta / hierarquia / Digital Twin)
-- Evolução incremental da CS01; tabelas CS01 permanecem intactas.
-- ============================================================

CREATE TABLE IF NOT EXISTS plantas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo           TEXT    NOT NULL UNIQUE,
    nome             TEXT    NOT NULL,
    descricao        TEXT,
    data_criacao     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plantas_codigo ON plantas(codigo);

CREATE TABLE IF NOT EXISTS areas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    planta_id        INTEGER NOT NULL,
    codigo           TEXT    NOT NULL,
    nome             TEXT    NOT NULL,
    descricao        TEXT,
    data_criacao     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planta_id) REFERENCES plantas(id) ON DELETE CASCADE,
    UNIQUE (planta_id, codigo)
);

CREATE INDEX IF NOT EXISTS idx_areas_planta ON areas(planta_id);

CREATE TABLE IF NOT EXISTS linhas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id          INTEGER NOT NULL,
    codigo           TEXT    NOT NULL,
    nome             TEXT    NOT NULL,
    descricao        TEXT,
    data_criacao     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (area_id) REFERENCES areas(id) ON DELETE CASCADE,
    UNIQUE (area_id, codigo)
);

CREATE INDEX IF NOT EXISTS idx_linhas_area ON linhas(area_id);

CREATE TABLE IF NOT EXISTS localizacoes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    linha_id         INTEGER NOT NULL,
    codigo           TEXT    NOT NULL,
    descricao        TEXT,
    coordenada_x     REAL    NOT NULL DEFAULT 0,
    coordenada_y     REAL    NOT NULL DEFAULT 0,
    data_criacao     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (linha_id) REFERENCES linhas(id) ON DELETE CASCADE,
    UNIQUE (linha_id, codigo)
);

CREATE INDEX IF NOT EXISTS idx_localizacoes_linha ON localizacoes(linha_id);

CREATE TABLE IF NOT EXISTS associacoes_ativos (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    motor_id             INTEGER NOT NULL UNIQUE,
    tag                  TEXT    NOT NULL UNIQUE,
    localizacao_id       INTEGER NOT NULL,
    status_operacional   TEXT    NOT NULL DEFAULT 'operacional'
        CHECK (status_operacional IN (
            'operacional', 'atencao', 'manutencao', 'critico', 'parado'
        )),
    origem_atualizacao   TEXT,
    data_criacao         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (motor_id)       REFERENCES motores(id)       ON DELETE CASCADE,
    FOREIGN KEY (localizacao_id) REFERENCES localizacoes(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_assoc_tag    ON associacoes_ativos(tag);
CREATE INDEX IF NOT EXISTS idx_assoc_motor ON associacoes_ativos(motor_id);

CREATE TABLE IF NOT EXISTS dados_placa_motor (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    motor_id             INTEGER NOT NULL UNIQUE,
    fabricante           TEXT,
    modelo               TEXT,
    numero_serie         TEXT,
    potencia             REAL,
    tensao_nominal       REAL,
    corrente_nominal     REAL,
    rpm_nominal          REAL,
    frequencia           REAL,
    fator_servico        REAL,
    rendimento           REAL,
    origem_imagem        TEXT,
    origem_arquivo       TEXT,
    data_extracao        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confianca_extracao   REAL,
    data_atualizacao     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (motor_id) REFERENCES motores(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS auditoria_operacional (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade     TEXT    NOT NULL,
    entidade_id  INTEGER,
    acao         TEXT    NOT NULL,
    origem       TEXT,
    detalhes     TEXT,
    data_evento  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auditoria_entidade ON auditoria_operacional(entidade, data_evento);

-- ============================================================
-- VIEWS CS02
-- ============================================================

CREATE VIEW IF NOT EXISTS vw_ativos_operacionais AS
SELECT
    m.id                AS motor_id,
    m.codigo            AS codigo_motor,
    m.modelo            AS modelo_motor,
    m.fabricante        AS fabricante_motor,
    aa.tag,
    aa.status_operacional,
    aa.origem_atualizacao,
    aa.data_atualizacao AS associacao_atualizada_em,
    p.id                AS planta_id,
    p.codigo            AS planta_codigo,
    p.nome              AS planta_nome,
    ar.id               AS area_id,
    ar.codigo           AS area_codigo,
    ar.nome             AS area_nome,
    ln.id               AS linha_id,
    ln.codigo           AS linha_codigo,
    ln.nome             AS linha_nome,
    loc.id              AS localizacao_id,
    loc.codigo          AS localizacao_codigo,
    loc.descricao       AS localizacao_descricao,
    loc.coordenada_x    AS coordenada_x,
    loc.coordenada_y    AS coordenada_y
FROM motores m
LEFT JOIN associacoes_ativos aa ON aa.motor_id = m.id
LEFT JOIN localizacoes loc     ON loc.id = aa.localizacao_id
LEFT JOIN linhas ln            ON ln.id = loc.linha_id
LEFT JOIN areas ar             ON ar.id = ln.area_id
LEFT JOIN plantas p            ON p.id = ar.planta_id;

CREATE VIEW IF NOT EXISTS vw_ultimas_leituras_por_ativo AS
WITH ult AS (
    SELECT
        l.id AS leitura_id,
        l.motor_id,
        l.timestamp,
        l.temperatura,
        l.vibracao,
        l.corrente,
        l.tensao,
        l.rpm,
        ROW_NUMBER() OVER (
            PARTITION BY l.motor_id
            ORDER BY l.timestamp DESC, l.id DESC
        ) AS rn
    FROM leituras l
)
SELECT
    m.id     AS motor_id,
    m.codigo AS codigo_motor,
    u.leitura_id,
    u.timestamp,
    u.temperatura,
    u.vibracao,
    u.corrente,
    u.tensao,
    u.rpm
FROM motores m
JOIN ult u ON u.motor_id = m.id AND u.rn = 1;

CREATE VIEW IF NOT EXISTS vw_digital_twin_ativos AS
SELECT
    o.*,
    dp.fabricante       AS placa_fabricante,
    dp.modelo           AS placa_modelo,
    dp.numero_serie     AS placa_numero_serie,
    dp.potencia         AS placa_potencia,
    dp.tensao_nominal   AS placa_tensao_nominal,
    dp.corrente_nominal AS placa_corrente_nominal,
    dp.rpm_nominal      AS placa_rpm_nominal,
    dp.frequencia       AS placa_frequencia,
    dp.fator_servico    AS placa_fator_servico,
    dp.rendimento       AS placa_rendimento,
    dp.origem_imagem,
    dp.origem_arquivo,
    dp.data_extracao,
    dp.confianca_extracao,
    ul.leitura_id,
    ul.timestamp      AS ultima_leitura_ts,
    ul.temperatura    AS ultima_temperatura,
    ul.vibracao       AS ultima_vibracao,
    ul.corrente       AS ultima_corrente,
    ul.tensao         AS ultima_tensao,
    ul.rpm            AS ultima_rpm
FROM vw_ativos_operacionais o
LEFT JOIN dados_placa_motor dp ON dp.motor_id = o.motor_id
LEFT JOIN vw_ultimas_leituras_por_ativo ul ON ul.motor_id = o.motor_id;

-- ============================================================
-- CS03 — Inteligência Operacional e Apoio à Decisão
-- ============================================================

CREATE TABLE IF NOT EXISTS catalogo_especificacoes_externas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    modelo_motor TEXT,
    fabricante TEXT,
    temp_max_tolerada REAL,
    vibracao_limite_rms REAL,
    guia_troubleshooting_json TEXT,
    dados_climaticos_json TEXT,
    data_coleta DATETIME DEFAULT CURRENT_TIMESTAMP,
    fonte_url TEXT
);

CREATE TABLE IF NOT EXISTS eventos_operacionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_ativo TEXT,
    codigo_motor TEXT,
    tipo_evento TEXT,
    severidade TEXT,
    descricao_anomalia TEXT,
    diagnostico_ia TEXT,
    acao_recomendada TEXT,
    status_resolucao TEXT DEFAULT 'pendente',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW IF NOT EXISTS vw_painel_decisao_operacional AS
SELECT
    o.tag,
    o.planta_nome,
    o.area_nome,
    o.linha_nome,
    ul.temperatura AS ultima_temperatura,
    ul.vibracao AS ultima_vibracao,
    ul.rpm AS ultima_rpm,
    o.status_operacional,
    c.temp_max_tolerada,
    c.vibracao_limite_rms,
    e.diagnostico_ia,
    e.acao_recomendada,
    e.created_at AS ultimo_evento
FROM vw_ativos_operacionais o
LEFT JOIN vw_ultimas_leituras_por_ativo ul ON ul.motor_id = o.motor_id
LEFT JOIN dados_placa_motor dp ON dp.motor_id = o.motor_id
LEFT JOIN catalogo_especificacoes_externas c ON c.modelo_motor = dp.modelo AND c.fabricante = dp.fabricante
LEFT JOIN (
    SELECT e1.* FROM eventos_operacionais e1
    INNER JOIN (
        SELECT tag_ativo, MAX(id) as max_id
        FROM eventos_operacionais
        GROUP BY tag_ativo
    ) e2 ON e1.id = e2.max_id
) e ON e.tag_ativo = o.tag
WHERE o.tag IS NOT NULL;
