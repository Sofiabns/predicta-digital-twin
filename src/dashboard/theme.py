"""Tema customizado do dashboard Predicta."""

import gradio as gr

# Tema escuro industrial com toques de azul/ciano
predicta_theme = gr.themes.Soft(
    primary_hue="cyan",
    secondary_hue="blue",
    neutral_hue="slate",
).set(
    body_background_fill="*neutral_950",
    body_background_fill_dark="*neutral_950",
    background_fill_primary="*neutral_900",
    background_fill_primary_dark="*neutral_900",
    block_background_fill="*neutral_900",
    block_background_fill_dark="*neutral_900",
    block_border_width="1px",
    block_title_text_weight="600",
    button_primary_background_fill="*primary_600",
    button_primary_background_fill_hover="*primary_500",
)

# CSS customizado
CUSTOM_CSS = """
.gradio-container {
    font-family: 'Inter', -apple-system, sans-serif;
}

#header-banner {
    background: linear-gradient(135deg, #0891b2 0%, #1e40af 100%);
    padding: 24px 32px;
    border-radius: 12px;
    margin-bottom: 16px;
    color: white;
}

#header-banner h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    color: white;
}

#header-banner p {
    margin: 4px 0 0 0;
    opacity: 0.9;
    font-size: 14px;
}

.kpi-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #334155;
    text-align: center;
}

.kpi-card .label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #94a3b8;
    margin-bottom: 8px;
}

.kpi-card .value {
    font-size: 32px;
    font-weight: 700;
    color: #06b6d4;
}

.kpi-card.warning .value { color: #f59e0b; }
.kpi-card.danger .value  { color: #ef4444; }
.kpi-card.success .value { color: #10b981; }

/* Tabelas com altura controlada, scroll e text-wrap */
.gradio-container table {
    table-layout: auto !important;
    width: 100% !important;
}
.gradio-container table th {
    display: table-cell !important;
    white-space: nowrap !important;
    height: 36px !important;
    max-height: 36px !important;
    padding: 6px 12px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    vertical-align: middle !important;
    background-color: #0f172a !important;
}
.gradio-container table td {
    display: table-cell !important;
    white-space: normal !important;
    height: auto !important;
    padding: 6px 12px !important;
    font-size: 12px !important;
    vertical-align: middle !important;
}
.table-wrap {
    max-height: 320px !important;
    overflow-y: auto !important;
    overflow-x: auto !important;
}

footer { display: none !important; }
"""
