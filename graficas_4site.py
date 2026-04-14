"""
graficas_4site.py
=================
Genera gráficas como imágenes PNG en memoria (BytesIO) para embeber en PDFs.
Usa matplotlib con estilo 4SITE (azul #0047AB + cyan #00D4D4).
"""

from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Backend sin pantalla
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

# Paleta 4SITE
C_BLUE   = "#0047AB"
C_CYAN   = "#00D4D4"
C_GREEN  = "#4CAF50"
C_YELLOW = "#FFC107"
C_RED    = "#F44336"
C_GRAY   = "#9E9E9E"
C_BG     = "#F8FAFF"
C_DARK   = "#1A1A2E"

plt.rcParams.update({
    'font.family':      'DejaVu Sans',
    'axes.facecolor':   C_BG,
    'figure.facecolor': 'white',
    'axes.spines.top':  False,
    'axes.spines.right':False,
    'axes.spines.left': False,
    'axes.grid':        True,
    'grid.alpha':       0.3,
    'grid.color':       '#CCCCCC',
    'text.color':       C_DARK,
})


def _guardar(fig, dpi=150):
    """Guarda figura en BytesIO y la retorna"""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────
# SCORE GAUGE
# ─────────────────────────────────────────────────────────────────
def grafica_score_gauge(score, nivel, ancho=4, alto=2.2):
    """Medidor semicircular del score de viabilidad"""
    fig, ax = plt.subplots(figsize=(ancho, alto))
    ax.set_aspect('equal')
    ax.axis('off')

    # Color según score
    if score >= 70:   color = C_GREEN
    elif score >= 50: color = C_YELLOW
    else:             color = C_RED

    # Arco de fondo (gris)
    theta_bg = np.linspace(np.pi, 0, 100)
    ax.plot(np.cos(theta_bg), np.sin(theta_bg), color='#E0E0E0', linewidth=18,
            solid_capstyle='round')

    # Arco de valor
    pct = score / 100
    theta_val = np.linspace(np.pi, np.pi - pct * np.pi, 100)
    ax.plot(np.cos(theta_val), np.sin(theta_val), color=color, linewidth=18,
            solid_capstyle='round')

    # Texto central
    ax.text(0, 0.15, f"{score}", ha='center', va='center',
            fontsize=36, fontweight='bold', color=color)
    ax.text(0, -0.15, "/ 100", ha='center', va='center',
            fontsize=14, color='#888888')
    ax.text(0, -0.42, nivel.upper(), ha='center', va='center',
            fontsize=11, fontweight='bold', color=color)

    # Etiquetas
    ax.text(-1.05, -0.05, "0", ha='center', fontsize=8, color='#888888')
    ax.text(1.05, -0.05, "100", ha='center', fontsize=8, color='#888888')

    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-0.6, 1.1)
    fig.patch.set_facecolor('white')
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# DESGLOSE SCORE — barras horizontales con explicación
# ─────────────────────────────────────────────────────────────────
def grafica_desglose_score(desglose, ancho=6, alto=2.5):
    """Barras horizontales del desglose del score con explicación"""
    fig, ax = plt.subplots(figsize=(ancho, alto))
    ax.axis('off')

    factores = [
        ("Densidad de\ncompetencia", desglose.get('densidad', 0), "50%",
         "Cuántos negocios similares hay en 500m"),
        ("Calidad de\ncompetencia",  desglose.get('calidad', 0),  "30%",
         "Rating promedio de los competidores"),
        ("Consolidación\ndel mercado", desglose.get('consolidacion', 0), "20%",
         "Madurez del mercado (reseñas promedio)"),
    ]

    y_positions = [0.78, 0.48, 0.18]
    for (nombre, valor, peso, desc), y in zip(factores, y_positions):
        # Barra de fondo
        bar_bg = mpatches.FancyBboxPatch((0.28, y - 0.06), 0.60, 0.14,
            boxstyle="round,pad=0.01", facecolor='#E8EEF8', edgecolor='none')
        ax.add_patch(bar_bg)
        # Barra de valor
        bar_val = mpatches.FancyBboxPatch((0.28, y - 0.06), 0.60 * valor / 100, 0.14,
            boxstyle="round,pad=0.01",
            facecolor=C_GREEN if valor >= 70 else C_YELLOW if valor >= 45 else C_RED,
            edgecolor='none', alpha=0.85)
        ax.add_patch(bar_val)

        # Textos
        ax.text(0.26, y + 0.02, nombre, ha='right', va='center', fontsize=8.5,
                fontweight='bold', color=C_DARK)
        ax.text(0.895, y + 0.02, f"{valor}/100", ha='left', va='center',
                fontsize=9, fontweight='bold', color=C_BLUE)
        ax.text(0.28, y - 0.11, desc, ha='left', va='top', fontsize=7,
                color='#888888')
        ax.text(0.895, y - 0.06, f"Peso: {peso}", ha='left', va='center',
                fontsize=7, color='#888888')

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("¿Cómo se calcula el score?", fontsize=10, fontweight='bold',
                 color=C_BLUE, pad=8)
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# TRÁFICO HORARIO — barras verticales 24h
# ─────────────────────────────────────────────────────────────────
def grafica_trafico_horario(trafico_horario, tipo_negocio_nombre="", ancho=7, alto=3):
    """Barras de tráfico estimado por hora (0-23h)"""
    fig, ax = plt.subplots(figsize=(ancho, alto))

    horas  = list(range(24))
    colores = []
    for v in trafico_horario:
        if v >= 75:   colores.append(C_BLUE)
        elif v >= 50: colores.append(C_CYAN)
        elif v >= 30: colores.append('#90CAF9')
        else:         colores.append('#E0E0E0')

    bars = ax.bar(horas, trafico_horario, color=colores, width=0.75,
                  edgecolor='white', linewidth=0.5)

    # Marcar horas pico
    max_val = max(trafico_horario)
    for i, (bar, val) in enumerate(zip(bars, trafico_horario)):
        if val >= max_val * 0.90:
            ax.text(bar.get_x() + bar.get_width()/2, val + 1.5,
                    '▲', ha='center', fontsize=7, color=C_BLUE, fontweight='bold')

    ax.set_xticks(horas)
    ax.set_xticklabels([f"{h}h" for h in horas], fontsize=7, rotation=45)
    ax.set_ylabel("Flujo relativo (%)", fontsize=9)
    ax.set_ylim(0, 115)
    ax.set_title(f"Perfil de Tráfico Estimado — {tipo_negocio_nombre}",
                 fontsize=10, fontweight='bold', color=C_BLUE)

    # Leyenda
    patches = [
        mpatches.Patch(color=C_BLUE,   label='Muy alto (≥75%)'),
        mpatches.Patch(color=C_CYAN,   label='Alto (50-74%)'),
        mpatches.Patch(color='#90CAF9',label='Medio (30-49%)'),
        mpatches.Patch(color='#E0E0E0',label='Bajo (<30%)'),
    ]
    ax.legend(handles=patches, loc='upper right', fontsize=7, framealpha=0.8)
    ax.spines['bottom'].set_visible(True)
    ax.spines['left'].set_visible(False)

    fig.tight_layout()
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# TRÁFICO SEMANAL — heatmap 7 días
# ─────────────────────────────────────────────────────────────────
def grafica_trafico_semanal(trafico_semanal, ancho=6, alto=1.6):
    """Barras de tráfico por día de la semana"""
    fig, ax = plt.subplots(figsize=(ancho, alto))

    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    colores_d = []
    for v in trafico_semanal:
        if v >= 85:   colores_d.append(C_BLUE)
        elif v >= 65: colores_d.append(C_CYAN)
        elif v >= 45: colores_d.append('#90CAF9')
        else:         colores_d.append('#E0E0E0')

    bars = ax.bar(dias, trafico_semanal, color=colores_d, width=0.6,
                  edgecolor='white', linewidth=0.5)

    for bar, val in zip(bars, trafico_semanal):
        ax.text(bar.get_x() + bar.get_width()/2, val + 1,
                f"{val}%", ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_ylim(0, 115)
    ax.set_ylabel("Flujo (%)", fontsize=9)
    ax.set_title("Flujo por Día de la Semana", fontsize=10, fontweight='bold', color=C_BLUE)
    ax.spines['bottom'].set_visible(True)
    ax.spines['left'].set_visible(False)
    fig.tight_layout()
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# FORECAST 3 ESCENARIOS — líneas
# ─────────────────────────────────────────────────────────────────
def grafica_forecast(forecast_data, ancho=7, alto=3.5):
    """Líneas de 3 escenarios de ventas a 12 meses"""
    fig, ax = plt.subplots(figsize=(ancho, alto))

    meses = list(range(1, 13))
    escenarios_cfg = [
        ("pesimista", C_RED,   "--", "Pesimista (-40%)"),
        ("base",      C_BLUE,  "-",  "Base (esperado)"),
        ("optimista", C_GREEN, "-.", "Optimista (+50%)"),
    ]

    for key, color, ls, label in escenarios_cfg:
        ventas = forecast_data["escenarios"][key]["ventas_mensuales"]
        ax.plot(meses, [v/1000 for v in ventas],
                color=color, linestyle=ls, linewidth=2.5,
                marker='o', markersize=4, label=label)
        # Anotar valor final
        ax.annotate(f"${ventas[-1]/1000:.0f}K",
                    xy=(12, ventas[-1]/1000), xytext=(12.2, ventas[-1]/1000),
                    fontsize=8, color=color, fontweight='bold', va='center')

    ax.set_xticks(meses)
    ax.set_xticklabels([f"M{m}" for m in meses], fontsize=8)
    ax.set_ylabel("Ventas mensuales (miles MXN)", fontsize=9)
    ax.set_xlabel("Mes de operación", fontsize=9)
    ax.set_title("Forecast de Ventas — 12 Meses (3 Escenarios)", fontsize=10,
                 fontweight='bold', color=C_BLUE)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    ax.set_xlim(0.5, 13.5)

    # Zona de rampa
    ax.axvspan(0.5, 4.5, alpha=0.06, color=C_YELLOW, label='Período de apertura')
    ax.text(2.5, ax.get_ylim()[1] * 0.95, "Apertura", ha='center',
            fontsize=8, color='#888888', fontstyle='italic')

    fig.tight_layout()
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# MERCADO POTENCIAL — donut
# ─────────────────────────────────────────────────────────────────
def grafica_mercado_donut(mercado_data, ancho=5, alto=3.2):
    """Donut chart del mercado total vs captura estimada"""
    fig, ax = plt.subplots(figsize=(ancho, alto))

    captura_pct = mercado_data["factor_captura_pct"]
    resto_pct   = 100 - captura_pct

    wedges, texts = ax.pie(
        [captura_pct, resto_pct],
        colors=[C_BLUE, '#E8EEF8'],
        startangle=90,
        wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2),
    )

    # Centro
    ax.text(0, 0.08, f"{captura_pct:.0f}%", ha='center', va='center',
            fontsize=24, fontweight='bold', color=C_BLUE)
    ax.text(0, -0.22, "captura\nestimada", ha='center', va='center',
            fontsize=9, color='#888888')

    # Números clave al lado
    ax.text(1.1, 0.4,  "Mercado total:", ha='left', fontsize=8, color='#555555')
    ax.text(1.1, 0.2,  f"${mercado_data['mercado_total_mensual']/1000:.0f}K/mes",
            ha='left', fontsize=9, fontweight='bold', color=C_DARK)
    ax.text(1.1, -0.05, "Tu captura:", ha='left', fontsize=8, color='#555555')
    ax.text(1.1, -0.25, f"${mercado_data['mercado_captura_mensual']/1000:.0f}K/mes",
            ha='left', fontsize=9, fontweight='bold', color=C_BLUE)
    ax.text(1.1, -0.50, f"~{mercado_data['clientes_dia_estimados']} clientes/día",
            ha='left', fontsize=8, color=C_CYAN, fontweight='bold')

    ax.set_title("Tamaño de Mercado Potencial (500m radio)",
                 fontsize=10, fontweight='bold', color=C_BLUE, pad=10)
    ax.set_xlim(-1.1, 2.2)
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# ROI + RECUPERACIÓN — dashboard compacto
# ─────────────────────────────────────────────────────────────────
def grafica_roi_dashboard(roi_data, forecast_data, ancho=7, alto=3):
    """Dashboard de ROI con 4 KPIs y gráfica de recuperación"""
    fig = plt.figure(figsize=(ancho, alto))
    gs  = gridspec.GridSpec(2, 4, figure=fig, hspace=0.5, wspace=0.4)

    # ── KPIs ─────────────────────────────────────────────
    kpis = [
        ("ROI 12 meses",   f"{roi_data['roi_12m_pct']}%",        C_BLUE),
        ("Recuperación",   f"{roi_data['meses_recuperacion']} meses", C_CYAN),
        ("Utilidad/mes",   f"${roi_data['utilidad_mensual_est']/1000:.0f}K", C_GREEN),
        ("Punto equilibrio", f"${roi_data['punto_eq_ventas_mes']/1000:.0f}K/mes", C_YELLOW),
    ]

    for i, (label, valor, color) in enumerate(kpis):
        ax_kpi = fig.add_subplot(gs[0, i])
        ax_kpi.axis('off')
        ax_kpi.add_patch(mpatches.FancyBboxPatch(
            (0.05, 0.1), 0.9, 0.85,
            boxstyle="round,pad=0.05",
            facecolor=f"{color}18", edgecolor=color, linewidth=1.5
        ))
        ax_kpi.text(0.5, 0.72, valor, ha='center', va='center',
                    fontsize=14, fontweight='bold', color=color)
        ax_kpi.text(0.5, 0.32, label, ha='center', va='center',
                    fontsize=7.5, color='#555555')
        ax_kpi.set_xlim(0, 1); ax_kpi.set_ylim(0, 1)

    # ── Gráfica acumulado vs inversión ────────────────────
    ax_rec = fig.add_subplot(gs[1, :])
    meses  = list(range(0, 13))
    ventas_base = [0] + forecast_data["escenarios"]["base"]["ventas_mensuales"]
    utilidad_acum = [0]
    for v in ventas_base[1:]:
        utilidad_acum.append(utilidad_acum[-1] + int(v * 0.35))

    inversion = roi_data["inversion_min"]
    ax_rec.fill_between(meses, [u/1000 for u in utilidad_acum],
                         alpha=0.25, color=C_BLUE, label='Utilidad acumulada')
    ax_rec.plot(meses, [u/1000 for u in utilidad_acum],
                color=C_BLUE, linewidth=2)
    ax_rec.axhline(y=inversion/1000, color=C_RED, linestyle='--',
                   linewidth=1.5, label=f'Inversión (${inversion/1000:.0f}K)')

    # Punto de cruce
    for i, u in enumerate(utilidad_acum):
        if u >= inversion and i > 0:
            ax_rec.axvline(x=i, color=C_YELLOW, linestyle=':', linewidth=1.5)
            ax_rec.text(i + 0.2, inversion/1000 * 1.05,
                        f"M{i}", fontsize=8, color=C_YELLOW, fontweight='bold')
            break

    ax_rec.set_xticks(meses)
    ax_rec.set_xticklabels([f"M{m}" for m in meses], fontsize=7)
    ax_rec.set_ylabel("Miles MXN", fontsize=8)
    ax_rec.set_title("Curva de Recuperación de Inversión", fontsize=9,
                     fontweight='bold', color=C_BLUE)
    ax_rec.legend(fontsize=7, loc='upper left')
    ax_rec.spines['bottom'].set_visible(True)
    ax_rec.spines['left'].set_visible(False)

    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# DEMOGRAFÍA — distribución de edad + NSE
# ─────────────────────────────────────────────────────────────────
def grafica_demografia(datos_inegi, ancho=6, alto=2.8):
    """Pie de distribución de edad + barra de NSE"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(ancho, alto))

    # Distribución de edad
    dist = datos_inegi.get("distribucion_edad",
                            {"0-17": 25, "18-35": 33, "36-55": 27, "56+": 15})
    colores_edad = [C_CYAN, C_BLUE, '#5C6BC0', C_GRAY]
    wedges, texts, autotexts = ax1.pie(
        list(dist.values()),
        labels=list(dist.keys()),
        colors=colores_edad,
        autopct='%1.0f%%',
        startangle=90,
        wedgeprops=dict(edgecolor='white', linewidth=1.5),
        textprops={'fontsize': 8}
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_fontweight('bold')
    ax1.set_title("Distribución de Edad", fontsize=9,
                  fontweight='bold', color=C_BLUE)

    # NSE visual
    nse_orden = ["A", "A/B", "B", "B/C+", "C+", "C", "C/D+", "D+", "D/E"]
    nse_colores_bar = ["#7B1FA2","#9C27B0","#1976D2","#0097A7",
                       "#2E7D32","#558B2F","#F57F17","#E65100","#B71C1C"]
    nse_actual = datos_inegi.get("nse_predominante", "C")
    valores = [100 if n == nse_actual else 15 for n in nse_orden]

    bars = ax2.barh(nse_orden, valores,
                    color=[nse_colores_bar[i] if nse_orden[i] == nse_actual
                           else '#E8EEF8' for i in range(len(nse_orden))],
                    edgecolor='white', linewidth=0.5)
    ax2.set_xlim(0, 130)
    ax2.set_xlabel("", fontsize=0)
    ax2.set_title("NSE Predominante", fontsize=9, fontweight='bold', color=C_BLUE)

    # Flecha al NSE actual
    idx = nse_orden.index(nse_actual)
    ax2.text(105, idx, f"◄ {nse_actual}", va='center',
             fontsize=9, fontweight='bold',
             color=nse_colores_bar[idx])
    ax2.spines['bottom'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.tick_params(bottom=False)
    ax2.set_xticks([])

    fig.suptitle("Perfil Demográfico del Área (500m)",
                 fontsize=10, fontweight='bold', color=C_BLUE, y=1.02)
    fig.tight_layout()
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# COMPARATIVA 3 UBICACIONES — radar + barras
# ─────────────────────────────────────────────────────────────────
def grafica_comparativa(ubicaciones_data, ancho=8, alto=4):
    """
    Compara hasta 3 ubicaciones en radar + barras de score.
    ubicaciones_data: lista de dicts con keys:
      nombre, score, densidad_comp, calidad_comp, consolidacion,
      poblacion, ingreso, num_competidores
    """
    n = len(ubicaciones_data)
    if n == 0:
        return None

    fig, (ax_radar, ax_bar) = plt.subplots(1, 2, figsize=(ancho, alto),
                                            subplot_kw={'polar': False})

    colores_ub = [C_BLUE, C_GREEN, C_RED][:n]
    nombres    = [u["nombre"][:20] for u in ubicaciones_data]

    # ── Barras comparativas ──
    categorias = ["Score\nViabilidad", "Densidad\nComp.", "Calidad\nComp.", "Consolidación"]
    x = np.arange(len(categorias))
    width = 0.25

    for i, (ub, color) in enumerate(zip(ubicaciones_data, colores_ub)):
        valores = [
            ub.get("score", 0),
            ub.get("densidad_comp", 0),
            ub.get("calidad_comp", 0),
            ub.get("consolidacion", 0),
        ]
        offset = (i - (n-1)/2) * width
        bars = ax_bar.bar(x + offset, valores, width, label=nombres[i],
                           color=color, alpha=0.85, edgecolor='white')
        for bar, val in zip(bars, valores):
            ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        str(val), ha='center', fontsize=7, fontweight='bold')

    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(categorias, fontsize=8)
    ax_bar.set_ylim(0, 120)
    ax_bar.set_ylabel("Score (0-100)", fontsize=9)
    ax_bar.set_title("Comparativa de Scores", fontsize=10,
                     fontweight='bold', color=C_BLUE)
    ax_bar.legend(fontsize=8)
    ax_bar.spines['left'].set_visible(False)

    # ── Radar chart ──
    categorias_radar = ["Score", "Demanda", "Accesibilidad", "NSE", "Sin\ncompetencia"]
    N = len(categorias_radar)
    angles = [n_a / float(N) * 2 * np.pi for n_a in range(N)]
    angles += angles[:1]

    ax_radar.remove()
    ax_radar = fig.add_subplot(1, 2, 1, polar=True)

    for i, (ub, color) in enumerate(zip(ubicaciones_data, colores_ub)):
        nse_score = {"A": 100, "A/B": 90, "B": 80, "B/C+": 70,
                     "C+": 60, "C": 50, "C/D+": 40, "D+": 30, "D/E": 20}
        valores_r = [
            ub.get("score", 50),
            min(100, ub.get("poblacion", 5000) / 150),
            70,  # Accesibilidad estimada
            nse_score.get(ub.get("nse", "C"), 50),
            max(0, 100 - ub.get("num_competidores", 5) * 8),
        ]
        valores_r += valores_r[:1]

        ax_radar.plot(angles, valores_r, color=color, linewidth=2,
                      linestyle='solid', label=nombres[i])
        ax_radar.fill(angles, valores_r, color=color, alpha=0.15)

    ax_radar.set_xticks(angles[:-1])
    ax_radar.set_xticklabels(categorias_radar, fontsize=8)
    ax_radar.set_ylim(0, 100)
    ax_radar.set_yticks([25, 50, 75, 100])
    ax_radar.set_yticklabels(["25", "50", "75", "100"], fontsize=6)
    ax_radar.set_title("Radar Comparativo", fontsize=10,
                       fontweight='bold', color=C_BLUE, pad=15)
    ax_radar.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=8)

    fig.tight_layout()
    return _guardar(fig)


# ─────────────────────────────────────────────────────────────────
# DASHBOARD PREMIUM — una sola imagen con todos los KPIs
# ─────────────────────────────────────────────────────────────────
def grafica_dashboard_premium(score, desglose, mercado_data, forecast_data,
                               roi_data, trafico_data, datos_inegi, ancho=8.5, alto=11,
                               titulo_negocio=""):
    """Una página completa con todos los KPIs del análisis"""
    fig = plt.figure(figsize=(ancho, alto), facecolor='white')
    fig.patch.set_facecolor('white')

    # Grid: 5 filas × 4 columnas
    gs = gridspec.GridSpec(5, 4, figure=fig, hspace=0.55, wspace=0.35,
                           left=0.06, right=0.96, top=0.93, bottom=0.04)

    # ── Fila 0: Header ──
    ax_header = fig.add_subplot(gs[0, :])
    ax_header.axis('off')
    ax_header.add_patch(mpatches.FancyBboxPatch(
        (0, 0), 1, 1, transform=ax_header.transAxes,
        boxstyle="round,pad=0.02",
        facecolor=C_BLUE, edgecolor='none', clip_on=False))
    ax_header.text(0.5, 0.70, "4SITE — DASHBOARD EJECUTIVO",
                   ha='center', va='center', fontsize=14,
                   fontweight='bold', color='white', transform=ax_header.transAxes)
    subtitulo = titulo_negocio if titulo_negocio else "Análisis completo de viabilidad comercial"
    ax_header.text(0.5, 0.28, subtitulo,
                   ha='center', va='center', fontsize=10,
                   color=C_CYAN, fontweight='bold', transform=ax_header.transAxes)

    # ── Fila 1: Score + 3 KPIs ──
    kpis_top = [
        ("Score de\nViabilidad", f"{score}/100",
         C_GREEN if score >= 70 else C_YELLOW if score >= 50 else C_RED),
        ("Mercado\nMensual", f"${mercado_data.get('mercado_captura_mensual',0)/1000:.0f}K", C_BLUE),
        ("Clientes/\nDía est.", str(mercado_data.get('clientes_dia_estimados', 0)), C_CYAN),
        ("ROI\n12 meses", f"{roi_data.get('roi_12m_pct',0)}%",
         C_GREEN if roi_data.get('roi_12m_pct',0) > 20 else C_YELLOW),
    ]
    for i, (label, valor, color) in enumerate(kpis_top):
        ax_k = fig.add_subplot(gs[1, i])
        ax_k.axis('off')
        ax_k.add_patch(mpatches.FancyBboxPatch(
            (0.05, 0.1), 0.9, 0.85, transform=ax_k.transAxes,
            boxstyle="round,pad=0.05",
            facecolor=f"{color}15", edgecolor=color, linewidth=2, clip_on=False))
        ax_k.text(0.5, 0.68, valor, ha='center', va='center', fontsize=16,
                  fontweight='bold', color=color, transform=ax_k.transAxes)
        ax_k.text(0.5, 0.28, label, ha='center', va='center', fontsize=8,
                  color='#555', transform=ax_k.transAxes)

    # ── Fila 2: Tráfico horario ──
    ax_tr = fig.add_subplot(gs[2, :3])
    horas = list(range(24))
    th = trafico_data.get("trafico_horario", [50]*24)
    colores_h = [C_BLUE if v >= 70 else C_CYAN if v >= 45 else '#90CAF9' if v >= 25 else '#E0E0E0'
                 for v in th]
    ax_tr.bar(horas, th, color=colores_h, width=0.75, edgecolor='white', linewidth=0.3)
    ax_tr.set_xticks(horas)
    ax_tr.set_xticklabels([f"{h}h" for h in horas], fontsize=6, rotation=45)
    ax_tr.set_ylim(0, 115)
    ax_tr.set_title("Tráfico Estimado por Hora", fontsize=9, fontweight='bold', color=C_BLUE)
    ax_tr.spines['left'].set_visible(False)
    ax_tr.tick_params(left=False)
    ax_tr.set_yticks([])

    # ── Fila 2 col 3: Días semana ──
    ax_ds = fig.add_subplot(gs[2, 3])
    dias_c = ["L","M","X","J","V","S","D"]
    ts = trafico_data.get("trafico_semanal", [75]*7)
    colores_dias = [C_BLUE if v >= 85 else C_CYAN if v >= 65 else '#E0E0E0' for v in ts]
    ax_ds.barh(dias_c, ts, color=colores_dias, edgecolor='white', linewidth=0.3)
    ax_ds.set_xlim(0, 115)
    ax_ds.set_title("Por Día", fontsize=9, fontweight='bold', color=C_BLUE)
    ax_ds.spines['bottom'].set_visible(False)
    ax_ds.set_xticks([])

    # ── Fila 3: Forecast 3 escenarios ──
    ax_fc = fig.add_subplot(gs[3, :3])
    meses_fc = list(range(1, 13))
    for key, color, ls in [("pesimista", C_RED, "--"), ("base", C_BLUE, "-"),
                            ("optimista", C_GREEN, "-.")]:
        ventas = forecast_data["escenarios"][key]["ventas_mensuales"]
        ax_fc.plot(meses_fc, [v/1000 for v in ventas],
                   color=color, linestyle=ls, linewidth=2, label=key.capitalize(),
                   marker='o', markersize=3)
    ax_fc.set_xticks(meses_fc)
    ax_fc.set_xticklabels([f"M{m}" for m in meses_fc], fontsize=7)
    ax_fc.set_ylabel("MXN (miles)", fontsize=8)
    ax_fc.set_title("Forecast de Ventas — 3 Escenarios", fontsize=9,
                    fontweight='bold', color=C_BLUE)
    ax_fc.legend(fontsize=7, loc='upper left')
    ax_fc.spines['left'].set_visible(False)
    ax_fc.axvspan(0.5, 4.5, alpha=0.05, color=C_YELLOW)

    # ── Fila 3 col 3: Desglose score ──
    ax_sc = fig.add_subplot(gs[3, 3])
    ax_sc.axis('off')
    factores_s = [
        ("Densidad", desglose.get('densidad', 0), "50%", C_BLUE),
        ("Calidad",  desglose.get('calidad', 0),  "30%", C_CYAN),
        ("Consolid.", desglose.get('consolidacion', 0), "20%", '#5C6BC0'),
    ]
    ax_sc.set_title("Score", fontsize=9, fontweight='bold', color=C_BLUE)
    y_s = [0.72, 0.45, 0.18]
    for (nombre, val, peso, color_s), y in zip(factores_s, y_s):
        ax_sc.add_patch(mpatches.FancyBboxPatch(
            (0.02, y-0.08), 0.96, 0.18,
            boxstyle="round,pad=0.01", facecolor='#E8EEF8', edgecolor='none'))
        ax_sc.add_patch(mpatches.FancyBboxPatch(
            (0.02, y-0.08), 0.96 * val/100, 0.18,
            boxstyle="round,pad=0.01", facecolor=color_s, edgecolor='none', alpha=0.7))
        ax_sc.text(0.5, y+0.01, f"{nombre}: {val}/100 ({peso})",
                   ha='center', va='center', fontsize=7.5, fontweight='bold')
    ax_sc.set_xlim(0, 1); ax_sc.set_ylim(0, 1)

    # ── Fila 4: Demografía ──
    ax_dem = fig.add_subplot(gs[4, :2])
    ax_dem.axis('off')
    año_actual = __import__('datetime').datetime.now().year
    dem_items = [
        ("Población " + str(año_actual), f"{datos_inegi.get('poblacion_actual', datos_inegi.get('poblacion_estimada',0)):,} hab"),
        ("Viviendas habitadas", f"{datos_inegi.get('viviendas_actual', datos_inegi.get('viviendas_habitadas',0)):,}"),
        ("NSE Predominante", datos_inegi.get('nse_predominante','C')),
        ("Ingreso prom/mes", f"${datos_inegi.get('ingreso_actual', datos_inegi.get('ingreso_promedio_mensual',0)):,}"),
        ("Gasto prom/mes", f"${datos_inegi.get('gasto_actual', datos_inegi.get('gasto_promedio_mensual',0)):,}"),
        ("Crec. anual zona", f"{datos_inegi.get('tasa_crecimiento_pct',0.55):.2f}%"),
    ]
    ax_dem.set_title("Perfil Demográfico del Área", fontsize=9,
                     fontweight='bold', color=C_BLUE)
    for i, (label, valor) in enumerate(dem_items):
        col_idx = i % 2
        row_idx = i // 2
        x_pos = 0.02 + col_idx * 0.5
        y_pos = 0.80 - row_idx * 0.30
        ax_dem.add_patch(mpatches.FancyBboxPatch(
            (x_pos, y_pos - 0.12), 0.45, 0.22,
            boxstyle="round,pad=0.02",
            facecolor='#F5F8FF', edgecolor='#0047AB22', linewidth=0.5))
        ax_dem.text(x_pos + 0.225, y_pos + 0.04, valor,
                    ha='center', fontsize=9, fontweight='bold', color=C_BLUE)
        ax_dem.text(x_pos + 0.225, y_pos - 0.06, label,
                    ha='center', fontsize=7, color='#666')
    ax_dem.set_xlim(0, 1); ax_dem.set_ylim(0, 1)

    # ── Fila 4 cols 2-3: ROI ──
    ax_roi = fig.add_subplot(gs[4, 2:])
    meses_roi = list(range(0, 13))
    ventas_base_roi = [0] + forecast_data["escenarios"]["base"]["ventas_mensuales"]
    util_acum = [0]
    for v in ventas_base_roi[1:]:
        util_acum.append(util_acum[-1] + int(v * 0.35))

    inv = roi_data.get('inversion_min', 300000)
    ax_roi.fill_between(meses_roi, [u/1000 for u in util_acum],
                         alpha=0.2, color=C_BLUE)
    ax_roi.plot(meses_roi, [u/1000 for u in util_acum],
                color=C_BLUE, linewidth=2, label='Utilidad acum.')
    ax_roi.axhline(y=inv/1000, color=C_RED, linestyle='--', linewidth=1.5,
                   label=f'Inversión ${inv/1000:.0f}K')
    ax_roi.set_title("Curva de Recuperación", fontsize=9,
                     fontweight='bold', color=C_BLUE)
    ax_roi.set_xticks(meses_roi)
    ax_roi.set_xticklabels([f"M{m}" for m in meses_roi], fontsize=7)
    ax_roi.set_ylabel("Miles MXN", fontsize=8)
    ax_roi.legend(fontsize=7)
    ax_roi.spines['left'].set_visible(False)

    # ── Footer ──
    import datetime as dt_mod
    fig.text(0.5, 0.01, f"4SITE · Don't guess. Foresee. · {dt_mod.datetime.now().strftime('%d/%m/%Y')}",
             ha='center', fontsize=8, color='#999999')

    return _guardar(fig, dpi=120)
