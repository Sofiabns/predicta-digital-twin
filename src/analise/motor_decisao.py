"""Motor de decisão (CS03, mantido na Sprint 4).

Agora delega a classificação às regras únicas de ``src.integracao.avaliacao`` e
a recomendação ao ``SuporteOperacional``, que funciona com ou sem Ollama.
A interface pública (``analisar_leitura``) continua a mesma.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.integracao.avaliacao import avaliar_leitura
from src.integracao.suporte_operacional import SuporteOperacional

logger = logging.getLogger(__name__)


class MotorDecisao:
    def __init__(self):
        self.suporte = SuporteOperacional()

    def analisar_leitura(self, leitura: Dict[str, Any], catalogo: Dict[str, Any]) -> Dict[str, Any]:
        av = avaliar_leitura(
            leitura,
            temp_max=float(catalogo.get("temp_max_tolerada") or 80),
            vib_max=float(catalogo.get("vibracao_limite_rms") or 2.5),
            corrente_nominal=leitura.get("corrente_nominal"),
            tensao_nominal=leitura.get("tensao_nominal"),
        )
        if av.severidade == "NORMAL":
            return {
                "severidade": "NORMAL",
                "diagnostico_ia": "Operação dentro dos limites normativos.",
                "acao_recomendada": "Nenhuma intervenção necessária.",
                "descricao_anomalia": "Sem anomalias.",
            }
        rec = self.suporte.recomendar(av, tag=str(leitura.get("tag", "ativo")),
                                      limites_fonte="catalogo" if catalogo else "padrao")
        return {
            "severidade": av.severidade,
            "descricao_anomalia": av.descricao,
            "diagnostico_ia": rec.diagnostico,
            "acao_recomendada": rec.acao_recomendada,
            "procedimentos": rec.procedimentos,
            "referencias": rec.referencias,
            "origem_recomendacao": rec.origem,
        }
