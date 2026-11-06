"""Orquestrador da analise de leituras e deteccao de anomalias."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.analise.detector import (
    AnomaliaDetectada,
    ResultadoAnalise,
    analisar_leitura,
)
from src.analise.estatisticas import ResumoEstatistico, calcular_resumo
from src.persistencia.anomalia_repository import inserir_anomalia
from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


@dataclass
class RelatorioAnalise:
    """Sumario do resultado da analise em lote."""

    total_leituras: int = 0
    total_normais: int = 0
    total_alertas: int = 0
    total_criticas: int = 0
    total_anomalias_persistidas: int = 0
    leituras_processadas: list[int] = None  # type: ignore

    def __post_init__(self):
        if self.leituras_processadas is None:
            self.leituras_processadas = []

    def resumo(self) -> str:
        """Retorna string com resumo amigavel."""
        return (
            f"Leituras analisadas: {self.total_leituras}\n"
            f"  Normais : {self.total_normais}\n"
            f"  Alertas : {self.total_alertas}\n"
            f"  Criticas: {self.total_criticas}\n"
            f"Anomalias persistidas: {self.total_anomalias_persistidas}"
        )


def buscar_leituras_nao_processadas(limite: int | None = None) -> list[dict]:
    """Busca leituras com processado = 0."""
    sql = """
        SELECT id, motor_id, temperatura, vibracao, corrente, rpm, tensao,
               classe_origem, label_origem
        FROM leituras
        WHERE processado = 0
        ORDER BY id ASC
    """
    if limite is not None:
        sql += f" LIMIT {int(limite)}"

    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

def obter_limites_todos_motores() -> dict[int, dict[str, float]]:
    """Limites de catálogo (ou padrão) de todos os motores, em um único lugar."""
    from src.integracao.limites import resolver_limites_todos

    return {
        mid: {"temp_max": lim.temp_max, "vib_max": lim.vib_max}
        for mid, lim in resolver_limites_todos().items()
    }


def marcar_leituras_processadas(ids: list[int]) -> int:
    """Marca leituras como processadas."""
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    sql = f"UPDATE leituras SET processado = 1 WHERE id IN ({placeholders})"
    with get_connection() as conn:
        cursor = conn.execute(sql, ids)
        return cursor.rowcount


def calcular_resumos_globais(leituras: list[dict]) -> tuple[ResumoEstatistico, ResumoEstatistico]:
    """Calcula resumo estatistico global de temperatura e vibracao."""
    temps = [float(l["temperatura"]) for l in leituras]
    vibs = [float(l["vibracao"]) for l in leituras]
    return calcular_resumo(temps), calcular_resumo(vibs)


def persistir_anomalias(anomalias: list[AnomaliaDetectada]) -> int:
    """Persiste lista de anomalias detectadas no banco."""
    if not anomalias:
        return 0

    contador = 0
    for a in anomalias:
        try:
            inserir_anomalia(
                motor_id=a.motor_id,
                leitura_id=a.leitura_id,
                tipo=a.tipo,
                severidade=a.severidade,
                valor_medido=a.valor_medido,
                valor_limite=a.valor_limite,
                descricao=a.descricao,
            )
            contador += 1
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Falha ao inserir anomalia leitura_id=%s: %s",
                a.leitura_id, exc,
            )
    return contador


def executar_analise(limite: int | None = None) -> RelatorioAnalise:
    """Executa o pipeline completo de analise de leituras nao processadas."""
    logger.info("=" * 60)
    logger.info("INICIO DA ANALISE DE LEITURAS")
    logger.info("=" * 60)

    leituras = buscar_leituras_nao_processadas(limite=limite)
    relatorio = RelatorioAnalise(total_leituras=len(leituras))

    if not leituras:
        logger.info("Nenhuma leitura pendente para analise.")
        return relatorio

    logger.info("Encontradas %d leituras nao processadas", len(leituras))

    # Calcula resumos estatisticos GLOBAIS (base para Z-score)
    resumo_temp, resumo_vib = calcular_resumos_globais(leituras)
    logger.info(
        "Resumo Temperatura: media=%.2f, desvio=%.2f",
        resumo_temp.media, resumo_temp.desvio,
    )
    logger.info(
        "Resumo Vibracao: media=%.2f, desvio=%.2f",
        resumo_vib.media, resumo_vib.desvio,
    )

    # Analisa cada leitura
    limites_motores = obter_limites_todos_motores()
    todas_anomalias: list[AnomaliaDetectada] = []
    for leitura in leituras:
        mid = leitura["motor_id"]
        t_max = limites_motores.get(mid, {}).get("temp_max", 80.0)
        v_max = limites_motores.get(mid, {}).get("vib_max", 2.8)
        
        resultado: ResultadoAnalise = analisar_leitura(
            leitura_id=leitura["id"],
            motor_id=mid,
            temperatura=float(leitura["temperatura"]),
            vibracao=float(leitura["vibracao"]),
            temp_max=t_max,
            vib_max=v_max,
            resumo_temp=resumo_temp,
            resumo_vib=resumo_vib,
        )

        # Atualiza contadores
        if resultado.classe_detectada == "normal":
            relatorio.total_normais += 1
        elif resultado.classe_detectada == "alerta":
            relatorio.total_alertas += 1
        else:
            relatorio.total_criticas += 1

        todas_anomalias.extend(resultado.anomalias)
        relatorio.leituras_processadas.append(leitura["id"])

    # Persiste anomalias
    relatorio.total_anomalias_persistidas = persistir_anomalias(todas_anomalias)
    logger.info(
        "Anomalias persistidas: %d", relatorio.total_anomalias_persistidas
    )

    # Marca leituras como processadas
    marcadas = marcar_leituras_processadas(relatorio.leituras_processadas)
    logger.info("Leituras marcadas como processadas: %d", marcadas)

    logger.info("=" * 60)
    logger.info("FIM DA ANALISE")
    logger.info("=" * 60)
    return relatorio
