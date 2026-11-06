"""
Aba "IA & Decisão" (CS03, evoluída na Sprint 4).

Mostra o painel operacional, os eventos com situação e histórico de rastreabilidade,
os ciclos da automação e o assistente de manutenção. O assistente usa o contexto
operacional exportado pela automação (RAG) e funciona mesmo sem o Ollama.
"""

import gradio as gr
import pandas as pd

from src.dashboard import data_service as ds
from src.integracao.config import Config
from src.integracao.contexto_rag import montar_contexto_assistente
from src.persistencia.database import get_connection


def atualizar_painel_decisao():
    return (ds.obter_painel_decisao(), ds.listar_eventos_operacionais(),
            ds.listar_historico_eventos(), ds.listar_ciclos_execucao())


def exibir_dossie(evt: gr.SelectData, df: pd.DataFrame):
    ativo = df.iloc[evt.index[0]]
    tag = ativo.get("TAG", "Desconhecido")
    sql = ("SELECT diagnostico_ia, acao_recomendada, procedimentos_json, origem_recomendacao, status_resolucao "
           "FROM eventos_operacionais WHERE tag_ativo = ? ORDER BY id DESC LIMIT 1")
    with get_connection() as conn:
        r = conn.execute(sql, (tag,)).fetchone()
    if not r:
        return f"### Dossiê técnico: {tag}\nNenhum evento registrado para este ativo."
    import json
    passos = json.loads(r["procedimentos_json"] or "[]")
    lista = "\n".join(f"{p['ordem']}. **{p['tipo'].capitalize()}**: {p['descricao']} _({p['referencia']})_" for p in passos)
    return (f"### Dossiê técnico: {tag}\n"
            f"**Situação do último evento:** {r['status_resolucao']} (recomendação: {r['origem_recomendacao']})\n\n"
            f"**Diagnóstico:**\n> {r['diagnostico_ia']}\n\n"
            f"**Ação recomendada:**\n> {r['acao_recomendada']}\n\n"
            f"**Procedimentos:**\n{lista or 'Sem procedimentos registrados.'}")


def chat_assistente(msg, history):
    contexto = montar_contexto_assistente(msg, top_k=4)
    prompt = (
        "Você é o responsável técnico de manutenção da planta Predicta. Responda em português, de forma objetiva, "
        "usando apenas as informações abaixo (estado real da planta e manuais). Se faltar informação, diga.\n\n"
        f"--- CONTEXTO ---\n{contexto}\n\n--- PERGUNTA ---\n{msg}"
    )
    try:
        import ollama

        cfg = Config.carregar()
        resp = ollama.Client(timeout=cfg.ollama_timeout_s).chat(
            model=cfg.ollama_modelo, messages=[{"role": "user", "content": prompt}])
        resposta = resp["message"]["content"]
    except Exception:  # noqa: BLE001 - sem IA generativa, devolve o que foi recuperado
        resposta = ("O modelo de linguagem não está disponível agora. Veja o que a base de conhecimento "
                    "e o histórico da planta trazem sobre a pergunta:\n\n" + (contexto or "Nada encontrado."))
    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": resposta})
    return "", history


def registrar_aba_decisao():
    with gr.Tab("🧠 IA & Decisão"):
        gr.Markdown("### Inteligência operacional e apoio à decisão")
        btn = gr.Button("Atualizar painéis", variant="primary")
        tabela_painel = gr.Dataframe(value=ds.obter_painel_decisao(), interactive=False, wrap=True,
                                     datatype="str", label="Painel operacional")
        dossie = gr.Markdown("Selecione um ativo na tabela para ver o dossiê e os procedimentos.")
        tabela_painel.select(fn=exibir_dossie, inputs=[tabela_painel], outputs=[dossie])

        gr.Markdown("### Eventos e recomendações")
        tabela_eventos = gr.Dataframe(value=ds.listar_eventos_operacionais(), interactive=False, wrap=True,
                                      datatype="str", label="Eventos registrados")
        gr.Markdown("### Rastreabilidade do ciclo de vida")
        tabela_hist = gr.Dataframe(value=ds.listar_historico_eventos(), interactive=False, wrap=True,
                                   datatype="str", label="Histórico de transições")
        gr.Markdown("### Execuções da automação")
        tabela_ciclos = gr.Dataframe(value=ds.listar_ciclos_execucao(), interactive=False, wrap=True,
                                     datatype="str", label="Ciclos")
        saidas = [tabela_painel, tabela_eventos, tabela_hist, tabela_ciclos]
        btn.click(fn=atualizar_painel_decisao, outputs=saidas)
        gr.Timer(value=20).tick(fn=atualizar_painel_decisao, outputs=saidas)

        gr.Markdown("### Pergunte ao assistente de manutenção")
        chatbot = gr.Chatbot(label="Assistente industrial Predicta", height=320)
        with gr.Row():
            txt = gr.Textbox(show_label=False, placeholder="Ex.: Qual o histórico do MTR-001 e o que foi recomendado?", scale=4)
            enviar = gr.Button("Enviar", scale=1)
        enviar.click(chat_assistente, inputs=[txt, chatbot], outputs=[txt, chatbot])
        txt.submit(chat_assistente, inputs=[txt, chatbot], outputs=[txt, chatbot])
