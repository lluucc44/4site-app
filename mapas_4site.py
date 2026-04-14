"""
mapas_4site.py
==============
Mapas avanzados con Folium:
  1. Mapa base con competidores coloreados por rating
  2. Heatmap de densidad de competencia
  3. Isócronas (OpenRouteService API gratuita)
  4. Mapa de canibalización (competidores que se solapan)
"""

import math
import json
import requests
import folium
from folium.plugins import HeatMap, MarkerCluster
import streamlit as st

# ─────────────────────────────────────────────────────────────────
# COLORES POR RATING
# ─────────────────────────────────────────────────────────────────

def color_por_rating(rating):
    if not rating or rating == 0:
        return "#9E9E9E", "grey", "Sin datos"
    elif rating >= 4.3:
        return "#22C55E", "green",  f"Excelente ({rating}★)"
    elif rating >= 3.5:
        return "#F97316", "orange", f"Bueno ({rating}★)"
    else:
        return "#EF4444", "red",    f"Débil ({rating}★)"


def icono_tier(rating):
    """Retorna ícono FontAwesome según rating"""
    if not rating or rating == 0: return "question"
    elif rating >= 4.3: return "star"
    elif rating >= 3.5: return "exclamation"
    else: return "times"


# ─────────────────────────────────────────────────────────────────
# 1. MAPA BASE CON COMPETIDORES
# ─────────────────────────────────────────────────────────────────

def crear_mapa_competidores(lat, lng, competidores, tipo_negocio_nombre="", idioma="es"):
    """
    Mapa Folium con:
    - Marcador principal (tu ubicación)
    - Círculo de 500m
    - Competidores coloreados por rating con popups
    """
    m = folium.Map(
        location=[lat, lng],
        zoom_start=16,
        tiles="CartoDB positron"
    )

    # ── Círculo de 500m ──
    folium.Circle(
        location=[lat, lng],
        radius=500,
        color="#0047AB",
        weight=2,
        fill=True,
        fill_color="#0047AB",
        fill_opacity=0.06,
        tooltip="Radio de análisis: 500m"
    ).add_to(m)

    # ── Tu ubicación ──
    folium.Marker(
        location=[lat, lng],
        popup=folium.Popup(
            f"<b>📍 Tu ubicación</b><br>{tipo_negocio_nombre}<br><i>Negocio propuesto</i>",
            max_width=200
        ),
        tooltip="⭐ Tu ubicación",
        icon=folium.Icon(color="blue", icon="star", prefix="fa")
    ).add_to(m)

    # ── Competidores ──
    n_verde  = n_naranja = n_rojo = n_gris = 0
    for comp in (competidores or []):
        loc = comp.get('location', {})
        c_lat = loc.get('latitude')
        c_lng = loc.get('longitude')
        if not c_lat or not c_lng:
            continue

        nombre  = comp.get('displayName', {}).get('text', 'Sin nombre')
        rating  = comp.get('rating', 0)
        reviews = comp.get('userRatingCount', 0)
        hex_col, fol_col, desc = color_por_rating(rating)

        if fol_col == "green":   n_verde   += 1
        elif fol_col == "orange": n_naranja += 1
        elif fol_col == "red":    n_rojo    += 1
        else:                     n_gris    += 1

        popup_html = f"""
        <div style='font-family:sans-serif; min-width:160px;'>
            <b style='color:{hex_col};'>{nombre}</b><br>
            <span style='font-size:13px;'>{'⭐'*int(rating) if rating else '—'}</span>
            {'<b>' + str(rating) + '/5</b>' if rating else '<i>Sin rating</i>'}<br>
            <span style='color:#888;'>{reviews:,} reseñas</span><br>
            <span style='background:{hex_col}22; padding:2px 6px; border-radius:4px;
                color:{hex_col}; font-size:11px;'>{desc}</span>
        </div>"""

        folium.CircleMarker(
            location=[c_lat, c_lng],
            radius=9,
            color=hex_col,
            weight=2,
            fill=True,
            fill_color=hex_col,
            fill_opacity=0.75,
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=f"{nombre} — {desc}"
        ).add_to(m)

    # ── Leyenda ──
    leyenda_html = f"""
    <div style='position:fixed; bottom:20px; left:20px; z-index:9999;
         background:white; padding:10px 14px; border-radius:8px;
         box-shadow:0 2px 8px rgba(0,0,0,0.15); font-family:sans-serif; font-size:12px;'>
        <b style='color:#0047AB;'>Competidores</b><br>
        <span style='color:#22C55E;'>●</span> Excelente ≥4.3★ ({n_verde})<br>
        <span style='color:#F97316;'>●</span> Bueno 3.5-4.2★ ({n_naranja})<br>
        <span style='color:#EF4444;'>●</span> Débil &lt;3.5★ ({n_rojo})<br>
        <span style='color:#9E9E9E;'>●</span> Sin datos ({n_gris})<br>
        <span style='color:#0047AB;'>◯</span> Radio 500m
    </div>"""
    m.get_root().html.add_child(folium.Element(leyenda_html))

    # Texto interpretación
    interpretacion = _interpretar_competidores(n_verde, n_naranja, n_rojo, n_gris)

    return m, interpretacion


def _interpretar_competidores(n_verde, n_naranja, n_rojo, n_gris):
    total = n_verde + n_naranja + n_rojo + n_gris
    if total == 0:
        return "✅ Sin competidores directos identificados en el radio de 500m — mercado sin saturar."
    interpretacion = f"Se identificaron {total} competidores en 500m. "
    if n_verde > 3:
        interpretacion += f"⚠️ Alta concentración de {n_verde} competidores con rating excelente (≥4.3★) — el mercado está bien atendido, se requiere diferenciación fuerte. "
    elif n_verde <= 1 and n_rojo >= 2:
        interpretacion += f"💡 La mayoría de competidores son débiles ({n_rojo} con rating bajo) — oportunidad clara de posicionarte como el mejor de la zona. "
    elif n_naranja >= total * 0.6:
        interpretacion += f"📊 Competencia de nivel medio predominante — hay espacio para un negocio que supere el estándar de la zona. "
    if total > 10:
        interpretacion += "🔴 Radio muy saturado — considera ampliar el análisis a 1km o buscar otra ubicación."
    elif total <= 3:
        interpretacion += "🟢 Baja saturación — buena oportunidad de captura de mercado."
    return interpretacion


# ─────────────────────────────────────────────────────────────────
# 2. HEATMAP DE COMPETENCIA
# ─────────────────────────────────────────────────────────────────

def crear_heatmap_competencia(lat, lng, competidores, idioma="es"):
    """
    Heatmap de densidad de competencia.
    Cada competidor aporta un punto de calor ponderado por su rating
    (mejor rating = más calor = más competencia consolidada).
    """
    m = folium.Map(
        location=[lat, lng],
        zoom_start=15,
        tiles="CartoDB positron"
    )

    # Círculo de 500m en modo oscuro
    folium.Circle(
        location=[lat, lng],
        radius=500,
        color="#00D4D4",
        weight=2,
        fill=False,
        tooltip="Radio 500m"
    ).add_to(m)

    # Tu ubicación
    folium.Marker(
        location=[lat, lng],
        tooltip="⭐ Tu ubicación",
        icon=folium.Icon(color="blue", icon="star", prefix="fa")
    ).add_to(m)

    # Puntos de calor — peso = rating/5 * (1 + log(reviews+1)/10)
    import math as _math
    heat_data = []
    for comp in (competidores or []):
        loc = comp.get('location', {})
        c_lat = loc.get('latitude')
        c_lng = loc.get('longitude')
        if not c_lat or not c_lng:
            continue
        rating  = comp.get('rating', 3.0) or 3.0
        reviews = comp.get('userRatingCount', 0) or 0
        # Peso: competidores fuertes = mayor calor
        peso = (rating / 5.0) * (1 + _math.log(reviews + 1) / 10)
        heat_data.append([c_lat, c_lng, round(peso, 2)])

    if heat_data:
        HeatMap(
            heat_data,
            min_opacity=0.4,
            max_zoom=18,
            radius=30,
            blur=18,
            gradient={0.0: '#22C55E', 0.4: '#FCD34D', 0.7: '#F97316', 1.0: '#EF4444'}
        ).add_to(m)

    # Leyenda
    leyenda_html = """
    <div style='position:fixed; bottom:20px; left:20px; z-index:9999;
         background:white; padding:10px 14px;
         border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.15);
         font-family:sans-serif; font-size:12px;'>
        <b style='color:#0047AB;'>Densidad de Competencia</b><br>
        <span style='color:#22C55E;'>●</span> Baja<br>
        <span style='color:#FCD34D;'>●</span> Media<br>
        <span style='color:#F97316;'>●</span> Alta<br>
        <span style='color:#EF4444;'>●</span> Muy alta<br>
        <small style='color:#888;'>Peso por rating y reseñas</small>
    </div>"""
    m.get_root().html.add_child(folium.Element(leyenda_html))

    # Interpretación
    n = len([c for c in (competidores or []) if c.get('location', {}).get('latitude')])
    if n == 0:
        interp = "✅ Sin datos de calor — no hay competidores con ubicación conocida en el radio."
    else:
        pesos = [(c.get('rating',3)/5) for c in competidores if c.get('location',{}).get('latitude')]
        calor_prom = sum(pesos)/len(pesos) if pesos else 0
        if calor_prom > 0.8:
            interp = "🔴 Zona de alta densidad competitiva — competidores muy consolidados. Diferenciación crítica."
        elif calor_prom > 0.6:
            interp = "🟠 Competencia moderada-alta — hay espacio pero el mercado ya tiene actores establecidos."
        elif calor_prom > 0.4:
            interp = "🟡 Competencia media — oportunidad de entrar con propuesta diferenciada."
        else:
            interp = "🟢 Zona de baja intensidad competitiva — competidores débiles o pocos consolidados."

    return m, interp


# ─────────────────────────────────────────────────────────────────
# 3. ISÓCRONAS (OpenRouteService — API gratuita)
# Docs: https://openrouteservice.org/dev/#/api-docs/v2/isochrones
# Límite gratuito: 2000 req/día
# ─────────────────────────────────────────────────────────────────

ORS_API_URL = "https://api.openrouteservice.org/v2/isochrones/{profile}"

def obtener_isocronas(lat, lng, ors_api_key=None,
                       tiempos=[5, 10, 15], perfil="foot-walking"):
    """
    Obtiene isócronas de la API gratuita de OpenRouteService.
    perfil: 'foot-walking', 'driving-car', 'cycling-regular'
    tiempos: lista de minutos
    Retorna GeoJSON con las isócronas o None si falla.
    """
    if not ors_api_key:
        return None, "No se configuró ORS_API_KEY"

    url = ORS_API_URL.format(profile=perfil)
    body = {
        "locations": [[lng, lat]],  # ORS usa [lng, lat]
        "range": [t * 60 for t in tiempos],  # segundos
        "range_type": "time",
        "smoothing": 0.8,
    }
    headers = {
        "Authorization": ors_api_key,
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, f"Error ORS: {resp.status_code} — {resp.text[:100]}"
    except Exception as e:
        return None, f"Error de conexión: {e}"


def crear_mapa_isocronas(lat, lng, ors_api_key=None,
                          tiempos=[5, 10, 15], perfil="foot-walking",
                          competidores=None, idioma="es"):
    """
    Mapa con isócronas de caminata/auto desde la ubicación.
    Si no hay API key, muestra círculos de distancia estimada.
    """
    m = folium.Map(
        location=[lat, lng],
        zoom_start=15,
        tiles="CartoDB positron"
    )

    colores_iso = {5: "#22C55E", 10: "#F97316", 15: "#EF4444"}
    labels_iso  = {5: "5 min", 10: "10 min", 15: "15 min"}

    # Tu ubicación
    folium.Marker(
        location=[lat, lng],
        tooltip="⭐ Tu ubicación",
        icon=folium.Icon(color="blue", icon="star", prefix="fa")
    ).add_to(m)

    isocronas_geojson, error = obtener_isocronas(lat, lng, ors_api_key, tiempos, perfil)

    if isocronas_geojson and "features" in isocronas_geojson:
        # Pintar isócronas reales desde ORS
        features = isocronas_geojson["features"]
        features_sorted = sorted(features,
            key=lambda f: f.get("properties", {}).get("value", 0), reverse=True)

        for i, feature in enumerate(features_sorted):
            valor_seg = feature.get("properties", {}).get("value", 0)
            minutos = int(valor_seg / 60)
            color = colores_iso.get(minutos, "#9E9E9E")
            folium.GeoJson(
                feature,
                style_function=lambda x, c=color: {
                    "fillColor": c, "color": c,
                    "weight": 2, "fillOpacity": 0.15, "opacity": 0.8
                },
                tooltip=f"Accesible en {minutos} min caminando"
            ).add_to(m)
        interp = _interpretar_isocronas(isocronas_geojson, competidores, perfil)
        fuente = "OpenRouteService API"
    else:
        # Fallback: círculos de distancia aproximada
        # 5 min caminando ≈ 400m, 10 min ≈ 800m, 15 min ≈ 1200m
        distancias = {5: 400, 10: 800, 15: 1200}
        for mins, metros in sorted(distancias.items(), reverse=True):
            color = colores_iso.get(mins, "#9E9E9E")
            folium.Circle(
                location=[lat, lng],
                radius=metros,
                color=color, weight=2,
                fill=True, fill_color=color, fill_opacity=0.10,
                tooltip=f"~{mins} min caminando ({metros}m radio aprox.)"
            ).add_to(m)
        fuente = "Estimación por distancia (configura ORS_API_KEY para isócronas reales)"
        interp = (f"⚠️ Isócronas estimadas por distancia. "
                  f"Verde: ~5 min a pie (400m) · Naranja: ~10 min (800m) · Rojo: ~15 min (1.2km). "
                  f"Para isócronas reales por red vial, configura ORS_API_KEY en tu .env (gratuito en openrouteservice.org).")

    # Competidores encima
    for comp in (competidores or [])[:15]:
        loc = comp.get('location', {})
        c_lat = loc.get('latitude')
        c_lng = loc.get('longitude')
        if not c_lat or not c_lng: continue
        nombre = comp.get('displayName', {}).get('text', 'N/A')
        rating = comp.get('rating', 0)
        hex_col, _, desc = color_por_rating(rating)
        folium.CircleMarker(
            location=[c_lat, c_lng], radius=7,
            color=hex_col, fill=True, fill_color=hex_col, fill_opacity=0.8,
            tooltip=f"{nombre} — {desc}"
        ).add_to(m)

    # Leyenda
    perfil_label = {"foot-walking": "caminata", "driving-car": "auto",
                    "cycling-regular": "bicicleta"}.get(perfil, perfil)
    leyenda_html = f"""
    <div style='position:fixed; bottom:20px; left:20px; z-index:9999;
         background:white; padding:10px 14px; border-radius:8px;
         box-shadow:0 2px 8px rgba(0,0,0,0.15); font-family:sans-serif; font-size:12px;'>
        <b style='color:#0047AB;'>Isócronas ({perfil_label})</b><br>
        <span style='color:#22C55E;'>●</span> 5 min<br>
        <span style='color:#F97316;'>●</span> 10 min<br>
        <span style='color:#EF4444;'>●</span> 15 min<br>
        <small style='color:#999;'>{fuente}</small>
    </div>"""
    m.get_root().html.add_child(folium.Element(leyenda_html))

    return m, interp


def _interpretar_isocronas(geojson, competidores, perfil):
    perfil_label = {"foot-walking": "caminata", "driving-car": "auto",
                    "cycling-regular": "bicicleta"}.get(perfil, perfil)
    n_comp = len([c for c in (competidores or []) if c.get('location',{}).get('latitude')])
    return (f"Las isócronas muestran el área de influencia real por {perfil_label} desde tu ubicación. "
            f"Todo cliente dentro de la zona verde (5 min) es tu mercado primario más accesible. "
            f"Se detectaron {n_comp} competidores en el radio, algunos dentro de tu zona de influencia primaria.")


# ─────────────────────────────────────────────────────────────────
# 4. MAPA DE CANIBALIZACIÓN
# Detecta competidores que se solapan con tu área de influencia
# ─────────────────────────────────────────────────────────────────

def calcular_distancia_m(lat1, lng1, lat2, lng2):
    """Distancia en metros entre dos puntos (Haversine)"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def crear_mapa_canibalizacion(lat, lng, competidores,
                               radio_canibalizacion=500, idioma="es"):
    """
    Mapa que identifica zonas de canibalización:
    - Radio rojo: zona donde hay solapamiento fuerte con competidores (≤200m)
    - Radio naranja: solapamiento parcial (200-350m)
    - Radio verde: zona propia sin solapamiento significativo
    """
    m = folium.Map(
        location=[lat, lng],
        zoom_start=16,
        tiles="CartoDB positron"
    )

    # Clasificar competidores por distancia
    muy_cercanos   = []  # ≤150m — canibalización crítica
    cercanos       = []  # 151-300m — canibalización media
    en_radio       = []  # 301-500m — competencia normal

    for comp in (competidores or []):
        loc = comp.get('location', {})
        c_lat = loc.get('latitude')
        c_lng = loc.get('longitude')
        if not c_lat or not c_lng: continue
        dist = calcular_distancia_m(lat, lng, c_lat, c_lng)
        comp['_distancia_m'] = int(dist)
        if dist <= 150:      muy_cercanos.append(comp)
        elif dist <= 300:    cercanos.append(comp)
        elif dist <= 500:    en_radio.append(comp)

    # Círculos de zona
    folium.Circle([lat, lng], radius=150, color="#EF4444", weight=2.5,
                  fill=True, fill_color="#EF4444", fill_opacity=0.12,
                  tooltip="⚠️ Zona crítica: canibalización alta (≤150m)").add_to(m)
    folium.Circle([lat, lng], radius=300, color="#F97316", weight=1.5,
                  fill=True, fill_color="#F97316", fill_opacity=0.07,
                  tooltip="🟠 Zona media: canibalización parcial (150-300m)").add_to(m)
    folium.Circle([lat, lng], radius=500, color="#22C55E", weight=1,
                  fill=True, fill_color="#22C55E", fill_opacity=0.05,
                  tooltip="🟢 Zona externa: competencia normal (300-500m)").add_to(m)

    # Tu ubicación
    folium.Marker(
        location=[lat, lng],
        tooltip="⭐ Tu ubicación propuesta",
        icon=folium.Icon(color="blue", icon="star", prefix="fa")
    ).add_to(m)

    # Competidores con indicador de riesgo de canibalización
    for comp, color_zona, label_zona in [
        (muy_cercanos, "#EF4444", "⚠️ CRÍTICO"),
        (cercanos,     "#F97316", "🟠 MEDIO"),
        (en_radio,     "#22C55E", "🟢 NORMAL"),
    ]:
        for c in comp:
            c_lat = c.get('location',{}).get('latitude')
            c_lng = c.get('location',{}).get('longitude')
            nombre = c.get('displayName',{}).get('text','N/A')
            rating = c.get('rating', 0)
            dist_m = c.get('_distancia_m', 0)
            hex_col, _, _ = color_por_rating(rating)
            popup_html = f"""
            <b>{nombre}</b><br>
            <span style='color:{color_zona};'>{label_zona}</span><br>
            Distancia: <b>{dist_m}m</b><br>
            Rating: {rating or 'N/A'}★<br>
            Reseñas: {c.get('userRatingCount',0):,}"""
            folium.CircleMarker(
                location=[c_lat, c_lng], radius=10,
                color=color_zona, weight=2.5,
                fill=True, fill_color=hex_col, fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=f"{nombre} — {dist_m}m — {label_zona}"
            ).add_to(m)

    # Leyenda
    leyenda_html = f"""
    <div style='position:fixed; bottom:20px; left:20px; z-index:9999;
         background:white; padding:10px 14px; border-radius:8px;
         box-shadow:0 2px 8px rgba(0,0,0,0.15); font-family:sans-serif; font-size:12px;'>
        <b style='color:#0047AB;'>Riesgo de Canibalización</b><br>
        <span style='color:#EF4444;'>●</span> Crítico ≤150m ({len(muy_cercanos)})<br>
        <span style='color:#F97316;'>●</span> Medio 150-300m ({len(cercanos)})<br>
        <span style='color:#22C55E;'>●</span> Normal 300-500m ({len(en_radio)})
    </div>"""
    m.get_root().html.add_child(folium.Element(leyenda_html))

    # Interpretación
    interp = _interpretar_canibalizacion(muy_cercanos, cercanos, en_radio)
    return m, interp, {
        "muy_cercanos": muy_cercanos,
        "cercanos": cercanos,
        "en_radio": en_radio
    }


def _interpretar_canibalizacion(muy_cercanos, cercanos, en_radio):
    n_critico = len(muy_cercanos)
    n_medio   = len(cercanos)
    n_normal  = len(en_radio)
    total = n_critico + n_medio + n_normal

    if n_critico == 0 and n_medio == 0:
        return ("✅ Sin riesgo de canibalización. No hay competidores directos en los primeros 300m. "
                "Tu área de influencia inmediata está libre.")
    elif n_critico >= 3:
        return (f"🔴 Riesgo alto de canibalización: {n_critico} competidores a menos de 150m. "
                f"Comparten prácticamente el mismo flujo peatonal — diferenciación de producto/precio es crítica.")
    elif n_critico >= 1:
        return (f"🟠 Riesgo moderado: {n_critico} competidor(es) muy cercanos (≤150m) y "
                f"{n_medio} en zona media. Evalúa si tu propuesta de valor justifica la proximidad.")
    else:
        return (f"🟡 Canibalización baja: los {n_medio} competidores cercanos están a 150-300m — "
                f"zona de influencia parcialmente compartida pero manejable.")


# ─────────────────────────────────────────────────────────────────
# RENDERIZADOR EN STREAMLIT
# ─────────────────────────────────────────────────────────────────

def render_mapa_con_interpretacion(mapa, interpretacion, altura=420, titulo=""):
    """Renderiza un mapa Folium en Streamlit con texto de interpretación"""
    try:
        from streamlit_folium import st_folium
        if titulo:
            st.markdown(f"**{titulo}**")
        st_folium(mapa, width=700, height=altura, returned_objects=[])
        st.markdown(
            f"<div style='background:#F5F8FF; border-left:3px solid #0047AB; "
            f"padding:8px 12px; border-radius:0 6px 6px 0; font-size:13px; "
            f"color:#333; margin-top:6px;'>{interpretacion}</div>",
            unsafe_allow_html=True
        )
    except ImportError:
        st.warning("Instala `streamlit-folium` para ver mapas interactivos: `pip install streamlit-folium`")
