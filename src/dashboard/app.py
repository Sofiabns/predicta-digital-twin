"""Dashboard interativo Predicta - Monitoramento de motores industriais."""

from __future__ import annotations

import logging

import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard import data_service as ds
from src.dashboard.operational_view import registrar_aba_digital_twin
from src.dashboard.decision_view import registrar_aba_decisao
from src.dashboard.theme import CUSTOM_CSS, predicta_theme

logger = logging.getLogger(__name__)

# Paleta de cores institucional
CORES_SEVERIDADE = {
    "critica": "#ef4444",
    "alta":    "#f59e0b",
    "media":   "#eab308",
    "baixa":   "#06b6d4",
}

CORES_METRICAS = {
    "temperatura": "#ef4444",
    "vibracao":    "#f59e0b",
    "corrente":    "#06b6d4",
    "rpm":         "#10b981",
    "tensao":      "#a855f7",
}

# Estilo padrão de tooltip (hover) para todos os gráficos
HOVERLABEL_STYLE = dict(
    bgcolor="#1e293b",
    bordercolor="#06b6d4",
    font=dict(color="#f1f5f9", size=13, family="Inter, sans-serif"),
)


# ============================================================
# Renderizadores de KPIs
# ============================================================
def render_kpi_card(label: str, value: str | int, kind: str = "default") -> str:
    """Gera HTML de um card de KPI."""
    return f"""
    <div class="kpi-card {kind}">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
    </div>
    """


def render_kpis_html() -> str:
    """Renderiza linha de KPIs em HTML."""
    k = ds.obter_kpis()

    saude_kind = "success" if k["taxa_saude"] >= 90 else (
        "warning" if k["taxa_saude"] >= 70 else "danger"
    )
    criticas_kind = "danger" if k["anomalias_criticas"] > 0 else "success"

    cards = f"""
    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
        {render_kpi_card("🏭 Motores Ativos", f'{k["motores_ativos"]} / {k["total_motores"]}')}
        {render_kpi_card("📊 Leituras Totais", f'{k["total_leituras"]:,}'.replace(",", "."))}
        {render_kpi_card("🚨 Anomalias Críticas", k["anomalias_criticas"], criticas_kind)}
        {render_kpi_card("💚 Taxa de Saúde", f'{k["taxa_saude"]}%', saude_kind)}
    </div>
    <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 16px;">
        {render_kpi_card("⚠️ Total de Anomalias", k["total_anomalias"], "warning")}
        {render_kpi_card("🔧 Manutenções Pendentes", k["manutencoes_pendentes"])}
    </div>
    """
    return cards


# ============================================================
# Graficos
# ============================================================
def grafico_anomalias_severidade() -> go.Figure:
    df = ds.contagem_anomalias_por_severidade()
    if df.empty:
        return _figura_vazia("Sem anomalias registradas")

    fig = px.pie(
        df,
        values="total",
        names="severidade",
        color="severidade",
        color_discrete_map=CORES_SEVERIDADE,
        hole=0.55,
    )
    fig.update_traces(
        textposition="outside",
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>Total: %{value}<br>Percentual: %{percent}<extra></extra>",
    )
    fig.update_layout(
        title="Distribuição de Anomalias por Severidade",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        showlegend=True,
        hoverlabel=HOVERLABEL_STYLE,
        font=dict(color="#e2e8f0"),
    )
    return fig


def grafico_anomalias_por_motor() -> go.Figure:
    df = ds.contagem_anomalias_por_motor()
    if df.empty:
        return _figura_vazia("Sem anomalias por motor")

    fig = px.bar(
        df,
        x="total",
        y="motor",
        orientation="h",
        color="total",
        color_continuous_scale=["#06b6d4", "#f59e0b", "#ef4444"],
        text="total",
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>Motor: %{y}</b><br>Anomalias: %{x}<extra></extra>",
    )
    fig.update_layout(
        title="Top Motores com Mais Anomalias",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        xaxis_title="Quantidade",
        yaxis_title="Motor",
        coloraxis_showscale=False,
        hoverlabel=HOVERLABEL_STYLE,
        font=dict(color="#e2e8f0"),
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def grafico_telemetria(codigo: str, metrica: str) -> go.Figure:
    if not codigo:
        return _figura_vazia("Selecione um motor")

    df = ds.obter_telemetria_motor(codigo, limite=500)
    if df.empty or metrica not in df.columns:
        return _figura_vazia(f"Sem dados para {codigo}")

    cor = CORES_METRICAS.get(metrica, "#06b6d4")

    fig = go.Figure()
    
    limites = ds.obter_limites_motor(codigo)
    if metrica in limites:
        fig.add_hline(
            y=limites[metrica],
            line_dash="dash",
            line_color="#facc15",
            annotation_text=f"Limite Catálogo ({limites[metrica]:.1f})",
            annotation_position="bottom right"
        )
        
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df[metrica],
        mode="lines",
        name=metrica.title(),
        line=dict(color=cor, width=2),
        fill="tozeroy",
        fillcolor=f"rgba({_hex_to_rgb(cor)}, 0.1)",
        hovertemplate=f"<b>{metrica.title()}</b><br>%{{x|%d/%m/%Y %H:%M}}<br>Valor: %{{y:.2f}}<extra></extra>",
    ))

    # ✅ NOVO: marca APENAS pontos com anomalia crítica REAL da métrica selecionada
    if metrica in limites:
        criticos = df[df[metrica] > limites[metrica]]
        if not criticos.empty:
            fig.add_trace(go.Scatter(
                x=criticos["timestamp"],
                y=criticos[metrica],
                mode="markers",
                name="Anomalia",
                marker=dict(
                    color="#ef4444",
                    size=14,
                    symbol="x",
                    line=dict(color="#fecaca", width=2),
                ),
                hovertemplate="<b>⚠️ ANOMALIA DETECTADA</b><br>%{x|%d/%m/%Y %H:%M}<br>Valor: %{y:.2f}<extra></extra>",
            ))

    fig.update_layout(
        title=f"Telemetria — {codigo} — {metrica.title()}",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.5)",
        height=420,
        xaxis_title="Timestamp",
        yaxis_title=metrica.title(),
        hovermode="x unified",
        hoverlabel=HOVERLABEL_STYLE,
        font=dict(color="#e2e8f0"),
        legend=dict(
            bgcolor="rgba(30,41,59,0.8)",
            bordercolor="#06b6d4",
            borderwidth=1,
            font=dict(color="#f1f5f9"),
        ),
    )
    return fig



def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


def _figura_vazia(mensagem: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=mensagem,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color="#94a3b8"),
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        hoverlabel=HOVERLABEL_STYLE,
        font=dict(color="#e2e8f0"),
    )
    return fig


# ============================================================
# Handlers de atualizacao
# ============================================================
def atualizar_visao_geral():
    return (
        render_kpis_html(),
        grafico_anomalias_severidade(),
        grafico_anomalias_por_motor(),
    )


def atualizar_motores():
    return ds.listar_motores_resumo()


def atualizar_telemetria(codigo: str, metrica: str):
    return grafico_telemetria(codigo, metrica)


def atualizar_anomalias(severidade: str):
    return ds.listar_anomalias(severidade if severidade != "todas" else None)


# ============================================================
# Construcao da UI
# ============================================================
def construir_app() -> gr.Blocks:
    with gr.Blocks(theme=predicta_theme, css=CUSTOM_CSS, title="Predicta Dashboard") as app:

        # Header
        gr.HTML("""
        <div id="header-banner">
            <h1>🏭 Predicta — Monitoramento Industrial Inteligente</h1>
            <p>Plataforma RPA + IA para manutenção preditiva de motores elétricos</p>
        </div>
        """)

        with gr.Tabs():

            # ==================== ABA 1: VISAO GERAL ====================
            with gr.Tab("📊 Visão Geral"):
                gr.Markdown("### Indicadores em tempo real")
                kpis_html = gr.HTML(render_kpis_html())

                with gr.Row():
                    grafico_pizza = gr.Plot(grafico_anomalias_severidade())
                    grafico_top = gr.Plot(grafico_anomalias_por_motor())

                btn_refresh = gr.Button("🔄 Atualizar Dados", variant="primary")
                btn_refresh.click(
                    fn=atualizar_visao_geral,
                    outputs=[kpis_html, grafico_pizza, grafico_top],
                )
                
                timer_geral = gr.Timer(value=20)
                timer_geral.tick(
                    fn=atualizar_visao_geral,
                    outputs=[kpis_html, grafico_pizza, grafico_top],
                )

            # ==================== ABA 2: MOTORES ====================
            with gr.Tab("🔧 Motores"):
                gr.Markdown("### Status consolidado da frota de motores")
                tabela_motores = gr.Dataframe(
                    value=ds.listar_motores_resumo(),
                    interactive=False,
                    wrap=True,
                    elem_id="tabela-motores",
                )
                btn_refresh_motores = gr.Button("🔄 Atualizar", variant="primary")
                btn_refresh_motores.click(fn=atualizar_motores, outputs=tabela_motores)
                
                timer_motores = gr.Timer(value=20)
                timer_motores.tick(fn=atualizar_motores, outputs=tabela_motores)

            # ==================== ABA 3: TELEMETRIA ====================
            with gr.Tab("📈 Telemetria"):
                gr.Markdown("### Análise temporal de variáveis por motor")

                codigos = ds.listar_codigos_motores()
                with gr.Row():
                    sel_motor = gr.Dropdown(
                        choices=codigos,
                        value=codigos[0] if codigos else None,
                        label="Motor",
                        interactive=True,
                    )
                    sel_metrica = gr.Dropdown(
                        choices=["temperatura", "vibracao", "corrente", "rpm", "tensao"],
                        value="temperatura",
                        label="Métrica",
                        interactive=True,
                    )

                grafico_tele = gr.Plot(
                    grafico_telemetria(codigos[0] if codigos else "", "temperatura")
                )

                sel_motor.change(
                    fn=atualizar_telemetria,
                    inputs=[sel_motor, sel_metrica],
                    outputs=grafico_tele,
                )
                sel_metrica.change(
                    fn=atualizar_telemetria,
                    inputs=[sel_motor, sel_metrica],
                    outputs=grafico_tele,
                )
                
                timer_tele = gr.Timer(value=20)
                timer_tele.tick(
                    fn=atualizar_telemetria,
                    inputs=[sel_motor, sel_metrica],
                    outputs=grafico_tele,
                )

            # ==================== ABA 4: ANOMALIAS ====================
            with gr.Tab("🚨 Anomalias"):
                gr.Markdown("### Anomalias detectadas pelo sistema")

                sel_severidade = gr.Radio(
                    choices=["todas", "critica", "alta", "media", "baixa"],
                    value="todas",
                    label="Filtrar por severidade",
                )

                tabela_anomalias = gr.Dataframe(
                    value=ds.listar_anomalias(),
                    interactive=False,
                    wrap=True,
                    elem_id="tabela-anomalias",
                )

                sel_severidade.change(
                    fn=atualizar_anomalias,
                    inputs=sel_severidade,
                    outputs=tabela_anomalias,
                )

            registrar_aba_digital_twin()
            registrar_aba_decisao()

        # Footer
        gr.HTML("""
        <div style="text-align:center; padding:20px; color:#64748b; font-size:12px;">
            <strong>Predicta</strong> · CS01 (telemetria) + CS02 (Digital Twin operacional) · FIAP 2026 ·
            Augusto Codo · Felipe Cabral · Gabriel Tonelli · Sofia Bueris · Vinicius Adrian
        </div>
        """)

    return app


# ============================================================
# Entrypoint
# ============================================================
def main():
    """Inicia o servidor Gradio do dashboard Predicta."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 60, flush=True)
    print("🚀 INICIANDO PREDICTA DASHBOARD", flush=True)
    print("=" * 60, flush=True)

    logger.info("Construindo interface Gradio...")
    app = construir_app()
    logger.info("Interface construída com sucesso.")

    print("\n📡 Servidor: http://127.0.0.1:7860", flush=True)
    print("🌐 Abrindo navegador automaticamente...\n", flush=True)

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        inbrowser=True,
        share=False,
        quiet=False,
    )


if __name__ == "__main__":
    main()
