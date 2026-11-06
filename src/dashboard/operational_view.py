"""Aba Digital Twin Operacional (CS02) — Gradio."""

from __future__ import annotations

import logging
from typing import Any

import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard import data_service as ds

logger = logging.getLogger(__name__)

METRICAS = ["temperatura", "vibracao", "corrente", "tensao", "rpm"]

CORES_METRICAS = {
    "temperatura": "#ef4444",
    "vibracao": "#f59e0b",
    "corrente": "#06b6d4",
    "rpm": "#10b981",
    "tensao": "#a855f7",
}


def _figura_vazia(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=msg,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=15, color="#94a3b8"),
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=360,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        font=dict(color="#e2e8f0"),
    )
    return fig


def calcular_status_visual(twin: dict[str, Any] | None) -> str:
    if not twin or not twin.get("tag"):
        return "Sem associação"
    if not twin.get("ultima_leitura_ts"):
        return "Sem leitura"

    motor_id = twin.get("motor_id")
    crit_recente = 0
    if motor_id is not None:
        crit_recente = ds.contar_anomalias_criticas_recentes(int(motor_id), dias=7)

    sop = (twin.get("status_operacional") or "operacional").lower()
    if crit_recente > 0 or sop == "critico":
        return "Crítico"
    if sop == "manutencao":
        return "Manutenção"
    if sop == "atencao":
        return "Atenção"
    if sop == "parado":
        return "Parado / indisponível"
    return "Operacional"


def _markdown_perfil(perfil: str) -> str:
    return "\n".join(
        [
            "### Controle de acesso (demonstrativo)",
            f"- **Perfil selecionado:** `{perfil}`",
            "- **Nível:** acadêmico — sem autenticação real; apenas mascaramento de informações na interface.",
            "- **Dados liberados:** conforme o perfil acima.",
        ]
    )


def _markdown_resumo(twin: dict[str, Any] | None, perfil: str, tag_digitada: str | None = None) -> str:
    if tag_digitada and (not twin or not twin.get("tag")):
        return f"### Ativo\n\n**TAG não encontrada:** `{tag_digitada.strip()}`. Verifique o cadastro operacional."

    if not twin or not twin.get("tag"):
        return (
            "### Ativo\n\nNenhuma associação operacional selecionada. "
            "Use a hierarquia ou a busca por TAG. Execute `scripts/atualizar_associacoes_ativos.py` se necessário."
        )

    st = calcular_status_visual(twin)
    coords = f"({twin.get('coordenada_x')}, {twin.get('coordenada_y')})"
    lines = [
        f"### Ativo selecionado — **{twin.get('tag')}**",
        "",
        f"- **Status visual:** {st}",
        f"- **Código do motor:** `{twin.get('codigo_motor')}`",
        f"- **Modelo (cadastro):** {twin.get('modelo_motor') or '—'}",
        f"- **TAG:** `{twin.get('tag')}`",
        f"- **Planta:** {twin.get('planta_nome') or '—'} (`{twin.get('planta_codigo') or '—'}`)",
        f"- **Área:** {twin.get('area_nome') or '—'}",
        f"- **Linha / setor:** {twin.get('linha_nome') or '—'}",
        f"- **Localização:** {twin.get('localizacao_descricao') or twin.get('localizacao_codigo') or '—'}",
        f"- **Coordenadas:** {coords}",
        f"- **Status operacional (cadastro):** {twin.get('status_operacional') or '—'}",
        f"- **Última atualização da associação:** {twin.get('associacao_atualizada_em') or '—'}",
        "",
    ]
    if perfil == "manutencao":
        lines.append("_Perfil manutenção: visão operacional e resumo técnico._")
    elif perfil == "engenharia":
        lines.append("_Perfil engenharia: inclui histórico, anomalias e dados completos da placa._")
    else:
        lines.append("_Perfil admin: inclui trilha de auditoria recente._")
    return "\n".join(lines)


def _markdown_placa(twin: dict[str, Any] | None, perfil: str) -> str:
    if not twin or not twin.get("tag"):
        return "### Dados da placa\n\n—"
    if not twin.get("placa_modelo") and not twin.get("placa_fabricante"):
        return (
            "### Dados da placa\n\n**Dados técnicos ainda não integrados.** "
            "Rode `scripts/processar_placas_motores.py` após colocar JSONs em `data/raw/placas_extraidas/`."
        )

    if perfil == "manutencao":
        return "\n".join(
            [
                "### Dados técnicos (resumo)",
                "",
                f"- **Fabricante:** {twin.get('placa_fabricante') or '—'}",
                f"- **Modelo:** {twin.get('placa_modelo') or '—'}",
                f"- **Potência (nominal):** {twin.get('placa_potencia') or '—'}",
                f"- **Confiança da extração:** "
                f"{twin.get('confianca_extracao') if twin.get('confianca_extracao') is not None else '—'}",
            ]
        )

    return "\n".join(
        [
            "### Dados técnicos da placa (completos)",
            "",
            f"- **Fabricante:** {twin.get('placa_fabricante') or '—'}",
            f"- **Modelo:** {twin.get('placa_modelo') or '—'}",
            f"- **Número de série:** {twin.get('placa_numero_serie') or '—'}",
            f"- **Potência:** {twin.get('placa_potencia') or '—'}",
            f"- **Tensão nominal (V):** {twin.get('placa_tensao_nominal') or '—'}",
            f"- **Corrente nominal (A):** {twin.get('placa_corrente_nominal') or '—'}",
            f"- **RPM nominal:** {twin.get('placa_rpm_nominal') or '—'}",
            f"- **Frequência (Hz):** {twin.get('placa_frequencia') or '—'}",
            f"- **Fator de serviço:** {twin.get('placa_fator_servico') or '—'}",
            f"- **Rendimento (%):** {twin.get('placa_rendimento') or '—'}",
            f"- **Confiança da extração:** "
            f"{twin.get('confianca_extracao') if twin.get('confianca_extracao') is not None else '—'}",
            f"- **Origem da imagem (OCR simulado):** {twin.get('origem_imagem') or '—'}",
        ]
    )


def _html_metricas_atuais(twin: dict[str, Any] | None) -> str:
    if not twin or not twin.get("tag"):
        return "<p style='color:#94a3b8'>Sem dados de leitura para exibir.</p>"
    if not twin.get("ultima_leitura_ts"):
        return (
            "<p style='color:#fbbf24'>Sem leituras persistidas para este motor. "
            "Execute o pipeline de telemetria.</p>"
        )

    def fmt(v: Any, unit: str) -> str:
        if v is None:
            return "—"
        return f"{float(v):.2f} {unit}"

    return f"""
    <div style="display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap:12px;">
      <div class="kpi-card default"><div class="label">Temperatura</div>
        <div class="value">{fmt(twin.get('ultima_temperatura'), '°C')}</div></div>
      <div class="kpi-card default"><div class="label">Vibração</div>
        <div class="value">{fmt(twin.get('ultima_vibracao'), 'mm/s')}</div></div>
      <div class="kpi-card default"><div class="label">Corrente</div>
        <div class="value">{fmt(twin.get('ultima_corrente'), 'A')}</div></div>
      <div class="kpi-card default"><div class="label">Tensão</div>
        <div class="value">{fmt(twin.get('ultima_tensao'), 'V')}</div></div>
      <div class="kpi-card default"><div class="label">RPM</div>
        <div class="value">{fmt(twin.get('ultima_rpm'), 'rpm')}</div></div>
    </div>
    """


def grafico_historico_por_codigo(codigo_motor: str | None, metrica: str) -> go.Figure:
    if not codigo_motor:
        return _figura_vazia("Selecione um ativo")
    df = ds.obter_telemetria_motor(codigo_motor, limite=400)
    if df.empty or metrica not in df.columns:
        return _figura_vazia("Sem histórico para esta métrica")

    cor = CORES_METRICAS.get(metrica, "#06b6d4")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df[metrica],
            mode="lines",
            name=metrica,
            line=dict(color=cor, width=2),
            hovertemplate=f"<b>{metrica}</b><br>%{{x|%d/%m/%Y %H:%M}}<br>%{{y:.2f}}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Histórico — {codigo_motor} — {metrica}",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.5)",
        height=400,
        xaxis_title="Tempo",
        yaxis_title=metrica,
        font=dict(color="#e2e8f0"),
    )
    return fig


def grafico_mapa_operacional(tag_selecionada: str | None) -> go.Figure:
    df = ds.obter_mapa_ativos_df()
    if df.empty:
        return _figura_vazia("Sem ativos com coordenadas para o mapa")

    dfc = df.copy()
    dfc["selecionado"] = dfc["tag"] == (tag_selecionada or "")
    fig = px.scatter(
        dfc,
        x="coordenada_x",
        y="coordenada_y",
        color="selecionado",
        color_discrete_map={True: "#22d3ee", False: "#64748b"},
        hover_name="tag",
        hover_data={
            "codigo_motor": True,
            "area_nome": True,
            "status_operacional": True,
            "planta_nome": True,
            "selecionado": False,
        },
        title="Mapa operacional simplificado (coordenadas da planta)",
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.5)",
        height=420,
        xaxis_title="coordenada_x",
        yaxis_title="coordenada_y",
        legend_title_text="Destaque",
        font=dict(color="#e2e8f0"),
    )
    return fig


def _render_painel(
    tag: str | None,
    perfil: str,
    metrica: str,
    *,
    tag_busca_digitada: str | None = None,
) -> tuple[Any, ...]:
    twin: dict[str, Any] | None = None
    if tag:
        twin = ds.consultar_digital_twin_por_tag(tag)
    elif tag_busca_digitada:
        twin = ds.consultar_digital_twin_por_tag(tag_busca_digitada)

    tag_hint = tag_busca_digitada if tag_busca_digitada else None
    if tag_hint and (not twin or not twin.get("tag")):
        st_md = "## TAG não encontrada"
        resumo = _markdown_resumo(None, perfil, tag_digitada=tag_hint)
        placa = "### Dados da placa\n\n—"
        html_met = _html_metricas_atuais(None)
        perfil_md = _markdown_perfil(perfil)
        return (
            perfil_md,
            st_md,
            resumo,
            placa,
            html_met,
            grafico_historico_por_codigo(None, metrica or "temperatura"),
            grafico_mapa_operacional(None),
            gr.update(value=pd.DataFrame(), visible=False),
            gr.update(value=pd.DataFrame(), visible=False),
        )

    codigo = twin.get("codigo_motor") if twin else None

    st_md = f"## Status visual: **{calcular_status_visual(twin)}**"
    resumo = _markdown_resumo(twin, perfil, tag_digitada=None)
    placa = _markdown_placa(twin, perfil)
    html_met = _html_metricas_atuais(twin)
    fig_hist = grafico_historico_por_codigo(codigo, metrica or "temperatura")
    fig_map = grafico_mapa_operacional(tag)

    if perfil in ("engenharia", "admin") and codigo:
        anom = ds.listar_anomalias_por_motor(codigo, limite=30)
    else:
        anom = pd.DataFrame()

    if perfil == "admin":
        audit = ds.listar_auditoria_operacional_df(40)
    else:
        audit = pd.DataFrame()

    perfil_md = _markdown_perfil(perfil)

    return (
        perfil_md,
        st_md,
        resumo,
        placa,
        html_met,
        fig_hist,
        fig_map,
        gr.update(value=anom, visible=perfil in ("engenharia", "admin")),
        gr.update(value=audit, visible=perfil == "admin"),
    )


def registrar_aba_digital_twin() -> None:
    """Deve ser chamado dentro de `with gr.Tabs():`."""
    with gr.Tab("🧭 Digital Twin Operacional"):
        gr.Markdown(
            "### Navegação operacional e Digital Twin\n"
            "Contextualize o ativo na planta, consulte TAG, telemetria e dados da placa "
            "(integração OCR **simulada** via JSON)."
        )

        perfil = gr.Radio(
            choices=["manutencao", "engenharia", "admin"],
            value="manutencao",
            label="Perfil de visualização (demonstrativo)",
        )
        perfil_info = gr.Markdown(value=_markdown_perfil("manutencao"))

        planta = gr.Dropdown(
            label="Planta (código)",
            choices=ds.listar_codigos_plantas(),
            value=None,
        )
        area = gr.Dropdown(label="Área (código)", choices=[], value=None)
        linha = gr.Dropdown(label="Linha / setor (código)", choices=[], value=None)
        tag_dd = gr.Dropdown(label="Ativo (TAG)", choices=[], value=None)

        gr.Markdown("#### Busca rápida por TAG")
        with gr.Row():
            tag_busca = gr.Textbox(label="TAG", placeholder="Ex.: MTR-L01-BOM-001")
            btn_busca = gr.Button("Buscar TAG", variant="primary")

        status_md = gr.Markdown(value="## Status visual: **Sem associação**")
        resumo_md = gr.Markdown()
        placa_md = gr.Markdown()
        metricas_html = gr.HTML()
        metrica_sel = gr.Dropdown(choices=METRICAS, value="temperatura", label="Métrica do histórico")
        graf_hist = gr.Plot(value=grafico_historico_por_codigo(None, "temperatura"))
        graf_mapa = gr.Plot(value=grafico_mapa_operacional(None))
        tbl_anom = gr.Dataframe(label="Anomalias recentes (engenharia/admin)", interactive=False, visible=False)
        tbl_audit = gr.Dataframe(label="Auditoria operacional (admin)", interactive=False, visible=False)

        outs = [
            perfil_info,
            status_md,
            resumo_md,
            placa_md,
            metricas_html,
            graf_hist,
            graf_mapa,
            tbl_anom,
            tbl_audit,
        ]

        def on_planta(pc: str | None):
            areas = ds.listar_codigos_areas(pc)
            return (
                gr.update(choices=areas, value=None),
                gr.update(choices=[], value=None),
                gr.update(choices=[], value=None),
            )

        def on_area(pc: str | None, ac: str | None):
            linhas = ds.listar_codigos_linhas(pc, ac)
            return gr.update(choices=linhas, value=None), gr.update(choices=[], value=None)

        def on_linha(pc: str | None, ac: str | None, lc: str | None):
            tags = ds.listar_tags_por_hierarquia(pc, ac, lc)
            return gr.update(choices=tags, value=None)

        planta.change(on_planta, inputs=planta, outputs=[area, linha, tag_dd])
        area.change(on_area, inputs=[planta, area], outputs=[linha, tag_dd])
        linha.change(on_linha, inputs=[planta, area, linha], outputs=tag_dd)

        def refresh_painel(tag, perf, met):
            return _render_painel(tag, perf, met)

        tag_dd.change(refresh_painel, inputs=[tag_dd, perfil, metrica_sel], outputs=outs)
        perfil.change(refresh_painel, inputs=[tag_dd, perfil, metrica_sel], outputs=outs)
        metrica_sel.change(refresh_painel, inputs=[tag_dd, perfil, metrica_sel], outputs=outs)

        def buscar_tag(tb: str, perf: str, met: str):
            t = (tb or "").strip()
            if not t:
                return _render_painel(None, perf, met)
            twin = ds.consultar_digital_twin_por_tag(t)
            if not twin:
                return _render_painel(None, perf, met, tag_busca_digitada=t)
            return _render_painel(str(twin.get("tag")), perf, met)

        btn_busca.click(buscar_tag, inputs=[tag_busca, perfil, metrica_sel], outputs=outs)
