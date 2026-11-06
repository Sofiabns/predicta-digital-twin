"""Procedimentos técnicos por tipo de desvio.

O conteúdo foi extraído dos manuais do projeto (data/manuais) e cada passo
aponta a seção de origem. É o que garante uma recomendação útil mesmo quando a
IA generativa está fora do ar. Quando ela está disponível, o playbook entra no
prompt como base para o texto final.
"""

from __future__ import annotations

from dataclasses import dataclass

MANUAL = "manual_normativo_motores_weg_iso.md"
GUIA = "guia_weg.txt"


@dataclass(frozen=True)
class Passo:
    tipo: str        # corretivo | preventivo
    descricao: str
    referencia: str


PLAYBOOK: dict[str, list[Passo]] = {
    "vibracao": [
        Passo("corretivo", "Realizar alinhamento a laser do eixo com a carga e inspecionar o acoplamento.", f"{MANUAL} > Manutenção Corretiva"),
        Passo("corretivo", "Conferir calços de nivelamento e a fixação dos parafusos da base (pé manco).", f"{GUIA} > SINTOMA 2"),
        Passo("corretivo", "Verificar folga nos rolamentos; se confirmada, substituir por rolamento homologado (SKF ou FAG).", f"{GUIA} > SINTOMA 2"),
        Passo("preventivo", "Incluir o ativo na análise de vibração espectral mensal.", f"{MANUAL} > Manutenção Preditiva"),
    ],
    "temperatura": [
        Passo("corretivo", "Reduzir a carga operacional e confirmar se a corrente está acima da nominal da placa.", f"{MANUAL} > Manutenção Corretiva"),
        Passo("corretivo", "Inspecionar aletas e entrada de ar da tampa defletora; limpar com ar comprimido se houver sujeira.", f"{GUIA} > SINTOMA 3"),
        Passo("corretivo", "Medir a resistência de isolamento do estator (Megger) e checar desbalanceamento de tensão.", f"{MANUAL} > Manutenção Corretiva"),
        Passo("preventivo", "Programar termografia quinzenal do estator e dos mancais.", f"{MANUAL} > Manutenção Preditiva"),
    ],
    "corrente": [
        Passo("corretivo", "Verificar sobrecarga mecânica na máquina acionada e avaliar redução de carga ou redimensionamento do motor.", f"{GUIA} > SINTOMA 3"),
        Passo("corretivo", "Medir a corrente em cada fase para identificar desequilíbrio entre fases.", f"{MANUAL} > Sobrecarga de Fase (Elétrica)"),
        Passo("preventivo", "Revisar parametrização do inversor ou soft-starter.", f"{GUIA} > SINTOMA 4"),
    ],
    "tensao": [
        Passo("corretivo", "Medir a tensão nos terminais do motor e na origem da alimentação.", f"{GUIA} > SINTOMA 1"),
        Passo("corretivo", "Acionar a equipe elétrica para verificar a rede, pois subtensão ou sobretensão elevam a corrente e aquecem as bobinas.", f"{MANUAL} > 4. Avaliação de Tensão (V) e Corrente (A)"),
        Passo("preventivo", "Acompanhar a variação de tensão por pelo menos uma semana.", f"{MANUAL} > 4. Avaliação de Tensão (V) e Corrente (A)"),
    ],
}

PASSO_CONJUNTO = Passo(
    "corretivo",
    "Parar a máquina assim que a operação permitir, drenar a graxa antiga, relubrificar os mancais e conferir o alinhamento a laser.",
    f"{MANUAL} > 3. Diretrizes de Diagnóstico Integrado",
)

CAUSAS: dict[str, str] = {
    "vibracao": "Vibração acima do limite costuma indicar desalinhamento, problema de fundação, desbalanceamento ou desgaste de rolamento.",
    "temperatura": "Temperatura acima do limite costuma vir de sobrecarga, ventilação obstruída ou alimentação elétrica fora da faixa.",
    "corrente": "Corrente acima da nominal aponta sobrecarga mecânica ou desequilíbrio entre fases.",
    "tensao": "Tensão fora da faixa de ±5% sobrecarrega as bobinas e aumenta a corrente.",
}

CONSULTA_RAG: dict[str, str] = {
    "vibracao": "vibração alta desalinhamento rolamento fundação alinhamento a laser",
    "temperatura": "temperatura alta sobrecarga ventilação aletas resistência isolamento",
    "corrente": "corrente acima da nominal sobrecarga fase desbalanceamento",
    "tensao": "tensão fora da faixa subtensão sobretensão alimentação",
}


def passos_para(tipos: set[str]) -> list[Passo]:
    """Monta a lista de passos para o conjunto de desvios, sem repetir."""
    passos: list[Passo] = []
    if {"temperatura", "vibracao"} <= tipos:
        passos.append(PASSO_CONJUNTO)
    for tipo in ("vibracao", "temperatura", "corrente", "tensao"):
        if tipo in tipos:
            passos.extend(p for p in PLAYBOOK[tipo] if p not in passos)
    return passos
