"""Gestão manual do ciclo de vida de eventos (ações da equipe de manutenção).

    python scripts/gerenciar_eventos.py listar
    python scripts/gerenciar_eventos.py assumir  MTR-L01-BOM-001 --tecnico maria.silva
    python scripts/gerenciar_eventos.py resolver MTR-L01-BOM-001 --tecnico maria.silva \
        --resolucao "Rolamento trocado e eixo alinhado"
    python scripts/gerenciar_eventos.py historico MTR-L01-BOM-001
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.integracao import ciclo_vida_eventos as cv  # noqa: E402
from src.integracao.migracao import garantir_schema  # noqa: E402
from src.persistencia.database import get_connection  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Gestão de eventos operacionais")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listar", help="eventos em aberto")
    for nome in ("assumir", "resolver"):
        p = sub.add_parser(nome)
        p.add_argument("tag")
        p.add_argument("--tecnico", required=True)
        if nome == "resolver":
            p.add_argument("--resolucao", required=True)
    h = sub.add_parser("historico")
    h.add_argument("tag")
    a = ap.parse_args()

    garantir_schema()
    try:
        if a.cmd == "listar":
            with get_connection() as c:
                linhas = c.execute("SELECT evento_id, tag_ativo, severidade, status_resolucao, ocorrencias, aberto_em "
                                   "FROM vw_eventos_abertos ORDER BY evento_id").fetchall()
            if not linhas:
                print("Nenhum evento em aberto.")
            for r in linhas:
                print(f"#{r['evento_id']:<4} {r['tag_ativo']:<20} {r['severidade']:<8} {r['status_resolucao']:<13} "
                      f"{r['ocorrencias']} ocorrência(s)  aberto em {r['aberto_em']}")
        elif a.cmd == "assumir":
            print(f"Evento #{cv.assumir_evento(a.tag, a.tecnico)} em atendimento por {a.tecnico}.")
        elif a.cmd == "resolver":
            print(f"Evento #{cv.concluir_evento(a.tag, a.tecnico, a.resolucao)} resolvido; ativo {a.tag} voltou a operacional.")
        elif a.cmd == "historico":
            with get_connection() as c:
                for r in c.execute("SELECT h.criado_em, h.acao, h.status_novo, h.ator, h.observacao FROM historico_eventos h "
                                   "JOIN eventos_operacionais e ON e.id = h.evento_id WHERE e.tag_ativo = ? "
                                   "ORDER BY h.id", (a.tag,)):
                    print(f"{r['criado_em']}  {r['acao']:<15} -> {r['status_novo']:<13} {r['ator']:<22} {r['observacao']}")
    except ValueError as exc:
        print(f"Erro: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
