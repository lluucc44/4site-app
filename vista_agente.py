"""
vista_agente.py — Interfaz tipo agente (inspirada en TomTom Site Selection) para 4SITE.

  Panel izquierdo (Streamlit): conversación con el agente, modos, formulario y chat.
  Panel derecho (HTML/Leaflet): mapa a pantalla completa con paneles flotantes.

Funciones públicas:
  css_shell()                       → CSS del layout de dos paneles
  html_mapa_sitio(data)             → mapa de resultados (validar / descubrir)
  html_mapa_zonas(data)             → mapa de resultados (descubrir zona)
  render_mapa(html, alto)           → incrusta un HTML en el panel derecho
  bloque_usuario(texto)             → burbuja del usuario
  bloque_ruta(pasos)                → "Revisé N fuentes ✓" con recorrido
  bloque_veredicto(data)            → anillo de score + veredicto + ventajas/riesgos
  bloque_agente_zonas(data)         → recomendación del agente para zonas
  interpretar_intencion(...)        → convierte una frase libre en modo/giro/dirección
"""

import json
import re

import streamlit as st
import streamlit.components.v1 as components

AVATAR_AGENTE = "📍"
AVATAR_USUARIO = "🙂"

PIN_SVG = ("<svg viewBox='0 0 24 24' width='16' height='16' fill='#F2B705' aria-hidden='true'>"
           "<path d='M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z'/></svg>")


def _esc(s) -> str:
    return (str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ════════════════════════════════════════════════════════════════
# CSS del layout
# ════════════════════════════════════════════════════════════════

def css_shell() -> str:
    return """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Montserrat:wght@700;800&display=swap');
:root{--navy:#13243B;--ink:#24364D;--muted:#5D6B7C;--faint:#93A0AF;--blue:#2A6FDB;--blue-soft:#E8F0FC;
      --signal:#F2B705;--wash:#F4F6F9;--line:#E2E7EE;--ok:#1E9A5A;--warn:#D3871B;--bad:#D9493F;}
/* Sin cromo de Streamlit: la app ocupa toda la ventana */
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer {display:none !important;}
.main .block-container, [data-testid="stMainBlockContainer"], .block-container {
  max-width:none !important; padding:0 !important; margin:0 !important;}
.stApp {background:var(--wash) !important;}
.st-key-shell > div > [data-testid="stHorizontalBlock"], .st-key-shell [data-testid="stHorizontalBlock"]:first-child {gap:0 !important;}

/* Panel del agente */
.st-key-agentpanel {background:#fff; border-right:1px solid var(--line); height:100vh !important; max-height:100vh !important; overflow-y:auto !important;
  padding:0 20px 16px !important; position:sticky; top:0;}
.st-key-agentpanel p, .st-key-agentpanel li, .st-key-agentpanel label, .st-key-agentpanel input,
.st-key-agentpanel textarea, .st-key-agentpanel button, .st-key-agentpanel div[data-baseweb] {
  font-family:'IBM Plex Sans', system-ui, sans-serif !important;}
.st-key-agentpanel label p {font-weight:600 !important; color:var(--navy) !important; font-size:13px !important;}
.st-key-agentpanel [data-testid="stChatMessage"] p,
.st-key-agentpanel [data-testid="stChatMessage"] li {font-size:13.5px !important; line-height:1.55 !important;}
.st-key-agentpanel [data-testid="stChatMessage"] {padding:4px 0 !important; background:none !important;}

/* Barra de marca */
.ag-brand {display:flex; align-items:center; gap:10px; padding:14px 0 12px; border-bottom:1px solid var(--line); margin:0 0 14px;}
.ag-logo {font:800 21px Montserrat, sans-serif; color:var(--navy); letter-spacing:-.02em;}
.ag-logo b {color:var(--blue);}
.ag-who {font-size:12px; color:var(--muted); line-height:1.15;}
.ag-plan {margin-left:auto; background:var(--blue-soft); color:var(--blue); font-weight:600; font-size:12px; border-radius:99px; padding:4px 10px; white-space:nowrap;}

/* Saludo del agente */
.ag-say {display:grid; grid-template-columns:30px 1fr; gap:10px; align-items:start; margin:4px 0 12px;}
.ag-pin {width:30px; height:30px; border-radius:9px; background:var(--navy); display:grid; place-items:center;}
.ag-say h1 {font:800 22px/1.25 Montserrat, sans-serif !important; color:var(--navy) !important; letter-spacing:-.015em; margin:0 0 4px !important; padding:0 !important;}
.ag-say p {color:var(--ink); font-size:14px; margin:0;}

/* Botones: el CSS global de la app usa "div.stButton > button:not([kind=primary])" con !important;
   aquí se usa un selector más específico para ganarle. */
.stApp [class*="st-key-mode"] div.stButton > button:not([kind="primary"]) {width:100%; justify-content:flex-start !important;
  border:1.5px solid var(--line) !important; border-radius:12px !important; background:#fff !important; background-color:#fff !important;
  padding:10px 14px !important; min-height:60px; font-family:'IBM Plex Sans', sans-serif !important; font-weight:400 !important;}
.stApp [class*="st-key-mode"] div.stButton > button > div {width:100%; justify-content:flex-start !important;}
.stApp [class*="st-key-mode"] div.stButton > button [data-testid="stMarkdownContainer"] {width:100%; text-align:left !important; display:block;}
.stApp [class*="st-key-mode"] div.stButton > button p {font-size:13px !important; line-height:1.4 !important; text-align:left !important;
  white-space:pre-line; font-family:'IBM Plex Sans', sans-serif !important; color:var(--muted) !important; -webkit-text-fill-color:var(--muted) !important;}
.stApp [class*="st-key-mode"] div.stButton > button p strong {color:var(--navy) !important; -webkit-text-fill-color:var(--navy) !important; font-size:14px; font-weight:600;}
.stApp [class*="st-key-mode"] div.stButton > button:not([kind="primary"]):hover {border-color:var(--blue) !important; background:#fff !important;}
.stApp [class*="st-key-modeon_"] div.stButton > button:not([kind="primary"]),
.stApp [class*="st-key-modeon_"] div.stButton > button:not([kind="primary"]):hover {border-color:var(--blue) !important; background:var(--blue-soft) !important; background-color:var(--blue-soft) !important;}
.stApp [class*="st-key-mode"] {margin-bottom:-6px;}

/* Botón principal */
.stApp .st-key-btn_analizar div.stButton > button:not([kind="primary"]),
.stApp .st-key-btn_zona div.stButton > button:not([kind="primary"]) {background:var(--navy) !important; background-color:var(--navy) !important;
  border:0 !important; border-radius:10px !important; padding:12px !important; min-height:48px;}
.stApp .st-key-btn_analizar div.stButton > button:not([kind="primary"]):hover,
.stApp .st-key-btn_zona div.stButton > button:not([kind="primary"]):hover {background:#20385A !important;}
.stApp .st-key-btn_analizar div.stButton > button *, .stApp .st-key-btn_zona div.stButton > button * {
  color:#fff !important; -webkit-text-fill-color:#fff !important; font-weight:600 !important; font-size:15px !important;}
.stApp .st-key-btn_analizar p:before, .stApp .st-key-btn_zona p:before {content:""; display:inline-block; width:8px; height:8px;
  border-radius:50%; background:var(--signal); margin-right:9px; vertical-align:1px;}

/* Controles en azul de marca (el slider venía en rojo por defecto) */
.st-key-agentpanel [data-baseweb="slider"] [role="slider"] {background:var(--blue) !important; box-shadow:none !important;}
.st-key-agentpanel [data-baseweb="slider"] > div > div > div:first-child {background:var(--blue) !important;}
.st-key-agentpanel [data-testid="stSliderThumbValue"], .st-key-agentpanel [data-testid="stThumbValue"] {color:var(--navy) !important;}

/* Chips (ejemplos, preguntas sugeridas, revisar zona) */
.stApp [class*="st-key-chip_"] {margin-bottom:-10px;}
.stApp [class*="st-key-chip_"] div.stButton > button:not([kind="primary"]) {border-radius:99px !important; background:var(--wash) !important;
  background-color:var(--wash) !important; border:1px solid var(--line) !important; padding:4px 13px !important; min-height:0 !important;
  font-family:'IBM Plex Sans', sans-serif !important; font-weight:400 !important;}
.stApp [class*="st-key-chip_"] div.stButton > button * {font-size:12.5px !important; font-weight:400 !important; font-family:'IBM Plex Sans', sans-serif !important;}
.stApp [class*="st-key-chip_"] div.stButton > button:not([kind="primary"]):hover {border-color:var(--blue) !important;}

/* Bloques que solo contienen <style> no deben ocupar espacio */
[data-testid="stElementContainer"]:has(~ [data-testid="stLayoutWrapper"] > .st-key-shell) {display:none;}
[data-testid="stElementContainer"]:has(style):not(:has(p, h1, h2, h3, h4, img, iframe, .ag-brand)) {display:none;}

/* Conversación */
.st-key-agentpanel .ag-me {margin:4px 0 12px auto; background:var(--navy); color:#fff !important; -webkit-text-fill-color:#fff !important; border-radius:14px 14px 4px 14px; padding:9px 13px;
  max-width:88%; font-size:13.5px; width:fit-content;}
.ag-log {border:1px solid var(--line); border-radius:12px; padding:10px 12px; background:var(--wash); margin-bottom:12px;}
.ag-log summary {cursor:pointer; font-size:12.5px; font-weight:600; color:var(--navy); list-style:none; display:flex; justify-content:space-between;}
.ag-log summary::-webkit-details-marker {display:none;}
.ag-route {margin-top:8px; position:relative; padding-left:24px; display:grid; gap:5px;}
.ag-route:before {content:""; position:absolute; left:5px; top:6px; bottom:6px; width:2px;
  background:repeating-linear-gradient(var(--blue) 0 4px, transparent 4px 7px);}
.ag-route div {position:relative; font-size:12.5px; color:var(--ink);}
.ag-route div:before {content:""; position:absolute; left:-24px; top:6px; width:10px; height:10px; border-radius:50%;
  background:#fff; border:2px solid var(--blue);}
.ag-route div.off {color:var(--faint);}
.ag-route div.off:before {border-color:#C9D2DD;}
.ag-route div:last-child:before {background:var(--signal); border-color:var(--navy);}
.ag-verdict {display:grid; grid-template-columns:30px 1fr; gap:10px; margin-bottom:10px;}
.ag-vrow {display:grid; grid-template-columns:auto 1fr; gap:12px; align-items:center;}
.ag-ring {width:62px; height:62px; border-radius:50%; display:grid; place-items:center;}
.ag-ring span {width:48px; height:48px; border-radius:50%; background:#fff; display:grid; place-items:center;
  font:800 19px Montserrat, sans-serif; color:var(--navy);}
.ag-vt {font:700 15px Montserrat, sans-serif; margin:0 0 2px;}
.ag-vs {font-size:13px; color:var(--muted); margin:0;}
.ag-pc {display:grid; gap:5px; font-size:13px; margin-top:10px; color:var(--ink);}
.ag-pc > div {display:grid; grid-template-columns:16px 1fr; gap:6px;}
.ag-pc .p {color:var(--ok); font-weight:700;} .ag-pc .c {color:var(--bad); font-weight:700;}
.ag-lock {font-size:12.5px; color:var(--muted); background:var(--wash); border-radius:10px; padding:8px 10px; margin-top:8px;}
.st-key-agentpanel p.ag-note {font-size:11.5px !important; color:var(--faint) !important; text-align:center; margin-top:6px;}

/* Panel del mapa */
.st-key-mappanel {position:relative; height:100vh;}
.st-key-mappanel iframe {height:100vh !important; width:100% !important; border:0; display:block;}
.ag-maphint {position:absolute; left:50%; top:46%; transform:translate(-50%,-50%); z-index:5; pointer-events:none;
  background:#fff; border-radius:14px; padding:18px 22px; box-shadow:0 10px 30px rgba(19,36,59,.14); max-width:340px; text-align:center;}
.ag-maphint h3 {font:700 16px Montserrat, sans-serif !important; color:var(--navy) !important; margin:0 0 4px !important; padding:0 !important;}
.ag-maphint p {font-size:13px; color:var(--muted); margin:0;}
.st-key-mappanel [data-testid="stElementContainer"]:has(.ag-maphint) {position:absolute; left:0; right:0; top:0; height:100vh; z-index:5; pointer-events:none;}

/* Debajo del layout (análisis completo, descargas, planes) */
[data-testid="stLayoutWrapper"]:has(> .st-key-shell) ~ * {padding-left:32px !important; padding-right:32px !important;}

@media (max-width: 860px) {
  .st-key-agentpanel {height:auto; position:static; border-right:0; border-bottom:1px solid var(--line);}
  .st-key-mappanel, .st-key-mappanel iframe {height:78vh !important;}
}
</style>"""


# ════════════════════════════════════════════════════════════════
# Bloques del panel izquierdo
# ════════════════════════════════════════════════════════════════

def bloque_marca(plan_txt: str = "") -> str:
    plan = f"<span class='ag-plan'>{_esc(plan_txt)}</span>" if plan_txt else ""
    return ("<div class='ag-brand'><div class='ag-logo'><b>4</b>SITE</div>"
            "<div class='ag-who'>Análisis de<br>ubicación</div>" + plan + "</div>")


def bloque_saludo(titulo: str, texto: str) -> str:
    return (f"<div class='ag-say'><div class='ag-pin'>{PIN_SVG}</div>"
            f"<div><h1>{_esc(titulo)}</h1><p>{_esc(texto)}</p></div></div>")


def bloque_usuario(texto: str) -> str:
    return f"<div class='ag-me'>{_esc(texto)}</div>"


def bloque_ruta(pasos, titulo=None) -> str:
    """pasos: lista de (texto, hecho_bool)."""
    n = sum(1 for _, ok in pasos if ok)
    items = "".join(f"<div class='{'' if ok else 'off'}'>{_esc(t)}{'' if ok else ' · en un plan superior'}</div>" for t, ok in pasos)
    return (f"<details class='ag-log' open><summary>{_esc(titulo or f'Revisé {n} fuentes')}"
            f"<span style='color:var(--ok)'>✓ listo</span></summary><div class='ag-route'>{items}</div></details>")


def _color_score(s):
    return "#1E9A5A" if s >= 65 else "#D3871B" if s >= 50 else "#D9493F"


_TITULO_VEREDICTO = {
    "PROCEDER":    ("Sí conviene", "#1E9A5A"),
    "PRECAUCIÓN":  ("Conviene con cuidado", "#D3871B"),
    "NO PROCEDER": ("No te lo recomiendo", "#D9493F"),
}


def bloque_veredicto(data: dict) -> str:
    s = int(data.get("score") or 0)
    diag = data.get("diag") or {}
    ver = diag.get("veredicto") or ""
    titulo, col = _TITULO_VEREDICTO.get(ver, (data.get("nivel", "").capitalize() or "Resultado", _color_score(s)))
    sub = diag.get("veredicto_txt") or diag.get("resumen") or ""
    if len(sub) > 220:
        sub = sub[:217].rsplit(" ", 1)[0] + "…"
    if data.get("modo") == "recomendar" and data.get("giros"):
        titulo = f"Lo que más te conviene: {data['giros'][0]['nombre']}"
        col = _color_score(s)
    ring = (f"<div class='ag-ring' style='background:conic-gradient({_color_score(s)} 0 {s}%, #E6EBF1 0)'>"
            f"<span>{s}</span></div>")
    pros = diag.get("ventajas") or []
    cons = diag.get("riesgos") or []
    locks = data.get("locks") or {}
    pc = ""
    if locks.get("diag_parcial"):
        if pros:
            pc += f"<div><span class='p'>+</span><span>{_esc(pros[0])}</span></div>"
        pc_lock = ("<div class='ag-lock'>🔒 Para ver los riesgos, todas las ventajas y mi recomendación completa, "
                   "necesitas el plan Básico.</div>")
    else:
        pc += "".join(f"<div><span class='p'>+</span><span>{_esc(x)}</span></div>" for x in pros[:2])
        pc += "".join(f"<div><span class='c'>−</span><span>{_esc(x)}</span></div>" for x in cons[:2])
        pc_lock = ""
    return (f"<div class='ag-verdict'><div class='ag-pin'>{PIN_SVG}</div><div>"
            f"<div class='ag-vrow'>{ring}<div><p class='ag-vt' style='color:{col}'>{_esc(titulo)}</p>"
            f"<p class='ag-vs'>{_esc(sub)}</p></div></div>"
            + (f"<div class='ag-pc'>{pc}</div>" if pc else "") + pc_lock + "</div></div>")


def bloque_agente_zonas(data: dict) -> str:
    zonas = data.get("zonas") or []
    top = zonas[0] if zonas else {}
    s = int(top.get("score") or 0)
    ring = (f"<div class='ag-ring' style='background:conic-gradient({_color_score(s)} 0 {s}%, #E6EBF1 0)'>"
            f"<span>{s if zonas else '—'}</span></div>")
    filas = "".join(f"<div><span class='{'c' if 'nodo' in r['t'].lower() or 'evitar' in r['t'].lower() else 'p'}'>›</span>"
                    f"<span><b>{_esc(r['t'])}:</b> {_esc(r['v'])}</span></div>"
                    for r in (data.get("agente") or []))
    nodos = data.get("nodos") or []
    if nodos:
        lista = "".join(f"<div><span class='c'>●</span><span><b>{_esc(n['nombre'])}</b>: "
                        f"{n['n']} negocios como el tuyo juntos</span></div>" for n in nodos)
        ext_min = min(n["extra_min"] for n in nodos)
        ext_max = max(n["extra_max"] for n in nodos)
        caja_nodos = (f"<div class='ag-lock' style='background:#FDF1F0;color:#7A2B25;margin-top:10px'>"
                  f"<b>⚠ Aquí se junta la competencia</b><div class='ag-pc' style='margin-top:6px'>{lista}</div>"
                  f"<p style='margin:6px 0 0;font-size:12.5px'>Hay clientes, pero ya tienen a dónde ir. Si abres ahí, ofrece algo "
                  f"distinto y ten redes sociales desde el primer día. Aparta de ${ext_min:,.0f} a ${ext_max:,.0f} más de lo normal "
                  f"para tu marca y publicidad (es una guía, no una cotización).</p></div>")
    else:
        caja_nodos = ""
    return (f"<div class='ag-verdict'><div class='ag-pin'>{PIN_SVG}</div><div>"
            f"<div class='ag-vrow'>{ring}<div><p class='ag-vt' style='color:var(--navy)'>"
            f"{_esc(top.get('nombre', 'Sin zonas detalladas'))}</p>"
            f"<p class='ag-vs'>La mejor de {len(data.get('celdas') or [])} zonas que revisé a {data.get('radio_km')} km</p></div></div>"
            + (f"<div class='ag-pc'>{filas}</div>" if filas else "") + caja_nodos + "</div></div>")


def bloque_maphint(titulo: str, texto: str) -> str:
    return f"<div class='ag-maphint'><h3>{_esc(titulo)}</h3><p>{_esc(texto)}</p></div>"


# ════════════════════════════════════════════════════════════════
# Intención en lenguaje natural
# ════════════════════════════════════════════════════════════════

def interpretar_intencion(claude, frase: str, tipos: dict, modos_permitidos, modelo="claude-sonnet-4-5") -> dict:
    """'¿dónde abro una farmacia en Toluca?' → {modo, giro, direccion, radio_km, respuesta}"""
    catalogo = "\n".join(f"- {k}: {re.sub(r'^[^A-Za-zÁÉÍÓÚÑáéíóúñ]+', '', v['nombre'])}" for k, v in tipos.items())
    prompt = f"""Eres el agente de 4SITE (análisis de ubicaciones comerciales en México). Convierte el mensaje del usuario en una acción.

Modos:
- validar: el usuario tiene giro Y dirección concreta y quiere saber si funciona ahí.
- recomendar: tiene dirección pero no sabe qué negocio poner.
- zona_potencial: tiene giro pero busca en qué parte de una ciudad/zona abrir (no tiene dirección exacta).

Giros disponibles (usa la clave exacta):
{catalogo}

Mensaje: "{frase}"

Responde SOLO con JSON:
{{"modo": "validar|recomendar|zona_potencial|ninguno", "giro": "clave o null", "direccion": "texto de dirección/zona o null",
  "radio_km": número 1-5 o null, "falta": "qué dato falta, en una frase corta en español, o null"}}"""
    try:
        r = claude.messages.create(model=modelo, max_tokens=300, messages=[{"role": "user", "content": prompt}])
        txt = r.content[0].text
        m = re.search(r"\{.*\}", txt, re.S)
        out = json.loads(m.group(0)) if m else {}
    except Exception as e:
        return {"modo": "ninguno", "falta": f"No pude entender el mensaje ({e})."}
    if out.get("giro") not in tipos:
        out["giro"] = None
    if out.get("modo") not in ("validar", "recomendar", "zona_potencial"):
        out["modo"] = "ninguno"
    out["permitido"] = out["modo"] in modos_permitidos
    return out


# ════════════════════════════════════════════════════════════════
# Mapas del panel derecho
# ════════════════════════════════════════════════════════════════

def render_mapa(html: str, alto: int = 860):
    if hasattr(st, "iframe"):
        st.iframe(html, height=alto)
    else:
        components.html(html, height=alto, scrolling=False)


_HEAD = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Montserrat:wght@700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
:root{--navy:#13243B;--ink:#24364D;--muted:#5D6B7C;--faint:#93A0AF;--blue:#2A6FDB;--blue-soft:#E8F0FC;
  --signal:#F2B705;--wash:#F4F6F9;--line:#E2E7EE;--ok:#1E9A5A;--warn:#D3871B;--bad:#D9493F;--sh:0 10px 30px rgba(19,36,59,.14)}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden;font:400 13px/1.45 'IBM Plex Sans',system-ui,sans-serif;color:var(--ink);background:#EEF1F4;color-scheme:light}
h3,h4,.num{font-family:Montserrat,sans-serif;color:var(--navy)}
button{font:inherit;color:inherit;cursor:pointer}
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
#map{position:absolute;inset:0}
.leaflet-popup-content{font:13px 'IBM Plex Sans',sans-serif;margin:10px 12px}
.chips{position:absolute;top:14px;left:14px;right:70px;z-index:500;display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:rgba(255,255,255,.97);border-radius:99px;padding:6px 12px;font-size:12.5px;font-weight:500;display:flex;gap:7px;align-items:center;box-shadow:0 1px 4px rgba(19,36,59,.06)}
.chip i{width:8px;height:8px;border-radius:50%;background:#C6CFDA}
.chip.on{border-color:var(--blue);color:var(--blue)}.chip.on i{background:var(--blue)}
.chip.lk{color:var(--faint)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:99px;overflow:hidden;background:#fff}
.seg button{border:0;background:none;padding:6px 11px;font-size:12.5px;font-weight:500;color:var(--muted)}
.seg button.on{background:var(--navy);color:#fff}
.panel{position:absolute;z-index:500;background:#fff;border-radius:14px;box-shadow:var(--sh);overflow:hidden}
.panel header{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 14px;border-bottom:1px solid var(--line)}
.panel header h3{font-size:14px}
.panel header .sub{font-size:12px;color:var(--muted)}
.mini{border:0;background:var(--wash);border-radius:7px;width:26px;height:26px;font-size:14px;line-height:1;flex:none}
.profile{top:58px;left:14px;width:310px;max-height:calc(100% - 72px);display:flex;flex-direction:column}
.profile .body{overflow:auto}
.profile.min .body{display:none}
.scorebar{display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid var(--line)}
.ring{width:54px;height:54px;border-radius:50%;display:grid;place-items:center;flex:none}
.ring span{width:42px;height:42px;border-radius:50%;background:#fff;display:grid;place-items:center;font:800 17px Montserrat;color:var(--navy)}
.scorebar b{font:700 14px Montserrat;display:block}
.scorebar small{color:var(--muted);font-size:12px}
.giro-sel{width:100%;border:1px solid var(--line);border-radius:8px;padding:6px 8px;font:inherit;background:#fff;margin-top:6px}
.kp{display:grid;grid-template-columns:1fr 1fr}
.kp div{padding:9px 14px;border-bottom:1px solid var(--line);position:relative;min-width:0}
.kp div:nth-child(odd){border-right:1px solid var(--line)}
.kp small{display:block;font-size:11.5px;color:var(--muted);line-height:1.3}
.kp b{font:700 15px Montserrat;color:var(--navy);white-space:nowrap}
.kp em{display:block;font-style:normal;font-size:11px;color:var(--faint);line-height:1.3}
.kp .lk b{filter:blur(4px);user-select:none}
.kp .lk small:after{content:" · " attr(data-plan);color:var(--blue)}
.bars{padding:10px 14px;display:grid;gap:8px;border-bottom:1px solid var(--line)}
.bars div{font-size:12px}
.bars .t{height:5px;border-radius:3px;background:#E6EBF1;margin-top:3px;overflow:hidden}
.bars .t i{display:block;height:100%;border-radius:3px}
.bars span{float:right;font-weight:600}
.blur{filter:blur(4px);pointer-events:none;user-select:none}
.lockline{font-size:12px;color:var(--muted);padding:9px 14px;border-bottom:1px solid var(--line)}
.lockline b{color:var(--blue)}
.pal{padding:10px 14px}
.pal h4{font-size:12.5px;margin-bottom:6px}
.pal div{display:flex;justify-content:space-between;font-size:12px;padding:3px 0}
.pal div b{color:var(--ok)}
.drawer{left:338px;right:14px;bottom:14px;max-height:46%;display:flex;flex-direction:column}
.drawer.min .in{display:none}
.tabs{display:flex;gap:2px;padding:6px;border-bottom:1px solid var(--line);align-items:center;overflow-x:auto}
.tabs button{border:0;background:none;padding:7px 12px;border-radius:8px;font-size:13px;font-weight:500;color:var(--muted);white-space:nowrap}
.tabs button.on{background:var(--navy);color:#fff}
.tabs .mini{margin-left:auto}
.in{overflow:auto;padding:12px 14px}
.cols{display:grid;grid-template-columns:1.25fr 1fr;gap:18px}
.hm{display:grid;grid-template-columns:30px repeat(5,1fr);gap:3px;font-size:11px}
.hm .h{color:var(--faint);text-align:center}.hm .d{color:var(--muted)}
.hm .c{height:16px;border-radius:3px}
.hours{display:flex;align-items:flex-end;gap:2px;height:76px}
.hours i{flex:1;border-radius:2px 2px 0 0;background:var(--blue)}
.ax{display:flex;justify-content:space-between;font-size:10.5px;color:var(--faint);margin-top:3px}
.cap{font-size:12px;color:var(--muted);margin-top:8px}
.clist{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px}
.cp{display:grid;grid-template-columns:22px 1fr auto;gap:8px;align-items:center;padding:7px 8px;border:1px solid var(--line);border-radius:10px;text-align:left;background:#fff;width:100%}
.cp:hover{border-color:var(--blue)}
.cp .nm{font-weight:600;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cp .mt{font-size:11px;color:var(--faint)}
.cp .rt{font:700 13px Montserrat}
.num-pin{width:20px;height:20px;border-radius:50%;color:#fff;font:700 10px 'IBM Plex Sans';display:grid;place-items:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35)}
.site-pin{width:24px;height:24px;border-radius:50%;background:var(--signal);border:4px solid var(--navy);box-shadow:0 0 0 8px rgba(242,183,5,.25)}
.age{display:grid;gap:7px}
.age .r{display:grid;grid-template-columns:44px 1fr 34px;gap:8px;align-items:center;font-size:12px}
.age .t{height:6px;border-radius:3px;background:#E6EBF1;overflow:hidden}.age .t i{display:block;height:100%;background:var(--blue);border-radius:3px}
.nse{font:800 26px Montserrat;color:var(--blue)}
.money{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.money div{border:1px solid var(--line);border-radius:10px;padding:9px 11px}
.money small{display:block;font-size:11.5px;color:var(--muted)}
.money b{font:700 16px Montserrat;color:var(--navy)}
.money .lk b{filter:blur(4px)}
.isec{padding:8px 0;border-bottom:1px solid #F0F3F7;max-width:760px}
.isec:last-child{border-bottom:0}
.isec h4{font-size:13px;margin-bottom:3px}
.isec p,.isec li{font-size:12.5px;line-height:1.55;color:#34465C}
.isec ul{margin:2px 0 0 18px}
.locked{position:relative}
.locked>.inner{filter:blur(5px);pointer-events:none;user-select:none}
.locked>.ov{position:absolute;inset:0;display:grid;place-items:center}
.locked>.ov span{background:var(--navy);color:#fff;font-weight:600;font-size:12px;border-radius:8px;padding:7px 12px}
.toast{position:absolute;left:50%;top:60px;transform:translateX(-50%);z-index:900;background:var(--navy);color:#fff;padding:8px 14px;border-radius:8px;font-size:12.5px;opacity:0;transition:opacity .2s;pointer-events:none}
.toast.show{opacity:1}
.legend{position:absolute;right:14px;top:96px;z-index:400;background:rgba(255,255,255,.96);border-radius:10px;padding:8px 10px;font-size:11.5px;display:grid;gap:3px;box-shadow:0 1px 4px rgba(19,36,59,.08)}
.legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.leaflet-control-zoom{border:1px solid var(--line)!important;border-radius:8px!important;overflow:hidden}
@media (max-width:760px){
  .profile{width:calc(100% - 28px);max-height:44%}
  .drawer{left:14px;max-height:40%}
  .cols{grid-template-columns:1fr}
  .legend{display:none}
}
@media (prefers-reduced-motion:no-preference){.site-pin{animation:land .6s ease-out}@keyframes land{from{transform:translateY(-14px);opacity:0}to{transform:none;opacity:1}}}
</style>
<script>
function addBase(m){
  /* Mapa base Esri (gris claro + nombres de calles): funciona dentro de la app y también en el
     archivo descargado. OpenStreetMap exige una dirección web de origen y desde un archivo
     abierto en la computadora responde con imágenes de error. OSM queda solo como respaldo. */
  const opt={maxZoom:19,attribution:'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap'};
  const base=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',opt);
  if(!m.getPane('etiquetas')){const pn=m.createPane('etiquetas');pn.style.zIndex=450;pn.style.pointerEvents='none';}
  const ref=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{maxZoom:19,pane:'etiquetas'});
  let errs=0,swapped=false;
  base.on('tileerror',()=>{ if(swapped||++errs<4) return; swapped=true; m.removeLayer(base); m.removeLayer(ref);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(m); });
  base.addTo(m); ref.addTo(m);
}
const $=id=>document.getElementById(id);
const fmt=n=>(n==null||isNaN(n))?'—':Number(n).toLocaleString('es-MX',{maximumFractionDigits:0});
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const scoreColor=s=>s>=65?'#1E9A5A':s>=50?'#D3871B':'#D9493F';
const ratingColor=r=>!r?'#9AA5B1':r>=4.3?'#1E9A5A':r>=3.5?'#D3871B':'#D9493F';
const ring=s=>`<div class="ring" style="background:conic-gradient(${scoreColor(s)} 0 ${s}%,#E6EBF1 0)"><span>${s}</span></div>`;
const locked=(inner,plan)=>`<div class="locked"><div class="inner">${inner}</div><div class="ov"><span>🔒 Disponible en ${plan}</span></div></div>`;
function toast(t){const e=$('toast');e.textContent=t;e.classList.add('show');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('show'),2200);}
function tabs(sel,render){document.querySelectorAll(sel+' .tabs button[data-t]').forEach(b=>b.onclick=()=>{document.querySelectorAll(sel+' .tabs button[data-t]').forEach(x=>x.classList.remove('on'));b.classList.add('on');render(b.dataset.t);});}
</script>
</head>"""


_SITIO_BODY = r"""<body>
<div id="map"></div>
<div class="chips" id="chips"></div>
<div class="toast" id="toast" role="status"></div>
<section class="panel profile" id="profile" aria-label="Perfil del sitio">
  <header><div><h3>Resumen de tu ubicación</h3><div class="sub" id="p-sub"></div></div><button class="mini" id="p-min" aria-label="Minimizar">–</button></header>
  <div class="body" id="p-body"></div>
</section>
<section class="panel drawer" id="drawer" aria-label="Detalle del análisis">
  <div class="tabs"><button data-t="trafico" class="on">¿Cuándo pasa gente?</button><button data-t="comp">Competencia</button><button data-t="demo">¿Quién vive aquí?</button><button data-t="dinero">Números</button><button data-t="interp">Explicación completa</button><button class="mini" id="d-min" aria-label="Minimizar">–</button></div>
  <div class="in" id="d-in"></div>
</section>
<div class="legend" id="legend"></div>
<script>
const D = __DATA__;
const L_ = D.locks||{};
const V = D.diag||{};
let giroSel = 0;

/* ── mapa ── */
const map=L.map('map',{zoomControl:false});
L.control.zoom({position:'topright'}).addTo(map);
L.control.scale({position:'bottomleft',imperial:false}).addTo(map);
addBase(map);
L.marker([D.lat,D.lng],{icon:L.divIcon({className:'',html:'<div class="site-pin"></div>',iconSize:[24,24],iconAnchor:[12,12]}),zIndexOffset:1000})
 .bindPopup(`<b>Tu ubicación</b><br>${esc(D.ubicacion)}`).addTo(map);
const fit=()=>{ const w=map.getSize().x; map.fitBounds(L.latLng(D.lat,D.lng).toBounds((D.radio_m||500)*2.3),{paddingTopLeft:[w>760?340:20,60],paddingBottomRight:[20,map.getSize().y*0.42]}); };
const G={radio:L.layerGroup([L.circle([D.lat,D.lng],{radius:D.radio_m||500,color:'#2A6FDB',weight:2,dashArray:'6 6',fillColor:'#2A6FDB',fillOpacity:.05})]),
         comp:L.layerGroup(),heat:L.layerGroup(),iso:L.layerGroup(),
         cani:L.layerGroup([L.circle([D.lat,D.lng],{radius:150,color:'#D9493F',weight:2,dashArray:'4 4',fillColor:'#D9493F',fillOpacity:.08}).bindTooltip('A menos de 150 m: te quitan clientes directamente'),
                            L.circle([D.lat,D.lng],{radius:300,color:'#D3871B',weight:1.5,dashArray:'4 4',fill:false}).bindTooltip('A menos de 300 m: compiten por los mismos clientes')])};
const compMk=[];
function drawComp(){
  G.comp.clearLayers();G.heat.clearLayers();compMk.length=0;
  (D.competidores||[]).forEach((c,i)=>{const m=L.marker([c.lat,c.lng],{icon:L.divIcon({className:'',html:`<div class="num-pin" style="background:${ratingColor(c.rating)}">${i+1}</div>`,iconSize:[20,20],iconAnchor:[10,10]})})
    .bindPopup(`<b>${esc(c.nombre)}</b><br>${c.rating?c.rating+' ★':'Sin calificación'} · ${fmt(c.reviews)} reseñas<br>A ${fmt(c.dist)} m de tu ubicación`);m.addTo(G.comp);compMk[i]=m;});
  if(L.heatLayer&&(D.competidores||[]).length){const mx=Math.max(1,...D.competidores.map(c=>c.reviews||0));
    L.heatLayer(D.competidores.map(c=>[c.lat,c.lng,Math.max(.25,((c.rating||3)/5)*(Math.log((c.reviews||0)+1)/Math.log(mx+1)))]),{radius:38,blur:28,maxZoom:17,gradient:{.2:'#9EC5FF',.45:'#2A6FDB',.7:'#D3871B',1:'#D9493F'}}).addTo(G.heat);}
}
let isoMode='walk';
function drawIso(){
  G.iso.clearLayers(); const cols=['#1E9A5A','#D3871B','#D9493F'];
  if(isoMode==='walk'&&D.isocronas&&D.isocronas.features){
    [...D.isocronas.features].sort((a,b)=>(b.properties.value||0)-(a.properties.value||0)).forEach((f,i,arr)=>{const k=arr.length-1-i;
      L.geoJSON(f,{style:{color:cols[k]||'#2A6FDB',weight:1.5,fillOpacity:.07}}).bindTooltip(`Llegas en ${Math.round((f.properties.value||0)/60)} min caminando`).addTo(G.iso);});
  } else { const r=isoMode==='walk'?[400,800,1200]:[1500,3000,4500];
    [2,1,0].forEach(k=>L.circle([D.lat,D.lng],{radius:r[k],color:cols[k],weight:1.5,fillColor:cols[k],fillOpacity:.05}).bindTooltip(`Llegas en ${[5,10,15][k]} min ${isoMode==='walk'?'caminando':'en auto'} (aprox.)`).addTo(G.iso)); }
}
const LAY=[{k:'radio',l:`Área de ${fmt(D.radio_m)} m`,on:true},{k:'comp',l:'Competencia',on:!L_.comp_mapa,lock:L_.comp_mapa},
           {k:'iso',l:'Hasta dónde llegas',on:false,lock:L_.mapa_avanzado},{k:'heat',l:'Dónde se junta',on:false,lock:L_.mapa_avanzado},{k:'cani',l:'Demasiado cerca',on:false,lock:L_.mapa_avanzado}];
function sync(){LAY.forEach(x=>{(x.on&&!x.lock)?G[x.k].addTo(map):map.removeLayer(G[x.k]);});}
function chips(){
  const iso=LAY.find(x=>x.k==='iso');
  $('chips').innerHTML=LAY.map(x=>`<button class="chip ${x.on&&!x.lock?'on':''} ${x.lock?'lk':''}" data-k="${x.k}"><i></i>${x.l}${x.lock?' 🔒':''}</button>`).join('')+
    (iso.on&&!iso.lock?`<span class="seg"><button data-m="walk" class="${isoMode==='walk'?'on':''}">A pie</button><button data-m="car" class="${isoMode==='car'?'on':''}">En auto</button></span>`:'');
  document.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{const x=LAY.find(y=>y.k===b.dataset.k);if(x.lock){toast(`🔒 ${x.l} disponible en ${x.lock}`);return;}x.on=!x.on;sync();chips();});
  document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{isoMode=b.dataset.m;drawIso();chips();if(isoMode==='car')map.setView([D.lat,D.lng],13);else fit();});
}
drawComp();drawIso();sync();chips();
$('legend').innerHTML=`<div><i style="background:#F2B705;box-shadow:0 0 0 2px #13243B"></i>Tu ubicación</div>`+(L_.comp_mapa?'':`<div><i style="background:#1E9A5A"></i>Competidor muy bien calificado</div><div><i style="background:#D3871B"></i>Calificación regular</div><div><i style="background:#D9493F"></i>Mal calificado</div>`);

/* ── perfil del sitio ── */
function drawProfile(){
  $('p-sub').textContent=`${D.tipo_nombre||''} · ${fmt(D.radio_m)} m a la redonda`;
  const s=Math.round(D.score||0);
  let h=`<div class="scorebar">${ring(s)}<div style="flex:1;min-width:0"><b style="color:${scoreColor(s)}">${s>=65?'Buena ubicación':s>=50?'Con cuidado':'No conviene'}</b><small>Calificación de 0 a 100. Más de 65 es buena.</small>`;
  if((D.giros||[]).length) h+=`<select class="giro-sel" id="giro" aria-label="Giro">${D.giros.map((g,i)=>`<option value="${i}" ${i===giroSel?'selected':''}>${i+1}. ${esc(g.nombre)} · ${g.score}</option>`).join('')}</select>`;
  h+=`</div></div>`;
  if(D.giros&&D.giros[giroSel]&&(D.giros[giroSel].por_que||[]).length){
    h+=`<div class="pal" style="border-bottom:1px solid var(--line)"><h4>Por qué este negocio</h4>${D.giros[giroSel].por_que.map(w=>`<div><span>${esc(w.t)}</span><b style="color:${w.s==='+'?'#1E9A5A':'#D9493F'}">${w.s}</b></div>`).join('')}</div>`;}
  h+='<div class="kp">'+(D.kpis||[]).slice(0,8).map(k=>`<div class="${k.lock?'lk':''}"><small data-plan="${k.lock||''}">${esc(k.k)}</small><b>${k.lock?'$00,000':esc(k.v)}</b>${k.n&&!k.lock?`<em>${esc(k.n)}</em>`:''}</div>`).join('')+'</div>';
  const b=D.desglose||{}, rows=[['Poca competencia alrededor','densidad'],['Competencia fácil de superar','calidad'],['Clientes que aún no tienen favorito','consolidacion']];
  const bars=`<div class="bars">${rows.map(([l,k])=>{const v=b[k]||0;return `<div>${l}<span>${L_.desglose?'00':v}</span><div class="t"><i style="width:${L_.desglose?60:v}%;background:${L_.desglose?'#2A6FDB':scoreColor(v)}"></i></div></div>`;}).join('')}</div>`;
  const barsTxt=`<div class="lockline" style="border-bottom:0;padding-bottom:0">De qué depende tu calificación (barra más llena = mejor para ti)</div>`;
  h+= L_.desglose ? `<div class="blur">${bars}</div><div class="lockline">🔒 De qué depende tu calificación: <b>plan Básico</b></div>` : barsTxt+bars;
  (D.ajustes||[]).forEach(a=>{h+=`<div class="lockline" style="display:flex;justify-content:space-between"><span>${esc(a.l)}</span><b style="color:${a.v>0?'#1E9A5A':'#D9493F'}">${a.v>0?'+':''}${a.v} pts</b></div>`;});
  if((D.palancas||[]).length) h+=`<div class="pal"><h4>Qué mejoraría tu calificación</h4>${D.palancas.map(p=>`<div><span>${esc(p.l)}</span><b>+${p.v} pts</b></div>`).join('')}</div>`;
  $('p-body').innerHTML=h;
  const gs=$('giro'); if(gs) gs.onchange=()=>selectGiro(+gs.value);
}
function selectGiro(i){const g=D.giros[i];if(!g)return;giroSel=i;
  Object.assign(D,{score:g.score,nivel:g.nivel,tipo_nombre:g.nombre,desglose:g.desglose,competidores:g.competidores,n_competidores:g.n_competidores});
  drawComp();sync();drawProfile();if(curTab==='comp')drawTab('comp');
  if(i>0) toast('Mapa y calificación de este negocio. Ventas y gente que pasa son del negocio #1.');}
$('p-min').onclick=()=>{const p=$('profile');p.classList.toggle('min');$('p-min').textContent=p.classList.contains('min')?'+':'–';};

/* ── cajón de detalle ── */
let curTab='trafico';
function drawTab(t){
  curTab=t; const el=$('d-in'); let h='';
  if(t==='trafico'){
    const T=D.trafico;
    if(!T){h='<p class="cap">No tengo datos de cuánta gente pasa para este análisis.</p>';}
    else{
      const fr=[['Mañana',6,11],['Mediodía',12,15],['Tarde',16,19],['Noche',20,23],['Madrug.',0,5]],dias=['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'],H=T.horario||[],S=T.semanal||[];
      const vals=dias.map((d,i)=>fr.map(([n,a,b])=>{let s=0,c=0;for(let x=a;x<=b;x++){s+=H[x]||0;c++;}return (S[i]||0)/100*s/c;}));
      const mx=Math.max(1,...vals.flat()),col=v=>{const q=v/mx;return q>.75?'#13243B':q>.55?'#2A6FDB':q>.35?'#7FA9EE':q>.18?'#C9DBF8':'#EEF3FB';};
      let hm='<div class="hm"><div></div>'+fr.map(f=>`<div class="h">${f[0]}</div>`).join('');
      dias.forEach((d,i)=>{hm+=`<div class="d">${d}</div>`+vals[i].map(v=>`<div class="c" title="${Math.round(v/mx*100)}" style="background:${col(v)}"></div>`).join('');});
      hm+=`</div><p class="cap">El día con más gente: <b>${esc(T.dia_pico||'—')}</b>. Color más oscuro = pasa más gente.</p>`;
      const hx=Math.max(1,...H);
      let hb=`<div class="hours">${H.map((v,i)=>`<i title="${i}:00 · ${v}%" style="height:${v/hx*100}%;opacity:${v>=70?1:.45}"></i>`).join('')}</div><div class="ax"><span>0 h</span><span>6 h</span><span>12 h</span><span>18 h</span><span>23 h</span></div>`;
      hb+=`<p class="cap">Horas con más gente: ${(T.picos||[]).map(esc).join(', ')||'—'}</p>`;
      const inner=`<div class="cols"><div>${hm}</div><div>${hb}</div></div>`;
      h=L_.trafico?locked(inner,'PRO'):inner;
    }
  }
  if(t==='comp'){
    const cs=D.competidores||[],nS=D.comp_visibles||cs.length;
    const n150=cs.filter(c=>c.dist<=150).length;
    h=`<p class="cap" style="margin:0 0 8px">Hay ${D.n_competidores}${D.n_competidores>=20?'+':''} negocios como el tuyo a ${fmt(D.radio_m)} m${n150?` · <b style="color:#D9493F">${n150} a menos de 150 m, casi enfrente</b>`:''}. Toca uno para verlo en el mapa.</p>`;
    h+=cs.length?`<div class="clist">${cs.slice(0,nS).map((c,i)=>`<button class="cp" data-i="${i}"><div class="num-pin" style="background:${ratingColor(c.rating)}">${i+1}</div><div style="min-width:0"><div class="nm">${esc(c.nombre)}</div><div class="mt">${fmt(c.dist)} m · ${fmt(c.reviews)} reseñas</div></div><div class="rt" style="color:${ratingColor(c.rating)}">${c.rating?c.rating.toFixed(1):'—'}★</div></button>`).join('')}</div>`:'<p class="cap">No encontré competidores directos en el radio.</p>';
    if(cs.length>nS) h+=`<p class="cap">🔒 ${cs.length-nS} competidores más en un plan superior.</p>`;
  }
  if(t==='demo'){
    const E=D.demo||{},ed=E.edad||{},rows=[['0-17','0 a 17'],['18-35','18 a 35'],['36-55','36 a 55'],['56+','56 o más']],mx=Math.max(1,...rows.map(r=>ed[r[0]]||0));
    const inner=`<div class="cols"><div><div class="nse">${esc(E.nse||'—')}</div><p class="cap" style="margin-top:2px">Nivel de ingresos que más hay en la zona (A/B alto, C medio, D bajo). Cada familia gana unos ${E.ingreso?'$'+fmt(E.ingreso):'—'} al mes${E.mujeres?` · ${E.mujeres}% son mujeres`:''}.</p><p class="cap">Edades de la gente que vive cerca:</p></div>
      <div class="age">${rows.map(([k,l])=>`<div class="r"><span>${l}</span><div class="t"><i style="width:${(ed[k]||0)/mx*100}%"></i></div><span>${ed[k]||0}%</span></div>`).join('')}</div></div>`;
    h=L_.demografia?locked(inner,'Básico'):inner;
  }
  if(t==='dinero'){
    const ks=(D.kpis||[]).filter(k=>/Gasto|Ventas|Clientes|Venta|Ganancia|Recuperas/.test(k.k));
    h=`<div class="money">${ks.map(k=>`<div class="${k.lock?'lk':''}"><small>${esc(k.k)}${k.lock?' · 🔒 '+k.lock:''}</small><b>${k.lock?'$00,000':esc(k.v)}</b>${k.n&&!k.lock?`<small>${esc(k.n)}</small>`:''}</div>`).join('')}</div><p class="cap">Son cálculos con datos de INEGI, la competencia y la gente que pasa. Tómalos como guía, no como promesa.</p>`;
  }
  if(t==='interp'){
    const sec=s=>`<div class="isec">${s.t?`<h4>${esc(s.t)}</h4>`:''}${(s.p||[]).map(x=>`<p>${esc(x)}</p>`).join('')}${(s.b||[]).length?'<ul>'+s.b.map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>':''}</div>`;
    const S=V.secciones||[],A=D.analisis_secciones||[];
    h=S.map(sec).join('')+(A.length?`<h4 style="margin:12px 0 4px;color:#2A6FDB">${D.modo==='recomendar'?'Cómo es la zona':'Sobre tu competencia'}</h4>`+A.map(sec).join(''):'');
    if(L_.diag_parcial) h=(S[0]?sec(S[0]):'')+locked(S.slice(1).map(sec).join('')||sec({t:'Interpretación completa',p:['Disponible en el plan Básico.']}),'Básico');
    if(!h) h='<p class="cap">No hay explicación disponible para este análisis.</p>';
  }
  el.innerHTML=h;
  document.querySelectorAll('.cp').forEach(b=>b.onclick=()=>{const i=+b.dataset.i,c=D.competidores[i];
    if(L_.comp_mapa){toast('🔒 Ubicación de competidores disponible en Básico');return;}
    const x=LAY.find(y=>y.k==='comp');if(!x.on){x.on=true;sync();chips();}
    map.flyTo([c.lat,c.lng],17,{duration:.6});setTimeout(()=>compMk[i]&&compMk[i].openPopup(),650);});
}
tabs('#drawer',drawTab);
$('d-min').onclick=()=>{const d=$('drawer');d.classList.toggle('min');$('d-min').textContent=d.classList.contains('min')?'+':'–';};
drawProfile();drawTab('trafico');
setTimeout(()=>{map.invalidateSize();fit();},150);
window.addEventListener('resize',()=>{map.invalidateSize();});
</script></body></html>"""


_ZONAS_BODY = r"""<body>
<div id="map"></div>
<div class="chips" id="chips"></div>
<div class="toast" id="toast" role="status"></div>
<section class="panel profile" id="profile" aria-label="Mejores zonas">
  <header><div><h3>Las mejores zonas para ti</h3><div class="sub" id="p-sub"></div></div><button class="mini" id="p-min" aria-label="Minimizar">–</button></header>
  <div class="body" id="p-body"></div>
</section>
<section class="panel drawer" id="drawer" aria-label="Detalle">
  <div class="tabs"><button data-t="tabla" class="on">Comparar zonas</button><button data-t="nodos">Donde se junta la competencia</button><button data-t="guia">Qué buscar en el local</button><button data-t="metodo">Cómo lo calculé</button><button class="mini" id="d-min" aria-label="Minimizar">–</button></div>
  <div class="in" id="d-in"></div>
</section>
<div class="legend" id="legend"></div>
<script>
const D=__DATA__;
const Z=D.zonas||[],C=D.celdas||[];
const CAT={mercado_probado:['Ya hay clientes','#1E9A5A'],moderada:['Competencia normal','#2A6FDB'],virgen:['Sin competencia','#8E6CD9'],saturada:['Demasiada competencia','#D9493F'],baja_densidad:['Vive poca gente','#93A0AF']};
const NODOS=D.nodos||[];
const money=n=>'$'+(n>=1e6?(n/1e6).toFixed(1)+' M':Math.round(n/1e3)+' mil');
const ramp=s=>{const t=Math.max(0,Math.min(1,(s-30)/60)),a=[217,73,63],b=[211,135,27],c=[30,154,90];const m=t<.5?a.map((v,i)=>v+(b[i]-v)*t*2):b.map((v,i)=>v+(c[i]-v)*(t-.5)*2);return `rgb(${m.map(Math.round).join(',')})`;};
let sel=0,colorMode='score';
const map=L.map('map',{zoomControl:false});L.control.zoom({position:'topright'}).addTo(map);L.control.scale({position:'bottomleft',imperial:false}).addTo(map);addBase(map);
L.marker([D.lat,D.lng],{icon:L.divIcon({className:'',html:'<div class="site-pin"></div>',iconSize:[24,24],iconAnchor:[12,12]}),zIndexOffset:1000}).bindPopup('<b>Tu punto de referencia</b><br>'+esc(D.ubicacion)).addTo(map);
const G={radio:L.layerGroup([L.circle([D.lat,D.lng],{radius:D.radio_km*1000,color:'#13243B',weight:1.2,dashArray:'6 6',fill:false})]),hex:L.layerGroup(),top:L.layerGroup(),comp:L.layerGroup(),nodos:L.layerGroup()};
NODOS.forEach(n=>{L.circle([n.lat,n.lng],{radius:n.radio_m,color:'#D9493F',weight:2,dashArray:'5 5',fillColor:'#D9493F',fillOpacity:.14})
  .bindTooltip(`<b>Aquí se junta la competencia</b><br>${esc(n.nombre)} · ${n.n} negocios como el tuyo`,{sticky:true}).addTo(G.nodos);
  L.marker([n.lat,n.lng],{icon:L.divIcon({className:'',html:`<div style="background:#D9493F;color:#fff;font:700 11px 'IBM Plex Sans';border-radius:99px;padding:3px 8px;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3);white-space:nowrap">⚠ ${n.n} competidores juntos</div>`,iconSize:[150,22],iconAnchor:[75,11]}),zIndexOffset:800}).on('click',()=>{document.querySelector('#drawer .tabs button[data-t="nodos"]').click();}).addTo(G.nodos);});
function paint(){G.hex.clearLayers();C.forEach(c=>{const col=colorMode==='score'?ramp(c.score):(CAT[c.categoria]||['','#9AA5B1'])[1];
  L.polygon(c.poly,{color:'#fff',weight:1.5,fillColor:col,fillOpacity:c.detallada?.5:.25,dashArray:c.detallada?null:'3 3'})
   .bindTooltip(`<b>${c.detallada?esc(c.nombre):'Zona que no revisé a fondo'}</b><br>Calificación ${c.score}/100 · ${(CAT[c.categoria]||[''])[0]}<br>${c.n_comp}${c.tope?'+':''} negocios como el tuyo`,{sticky:true}).addTo(G.hex);});}
paint();
const mk=[];Z.forEach((z,i)=>{mk[i]=L.marker([z.lat,z.lng],{icon:L.divIcon({className:'',html:`<div class="num-pin" style="background:#13243B;width:24px;height:24px;font-size:11px">${i+1}</div>`,iconSize:[24,24],iconAnchor:[12,12]}),zIndexOffset:900})
  .bindPopup(`<b>${i+1}. ${esc(z.nombre)}</b><br>Calificación <b style="color:${scoreColor(z.score)}">${z.score}/100</b> · ${(CAT[z.categoria]||[''])[0]}<br>${z.n_comp} negocios como el tuyo · a ${z.dist_km} km del punto que buscaste`).on('click',()=>pick(i,false)).addTo(G.top);});
(D.competidores||[]).forEach(c=>L.circleMarker([c.lat,c.lng],{radius:3.5,weight:1,color:'#fff',fillColor:ratingColor(c.rating),fillOpacity:.95}).bindTooltip(`${esc(c.nombre)} · ${c.rating?c.rating+'★':'s/c'}`).addTo(G.comp));
const LAY=[{k:'hex',l:'Zonas',on:true},{k:'top',l:'Las mejores',on:true},{k:'nodos',l:'Donde se junta la competencia',on:true},{k:'comp',l:'Competencia',on:false},{k:'radio',l:`${D.radio_km} km a la redonda`,on:true}];
function sync(){LAY.forEach(x=>x.on?G[x.k].addTo(map):map.removeLayer(G[x.k]));}
function chips(){$('chips').innerHTML=LAY.map(x=>`<button class="chip ${x.on?'on':''}" data-k="${x.k}"><i></i>${x.l}</button>`).join('')+`<span class="seg"><button data-m="score" class="${colorMode==='score'?'on':''}">Color por calificación</button><button data-m="cat" class="${colorMode==='cat'?'on':''}">Color por tipo de zona</button></span>`;
  document.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{const x=LAY.find(y=>y.k===b.dataset.k);x.on=!x.on;sync();chips();});
  document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{colorMode=b.dataset.m;paint();chips();legend();});}
function legend(){$('legend').innerHTML=colorMode==='score'?`<div><i style="background:#1E9A5A"></i>Buena zona</div><div><i style="background:#D3871B"></i>Regular</div><div><i style="background:#D9493F"></i>No conviene</div><div style="color:#93A0AF">Punteado: no la revisé a fondo</div>`:Object.values(CAT).map(([l,c])=>`<div><i style="background:${c}"></i>${l}</div>`).join('');}
sync();chips();legend();
const fit=()=>{const w=map.getSize().x;map.fitBounds(L.latLng(D.lat,D.lng).toBounds(D.radio_km*2000*1.1),{paddingTopLeft:[w>760?340:20,60],paddingBottomRight:[20,map.getSize().y*0.4]});};

function cards(){
  $('p-sub').textContent=`${D.tipo_nombre} · revisé ${C.length} zonas`;
  $('p-body').innerHTML=Z.length?Z.map((z,i)=>`<button class="cp" data-i="${i}" style="border-radius:0;border:0;border-bottom:1px solid var(--line);padding:10px 14px;grid-template-columns:24px 1fr auto;${i===sel?'background:#E8F0FC':''}">
    <div class="num-pin" style="background:#13243B;width:22px;height:22px">${i+1}</div>
    <div style="min-width:0"><div class="nm">${esc(z.nombre)}</div><div class="mt"><span style="color:${CAT[z.categoria][1]};font-weight:600">${CAT[z.categoria][0]}</span>${z.nodo?` · <span style="color:#D9493F;font-weight:600">mucha competencia junta</span>`:''} · ${z.n_comp}${z.tope?'+':''} competidores${z.actividad?' · '+({alta:'vive mucha gente',media:'vive gente',baja:'vive poca gente'})[z.actividad]:''} · a ${z.dist_km} km</div>
    ${i===sel?`<div style="margin-top:6px;display:grid;gap:3px">${(z.por_que||[]).map(w=>`<div style="font-size:11.5px;color:#34465C;display:grid;grid-template-columns:12px 1fr;gap:4px"><b style="color:${w.s==='+'?'#1E9A5A':w.s==='−'||w.s==='!'?'#D9493F':'#D3871B'}">${w.s==='+'?'+':w.s==='−'?'−':w.s==='!'?'!':'•'}</b><span>${esc(w.t)}</span></div>`).join('')}</div>`:''}</div>
    <div class="rt" style="color:${scoreColor(z.score)};font-size:17px">${z.score}</div></button>`).join(''):'<p class="cap" style="padding:12px 14px">No se pudieron detallar zonas en este radio.</p>';
  document.querySelectorAll('#p-body .cp').forEach(b=>b.onclick=()=>pick(+b.dataset.i,true));
}
function pick(i,fly){sel=i;cards();if(curTab!=='metodo')drawTab(curTab);if(fly){map.flyTo([Z[i].lat,Z[i].lng],15,{duration:.6});setTimeout(()=>mk[i].openPopup(),650);}}
$('p-min').onclick=()=>{const p=$('profile');p.classList.toggle('min');$('p-min').textContent=p.classList.contains('min')?'+':'–';};

let curTab='tabla';
function drawTab(t){curTab=t;let h='';
  if(t==='tabla'){h=`<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px"><tr style="text-align:left;color:#5D6B7C;font-size:11.5px"><th style="padding:5px 6px">#</th><th style="padding:5px 6px">Zona</th><th style="padding:5px 6px">Calificación</th><th style="padding:5px 6px">¿Vive gente?</th><th style="padding:5px 6px">Tipo de zona</th><th style="padding:5px 6px">Competidores</th><th style="padding:5px 6px">Ingresos</th><th style="padding:5px 6px">Calle</th><th style="padding:5px 6px">Distancia</th></tr>`+
    Z.map((z,i)=>`<tr data-i="${i}" style="cursor:pointer;border-top:1px solid #F0F3F7;${i===sel?'background:#E8F0FC':''}"><td style="padding:6px"><b>${i+1}</b></td><td style="padding:6px;font-weight:600">${esc(z.nombre)}</td><td style="padding:6px;font-weight:700;color:${scoreColor(z.score)}">${z.score}</td><td style="padding:6px">${({alta:'Mucha',media:'Algo',baja:'Poca'})[z.actividad]||'—'}</td><td style="padding:6px;color:${CAT[z.categoria][1]}">${CAT[z.categoria][0]}</td><td style="padding:6px">${z.n_comp}${z.tope?'+':''}</td><td style="padding:6px">${esc(z.nse)}</td><td style="padding:6px">${esc((z.vial||{}).badge||'—')}</td><td style="padding:6px">${z.dist_km} km</td></tr>`).join('')+'</table></div>';}
  if(t==='nodos'){
    if(!NODOS.length){h='<p class="cap" style="margin:0">No encontré lugares donde se junte mucha competencia: está repartida.</p>';}
    else{h=`<div class="isec" style="background:#FDF1F0;border-radius:10px;padding:10px 12px;border:0;margin-bottom:8px"><p><b>Aquí sí hay clientes, pero también muchos negocios como el tuyo.</b> Si abres aquí, la gente ya tiene a dónde ir, así que necesitas ofrecer algo distinto (producto, precio, trato u horario) y estar en redes sociales y Google Maps desde el primer día. Eso cuesta más que abrir en una zona normal.</p></div>`+
      `<div class="clist">`+NODOS.map(n=>`<button class="cp" data-n="${n.rank-1}" style="grid-template-columns:auto 1fr;align-items:start"><span style="background:#D9493F;color:#fff;font:700 11px 'IBM Plex Sans';border-radius:99px;padding:3px 8px">⚠ ${n.rank}</span><div style="min-width:0"><div class="nm">${esc(n.nombre)}</div><div class="mt">${n.n} negocios como el tuyo en ${fmt(n.radio_m)} m${n.rating_prom?` · calificación promedio ${n.rating_prom}★`:''}</div>${n.top&&n.top.nombre?`<div class="mt">El más fuerte: ${esc(n.top.nombre)} (${n.top.rating||'—'}★, ${fmt(n.top.reviews)} reseñas)</div>`:''}<div class="mt" style="color:#D9493F">Aparta de ${money(n.extra_min)} a ${money(n.extra_max)} más para tu marca y redes</div></div></button>`).join('')+`</div>`+
      `<p class="cap">Ese dinero extra es una guía (10 % a 20 % de lo que normalmente cuesta abrir este negocio), no una cotización.</p>`;}
  }
  if(t==='guia'){const z=Z[sel]||{},r=z.recom||{};const it=[['Qué calle te conviene',r.vialidad_ideal],['Que se vea desde la calle',r.visibilidad],['Estacionamiento',r.estacionamiento],['Si es en plaza comercial',r.plaza_recomendacion],['A quién copiarle lo bueno',r.ref_competidor],['Según los ingresos de la zona',r.tip_nse]].filter(x=>x[1]);
    h=`<p class="cap" style="margin:0 0 6px">Qué buscar en un local de la zona ${sel+1}: <b>${esc(z.nombre||'')}</b></p>`+it.map(([a,b])=>`<div class="isec"><h4>${a}</h4><p>${esc(b)}</p></div>`).join('');}
  if(t==='metodo'){h=`<div class="isec"><p><b>1.</b> Dividí ${D.radio_km} km alrededor del punto que buscaste en ${C.length} zonas.</p></div>
    <div class="isec"><p><b>2.</b> En cada zona conté cuántos negocios como el tuyo hay, qué tan bien calificados están y qué tan fieles son sus clientes.</p></div>
    <div class="isec"><p><b>3.</b> En las 10 mejores revisé si vive gente: conté tienditas, farmacias y escuelas, que solo existen donde hay vecinos. Si casi no hay, la marco como <b>Vive poca gente</b> y no la recomiendo.</p></div>
    <div class="isec"><p><b>4.</b> A las ${Z.length} mejores les sumé los ingresos de la colonia (INEGI) y si la calle le conviene a tu giro.</p></div>
    <div class="isec"><p><b>Ya hay clientes:</b> hay un negocio bien calificado y no demasiada competencia. <b>Sin competencia:</b> serías el primero, pero hay que comprobar que la gente compraría. <b>Demasiada competencia:</b> muchos negocios como el tuyo. <b>Donde se junta la competencia:</b> lugares con muchos negocios juntos.</p></div>
    <p class="cap">Esta búsqueda usó ${D.llamadas} consultas a Google.</p>`;}
  $('d-in').innerHTML=h;
  document.querySelectorAll('#d-in tr[data-i]').forEach(e=>e.onclick=()=>pick(+e.dataset.i,true));
  document.querySelectorAll('#d-in [data-n]').forEach(e=>e.onclick=()=>{const n=NODOS[+e.dataset.n];map.flyTo([n.lat,n.lng],15,{duration:.6});});
}
tabs('#drawer',drawTab);
$('d-min').onclick=()=>{const d=$('drawer');d.classList.toggle('min');$('d-min').textContent=d.classList.contains('min')?'+':'–';};
cards();drawTab('tabla');
setTimeout(()=>{map.invalidateSize();fit();},150);
</script></body></html>"""


def _payload(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")


def html_mapa_sitio(data: dict) -> str:
    """data = salida de preparar_datos_dashboard (sin campos internos)."""
    try:
        from dashboard_4site import extraer_secciones
        if data.get("analisis_competencia") and not data.get("analisis_secciones"):
            data = dict(data)
            data["analisis_secciones"] = extraer_secciones(data.pop("analisis_competencia"))
    except Exception:
        pass
    return _HEAD + _SITIO_BODY.replace("__DATA__", _payload(data))


def html_mapa_zonas(data: dict) -> str:
    return _HEAD + _ZONAS_BODY.replace("__DATA__", _payload(data))


# ════════════════════════════════════════════════════════════════
# Chat del agente dentro del panel izquierdo
# ════════════════════════════════════════════════════════════════

def render_chat(claude, data: dict, tier_key: str, idioma: str = "es", modelo: str = "claude-sonnet-4-5"):
    from dashboard_4site import _contexto_agente, LIMITE_PREGUNTAS, SUGERENCIAS, SUGERENCIAS_ZONA
    aid = data.get("id", "x")
    k_msgs, k_pend = f"_agente_msgs_{aid}", f"_agente_pend_{aid}"
    msgs = st.session_state.setdefault(k_msgs, [])
    limite = LIMITE_PREGUNTAS.get(tier_key, 1)
    restantes = max(limite - sum(1 for m in msgs if m["role"] == "user"), 0)

    for m in msgs:
        with st.chat_message(m["role"], avatar=AVATAR_AGENTE if m["role"] == "assistant" else AVATAR_USUARIO):
            st.markdown(m["content"])

    prompt = None
    if restantes > 0:
        sugs = SUGERENCIAS_ZONA if data.get("modo") == "zona" else SUGERENCIAS
        ya = {m["content"] for m in msgs if m["role"] == "user"}
        sugs = [s for s in sugs if s not in ya][:3]
        for i, sug in enumerate(sugs):
            with st.container(key=f"chip_q{i}_{aid}"):
                if st.button(sug, key=f"sugq_{aid}_{i}"):
                    st.session_state[k_pend] = sug
        prompt = st.chat_input(f"Pregúntame lo que quieras · te quedan {restantes}", key=f"chat_{aid}")
    else:
        st.caption("Usaste las preguntas de tu plan. PRO y Premium incluyen más consultas al agente.")
    prompt = prompt or st.session_state.pop(k_pend, None)
    if not prompt:
        return
    msgs.append({"role": "user", "content": prompt})
    contexto, bloqueados = _contexto_agente(data)
    system = (
        "Eres el agente de 4SITE, analista senior de ubicaciones comerciales en México. "
        f"Responde en {'español' if idioma == 'es' else 'English'}, directo y accionable, máximo 130 palabras, "
        "con bullets cortos cuando ayude. Usa SOLO los datos del análisis; no inventes cifras. "
        "Habla sencillo, como a alguien que nunca ha abierto un negocio: nada de siglas ni tecnicismos "
        "(NSE, ROI, ticket, score, vialidad) sin explicarlos en palabras comunes. "
        "Si preguntan por algo que no está en los datos, dilo."
        + (f" Estos módulos NO están en el plan del usuario: {', '.join(bloqueados)}. "
           "Si preguntan por ellos, di que están en un plan superior, sin estimarlos." if bloqueados else "")
        + f"\n\nDATOS DEL ANÁLISIS (JSON):\n{contexto}"
    )
    with st.spinner("Pensando…"):
        try:
            r = claude.messages.create(model=modelo, max_tokens=600, system=system,
                                       messages=[{"role": m["role"], "content": m["content"]} for m in msgs[-10:]])
            resp = r.content[0].text
        except Exception as e:
            resp = f"No pude responder en este momento ({e})."
    msgs.append({"role": "assistant", "content": resp})
    st.rerun()
