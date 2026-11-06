"""Serviço de notificação de eventos operacionais.

Simula o envio de e-mail HTML: o conteúdo é registrado no log e salvo como
arquivo na caixa de saída (logs/notificacoes), servindo de evidência do envio.
Trocar por SMTP real exige apenas substituir a gravação do arquivo.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

logger = logging.getLogger(__name__)

PASTA_PADRAO = Path(__file__).resolve().parents[2] / "logs" / "notificacoes"


def enviar_alerta_html(
    tag_ativo: str,
    severidade: str,
    diagnostico: str,
    acao: str,
    procedimentos: Sequence[dict[str, Any]] | None = None,
    pasta: Path | None = None,
) -> Path | None:
    """Gera o e-mail de alerta e devolve o caminho do arquivo salvo."""
    cor = "#ef4444" if severidade == "CRITICO" else "#f59e0b"
    esc = html.escape
    itens = ""
    if procedimentos:
        linhas = "".join(
            f"<li><b>{esc(str(p.get('tipo', '')).capitalize())}:</b> {esc(str(p.get('descricao', '')))} "
            f"<i>({esc(str(p.get('referencia', '')))})</i></li>"
            for p in procedimentos
        )
        itens = f"<tr><th>Procedimentos</th><td><ol>{linhas}</ol></td></tr>"

    corpo = f"""<html><head><meta charset="utf-8"><style>
body {{ font-family: Arial, sans-serif; background:#f8fafc; color:#1e293b; padding:20px; }}
.c {{ background:#fff; padding:20px; border-radius:8px; border-left:5px solid {cor}; }}
.b {{ background:{cor}; color:#fff; padding:4px 8px; border-radius:4px; font-size:12px; }}
table {{ width:100%; border-collapse:collapse; margin-top:15px; }}
th,td {{ padding:10px; border-bottom:1px solid #e2e8f0; text-align:left; vertical-align:top; }}
th {{ background:#f1f5f9; width:170px; }}
</style></head><body><div class="c">
<h2>Alerta operacional - ativo {esc(tag_ativo)} <span class="b">{esc(severidade)}</span></h2>
<p>O Digital Twin Predicta detectou um desvio operacional e registrou a recomendação abaixo.</p>
<table>
<tr><th>Horário</th><td>{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</td></tr>
<tr><th>Diagnóstico</th><td>{esc(diagnostico)}</td></tr>
<tr><th>Ação recomendada</th><td><b>{esc(acao)}</b></td></tr>
{itens}
</table></div></body></html>"""

    destino = None
    try:
        pasta = Path(pasta or PASTA_PADRAO)
        pasta.mkdir(parents=True, exist_ok=True)
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destino = pasta / f"alerta_{tag_ativo}_{severidade}_{carimbo}.html"
        destino.write_text(corpo, encoding="utf-8")
    except OSError as exc:
        logger.error("Não foi possível salvar a notificação de %s: %s", tag_ativo, exc)

    logger.info("Notificação (simulação SMTP) para %s [%s] - arquivo: %s", tag_ativo, severidade, destino)
    return destino
