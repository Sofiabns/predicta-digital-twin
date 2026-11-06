"""Entry point: RPA de associação Ativo / TAG / Localização (CS02)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cadastro_ativo.ativo_association_pipeline import executar_associacao_ativos  # noqa: E402
from src.coleta.logger_config import LOG_DIR, configurar_logger  # noqa: E402


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    configurar_logger("rpa-cs02.associacao")

    print("=" * 60)
    print("RPA CS02 — Atualização de associações (Ativo / TAG / Localização)")
    print("=" * 60)

    resumo = executar_associacao_ativos(arquivar=True, origem="script_atualizar_associacoes_ativos")

    print(f"\nArquivo: {resumo['arquivo']}")
    print(f"Registros lidos:      {resumo['lidos']}")
    print(f"Registros válidos:    {resumo['validos']}")
    print(f"Criados (associação): {resumo['criados']}")
    print(f"Atualizados:          {resumo['atualizados']}")
    print(f"Inalterados:         {resumo['inalterados']}")
    print(f"Ignorados:           {resumo['ignorados']}")
    print(f"Erros:               {resumo['erros']}")
    if resumo["detalhes_erros"]:
        print("\nDetalhes de erros:")
        for e in resumo["detalhes_erros"][:30]:
            print(f"  - {e}")
        if len(resumo["detalhes_erros"]) > 30:
            print("  ...")
    print("=" * 60)

    logging.shutdown()
    return 0 if resumo["erros"] == 0 or resumo["validos"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
