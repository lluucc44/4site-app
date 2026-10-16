"""
dashboard_4site.py — Vista tipo "agente de análisis geoespacial" para 4SITE.

Dos piezas:
  1. construir_html_dashboard(data)  -> HTML autocontenido (Leaflet) con mapa + capas,
     score, KPIs, tráfico, perfil, ventajas/riesgos, veredicto y competidores.
  2. render_panel_agente(...)        -> Panel lateral en Streamlit con pasos del
     análisis y chat con el agente (Claude) sobre los datos del análisis.

El módulo no importa nada de la app: recibe un dict `data` ya calculado.
"""

import json
import re

import streamlit as st
import streamlit.components.v1 as components


# ════════════════════════════════════════════════════════════════
# Parseo del texto de Claude (diagnóstico / análisis)
# ════════════════════════════════════════════════════════════════

_RE_HEADER = re.compile(r"^\s*\*\*(.+?)\*\*\s*:?\s*(.*)$")


def _limpiar(txt: str) -> str:
    txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt or "")
    return txt.strip().lstrip("-•").strip()


def extraer_secciones(texto: str) -> list:
    """Todas las secciones **Título:** del texto de Claude, en orden: [{t, p:[...], b:[...]}]."""
    secs, cur = [], None
    for raw in (texto or "").split("\n"):
        linea = raw.strip()
        if not linea:
            continue
        m = _RE_HEADER.match(linea)
        if m and not linea.startswith(("-", "•")):
            titulo = m.group(1).strip().rstrip(":")
            if titulo.upper().startswith("✅ RECOMENDACIÓN FINAL") or titulo.upper().startswith("RECOMENDACIÓN FINAL"):
                cur = None
                continue
            cur = {"t": titulo, "p": [], "b": []}
            secs.append(cur)
            resto = _limpiar(m.group(2))
            if resto:
                cur["p"].append(resto)
            continue
        if linea.startswith("*") and linea.endswith("*") and not linea.startswith("**"):
            continue  # notas en cursiva (upsell)
        if cur is None:
            cur = {"t": "", "p": [], "b": []}
            secs.append(cur)
        if linea.startswith(("-", "•")):
            cur["b"].append(_limpiar(linea))
        else:
            cur["p"].append(_limpiar(linea))
    return [x for x in secs if x["t"] or x["p"] or x["b"]]


def parsear_diagnostico(texto: str) -> dict:
    """Extrae ventajas, riesgos, veredicto, confianza y resumen del texto de Claude."""
    out = {"resumen": "", "ventajas": [], "riesgos": [], "veredicto": "",
           "veredicto_txt": "", "confianza": "", "digital": "", "vial": ""}
    if not texto:
        return out

    seccion = None
    lineas = texto.split("\n")
    for i, raw in enumerate(lineas):
        linea = raw.strip()
        if not linea:
            continue
        low = linea.lower()

        if "veredicto" in low or low.startswith("**🎯 recomendación") or low.startswith("**🎯 recomendacion"):
            seccion = "veredicto"
            cuerpo = _limpiar(linea.split(":", 1)[1] if ":" in linea else linea)
            if "no proceder" in low or "rechazar" in low:
                out["veredicto"] = "NO PROCEDER"
            elif "precaución" in low or "precaucion" in low or "analizar más" in low or "analizar mas" in low:
                out["veredicto"] = "PRECAUCIÓN"
            elif "proceder" in low or "tomar" in low:
                out["veredicto"] = "PROCEDER"
            # En el formato de validar, la justificación viene tras " — "
            if "—" in cuerpo:
                out["veredicto_txt"] = cuerpo.split("—", 1)[1].strip()
            continue
        if "nivel de confianza" in low:
            out["confianza"] = _limpiar(linea.split(":", 1)[1] if ":" in linea else linea).replace("*", "")
            seccion = None
            continue

        m = _RE_HEADER.match(linea)
        if m and not linea.startswith("-"):
            titulo = m.group(1).lower()
            resto = _limpiar(m.group(2))
            if "favor" in titulo or "ventaja" in titulo:
                seccion = "ventajas"
            elif "riesgo" in titulo:
                seccion = "riesgos"
            elif "resumen" in titulo:
                seccion = "resumen"
                if resto:
                    out["resumen"] += resto + " "
            elif "digital" in titulo:
                seccion = "digital"
            elif "vial" in titulo:
                seccion = "vial"
            else:
                seccion = None
            continue

        if linea.startswith(("-", "•")):
            if seccion in ("ventajas", "riesgos"):
                out[seccion].append(_limpiar(linea))
            continue

        if seccion == "resumen":
            out["resumen"] += _limpiar(linea) + " "
        elif seccion == "veredicto":
            out["veredicto_txt"] += _limpiar(linea) + " "
        elif seccion in ("digital", "vial"):
            out[seccion] += _limpiar(linea) + " "

    for k in ("resumen", "veredicto_txt", "digital", "vial"):
        out[k] = out[k].strip()
    out["secciones"] = extraer_secciones(texto)
    return out


# ════════════════════════════════════════════════════════════════
# HTML del dashboard
# ════════════════════════════════════════════════════════════════

_HTML = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
:root{
  --navy:#13243B; --blue:#2A6FDB; --blue-2:#1F5FC2; --bg:#F3F5F9; --card:#FFFFFF;
  --line:#E3E8EF; --muted:#5C6B7A; --faint:#8C99A8; --green:#1F9D57; --amber:#D98A1F; --red:#E0524A;
  --chip:#EEF3FB;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--bg);color:var(--navy);font-family:'Montserrat',system-ui,sans-serif;font-size:12px;color-scheme:light}
.app{height:100vh;display:grid;grid-template-rows:auto 1fr;overflow:hidden}

/* ── header ── */
.top{display:flex;align-items:center;gap:14px;padding:10px 16px;background:var(--card);border-bottom:1px solid var(--line)}
.logo{font-weight:800;font-size:18px;letter-spacing:-.02em}.logo b{color:var(--blue)}
.addr{flex:1;min-width:0}
.addr .l1{font-weight:700;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.addr .l2{color:var(--muted);font-size:11px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pill{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:99px;font-weight:700;font-size:11px;white-space:nowrap}
.pill.tier{background:var(--chip);color:var(--blue)}
.pill.ver{color:#fff}

/* ── grid ── */
.grid{display:grid;grid-template-columns:270px minmax(0,1fr) 300px;gap:12px;padding:12px;min-height:0}
.col{display:flex;flex-direction:column;gap:12px;min-height:0;min-width:0;overflow:auto;padding-right:2px}
.col::-webkit-scrollbar{width:5px}.col::-webkit-scrollbar-thumb{background:#C9D3E0;border-radius:3px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;position:relative}
.card h3{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:6px}
.card h3 .sub{font-weight:500;text-transform:none;letter-spacing:0;color:var(--faint);font-size:10px}

/* ── score ── */
.score-wrap{display:flex;align-items:center;gap:12px}
.gauge{position:relative;width:118px;height:70px;flex:none}
.gauge .num{position:absolute;left:0;right:0;bottom:2px;text-align:center;font-size:30px;font-weight:800;line-height:1}
.gauge .den{position:absolute;left:0;right:0;bottom:-12px;text-align:center;font-size:9px;color:var(--faint)}
.score-meta .nivel{font-weight:800;font-size:14px}
.score-meta .tipo{color:var(--muted);font-size:11px;margin-top:3px;line-height:1.4}
.bars{margin-top:16px;display:flex;flex-direction:column;gap:8px}
.bar-row .lbl{display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px}
.bar-row .lbl span:last-child{font-weight:700}
.track{height:6px;background:#EDF1F6;border-radius:3px;overflow:hidden}
.fill{height:100%;border-radius:3px}
.adj{display:flex;justify-content:space-between;font-size:11px;padding:6px 0;border-top:1px dashed var(--line)}
.adj:first-of-type{margin-top:6px}
.adj b.pos{color:var(--green)}.adj b.neg{color:var(--red)}.adj b.neu{color:var(--muted)}

/* ── kpis ── */
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.kpi{border:1px solid var(--line);border-radius:10px;padding:9px 10px;background:#FBFCFE;position:relative;overflow:hidden}
.kpi .k{font-size:9.5px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;line-height:1.25}
.kpi .v{font-size:15px;font-weight:800;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpi .n{font-size:9.5px;color:var(--faint);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpi.lock .v{filter:blur(4px);user-select:none}
.kpi .lk{position:absolute;bottom:7px;right:7px;font-size:9px;font-weight:700;color:var(--blue);background:var(--chip);border-radius:6px;padding:1px 5px}

/* ── map ── */
.map-card{flex:1;min-height:430px;padding:0;overflow:hidden;display:flex;flex-direction:column}
#map{flex:1;min-height:380px;background:#E9EEF4}
.layers{position:absolute;top:10px;left:10px;z-index:500;display:flex;flex-wrap:wrap;gap:6px;max-width:calc(100% - 20px)}
.lyr{border:1px solid var(--line);background:rgba(255,255,255,.96);color:var(--navy);border-radius:99px;padding:6px 11px;font:600 11px 'Montserrat',sans-serif;cursor:pointer;display:flex;align-items:center;gap:6px;box-shadow:0 1px 4px rgba(19,36,59,.08)}
.lyr .dot{width:8px;height:8px;border-radius:50%;background:#C4CDD8}
.lyr.on{border-color:var(--blue);color:var(--blue)}.lyr.on .dot{background:var(--blue)}
.lyr.locked{color:var(--faint);cursor:not-allowed}
.mode{position:absolute;bottom:122px;right:10px;z-index:500;display:flex;background:#fff;border:1px solid var(--line);border-radius:99px;overflow:hidden}
.mode button{border:0;background:none;padding:6px 10px;font:600 11px 'Montserrat',sans-serif;cursor:pointer;color:var(--muted)}
.mode button.on{background:var(--blue);color:#fff}
.legend{position:absolute;bottom:10px;left:10px;z-index:500;background:rgba(255,255,255,.96);border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:10.5px;display:flex;flex-direction:column;gap:4px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.map-foot{display:flex;gap:16px;flex-wrap:wrap;padding:9px 14px;border-top:1px solid var(--line);font-size:11px;color:var(--muted)}
.map-foot b{color:var(--navy)}
.toast{position:absolute;left:50%;top:54px;transform:translateX(-50%);z-index:600;background:var(--navy);color:#fff;padding:8px 14px;border-radius:8px;font-size:11px;font-weight:600;opacity:0;transition:opacity .2s;pointer-events:none}
.toast.show{opacity:1}
.site-pin{width:22px;height:22px;border-radius:50%;background:var(--navy);border:3px solid #fff;box-shadow:0 0 0 3px var(--blue),0 3px 10px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px}
.num-pin{width:20px;height:20px;border-radius:50%;color:#fff;font-weight:800;font-size:10px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35)}
.leaflet-popup-content{font-family:'Montserrat',sans-serif;font-size:11.5px;margin:10px 12px}

/* ── bottom analytics row ── */
.row3{display:grid;grid-template-columns:1.25fr 1fr .9fr;gap:12px}
.hm{display:grid;grid-template-columns:34px repeat(5,1fr);gap:3px;font-size:9.5px}
.hm .h{color:var(--faint);text-align:center;font-weight:600}
.hm .d{color:var(--muted);font-weight:600;display:flex;align-items:center}
.hm .c{height:17px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700}
.hours{display:flex;align-items:flex-end;gap:2px;height:92px}
.hours div{flex:1;border-radius:2px 2px 0 0;min-height:2px}
.hours-ax{display:flex;justify-content:space-between;font-size:9px;color:var(--faint);margin-top:4px}
.peaks{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}
.peaks span{background:var(--chip);color:var(--blue);border-radius:6px;padding:2px 7px;font-size:10px;font-weight:700}
.age{display:flex;flex-direction:column;gap:7px}
.age .r{display:grid;grid-template-columns:38px 1fr 30px;gap:6px;align-items:center;font-size:10.5px}
.age .r span:last-child{text-align:right;font-weight:700}
.nse{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.nse .b{font-size:20px;font-weight:800;color:var(--blue);background:var(--chip);border-radius:8px;padding:4px 10px}
.nse .t{font-size:10.5px;color:var(--muted);line-height:1.4}

/* ── locks ── */
.locked-body{position:relative}
.locked-body > .inner{filter:blur(5px);pointer-events:none;user-select:none}
.lock-over{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;z-index:5}
.lock-over span{background:var(--navy);color:#fff;font-weight:700;font-size:11px;border-radius:8px;padding:7px 12px;box-shadow:0 4px 14px rgba(19,36,59,.25);text-align:center}

/* ── right rail ── */
.verdict{border-radius:12px;padding:13px 14px;color:#fff}
.verdict .k{font-size:10px;font-weight:700;letter-spacing:.08em;opacity:.85;text-transform:uppercase}
.verdict .v{font-size:19px;font-weight:800;margin:3px 0 6px}
.verdict .t{font-size:11.5px;line-height:1.5;opacity:.95}
.verdict .c{font-size:10.5px;margin-top:8px;opacity:.85}
.list{display:flex;flex-direction:column;gap:7px}
.li{display:grid;grid-template-columns:16px 1fr;gap:6px;font-size:11.5px;line-height:1.45}
.li .ic{font-weight:800}
.pros .ic{color:var(--green)}.cons .ic{color:var(--red)}
.resumen{font-size:11.5px;line-height:1.55;color:#34465C}
.comp{display:flex;flex-direction:column}
.cp{display:grid;grid-template-columns:22px 1fr auto;gap:8px;align-items:center;padding:7px 4px;border-bottom:1px solid #F0F3F7;cursor:pointer;border-radius:6px}
.cp:hover{background:#F6F9FE}
.cp .nm{font-weight:600;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cp .mt{font-size:10px;color:var(--faint);margin-top:1px}
.cp .rt{font-weight:800;font-size:12px;text-align:right}
.cp .rt small{display:block;font-weight:500;font-size:9.5px;color:var(--faint)}
.more{font-size:10.5px;color:var(--blue);font-weight:700;padding:8px 4px 0}
.rank{display:flex;flex-direction:column;gap:6px}
.rk{display:grid;grid-template-columns:18px 1fr 34px;gap:8px;align-items:center;font-size:11px}
.rk .n{color:var(--faint);font-weight:700}
.rk .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600}
.rk .sc{font-weight:800;text-align:right}
.rk{cursor:pointer;border-radius:8px;padding:4px 4px}
.rk:hover{background:#F6F9FE}.rk.on{background:#EEF3FB}
.why{display:flex;flex-direction:column;gap:4px}
.why div{display:grid;grid-template-columns:14px 1fr;gap:5px;font-size:10.5px;line-height:1.45;color:#34465C}
.rk .tr{grid-column:2/4;height:4px;background:#EDF1F6;border-radius:2px;overflow:hidden;margin-top:-3px}
.note{font-size:10px;color:var(--faint);line-height:1.45;margin-top:8px}
.tabs{display:flex;background:#fff;border:1px solid var(--line);border-radius:10px;padding:3px;gap:3px;flex:none}
.tabs button{flex:1;border:0;background:none;border-radius:8px;padding:7px 6px;font:700 11px 'Montserrat',sans-serif;color:var(--muted);cursor:pointer}
.tabs button.on{background:var(--navy);color:#fff}
.pane{display:flex;flex-direction:column;gap:12px}
.pane[hidden]{display:none}
.isec{padding:10px 0;border-bottom:1px solid #F0F3F7}
.isec:last-child{border-bottom:0}
.isec h4{font-size:12px;font-weight:800;margin-bottom:5px}
.isec p{font-size:11.5px;line-height:1.6;color:#34465C;margin-bottom:4px}
.isec ul{margin:2px 0 0 16px}.isec li{font-size:11.5px;line-height:1.55;color:#34465C;margin-bottom:3px}
.grp{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--blue);margin:4px 0 2px}
.read{font-size:11px;color:#34465C;line-height:1.5;padding:8px 14px;border-top:1px solid var(--line);background:#FAFBFD}
.tip{background:#F6F9FE;border-left:3px solid var(--blue);border-radius:0 8px 8px 0;padding:8px 10px;font-size:11px;line-height:1.5;color:#34465C}

/* ── responsive ── */
@media (max-width:1180px){
  .grid{grid-template-columns:250px minmax(0,1fr)}
  .right{grid-column:1/-1}
  .grid{grid-template-columns:250px minmax(0,1fr)}
  .app{height:auto;overflow:visible}
  .col{overflow:visible}
}
@media (max-width:820px){
  .grid{grid-template-columns:minmax(0,1fr);padding:8px}
  .addr{flex-basis:100%;order:3}
  .row3{grid-template-columns:1fr}
  .map-card{min-height:420px}
  .top{flex-wrap:wrap}
}
</style></head>
<body>
<div class="app">
  <div class="top">
    <div class="logo"><b>4</b>SITE</div>
    <div class="addr"><div class="l1" id="h-addr"></div><div class="l2" id="h-sub"></div></div>
    <span class="pill tier" id="h-tier"></span>
    <span class="pill ver" id="h-ver"></span>
  </div>

  <div class="grid">
    <!-- LEFT -->
    <div class="col left">
      <div class="card">
        <h3>Score de viabilidad <span class="sub" id="s-radio"></span></h3>
        <div class="score-wrap">
          <div class="gauge"><svg viewBox="0 0 120 70" width="118" height="70" id="gauge"></svg>
            <div class="num" id="s-num"></div><div class="den">/ 100</div></div>
          <div class="score-meta"><div class="nivel" id="s-nivel"></div><div class="tipo" id="s-tipo"></div></div>
        </div>
        <div id="s-break"></div>
      </div>
      <div class="card" id="pal-card" style="display:none">
        <h3>Qué subiría el score</h3>
        <div id="pal"></div>
      </div>
      <div class="card">
        <h3>Indicadores clave</h3>
        <div class="kpis" id="kpis"></div>
      </div>
      <div class="card" id="rank-card" style="display:none">
        <h3>Ranking de giros <span class="sub">clic para ver cada uno</span></h3>
        <div class="rank" id="rank"></div>
        <div class="note" id="giro-note" style="display:none">Score, mapa y competidores cambian al giro elegido. KPIs de mercado, tráfico y recomendación del agente corresponden al giro #1.</div>
      </div>
    </div>

    <!-- CENTER -->
    <div class="col center">
      <div class="card map-card">
        <div style="position:relative;flex:1;display:flex">
          <div id="map" style="flex:1"></div>
          <div class="layers" id="layers"></div>
          <div class="mode" id="mode"><button data-m="walk" class="on">🚶 A pie</button><button data-m="car">🚗 Auto</button></div>
          <div class="legend" id="legend"></div>
          <div class="toast" id="toast"></div>
        </div>
        <div class="map-foot" id="map-foot"></div>
        <div class="read" id="map-read"></div>
      </div>
      <div class="row3">
        <div class="card" id="c-traf">
          <h3>Mapa de calor de tráfico <span class="sub">día × franja</span></h3>
          <div id="traf-body"></div>
        </div>
        <div class="card" id="c-hours">
          <h3>Flujo por hora <span class="sub" id="traf-nivel"></span></h3>
          <div id="hours-body"></div>
        </div>
        <div class="card" id="c-demo">
          <h3>Perfil del entorno</h3>
          <div id="demo-body"></div>
        </div>
      </div>
    </div>

    <!-- RIGHT -->
    <div class="col right">
      <div class="tabs" id="tabs"><button data-p="res" class="on">Resumen</button><button data-p="int">Interpretación completa</button></div>
      <div class="pane" id="pane-int" hidden><div class="card"><div id="interp"></div></div></div>
      <div class="pane" id="pane-res">
      <div class="verdict" id="verdict"></div>
      <div class="card" id="c-pros"><h3>Ventajas</h3><div id="pros"></div></div>
      <div class="card" id="c-cons"><h3>Riesgos</h3><div id="cons"></div></div>
      <div class="card">
        <h3>Competidores <span class="sub" id="comp-sub"></span></h3>
        <div class="comp" id="comp"></div>
      </div>
      <div class="card" id="c-vial"><h3>Vialidad y acceso</h3><div id="vial"></div></div>
      </div>
    </div>
  </div>
</div>

<script>
const D = __DATA__;
const L_ = D.locks || {};
const $ = id => document.getElementById(id);
const fmt = n => (n==null||isNaN(n)) ? '—' : Number(n).toLocaleString('es-MX',{maximumFractionDigits:0});
const money = n => (n==null||isNaN(n)||n===0) ? '—' : '$' + (Math.abs(n)>=1e6 ? (n/1e6).toFixed(2)+'M' : Math.abs(n)>=1e4 ? (n/1e3).toFixed(0)+'K' : fmt(n));
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const scoreColor = s => s>=65 ? '#1F9D57' : s>=50 ? '#D98A1F' : '#E0524A';
const ratingColor = r => !r ? '#9AA5B1' : r>=4.3 ? '#1F9D57' : r>=3.5 ? '#D98A1F' : '#E0524A';
function lockHTML(inner, plan){ return `<div class="locked-body"><div class="inner">${inner}</div><div class="lock-over"><span>🔒 Disponible en ${plan}</span></div></div>`; }

/* ── header ── */
$('h-addr').textContent = D.ubicacion;
$('h-sub').textContent = [D.tipo_nombre, D.modo==='recomendar' ? 'Modo: descubrir negocio' : 'Modo: validar idea', D.plaza_label].filter(Boolean).join('  ·  ');
$('h-tier').textContent = 'Plan ' + D.tier_nombre;
const V = D.diag || {};
const verColor = {'PROCEDER':'#1F9D57','PRECAUCIÓN':'#D98A1F','NO PROCEDER':'#E0524A'}[V.veredicto] || '#13243B';
if (V.veredicto){ $('h-ver').style.background = verColor; $('h-ver').textContent = '● ' + V.veredicto; } else { $('h-ver').style.display='none'; }

/* ── score ── */
function drawScore(){
  const s = Math.max(0, Math.min(100, D.score)), c = scoreColor(s);
  const a0 = Math.PI, a1 = Math.PI*(1 - s/100), r = 50, cx = 60, cy = 62;
  const p = a => [cx + r*Math.cos(a), cy - r*Math.sin(a)];
  const [x0,y0] = p(a0), [x1,y1] = p(a1), [xe,ye] = p(0);
  $('gauge').innerHTML = `<path d="M${x0} ${y0} A${r} ${r} 0 0 1 ${xe} ${ye}" stroke="#EDF1F6" stroke-width="11" fill="none" stroke-linecap="round"/>`+
    (s>0 ? `<path d="M${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1}" stroke="${c}" stroke-width="11" fill="none" stroke-linecap="round"/>` : '');
  $('s-num').textContent = Math.round(s); $('s-num').style.color = c;
  $('s-nivel').textContent = D.nivel; $('s-nivel').style.color = c;
  $('s-tipo').textContent = D.tipo_nombre || '';
  $('s-radio').textContent = 'radio ' + (D.radio_m||500) + ' m';

  const b = D.desglose || {};
  const rows = [['Densidad de competencia','densidad','50%'],['Calidad de competencia','calidad','30%'],['Consolidación del mercado','consolidacion','20%']];
  let h = '';
  if (!L_.desglose){
    h += '<div class="bars">' + rows.map(([l,k,w]) => { const v = b[k]||0; return `<div class="bar-row"><div class="lbl"><span>${l} <span style="color:#8C99A8">· ${w}</span></span><span>${v}</span></div><div class="track"><div class="fill" style="width:${v}%;background:${scoreColor(v)}"></div></div></div>`; }).join('') + '</div>';
  } else {
    h += '<div style="margin-top:14px">' + lockHTML('<div class="bars">'+rows.map(([l])=>`<div class="bar-row"><div class="lbl"><span>${l}</span><span>00</span></div><div class="track"><div class="fill" style="width:60%;background:#2A6FDB"></div></div></div>`).join('')+'</div>', 'Básico') + '</div>';
  }
  (D.ajustes||[]).forEach(a => { const cls = a.v>0?'pos':a.v<0?'neg':'neu'; h += `<div class="adj"><span>${esc(a.l)}</span><b class="${cls}">${a.v>0?'+':''}${a.v} pts</b></div>`; });
  $('s-break').innerHTML = h;
}
drawScore();

/* ── palancas (modo validar) ── */
if ((D.palancas||[]).length){
  $('pal-card').style.display='block';
  $('pal').innerHTML = D.palancas.map(p=>`<div class="adj"><span>${esc(p.l)}</span><b class="pos">+${p.v} pts</b></div>`).join('') +
    `<div class="note">Estimado con las mismas reglas del score. Si aplicas todas no se suman exactamente (el score se topa en 100).</div>`;
}

/* ── KPIs ── */
(function(){
  $('kpis').innerHTML = (D.kpis||[]).map(k => `<div class="kpi ${k.lock?'lock':''}">${k.lock?`<span class="lk">🔒 ${k.lock}</span>`:''}<div class="k">${esc(k.k)}</div><div class="v" style="${k.c&&!k.lock?'color:'+k.c:''}">${k.lock ? '$00,000' : esc(k.v)}</div>${k.n?`<div class="n">${esc(k.n)}</div>`:''}</div>`).join('');
})();

/* ── ranking (modo recomendar): clic en un giro cambia el dashboard ── */
function drawRanking(){
  const R = D.giros||[]; if (!R.length) return;
  $('rank-card').style.display='block';
  const sel = typeof giroSel==='number' ? giroSel : 0;
  let h = R.map((r,i)=>`<div class="rk ${i===sel?'on':''}" data-i="${i}"><span class="n">${i+1}</span><span class="nm">${esc(r.nombre)}</span><span class="sc" style="color:${scoreColor(r.score)}">${r.score}</span><div class="tr"><div class="fill" style="width:${r.score}%;background:${scoreColor(r.score)}"></div></div>`+
     (i===sel && (r.por_que||[]).length ? `<div class="why" style="grid-column:1/-1;margin:4px 0 2px">${r.por_que.map(w=>`<div><b style="color:${w.s==='+'?'#1F9D57':'#E0524A'}">${w.s}</b><span>${esc(w.t)}</span></div>`).join('')}</div>` : '') + `</div>`).join('');
  if (D.ranking_ocultos) h += `<div class="more">🔒 ${D.ranking_ocultos} giros más en planes superiores</div>`;
  $('rank').innerHTML = h;
  document.querySelectorAll('.rk[data-i]').forEach(e=>e.onclick=()=>selectGiro(+e.dataset.i));
}
if ((D.giros||[]).length) setTimeout(drawRanking, 0);

/* ── MAP ── */
const map = L.map('map', {zoomControl:false, attributionControl:true}).setView([D.lat, D.lng], 15);
L.control.zoom({position:'bottomright'}).addTo(map);
L.control.scale({position:'bottomright', imperial:false}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {attribution:'© OpenStreetMap © CARTO', subdomains:'abcd', maxZoom:20}).addTo(map);

const site = L.marker([D.lat, D.lng], {icon: L.divIcon({className:'', html:'<div class="site-pin">★</div>', iconSize:[22,22], iconAnchor:[11,11]}), zIndexOffset:1000})
  .bindPopup(`<b>Tu ubicación</b><br>${esc(D.ubicacion)}<br>Score: <b style="color:${scoreColor(D.score)}">${D.score}/100</b>`).addTo(map);

const G = {};
const radioCircle = L.circle([D.lat,D.lng], {radius:D.radio_m||500, color:'#2A6FDB', weight:1.5, dashArray:'5 5', fillColor:'#2A6FDB', fillOpacity:.05});
G.radio = L.layerGroup([radioCircle]);
const fitRadio = () => map.fitBounds(L.latLng(D.lat,D.lng).toBounds((D.radio_m||500)*2), {padding:[30,30]});
fitRadio();

// Isócronas
const isoColors = ['#1F9D57','#D98A1F','#E0524A'];
function buildIso(mode){
  const g = L.layerGroup();
  if (mode==='walk' && D.isocronas && D.isocronas.features){
    const feats = [...D.isocronas.features].sort((a,b)=>(b.properties.value||0)-(a.properties.value||0));
    feats.forEach((f,i)=>{ const idx = feats.length-1-i; L.geoJSON(f,{style:{color:isoColors[idx]||'#2A6FDB',weight:1.5,fillOpacity:.07}}).bindTooltip(`${Math.round((f.properties.value||0)/60)} min a pie`).addTo(g); });
  } else {
    const radii = mode==='walk' ? [400,800,1200] : [1500,3000,4500];
    [...radii].reverse().forEach((r,i)=>{ const idx = radii.length-1-i;
      L.circle([D.lat,D.lng],{radius:r,color:isoColors[idx],weight:1.5,fillColor:isoColors[idx],fillOpacity:.05}).bindTooltip(`${[5,10,15][idx]} min ${mode==='walk'?'a pie':'en auto'} (estimado)`).addTo(g); });
  }
  return g;
}
let isoMode = 'walk';
G.iso = buildIso(isoMode);

// Competidores + heatmap (se redibujan al cambiar de giro)
G.comp = L.layerGroup(); G.heat = L.layerGroup(); const compMarkers = [];
function drawCompLayers(){
G.comp.clearLayers(); G.heat.clearLayers(); compMarkers.length = 0;
(D.competidores||[]).forEach((c,i)=>{
  const col = ratingColor(c.rating);
  const m = L.marker([c.lat,c.lng], {icon: L.divIcon({className:'', html:`<div class="num-pin" style="background:${col}">${i+1}</div>`, iconSize:[20,20], iconAnchor:[10,10]})})
    .bindPopup(`<b>${esc(c.nombre)}</b><br>${c.rating?c.rating+' ★':'Sin rating'} · ${fmt(c.reviews)} reseñas<br>${fmt(c.dist)} m de tu ubicación${c.dist<=150?'<br><b style="color:#E0524A">Riesgo alto de canibalización</b>':''}`);
  m.addTo(G.comp); compMarkers[i] = m;
});
if (window.L && L.heatLayer && (D.competidores||[]).length){
  const maxR = Math.max(1, ...D.competidores.map(c=>c.reviews||0));
  const pts = D.competidores.map(c=>[c.lat, c.lng, Math.max(.25, ((c.rating||3)/5) * (Math.log((c.reviews||0)+1)/Math.log(maxR+1)))]);
  L.heatLayer(pts, {radius:38, blur:28, maxZoom:17, gradient:{.2:'#9EC5FF',.45:'#2A6FDB',.7:'#D98A1F',1:'#E0524A'}}).addTo(G.heat);
}
}
drawCompLayers();

// Canibalización
G.cani = L.layerGroup([
  L.circle([D.lat,D.lng],{radius:150,color:'#E0524A',weight:2,dashArray:'4 4',fillColor:'#E0524A',fillOpacity:.08}).bindTooltip('Zona crítica ≤150 m'),
  L.circle([D.lat,D.lng],{radius:300,color:'#D98A1F',weight:1.5,dashArray:'4 4',fill:false}).bindTooltip('Zona de influencia ≤300 m')
]);

const LAYERS = [
  {k:'radio', l:'Radio de análisis', on:true},
  {k:'comp',  l:'Competidores', on:!L_.comp_mapa, lock:L_.comp_mapa},
  {k:'iso',   l:'Isócronas', on:!L_.mapa_avanzado, lock:L_.mapa_avanzado},
  {k:'heat',  l:'Heatmap', on:false, lock:L_.mapa_avanzado},
  {k:'cani',  l:'Canibalización', on:false, lock:L_.mapa_avanzado},
];
function toast(t){ const e=$('toast'); e.textContent=t; e.classList.add('show'); clearTimeout(e._t); e._t=setTimeout(()=>e.classList.remove('show'),2200); }
function renderLayers(){
  $('layers').innerHTML = LAYERS.map(x=>`<button class="lyr ${x.on?'on':''} ${x.lock?'locked':''}" data-k="${x.k}"><span class="dot"></span>${x.l}${x.lock?' 🔒':''}</button>`).join('');
  document.querySelectorAll('.lyr').forEach(b=>b.onclick=()=>{
    const x = LAYERS.find(y=>y.k===b.dataset.k);
    if (x.lock){ toast('🔒 ' + x.l + ' disponible en ' + x.lock); return; }
    x.on = !x.on; sync(); renderLayers();
  });
}
function sync(){ LAYERS.forEach(x=>{ if (x.on && !x.lock) G[x.k].addTo(map); else map.removeLayer(G[x.k]); }); $('mode').style.display = (LAYERS[2].on && !LAYERS[2].lock) ? 'flex' : 'none'; }
renderLayers(); sync();
document.querySelectorAll('#mode button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#mode button').forEach(x=>x.classList.remove('on')); b.classList.add('on');
  isoMode = b.dataset.m; const wasOn = map.hasLayer(G.iso); map.removeLayer(G.iso); G.iso = buildIso(isoMode); if (wasOn) G.iso.addTo(map);
  if (isoMode==='car') map.setView([D.lat,D.lng],13); else fitRadio();
});

$('legend').innerHTML = `<div><i style="background:#13243B;box-shadow:0 0 0 2px #2A6FDB"></i>Tu ubicación</div>`+
  (L_.comp_mapa ? '' : `<div><i style="background:#1F9D57"></i>Rating ≥ 4.3</div><div><i style="background:#D98A1F"></i>3.5 – 4.2</div><div><i style="background:#E0524A"></i>&lt; 3.5 / sin datos</div>`);

function drawMapFoot(){
  const cs = D.competidores||[];
  const n150 = cs.filter(c=>c.dist<=150).length, n300 = cs.filter(c=>c.dist<=300).length;
  const near = cs.length ? Math.min(...cs.map(c=>c.dist)) : null;
  $('map-foot').innerHTML = `<span><b>${D.n_competidores}</b> competidores en ${D.radio_m} m</span>`+
    (L_.comp_mapa ? '' : `<span>Más cercano: <b>${near==null?'—':fmt(near)+' m'}</b></span><span>≤150 m: <b style="color:${n150?'#E0524A':'#1F9D57'}">${n150}</b></span><span>≤300 m: <b>${n300}</b></span>`)+
    `<span>Isócronas: <b>${D.isocronas ? 'red vial (ORS)' : 'estimadas por distancia'}</b></span>`;
}
drawMapFoot();

/* ── tráfico ── */
(function(){
  const T = D.trafico;
  if (!T){ $('traf-body').innerHTML = '<div class="note">Sin datos de tráfico para este análisis.</div>'; $('hours-body').innerHTML=''; return; }
  const franjas = [['Mañana',6,11],['Mediodía',12,15],['Tarde',16,19],['Noche',20,23],['Madrug.',0,5]];
  const dias = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];
  const H = T.horario||[], S = T.semanal||[];
  const vals = dias.map((d,i)=>franjas.map(([n,a,b])=>{ let s=0,c=0; for(let h=a;h<=b;h++){ s+=H[h]||0; c++; } return (S[i]||0)/100 * s/c; }));
  const mx = Math.max(1, ...vals.flat());
  const cell = v => { const t = v/mx; const bg = t>.75?'#13243B':t>.55?'#2A6FDB':t>.35?'#7FA9EE':t>.18?'#C9DBF8':'#EEF3FB'; const fg = t>.55?'#fff':'#13243B'; return `<div class="c" style="background:${bg};color:${fg}">${Math.round(t*100)}</div>`; };
  let hm = '<div class="hm"><div></div>' + franjas.map(f=>`<div class="h">${f[0]}</div>`).join('');
  dias.forEach((d,i)=>{ hm += `<div class="d">${d}</div>` + vals[i].map(cell).join(''); });
  hm += '</div><div class="note">Índice relativo de flujo (100 = máximo de la semana). Mejor día: <b>'+esc(T.dia_pico||'—')+'</b>.</div>';

  const hmx = Math.max(1,...H);
  let hb = '<div class="hours">' + H.map((v,h)=>`<div title="${String(h).padStart(2,'0')}h · ${v}%" style="height:${v/hmx*100}%;background:${v>=70?'#13243B':v>=45?'#2A6FDB':'#C9D3E0'}"></div>`).join('') + '</div><div class="hours-ax"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div>';
  hb += '<div class="peaks">' + (T.picos||[]).map(p=>`<span>${esc(p)}</span>`).join('') + '</div>';
  $('traf-nivel').textContent = T.nivel ? 'flujo ' + T.nivel.toLowerCase() : '';

  if (L_.trafico){ $('traf-body').innerHTML = lockHTML(hm,'PRO'); $('hours-body').innerHTML = lockHTML(hb,'PRO'); }
  else { $('traf-body').innerHTML = hm; $('hours-body').innerHTML = hb; }
})();

/* ── demografía ── */
(function(){
  const E = D.demo||{}; const ed = E.edad||{};
  const rows = [['0-17','0–17'],['18-35','18–35'],['36-55','36–55'],['56+','56+']];
  const mx = Math.max(1,...rows.map(r=>ed[r[0]]||0));
  let h = `<div class="nse"><div class="b">${esc(E.nse||'—')}</div><div class="t">NSE predominante<br>Ingreso ${money(E.ingreso)}/mes</div></div>`;
  h += '<div class="age">' + rows.map(([k,l])=>`<div class="r"><span>${l}</span><div class="track"><div class="fill" style="width:${(ed[k]||0)/mx*100}%;background:#2A6FDB"></div></div><span>${ed[k]||0}%</span></div>`).join('') + '</div>';
  if (E.mujeres) h += `<div class="note">Mujeres ${E.mujeres}% · Hombres ${E.hombres}%</div>`;
  $('demo-body').innerHTML = L_.demografia ? lockHTML(h,'Básico') : h;
})();

/* ── veredicto / pros / cons ── */
(function(){
  let h = `<div class="k">Recomendación del agente</div><div class="v">${esc(V.veredicto || D.nivel)}</div>`;
  const txt = V.veredicto_txt || V.resumen || '';
  if (txt) h += `<div class="t">${esc(txt.length>320 ? txt.slice(0,317)+'…' : txt)}</div>`;
  if (V.confianza) h += `<div class="c">Confianza: ${esc(V.confianza)}</div>`;
  $('verdict').style.background = `linear-gradient(135deg, ${verColor}, ${verColor}DD)`;
  $('verdict').innerHTML = h;

  const li = (arr, sym) => '<div class="list">' + arr.map(x=>`<div class="li"><span class="ic">${sym}</span><span>${esc(x)}</span></div>`).join('') + '</div>';
  const pros = V.ventajas||[], cons = V.riesgos||[];
  const nPros = L_.diag_parcial ? 1 : pros.length, nCons = L_.diag_parcial ? 0 : cons.length;
  const fake = ['Mercado con demanda comprobada en la zona','Perfil socioeconómico compatible con el ticket','Competencia con áreas de mejora detectadas'];
  $('pros').innerHTML = pros.length ? (li(pros.slice(0,nPros),'+') + (L_.diag_parcial && pros.length>1 ? '<div style="margin-top:7px">'+lockHTML(li(pros.slice(1).length?fake.slice(0,pros.length-1):fake,'+'),'Básico')+'</div>' : '')) : '<div class="note">Sin ventajas destacadas.</div>';
  $('cons').innerHTML = L_.diag_parcial ? lockHTML(li(fake,'−'),'Básico') : (cons.length ? li(cons,'−') : '<div class="note">Sin riesgos críticos detectados.</div>');
})();

/* ── competidores ── */
function drawCompList(){
  const cs = D.competidores||[]; const nShow = D.comp_visibles;
  $('comp-sub').textContent = D.n_competidores + ' en ' + D.radio_m + ' m';
  if (!cs.length){ $('comp').innerHTML = '<div class="note">No se detectaron competidores directos en el radio.</div>'; return; }
  let h = cs.slice(0,nShow).map((c,i)=>`<div class="cp" data-i="${i}"><div class="num-pin" style="background:${ratingColor(c.rating)}">${i+1}</div><div style="min-width:0"><div class="nm">${esc(c.nombre)}</div><div class="mt">${fmt(c.dist)} m · ${fmt(c.reviews)} reseñas${c.dist<=150?' · <b style="color:#E0524A">crítico</b>':''}</div></div><div class="rt" style="color:${ratingColor(c.rating)}">${c.rating?c.rating.toFixed(1):'—'}<small>★</small></div></div>`).join('');
  if (cs.length > nShow) h += `<div class="more">🔒 ${cs.length-nShow} competidores más en plan superior</div>`;
  $('comp').innerHTML = h;
  document.querySelectorAll('.cp').forEach(e=>e.onclick=()=>{
    const i = +e.dataset.i, c = cs[i];
    if (L_.comp_mapa){ toast('🔒 Ubicación de competidores disponible en Básico'); return; }
    const lay = LAYERS.find(x=>x.k==='comp'); if (!lay.on){ lay.on=true; sync(); renderLayers(); }
    map.flyTo([c.lat,c.lng],17,{duration:.6}); setTimeout(()=>compMarkers[i].openPopup(),650);
  });
}
drawCompList();

/* ── vialidad ── */
(function(){
  const A = D.vial||{}; let h = '';
  if (A.badge) h += `<div style="font-weight:700;margin-bottom:6px">${esc(A.badge)}</div>`;
  if (A.descripcion) h += `<div class="tip">${esc(A.descripcion)}</div>`;
  if (D.perfil_cap) h += `<div class="note"><b>${esc(D.perfil_cap)}</b></div>`;
  if (D.nota_vehicular) h += `<div class="note">${esc(D.nota_vehicular)}</div>`;
  if (V.digital && !L_.diag_parcial) h += `<div class="tip" style="margin-top:8px">📱 ${esc(V.digital)}</div>`;
  $('vial').innerHTML = h || '<div class="note">Sin análisis vial.</div>';
})();

setTimeout(()=>{ map.invalidateSize(); fitRadio(); }, 300);

/* ── lectura del mapa (determinística, sin IA) ── */
function drawMapRead(){
  const cs = D.competidores||[]; if (L_.comp_mapa){ $('map-read').style.display='none'; return; }
  const n150 = cs.filter(c=>c.dist<=150), fuertes = cs.filter(c=>(c.rating||0)>=4.3 && c.reviews>=100);
  let t = '💬 ';
  if (!D.n_competidores) t += `No hay competidores directos en ${fmt(D.radio_m)} m: mercado sin saturar, pero valida que exista demanda.`;
  else {
    t += `${D.n_competidores}${D.n_competidores>=20?'+':''} competidores en ${fmt(D.radio_m)} m`;
    if (D.radio_m !== 500 && D.equiv_500) t += ` (≈${D.equiv_500} por cada 500 m, que es lo que usa el score)`;
    t += '. ';
    if (n150.length) t += `${n150.length} a menos de 150 m compite${n150.length>1?'n':''} por el mismo cliente de paso. `;
    if (fuertes.length) { const f = fuertes.sort((a,b)=>b.reviews-a.reviews)[0]; t += `Rival de referencia: ${f.nombre} (${f.rating}★, ${fmt(f.reviews)} reseñas, a ${fmt(f.dist)} m).`; }
    else t += 'Ningún competidor combina rating alto y muchas reseñas: hay espacio para posicionarte como el mejor.';
  }
  if (D.n_competidores>=20) t += ' Google devuelve máximo 20 resultados: con radios grandes la cifra real puede ser mayor.';
  $('map-read').textContent = t;
}
drawMapRead();

/* ── cambio de giro (modo descubrir) ── */
let giroSel = 0;
function selectGiro(i){
  const g = (D.giros||[])[i]; if (!g) return;
  giroSel = i;
  Object.assign(D, {score:g.score, nivel:g.nivel, tipo_nombre:g.nombre, desglose:g.desglose,
                    competidores:g.competidores, n_competidores:g.n_competidores, equiv_500:g.equiv_500});
  drawScore(); drawCompLayers(); drawMapFoot(); drawCompList(); drawMapRead(); drawRanking();
  $('h-sub').textContent = [g.nombre, 'Modo: descubrir negocio · giro #'+(i+1), D.plaza_label].filter(Boolean).join('  ·  ');
  $('giro-note').style.display = i===0 ? 'none' : 'block';
}

/* ── interpretación completa ── */
(function(){
  const sec = s => `<div class="isec">${s.t?`<h4>${esc(s.t)}</h4>`:''}${(s.p||[]).map(x=>`<p>${esc(x)}</p>`).join('')}${(s.b||[]).length?'<ul>'+s.b.map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>':''}</div>`;
  let h = '';
  const S = (V.secciones||[]);
  if (S.length) h += '<div class="grp">Recomendación final del agente</div>' + S.map(sec).join('');
  const A = D.analisis_secciones||[];
  if (A.length) h += '<div class="grp" style="margin-top:12px">' + (D.modo==='recomendar' ? 'Lectura de la zona' : 'Análisis de competencia') + '</div>' + A.map(sec).join('');
  if (!h) h = '<div class="note">Sin interpretación disponible.</div>';
  $('interp').innerHTML = L_.diag_parcial ? (S.length? sec(S[0]) : '') + lockHTML(S.slice(1).map(sec).join('') || sec({t:'Interpretación completa',p:['Contenido disponible en el plan Básico.']}), 'Básico') : h;
  document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('#tabs button').forEach(x=>x.classList.remove('on')); b.classList.add('on');
    $('pane-res').hidden = b.dataset.p!=='res'; $('pane-int').hidden = b.dataset.p!=='int';
  });
})();
</script>
</body></html>"""


def _embed(html: str, height: int):
    """st.iframe en Streamlit reciente (components.v1.html está deprecado); fallback a components."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height, scrolling=True)


def construir_html_dashboard(data: dict) -> str:
    data = dict(data)
    if data.get("analisis_competencia") and not data.get("analisis_secciones"):
        data["analisis_secciones"] = extraer_secciones(data.pop("analisis_competencia"))
    data.pop("analisis_competencia", None)
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    return _HTML.replace("__DATA__", payload)


def render_dashboard(data: dict, height: int = 1000):
    """Renderiza el dashboard dentro de Streamlit."""
    _embed(construir_html_dashboard(data), height)


# ════════════════════════════════════════════════════════════════
# Panel del agente (Streamlit + Claude)
# ════════════════════════════════════════════════════════════════

LIMITE_PREGUNTAS = {"free": 1, "basic": 5, "pro": 15, "premium": 30, "premium2": 30}

SUGERENCIAS_ZONA = [
    "¿Cuál zona elegirías tú y por qué?",
    "¿Qué riesgos tiene la zona #1?",
    "¿Conviene más mercado probado o zona virgen?",
    "¿Qué debo validar en campo antes de rentar?",
]

SUGERENCIAS = [
    "¿Qué opinas de esta ubicación?",
    "¿Cuáles son los principales riesgos?",
    "¿Qué precio o ticket debería manejar?",
    "¿Cómo me diferencio de la competencia?",
]


def _contexto_agente(data: dict) -> str:
    """Contexto compacto para el agente — solo con datos desbloqueados del tier."""
    if data.get("modo") == "zona":
        ctx = {"modo": "zona potencial", "tipo_negocio": data.get("tipo_nombre"),
               "referencia": data.get("ubicacion"), "radio_km": data.get("radio_km"),
               "zonas": [{k: z.get(k) for k in ("rank", "nombre", "score", "categoria", "n_comp", "nse",
                                                "ingreso", "dist_km", "mejor", "por_que")} for z in data.get("zonas", [])],
               "hexagonos": [{k: c.get(k) for k in ("score", "categoria", "n_comp", "dist_km")} for c in data.get("celdas", [])],
               "recomendacion_agente": data.get("agente")}
        return json.dumps(ctx, ensure_ascii=False, default=str), []
    L = data.get("locks", {})
    ctx = {
        "ubicacion": data.get("ubicacion"),
        "tipo_negocio": data.get("tipo_nombre"),
        "modo": data.get("modo"),
        "score": data.get("score"),
        "nivel": data.get("nivel"),
        "ajustes_score": data.get("ajustes"),
        "competidores_en_radio": data.get("n_competidores"),
        "radio_m": data.get("radio_m"),
        "competidores": [
            {k: c.get(k) for k in ("nombre", "rating", "reviews", "dist")}
            for c in (data.get("competidores") or [])[: data.get("comp_visibles", 3)]
        ],
        "vialidad": data.get("vial"),
        "perfil_captacion": data.get("perfil_cap"),
        "plaza": data.get("plaza_label"),
    }
    if not L.get("desglose"):
        ctx["desglose_score"] = data.get("desglose")
    if not L.get("demografia"):
        ctx["demografia"] = data.get("demo")
    if not L.get("trafico") and data.get("trafico"):
        t = data["trafico"]
        ctx["trafico"] = {k: t.get(k) for k in ("nivel", "dia_pico", "picos")}
    for k in ("ticket", "mercado", "forecast", "roi"):
        if not L.get(k) and data.get(f"_{k}_raw"):
            ctx[k] = data[f"_{k}_raw"]
    if data.get("ranking"):
        ctx["ranking_giros"] = data["ranking"]
    if data.get("_diag_texto") and not L.get("diag_parcial"):
        ctx["diagnostico_previo"] = data["_diag_texto"]
    bloqueados = [k for k, v in L.items() if v and k not in ("comp_mapa", "diag_parcial")]
    return json.dumps(ctx, ensure_ascii=False, default=str), bloqueados


def _pasos_html(data: dict) -> str:
    L = data.get("locks", {})
    if data.get("modo") == "zona":
        pasos = [("Geocodificación de la referencia", True),
                 (f"Rejilla de {len(data.get('celdas', []))} hexágonos", True),
                 (f"Competencia por zona ({data.get('n_competidores', 0)} negocios)", True),
                 (f"Demografía y vialidad de las {len(data.get('zonas', []))} mejores", True),
                 ("Ranking y guía de ubicación", True),
                 ("Recomendación del agente", bool(data.get("agente")))]
    else:
        pasos = _pasos_analisis(data, L)
    return _pasos_render(pasos)


def _pasos_analisis(data, L):
    return [
        ("Geocodificación del sitio", True),
        (f"Competencia ({data.get('n_competidores', 0)} en {data.get('radio_m', 500)} m)", True),
        ("Análisis de vialidad", bool(data.get("vial"))),
        ("Demografía INEGI / NSE", not L.get("demografia")),
        ("Tráfico por hora y día", not L.get("trafico")),
        ("Isócronas y heatmap", not L.get("mapa_avanzado")),
        ("Mercado y forecast", not L.get("forecast")),
        ("ROI y punto de equilibrio", not L.get("roi")),
        ("Recomendación final", not L.get("diag_parcial")),
    ]


def _pasos_render(pasos):
    items = "".join(
        f"<div style='display:flex;gap:8px;align-items:center;padding:3px 0;font-size:11.5px;"
        f"color:{'#13243B' if ok else '#A3AEBB'}'>"
        f"<span style='width:16px;height:16px;border-radius:50%;display:inline-flex;align-items:center;"
        f"justify-content:center;font-size:10px;font-weight:800;color:#fff;"
        f"background:{'#1F9D57' if ok else '#D5DCE5'}'>{'✓' if ok else '🔒'}</span>{txt}</div>"
        for txt, ok in pasos
    )
    return (
        "<div style='border:1px solid #E3E8EF;border-radius:12px;padding:10px 12px;background:#FFFFFF;margin-bottom:10px'>"
        "<div style='font-size:10.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#5C6B7A;margin-bottom:6px'>"
        f"Herramientas usadas · {sum(1 for _, ok in pasos if ok)}/{len(pasos)}</div>{items}</div>"
    )


def render_panel_agente(claude, data: dict, tier_key: str, idioma: str = "es",
                        modelo: str = "claude-sonnet-4-5", alto_chat: int = 470):
    """Panel lateral tipo agente: pasos del análisis + chat sobre los resultados."""
    aid = data.get("id", "x")
    k_msgs = f"_agente_msgs_{aid}"
    k_pend = f"_agente_pend_{aid}"
    msgs = st.session_state.setdefault(k_msgs, [])
    limite = LIMITE_PREGUNTAS.get(tier_key, 1)
    usadas = sum(1 for m in msgs if m["role"] == "user")

    st.markdown(
        "<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
        "<div style='width:28px;height:28px;border-radius:8px;background:#2A6FDB;color:#fff;font-weight:800;"
        "display:flex;align-items:center;justify-content:center'>4</div>"
        "<div><div style='font-weight:800;font-size:14px;color:#13243B;line-height:1.1'>Agente 4SITE</div>"
        "<div style='font-size:10.5px;color:#8C99A8'>Análisis geoespacial asistido por IA</div></div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(_pasos_html(data), unsafe_allow_html=True)

    caja = st.container(height=alto_chat, border=True)

    restantes = max(limite - usadas, 0)
    if restantes > 0:
        cols = st.columns(2)
        for i, sug in enumerate(SUGERENCIAS_ZONA if data.get("modo") == "zona" else SUGERENCIAS):
            if cols[i % 2].button(sug, key=f"sug_{aid}_{i}", use_container_width=True):
                st.session_state[k_pend] = sug
        prompt = st.chat_input("Pregúntale al agente sobre esta ubicación…", key=f"chat_{aid}")
        st.caption(f"{restantes} pregunta{'s' if restantes != 1 else ''} disponible{'s' if restantes != 1 else ''} en tu plan · La IA puede cometer errores.")
    else:
        prompt = None
        st.info("Llegaste al límite de preguntas de tu plan. Los planes PRO y Premium incluyen más consultas al agente.")

    prompt = prompt or st.session_state.pop(k_pend, None)

    with caja:
        if not msgs and not prompt:
            with st.chat_message("assistant"):
                st.markdown(
                    (f"Barrí **{data.get('radio_km')} km** alrededor de **{data.get('ubicacion', '')[:50]}** buscando zonas para "
                     f"**{data.get('tipo_nombre')}**. La mejor quedó en **{(data.get('zonas') or [{}])[0].get('score', '—')}/100**. "
                     "Pregúntame cuál elegiría, qué riesgos tiene cada una o qué validar en campo.")
                    if data.get("modo") == "zona" else
                    (f"Hola, analicé **{data.get('ubicacion', '')[:60]}** para "
                     f"**{data.get('tipo_nombre') or 'tu negocio'}**. Score **{data.get('score')}/100**. "
                     "Pregúntame por riesgos, competencia, precio o qué haría yo en tu lugar.")
                )
        for m in msgs:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        if prompt:
            msgs.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            contexto, bloqueados = _contexto_agente(data)
            system = (
                "Eres el Agente 4SITE, analista senior de inteligencia de ubicaciones comerciales en México. "
                f"Responde en {'español' if idioma == 'es' else 'English'}, directo y accionable, máximo 150 palabras, "
                "con bullets cortos cuando ayude. Usa SOLO los datos del análisis; no inventes cifras. "
                "Si preguntan por algo que no está en los datos, dilo."
                + (f" Estos módulos NO están incluidos en el plan del usuario: {', '.join(bloqueados)}. "
                   "Si preguntan por ellos, explica brevemente que están disponibles en un plan superior, sin estimarlos."
                   if bloqueados else "")
                + f"\n\nDATOS DEL ANÁLISIS (JSON):\n{contexto}"
            )
            with st.chat_message("assistant"):
                with st.spinner("Analizando…"):
                    try:
                        r = claude.messages.create(
                            model=modelo, max_tokens=600, system=system,
                            messages=[{"role": m["role"], "content": m["content"]} for m in msgs[-10:]],
                        )
                        resp = r.content[0].text
                    except Exception as e:
                        resp = f"No pude responder en este momento ({e})."
                st.markdown(resp)
            msgs.append({"role": "assistant", "content": resp})


# ════════════════════════════════════════════════════════════════
# DASHBOARD — ZONA POTENCIAL (rejilla hexagonal)
# ════════════════════════════════════════════════════════════════

_ZONA_CSS = r"""
<style>
.zgrid{display:grid;grid-template-columns:250px minmax(0,1fr) 330px;gap:12px;padding:12px;min-height:0}
.cats{display:flex;flex-direction:column;gap:7px}
.cat{display:grid;grid-template-columns:12px 1fr auto;gap:8px;align-items:center;font-size:11.5px}
.cat i{width:12px;height:12px;border-radius:3px}
.cat b{font-weight:800}
.ztbl{width:100%;border-collapse:collapse;font-size:11px}
.ztbl th{text-align:left;font-size:9.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:700;padding:6px 6px;border-bottom:1px solid var(--line)}
.ztbl td{padding:7px 6px;border-bottom:1px solid #F0F3F7;white-space:nowrap}
.ztbl tr{cursor:pointer}.ztbl tr:hover td{background:#F6F9FE}
.ztbl td.nm{white-space:normal;font-weight:600;min-width:130px}
.tag{display:inline-block;border-radius:6px;padding:2px 7px;font-size:10px;font-weight:700}
.zc{border:1px solid var(--line);border-radius:12px;padding:11px 12px;background:#fff;cursor:pointer;transition:border-color .15s}
.zc:hover,.zc.sel{border-color:var(--blue);box-shadow:0 0 0 2px rgba(42,111,219,.12)}
.zc .hd{display:flex;align-items:center;gap:9px}
.zc .rk{width:24px;height:24px;border-radius:50%;background:var(--navy);color:#fff;font-weight:800;font-size:11px;display:flex;align-items:center;justify-content:center;flex:none}
.zc .nm{font-weight:700;font-size:12px;line-height:1.3;flex:1;min-width:0}
.zc .sc{font-weight:800;font-size:20px;line-height:1}
.zc .meta{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0 6px}
.zc .meta span{background:#F1F4F8;border-radius:6px;padding:2px 7px;font-size:10px;color:#34465C}
.why{display:flex;flex-direction:column;gap:4px}
.why div{display:grid;grid-template-columns:14px 1fr;gap:5px;font-size:11px;line-height:1.45;color:#34465C}
.why b{font-weight:800}
.agent{background:linear-gradient(135deg,#13243B,#20364F);color:#fff;border-radius:12px;padding:13px 14px}
.agent .k{font-size:10px;font-weight:700;letter-spacing:.08em;opacity:.8;text-transform:uppercase;margin-bottom:6px}
.agent .row{font-size:11.5px;line-height:1.5;margin-bottom:6px}
.agent .row b{color:#9EC5FF}
.zlbl{background:transparent;border:0;box-shadow:none;color:#13243B;font:800 10px 'Montserrat',sans-serif;text-shadow:0 0 3px #fff,0 0 3px #fff}
@media (max-width:1180px){.zgrid{grid-template-columns:240px minmax(0,1fr)}.zgrid .right{grid-column:1/-1}}
@media (max-width:820px){.zgrid{grid-template-columns:minmax(0,1fr);padding:8px}}
</style>
"""

_ZONA_BODY = r"""
<body>
<div class="app">
  <div class="top">
    <div class="logo"><b>4</b>SITE</div>
    <div class="addr"><div class="l1" id="h-addr"></div><div class="l2" id="h-sub"></div></div>
    <span class="pill tier" id="h-tier"></span>
  </div>
  <div class="zgrid">
    <div class="col left">
      <div class="card">
        <h3>Mejor zona</h3>
        <div class="score-wrap">
          <div class="gauge"><svg viewBox="0 0 120 70" width="118" height="70" id="gauge"></svg>
            <div class="num" id="s-num"></div><div class="den">/ 100</div></div>
          <div class="score-meta"><div class="nivel" id="s-nivel"></div><div class="tipo" id="s-tipo"></div></div>
        </div>
      </div>
      <div class="card"><h3>Barrido</h3><div class="kpis" id="kpis"></div></div>
      <div class="card"><h3>Zonas por tipo de mercado</h3><div class="cats" id="cats"></div>
        <div class="note">Mercado probado: hay un competidor bien calificado (≥3.8★, 30+ reseñas) sin saturación — la demanda existe.
        Virgen: sin competencia, demanda por validar (su score de competencia se topa en 80 por esa incertidumbre). Saturada: muchos competidores por cada 500 m.</div></div>
      <div class="card"><h3>Cómo se calcula</h3><div class="note" id="metodo" style="margin-top:0"></div></div>
    </div>

    <div class="col center">
      <div class="card map-card">
        <div style="position:relative;flex:1;display:flex">
          <div id="map" style="flex:1"></div>
          <div class="layers" id="layers"></div>
          <div class="mode" id="mode" style="display:flex;bottom:122px"><button data-m="score" class="on">Score</button><button data-m="cat">Mercado</button></div>
          <div class="legend" id="legend"></div>
          <div class="toast" id="toast"></div>
        </div>
        <div class="read" id="map-read"></div>
      </div>
      <div class="card" style="overflow:auto">
        <h3>Comparativa de zonas <span class="sub">clic para ubicarla en el mapa</span></h3>
        <table class="ztbl" id="tbl"></table>
      </div>
    </div>

    <div class="col right">
      <div class="agent" id="agent"></div>
      <div id="zcards" style="display:flex;flex-direction:column;gap:10px"></div>
      <div class="card"><h3>Guía de ubicación ideal <span class="sub" id="guia-sub"></span></h3><div id="guia"></div></div>
    </div>
  </div>
</div>
<script>
const D = __DATA__;
const $ = id => document.getElementById(id);
const fmt = n => (n==null||isNaN(n)) ? '—' : Number(n).toLocaleString('es-MX',{maximumFractionDigits:0});
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const scoreColor = s => s>=65 ? '#1F9D57' : s>=50 ? '#D98A1F' : '#E0524A';
const CAT = {mercado_probado:['Mercado probado','#1F9D57'], moderada:['Competencia moderada','#2A6FDB'], virgen:['Zona virgen','#8E6CD9'], saturada:['Saturada','#E0524A']};
const ramp = s => { const t=Math.max(0,Math.min(1,(s-30)/60)); const a=[224,82,74], b=[217,138,31], c=[31,157,87];
  const m = t<.5 ? a.map((v,i)=>v+(b[i]-v)*t*2) : b.map((v,i)=>v+(c[i]-v)*(t-.5)*2); return `rgb(${m.map(Math.round).join(',')})`; };
const Z = D.zonas||[], C = D.celdas||[];

$('h-addr').textContent = 'Zona potencial · ' + (D.tipo_nombre||'');
$('h-sub').textContent = `Referencia: ${D.ubicacion} · radio ${D.radio_km} km`;
$('h-tier').textContent = 'Plan ' + D.tier_nombre;

/* gauge mejor zona */
(function(){
  const top = Z[0]; const s = top ? top.score : 0, c = scoreColor(s);
  const r=50,cx=60,cy=62,p=a=>[cx+r*Math.cos(a),cy-r*Math.sin(a)],[x0,y0]=p(Math.PI),[x1,y1]=p(Math.PI*(1-s/100)),[xe,ye]=p(0);
  $('gauge').innerHTML = `<path d="M${x0} ${y0} A${r} ${r} 0 0 1 ${xe} ${ye}" stroke="#EDF1F6" stroke-width="11" fill="none" stroke-linecap="round"/>`+(s>0?`<path d="M${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1}" stroke="${c}" stroke-width="11" fill="none" stroke-linecap="round"/>`:'');
  $('s-num').textContent = top ? top.score : '—'; $('s-num').style.color = c;
  $('s-nivel').textContent = top ? (CAT[top.categoria]||[''])[0] : 'Sin zonas'; $('s-nivel').style.color = top ? CAT[top.categoria][1] : '#5C6B7A';
  $('s-tipo').textContent = top ? top.nombre : '';
})();

/* kpis + categorías */
(function(){
  const cnt = k => C.filter(c=>c.categoria===k).length;
  const k = [['Zonas evaluadas',C.length,'hexágonos de '+fmt(D.hex_m*2)+' m'],['Detalladas',Z.length,'con demografía y vialidad'],
             ['Competidores',D.n_competidores,'únicos en el radio'],['Consultas Google',D.llamadas,'en esta búsqueda']];
  $('kpis').innerHTML = k.map(x=>`<div class="kpi"><div class="k">${x[0]}</div><div class="v">${fmt(x[1])}</div><div class="n">${x[2]}</div></div>`).join('');
  $('cats').innerHTML = Object.entries(CAT).map(([key,[l,col]])=>`<div class="cat"><i style="background:${col}"></i><span>${l}</span><b>${cnt(key)}</b></div>`).join('');
  $('metodo').innerHTML = `El <b>índice</b> es la misma suma de factores sin tope de 100: ordena las zonas cuando varias llegan al máximo. Dividimos ${D.radio_km} km en 19 hexágonos. En cada uno medimos la competencia (densidad normalizada a 500 m, calidad y consolidación) y le sumamos un bono según el tipo de mercado. A las ${Z.length} mejores les agregamos NSE/ingreso del municipio y colonia (INEGI) y el tipo de vialidad para este giro. Los hexágonos claros son preliminares.`;
})();

/* mapa */
const map = L.map('map',{zoomControl:false}).setView([D.lat,D.lng],13);
L.control.zoom({position:'bottomright'}).addTo(map); L.control.scale({position:'bottomright',imperial:false}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{attribution:'© OpenStreetMap © CARTO',subdomains:'abcd',maxZoom:20}).addTo(map);
L.marker([D.lat,D.lng],{icon:L.divIcon({className:'',html:'<div class="site-pin">★</div>',iconSize:[22,22],iconAnchor:[11,11]}),zIndexOffset:1000}).bindPopup('<b>Tu punto de referencia</b><br>'+esc(D.ubicacion)).addTo(map);
const G = {radio: L.layerGroup([L.circle([D.lat,D.lng],{radius:D.radio_km*1000,color:'#13243B',weight:1.2,dashArray:'6 6',fill:false})]), hex: L.layerGroup(), top: L.layerGroup(), comp: L.layerGroup()};
let colorMode = 'score';
const hexLayers = [];
function paintHex(){
  G.hex.clearLayers(); hexLayers.length = 0;
  C.forEach(c=>{
    const col = colorMode==='score' ? ramp(c.score) : (CAT[c.categoria]||['','#9AA5B1'])[1];
    const pl = L.polygon(c.poly,{color:'#fff',weight:1.5,fillColor:col,fillOpacity:c.detallada?.55:.28,dashArray:c.detallada?null:'3 3'})
      .bindTooltip(`<b>${c.detallada?esc(c.nombre):'Zona preliminar'}</b><br>Score ${c.score}${c.detallada?'':' (preliminar)'} · ${(CAT[c.categoria]||[''])[0]}<br>${c.n_comp}${c.tope?'+':''} competidores`,{sticky:true});
    pl.addTo(G.hex); hexLayers.push(pl);
    if (c.detallada) L.marker([c.lat,c.lng],{icon:L.divIcon({className:'zlbl',html:String(c.score),iconSize:[24,14],iconAnchor:[12,-10]}),interactive:false}).addTo(G.hex);
  });
}
paintHex();
const topMk = [];
Z.forEach((z,i)=>{ const m = L.marker([z.lat,z.lng],{icon:L.divIcon({className:'',html:`<div class="num-pin" style="background:#13243B;width:24px;height:24px;font-size:11px">${i+1}</div>`,iconSize:[24,24],iconAnchor:[12,12]}),zIndexOffset:900})
  .bindPopup(`<b>#${i+1} ${esc(z.nombre)}</b><br>Score <b style="color:${scoreColor(z.score)}">${z.score}</b> · ${(CAT[z.categoria]||[''])[0]}<br>NSE ${esc(z.nse)} · ${z.n_comp} competidores · ${z.dist_km} km de tu referencia`); m.addTo(G.top); topMk[i]=m; });
(D.competidores||[]).forEach(c=>L.circleMarker([c.lat,c.lng],{radius:3.5,weight:1,color:'#fff',fillColor:!c.rating?'#9AA5B1':c.rating>=4.3?'#1F9D57':c.rating>=3.5?'#D98A1F':'#E0524A',fillOpacity:.95})
  .bindTooltip(`${esc(c.nombre)} · ${c.rating?c.rating+'★':'s/r'} · ${fmt(c.reviews)} reseñas`).addTo(G.comp));
const LAYERS = [{k:'hex',l:'Hexágonos',on:true},{k:'top',l:'Mejores zonas',on:true},{k:'comp',l:'Competidores',on:false},{k:'radio',l:'Radio de búsqueda',on:true}];
function sync(){ LAYERS.forEach(x=>{ x.on ? G[x.k].addTo(map) : map.removeLayer(G[x.k]); }); }
function renderLayers(){ $('layers').innerHTML = LAYERS.map(x=>`<button class="lyr ${x.on?'on':''}" data-k="${x.k}"><span class="dot"></span>${x.l}</button>`).join('');
  document.querySelectorAll('.lyr').forEach(b=>b.onclick=()=>{ const x=LAYERS.find(y=>y.k===b.dataset.k); x.on=!x.on; sync(); renderLayers(); }); }
renderLayers(); sync();
document.querySelectorAll('#mode button').forEach(b=>b.onclick=()=>{ document.querySelectorAll('#mode button').forEach(x=>x.classList.remove('on')); b.classList.add('on'); colorMode=b.dataset.m; paintHex(); renderLegend(); });
function renderLegend(){ $('legend').innerHTML = colorMode==='score'
  ? `<div><i style="background:#1F9D57"></i>Score alto</div><div><i style="background:#D98A1F"></i>Medio</div><div><i style="background:#E0524A"></i>Bajo</div><div style="color:#8C99A8">Punteado = preliminar</div>`
  : Object.values(CAT).map(([l,c])=>`<div><i style="background:${c}"></i>${l}</div>`).join(''); }
renderLegend();
const fit = () => map.fitBounds(L.latLng(D.lat,D.lng).toBounds(D.radio_km*2000*1.05),{padding:[20,20]}); fit();
setTimeout(()=>{map.invalidateSize();fit();},300);

(function(){
  if (!Z.length){ $('map-read').textContent='💬 No se pudieron detallar zonas en este radio.'; return; }
  const t = Z[0], mp = C.filter(c=>c.categoria==='mercado_probado').length, sat = C.filter(c=>c.categoria==='saturada').length;
  $('map-read').textContent = `💬 La mejor zona es ${t.nombre} (score ${t.score}, ${(CAT[t.categoria]||[''])[0].toLowerCase()}, a ${t.dist_km} km de tu referencia). `+
    `${mp} de ${C.length} hexágonos tienen mercado probado y ${sat} están saturados` + (sat>C.length/2 ? ' — el giro está muy competido en esta zona; considera ampliar el radio.' : '.');
})();

/* tabla */
$('tbl').innerHTML = '<tr><th>#</th><th>Zona</th><th>Score</th><th title="Suma de factores sin tope de 100; desempata zonas con el mismo score">Índice</th><th>Mercado</th><th>Comp.</th><th>NSE</th><th>Vialidad</th><th>Dist.</th></tr>' +
  Z.map((z,i)=>`<tr data-i="${i}"><td><b>${i+1}</b></td><td class="nm">${esc(z.nombre)}</td><td><b style="color:${scoreColor(z.score)}">${z.score}</b></td><td style="color:#5C6B7A">${Math.round(z.indice)}</td>
    <td><span class="tag" style="background:${CAT[z.categoria][1]}1F;color:${CAT[z.categoria][1]}">${CAT[z.categoria][0]}</span></td>
    <td>${z.n_comp}${z.tope?'+':''}</td><td>${esc(z.nse)}</td><td>${esc((z.vial||{}).badge||'—')}</td><td>${z.dist_km} km</td></tr>`).join('') +
  (D.zonas_ocultas ? `<tr><td colspan="9" style="color:#2A6FDB;font-weight:700">🔒 ${D.zonas_ocultas} zonas detalladas más en Premium</td></tr>` : '');

/* agente */
(function(){
  const rows = (D.agente||[]).map(r=>`<div class="row"><b>${esc(r.t)}:</b> ${esc(r.v)}</div>`).join('');
  $('agent').innerHTML = `<div class="k">Recomendación del agente</div>` + (rows || '<div class="row">Sin resumen.</div>');
})();

/* tarjetas */
function sel(i){
  document.querySelectorAll('.zc').forEach(e=>e.classList.toggle('sel', +e.dataset.i===i));
  const z = Z[i]; map.flyTo([z.lat,z.lng],15,{duration:.6}); setTimeout(()=>topMk[i].openPopup(),650); guia(i);
}
$('zcards').innerHTML = Z.map((z,i)=>`<div class="zc" data-i="${i}"><div class="hd"><div class="rk">${i+1}</div><div class="nm">${esc(z.nombre)}</div><div class="sc" style="color:${scoreColor(z.score)}">${z.score}</div></div>
  <div class="meta"><span style="background:${CAT[z.categoria][1]}1F;color:${CAT[z.categoria][1]};font-weight:700">${CAT[z.categoria][0]}</span><span>NSE ${esc(z.nse)}</span><span>${z.n_comp}${z.tope?'+':''} comp.</span><span>${z.dist_km} km</span></div>
  <div class="why">${(z.por_que||[]).map(w=>`<div><b style="color:${w.s==='+'?'#1F9D57':w.s==='−'?'#E0524A':'#D98A1F'}">${w.s==='+'?'+':w.s==='−'?'−':w.s==='!'?'!':'•'}</b><span>${esc(w.t)}</span></div>`).join('')}</div></div>`).join('');
document.querySelectorAll('.zc').forEach(e=>e.onclick=()=>sel(+e.dataset.i));
document.querySelectorAll('#tbl tr[data-i]').forEach(e=>e.onclick=()=>sel(+e.dataset.i));

function guia(i){
  const z = Z[i]; if (!z){ $('guia').innerHTML=''; return; } const r = z.recom||{};
  $('guia-sub').textContent = 'para zona #' + (i+1);
  const it = [['🛣️ Vialidad ideal',r.vialidad_ideal],['👀 Visibilidad',r.visibilidad],['🅿️ Estacionamiento',r.estacionamiento],['🏬 En plaza comercial',r.plaza_recomendacion],['🎯 Competidor de referencia',r.ref_competidor],['💡 Tip para este NSE',r.tip_nse]].filter(x=>x[1]);
  $('guia').innerHTML = it.map(([t,v])=>`<div class="isec"><h4>${t}</h4><p>${esc(v)}</p></div>`).join('');
}
guia(0);
</script>
</body></html>
"""


def construir_html_zona(data: dict) -> str:
    head = _HTML.split("<body>")[0]
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    return head.replace("</head>", _ZONA_CSS + "</head>") + _ZONA_BODY.replace("__DATA__", payload)


def render_dashboard_zona(data: dict, height: int = 1000):
    _embed(construir_html_zona(data), height)
