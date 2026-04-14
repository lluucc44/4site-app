import streamlit as st
import googlemaps
import os
from dotenv import load_dotenv
from anthropic import Anthropic
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import requests
import math
import hashlib
import datetime

load_dotenv()  # Carga el .env local (no afecta Streamlit Cloud)

# Módulos 4SITE — datos enriquecidos
try:
    from modulos_4site import (
        obtener_datos_inegi, clasificar_densidad,
        generar_reporte_trafico, calcular_mercado_potencial,
        generar_forecast, calcular_roi, DIAS_SEMANA
    )
    MODULOS_OK = True
except ImportError:
    MODULOS_OK = False

try:
    from graficas_4site import (
        grafica_score_gauge, grafica_desglose_score,
        grafica_trafico_horario, grafica_trafico_semanal,
        grafica_forecast, grafica_mercado_donut,
        grafica_roi_dashboard, grafica_demografia,
        grafica_dashboard_premium, grafica_comparativa
    )
    GRAFICAS_OK = True
except ImportError:
    GRAFICAS_OK = False

try:
    from mapas_4site import (
        crear_mapa_competidores, crear_heatmap_competencia,
        crear_mapa_isocronas, crear_mapa_canibalizacion,
        render_mapa_con_interpretacion
    )
    MAPAS_OK = True
except ImportError:
    MAPAS_OK = False

# ORS API key para isócronas (opcional — gratuito en openrouteservice.org)
try:
    ORS_API_KEY = st.secrets.get("ORS_API_KEY", None)
except:
    ORS_API_KEY = os.getenv("ORS_API_KEY", None)

# ============================================
# CONFIGURACIÓN
# ============================================

st.set_page_config(
    page_title="4SITE - Location Analysis",
    page_icon="📍",
    layout="wide"
)

GA_MEASUREMENT_ID = "G-WW1XFBQ1PN"
ga_script = f"""
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA_MEASUREMENT_ID}');
</script>
"""
st.markdown(ga_script, unsafe_allow_html=True)

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    CLAUDE_API_KEY = st.secrets["CLAUDE_API_KEY"]
    CODIGOS_BASIC  = set(st.secrets.get("CODIGOS_BASIC", "").split(","))
    CODIGOS_PRO    = set(st.secrets.get("CODIGOS_PRO", "").split(","))
    CODIGOS_PREMIUM= set(st.secrets.get("CODIGOS_PREMIUM", "").split(","))
except:
    GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY", "")
    CLAUDE_API_KEY  = os.getenv("CLAUDE_API_KEY", "")
    # Limpiar espacios y convertir a mayúsculas para evitar errores de formato
    def _leer_codigos(var, default):
        raw = os.getenv(var, default)
        return set(c.strip().upper() for c in raw.split(",") if c.strip())
    CODIGOS_BASIC   = _leer_codigos("CODIGOS_BASIC",   "BASIC-TEST")
    CODIGOS_PRO     = _leer_codigos("CODIGOS_PRO",     "PRO-TEST")
    CODIGOS_PREMIUM = _leer_codigos("CODIGOS_PREMIUM", "PREM-TEST")

gmaps  = googlemaps.Client(key=GOOGLE_API_KEY)
claude = Anthropic(api_key=CLAUDE_API_KEY)

# ============================================
# SISTEMA DE TIERS
# ============================================

TIERS = {
    "free": {
        "nombre": "Gratis",
        "precio": "$0",
        "color": "#9E9E9E",
        "competidores_mostrados": 3,   # filas en tabla
        "top_negocios": 3,              # en modo recomendador
        "muestra_demografia": False,
        "muestra_badges": False,
        "muestra_score_desglose": False,
        "muestra_fotos_comp": False,
        "muestra_mapa_comp": False,
        "muestra_forecast": False,
        "muestra_mercado": False,
        "muestra_roi": False,
        "muestra_comparativa": False,
        "pdf_paginas": "Análisis básico",
        "watermark": True,
    },
    "basic": {
        "nombre": "Básico",
        "precio": "$99 MXN",
        "color": "#0047AB",
        "competidores_mostrados": 10,
        "top_negocios": 5,
        "muestra_demografia": True,
        "muestra_badges": True,
        "muestra_score_desglose": True,
        "muestra_fotos_comp": False,    # Fase 2
        "muestra_mapa_comp": False,     # Fase 2
        "muestra_forecast": False,
        "muestra_mercado": False,
        "muestra_roi": False,
        "muestra_comparativa": False,
        "pdf_paginas": "Análisis completo",
        "watermark": False,
    },
    "pro": {
        "nombre": "PRO",
        "precio": "$299 MXN",
        "color": "#00D4D4",
        "competidores_mostrados": 20,
        "top_negocios": 10,
        "muestra_demografia": True,
        "muestra_badges": True,
        "muestra_score_desglose": True,
        "muestra_fotos_comp": True,     # Fase 2
        "muestra_mapa_comp": True,      # Fase 2
        "muestra_forecast": True,       # Fase 2
        "muestra_mercado": True,        # Fase 2
        "muestra_roi": False,
        "muestra_comparativa": False,
        "pdf_paginas": "Análisis PRO",
        "watermark": False,
    },
    "premium": {
        "nombre": "PREMIUM",
        "precio": "$999 MXN",
        "color": "#FFD700",
        "competidores_mostrados": 20,
        "top_negocios": 15,
        "muestra_demografia": True,
        "muestra_badges": True,
        "muestra_score_desglose": True,
        "muestra_fotos_comp": True,
        "muestra_mapa_comp": True,
        "muestra_forecast": True,
        "muestra_mercado": True,
        "muestra_roi": True,            # Fase 3
        "muestra_comparativa": True,    # Fase 3
        "pdf_paginas": "Análisis PREMIUM",
        "watermark": False,
    }
}

# Archivo de registro de códigos usados
ARCHIVO_USADOS = os.path.join(os.path.dirname(__file__), "codigos_usados.txt")

def _cargar_codigos_usados():
    """Carga la lista de códigos ya utilizados"""
    try:
        if os.path.exists(ARCHIVO_USADOS):
            with open(ARCHIVO_USADOS, 'r') as f:
                return set(line.strip().upper() for line in f if line.strip())
    except:
        pass
    return set()

def _marcar_codigo_usado(codigo):
    """Registra un código como utilizado"""
    try:
        with open(ARCHIVO_USADOS, 'a') as f:
            f.write(f"{codigo.strip().upper()}\n")
    except:
        pass  # En Streamlit Cloud usar session_state como fallback

def codigo_ya_usado(codigo):
    """Verifica si un código ya fue utilizado"""
    # Primero verificar en session_state (misma sesión)
    usados_sesion = st.session_state.get("codigos_usados_sesion", set())
    if codigo.upper() in usados_sesion:
        return True
    # Luego verificar en archivo persistente
    usados = _cargar_codigos_usados()
    return codigo.upper() in usados

def validar_codigo(codigo_ingresado):
    """
    Valida código y retorna el tier correspondiente.
    Códigos de prueba (TEST) nunca se marcan como usados.
    """
    codigo = codigo_ingresado.strip().upper()
    if not codigo:
        return "free"

    # Códigos de prueba — nunca caducan
    es_test = codigo.endswith("-TEST") or codigo == "TEST"

    # Verificar si ya fue usado (solo para códigos reales)
    if not es_test and codigo_ya_usado(codigo):
        return "usado"  # Código válido pero ya utilizado

    if codigo in CODIGOS_PREMIUM:
        return "premium"
    if codigo in CODIGOS_PRO:
        return "pro"
    if codigo in CODIGOS_BASIC:
        return "basic"
    return None  # Código inválido

def activar_codigo(codigo):
    """Marca el código como activo en la sesión y lo registra como usado"""
    codigo = codigo.strip().upper()
    es_test = codigo.endswith("-TEST") or codigo == "TEST"

    # Guardar en session_state
    if "codigos_usados_sesion" not in st.session_state:
        st.session_state.codigos_usados_sesion = set()
    st.session_state.codigos_usados_sesion.add(codigo)

    # Registrar en archivo solo para códigos reales
    if not es_test:
        _marcar_codigo_usado(codigo)

# ============================================
# TIPOS DE NEGOCIO
# ============================================

TIPOS_NEGOCIO = {
    "cafe_premium":       {"nombre": "☕ Cafetería Premium/Specialty",   "keywords": ["cafe","coffee","specialty","cafetería"],               "inversion_min": 300000,  "inversion_max": 600000,  "competencia_optima": 2, "descripcion": "Café de especialidad, third wave, ambiente trendy"},
    "cafe_casual":        {"nombre": "☕ Cafetería Casual/Cadena",        "keywords": ["cafe","coffee","starbucks","italian coffee"],          "inversion_min": 400000,  "inversion_max": 800000,  "competencia_optima": 3, "descripcion": "Café estilo cadena, servicio rápido"},
    "restaurante_casual": {"nombre": "🍕 Restaurante Casual",             "keywords": ["restaurant","restaurante","comida","food"],            "inversion_min": 500000,  "inversion_max": 1000000, "competencia_optima": 4, "descripcion": "Restaurante familiar, menú variado"},
    "restaurante_fino":   {"nombre": "🍽️ Restaurante Fino/Gourmet",      "keywords": ["restaurant","fine dining","gourmet"],                  "inversion_min": 1000000, "inversion_max": 3000000, "competencia_optima": 1, "descripcion": "Alta cocina, experiencia premium"},
    "comida_rapida":      {"nombre": "🌮 Comida Rápida/Fast Food",        "keywords": ["fast food","taco","burger","torta","comida rápida"],   "inversion_min": 200000,  "inversion_max": 500000,  "competencia_optima": 5, "descripcion": "Servicio rápido, alto volumen"},
    "gimnasio_boutique":  {"nombre": "🏋️ Gimnasio Boutique/Crossfit",    "keywords": ["gym","gimnasio","crossfit","fitness boutique"],        "inversion_min": 800000,  "inversion_max": 1500000, "competencia_optima": 1, "descripcion": "Fitness especializado, clases grupales"},
    "gimnasio_regular":   {"nombre": "🏋️ Gimnasio Regular/Cadena",       "keywords": ["gym","gimnasio","fitness","sportium"],                 "inversion_min": 1500000, "inversion_max": 3000000, "competencia_optima": 2, "descripcion": "Gym completo, equipamiento variado"},
    "farmacia":           {"nombre": "💊 Farmacia",                        "keywords": ["pharmacy","farmacia","drogueria"],                     "inversion_min": 400000,  "inversion_max": 800000,  "competencia_optima": 2, "descripcion": "Venta de medicamentos y productos de salud"},
    "tienda_conveniencia":{"nombre": "🏪 Tienda de Conveniencia",          "keywords": ["convenience store","oxxo","7-eleven","minisuper"],     "inversion_min": 300000,  "inversion_max": 600000,  "competencia_optima": 2, "descripcion": "Productos básicos 24/7"},
    "panaderia":          {"nombre": "🥖 Panadería/Repostería",            "keywords": ["bakery","panaderia","pastry","reposteria"],            "inversion_min": 250000,  "inversion_max": 500000,  "competencia_optima": 3, "descripcion": "Pan artesanal, pasteles, café"},
    "bar":                {"nombre": "🍺 Bar/Cantina",                     "keywords": ["bar","pub","cantina","cerveceria"],                    "inversion_min": 600000,  "inversion_max": 1200000, "competencia_optima": 3, "descripcion": "Bebidas alcohólicas, ambiente social"},
    "yoga_wellness":      {"nombre": "🧘 Yoga/Wellness Studio",            "keywords": ["yoga","wellness","spa","pilates"],                     "inversion_min": 400000,  "inversion_max": 800000,  "competencia_optima": 1, "descripcion": "Clases de yoga, meditación, bienestar"},
    "guarderia":          {"nombre": "👶 Guardería/Kinder",                "keywords": ["daycare","guarderia","kinder","preescolar"],           "inversion_min": 500000,  "inversion_max": 1000000, "competencia_optima": 2, "descripcion": "Cuidado infantil, educación temprana"},
    "libreria":           {"nombre": "📚 Librería/Papelería",              "keywords": ["bookstore","libreria","papeleria","stationery"],       "inversion_min": 300000,  "inversion_max": 600000,  "competencia_optima": 2, "descripcion": "Libros, útiles escolares, regalos"},
    "servicios":          {"nombre": "💇 Servicios (Peluquería/Tintorería)","keywords": ["salon","peluqueria","barberia","tintoreria"],         "inversion_min": 200000,  "inversion_max": 400000,  "competencia_optima": 3, "descripcion": "Servicios personales del día a día"},
}

TYPE_MAPPING = {
    "cafe_premium":       ["cafe", "restaurant"],
    "cafe_casual":        ["cafe", "restaurant"],
    "restaurante_casual": ["restaurant", "meal_delivery", "meal_takeaway"],
    "restaurante_fino":   ["restaurant"],
    "comida_rapida":      ["restaurant", "meal_takeaway"],
    "gimnasio_boutique":  ["gym"],
    "gimnasio_regular":   ["gym", "sports_complex"],
    "farmacia":           ["pharmacy", "drugstore"],
    "tienda_conveniencia":["convenience_store", "supermarket"],
    "panaderia":          ["bakery", "cafe", "restaurant"],
    "bar":                ["bar", "night_club"],
    "yoga_wellness":      ["gym", "spa", "beauty_salon"],
    "guarderia":          ["school", "primary_school"],
    "libreria":           ["book_store"],
    "servicios":          ["beauty_salon", "hair_care", "laundry", "spa"],
}

# ============================================
# DICCIONARIO BILINGÜE
# ============================================

TEXTOS = {
    "es": {
        "titulo": "4SITE",
        "subtitulo": "Don't guess. Foresee.",
        "selector_idioma": "Idioma / Language",
        "input_ubicacion": "📍 Ingresa la ubicación que quieres analizar",
        "placeholder_direccion": "Ej: Av. Insurgentes Sur 1458, CDMX",
        "boton_analizar": "🔍 Analizar Ubicación",
        "modo_analisis": "🎯 ¿Qué quieres hacer?",
        "modo_validar": "Validar mi idea de negocio",
        "modo_recomendar": "Descubrir qué negocio es mejor",
        "selecciona_tipo": "Selecciona el tipo de negocio:",
        "titulo_analisis": "📊 Análisis de Ubicación",
        "score_viabilidad": "Score de Viabilidad",
        "resumen": "Resumen Ejecutivo",
        "competencia_titulo": "Competencia Cercana (500m)",
        "tabla_nombre": "Nombre",
        "tabla_rating": "Rating",
        "tabla_reseñas": "Reseñas",
        "descargar_pdf": "📄 Descargar Reporte PDF",
        "top_recomendaciones": "🎯 TOP NEGOCIOS RECOMENDADOS",
        "mejor_opcion": "⭐ MEJOR OPCIÓN",
        "inversion_estimada": "💰 Inversión estimada",
        "evitar": "❌ Evitar estos negocios",
        "watermark": "Reporte Gratis · 4SITE · Actualiza para análisis completo",
        "ingresa_codigo": "🔑 ¿Tienes un código de acceso?",
        "placeholder_codigo": "Ej: BASIC-ABC123",
        "validar_codigo": "Aplicar código",
        "codigo_invalido": "❌ Código inválido. Verifica e intenta de nuevo.",
        "codigo_valido": "✅ Código válido —",
        "sin_codigo": "Continuar gratis",
        "tier_activo": "Plan activo:",
        "desglose_score": "📊 Desglose del Score",
        "densidad_comp": "Densidad competencia",
        "calidad_comp": "Calidad competencia",
        "consolidacion": "Consolidación mercado",
        "demografía": "📍 Datos del Área (500m)",
        "poblacion": "Población estimada",
        "nse": "NSE Predominante",
        "densidad_hab": "Densidad",
        "datos_estimados": "💡 Datos estimados basados en la zona.",
        "cta_titulo": "🚀 ¿Quieres el análisis completo?",
        "cta_intro": "Upgrades disponibles:",
        "footer_derechos": "© 2026 4SITE - Todos los derechos reservados",
        "footer_contacto": "hola@4site.mx",
        "coming_soon": "🔜 Próximamente",
        "pro_badge": "PRO",
        "premium_badge": "PREMIUM",
    },
    "en": {
        "titulo": "4SITE",
        "subtitulo": "Don't guess. Foresee.",
        "selector_idioma": "Language / Idioma",
        "input_ubicacion": "📍 Enter the location you want to analyze",
        "placeholder_direccion": "Ex: 1458 Insurgentes Sur Ave, Mexico City",
        "boton_analizar": "🔍 Analyze Location",
        "modo_analisis": "🎯 What do you want to do?",
        "modo_validar": "Validate my business idea",
        "modo_recomendar": "Discover which business is best",
        "selecciona_tipo": "Select business type:",
        "titulo_analisis": "📊 Location Analysis",
        "score_viabilidad": "Viability Score",
        "resumen": "Executive Summary",
        "competencia_titulo": "Nearby Competition (500m)",
        "tabla_nombre": "Name",
        "tabla_rating": "Rating",
        "tabla_reseñas": "Reviews",
        "descargar_pdf": "📄 Download PDF Report",
        "top_recomendaciones": "🎯 TOP RECOMMENDED BUSINESSES",
        "mejor_opcion": "⭐ BEST OPTION",
        "inversion_estimada": "💰 Estimated investment",
        "evitar": "❌ Avoid these businesses",
        "watermark": "Free Report · 4SITE · Upgrade for full analysis",
        "ingresa_codigo": "🔑 Do you have an access code?",
        "placeholder_codigo": "Ex: BASIC-ABC123",
        "validar_codigo": "Apply code",
        "codigo_invalido": "❌ Invalid code. Check and try again.",
        "codigo_valido": "✅ Valid code —",
        "sin_codigo": "Continue for free",
        "tier_activo": "Active plan:",
        "desglose_score": "📊 Score Breakdown",
        "densidad_comp": "Competition density",
        "calidad_comp": "Competition quality",
        "consolidacion": "Market consolidation",
        "demografía": "📍 Area Data (500m)",
        "poblacion": "Estimated population",
        "nse": "Predominant NSE",
        "densidad_hab": "Density",
        "datos_estimados": "💡 Estimated data based on the area.",
        "cta_titulo": "🚀 Want the complete analysis?",
        "cta_intro": "Available upgrades:",
        "footer_derechos": "© 2026 4SITE - All rights reserved",
        "footer_contacto": "hello@4site.mx",
        "coming_soon": "🔜 Coming soon",
        "pro_badge": "PRO",
        "premium_badge": "PREMIUM",
    }
}

# ============================================
# FUNCIONES AUXILIARES - GEOCODING
# ============================================

def geocodificar_direccion(direccion):
    try:
        result = gmaps.geocode(direccion)
        if result:
            loc = result[0]['geometry']['location']
            return loc['lat'], loc['lng']
    except Exception as e:
        st.error(f"Error al geocodificar: {e}")
    return None, None

def geocodificar_inversa(lat, lng):
    try:
        result = gmaps.reverse_geocode((lat, lng))
        if result:
            return result[0]['formatted_address']
    except:
        pass
    return f"{lat:.6f}, {lng:.6f}"

# ============================================
# FUNCIONES DE CONTEXTO Y DEMOGRAFÍA
# ============================================

def detectar_contexto_ubicacion(lat, lng, direccion):
    contexto = {"tipo_zona": "residencial", "pois_cercanos": [], "trafico": "medio", "badges": []}
    dl = direccion.lower()

    avenidas = ["calzada","autopista","periférico","circuito","anillo","viaducto","eje","insurgentes","reforma","constituyentes"]
    if any(av in dl for av in avenidas):
        contexto.update({"tipo_zona": "paso", "trafico": "alto"})
        contexto["badges"].append("🚗 Alto tráfico vehicular")
    elif "calle" in dl or "privada" in dl:
        contexto.update({"tipo_zona": "residencial", "trafico": "bajo"})
    elif "avenida" in dl or "av." in dl:
        contexto.update({"tipo_zona": "comercial", "trafico": "medio"})

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY,
               "X-Goog-FieldMask": "places.displayName,places.types"}
    data = {
        "includedTypes": ["gas_station","shopping_mall","hospital","school","university","transit_station","park"],
        "maxResultCount": 20,
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 500.0}}
    }
    try:
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 200:
            for place in resp.json().get('places', []):
                tipos = place.get('types', [])
                nombre = place.get('displayName', {}).get('text', '')
                if 'gas_station' in tipos:
                    contexto["pois_cercanos"].append({"tipo": "gasolinera", "nombre": nombre})
                    contexto["badges"].append("⛽ Gasolinera cercana")
                    contexto["tipo_zona"] = "paso"
                elif 'shopping_mall' in tipos:
                    contexto["pois_cercanos"].append({"tipo": "plaza", "nombre": nombre})
                    contexto["badges"].append("🏬 Plaza comercial")
                    contexto["tipo_zona"] = "comercial"
                elif 'hospital' in tipos:
                    contexto["pois_cercanos"].append({"tipo": "hospital", "nombre": nombre})
                    contexto["badges"].append("🏥 Hospital cercano")
                elif 'school' in tipos or 'university' in tipos:
                    contexto["pois_cercanos"].append({"tipo": "escuela", "nombre": nombre})
                    contexto["badges"].append("🎓 Escuela/Universidad")
                elif 'transit_station' in tipos:
                    contexto["pois_cercanos"].append({"tipo": "transporte", "nombre": nombre})
                    contexto["badges"].append("🚌 Transporte público")
    except:
        pass
    contexto["badges"] = list(set(contexto["badges"]))
    return contexto


def obtener_demografia(lat, lng, direccion=""):
    """Wrapper — usa INEGI Engine si está disponible, fallback si no"""
    if MODULOS_OK and direccion:
        try:
            return obtener_datos_inegi(lat, lng, direccion, gmaps)
        except:
            pass
    # Fallback básico
    dem = {
        "poblacion_estimada": 0, "densidad_hab_km2": 8000,
        "nse_predominante": "C", "ingreso_promedio_mensual": 15000,
        "distribucion_edad": {"0-17": 25, "18-35": 35, "36-55": 25, "56+": 15},
        "viviendas_habitadas": 0, "gasto_promedio_mensual": 12000,
        "ingreso_actual": 15000, "gasto_actual": 12000,
        "poblacion_actual": 0, "viviendas_actual": 0,
        "densidad_actual": 8000, "personas_manzana": 80,
        "tasa_crecimiento_pct": 0.55, "zona_detectada": "default",
        "fuente": "Estimación basada en zona",
    }
    try:
        result = gmaps.reverse_geocode((lat, lng))
        if result:
            for comp in result[0].get('address_components', []):
                tipos = comp.get('types', [])
                name = comp.get('long_name', '').lower()
                if 'locality' in tipos or 'administrative_area_level_1' in tipos:
                    if any(x in name for x in ['polanco','condesa','roma','santa fe','lomas']):
                        dem.update({"nse_predominante": "A/B", "ingreso_promedio_mensual": 35000, "densidad_hab_km2": 15000})
                    elif 'ciudad de méxico' in name or 'cdmx' in name:
                        dem.update({"nse_predominante": "C+", "ingreso_promedio_mensual": 18000, "densidad_hab_km2": 12000})
                    elif any(x in name for x in ['guadalajara','monterrey','zapopan','san pedro']):
                        dem.update({"nse_predominante": "B/C+", "ingreso_promedio_mensual": 20000, "densidad_hab_km2": 10000})
                    elif any(x in name for x in ['querétaro','puebla','león','mérida']):
                        dem.update({"nse_predominante": "C", "ingreso_promedio_mensual": 15000, "densidad_hab_km2": 8000})
                    elif any(x in name for x in ['estado de méxico','edomex','toluca']):
                        dem.update({"nse_predominante": "C/D+", "ingreso_promedio_mensual": 12000, "densidad_hab_km2": 9000})
    except:
        pass
    area_km2 = 0.785
    dem["poblacion_estimada"]  = int(dem["densidad_hab_km2"] * area_km2)
    dem["poblacion_actual"]    = dem["poblacion_estimada"]
    dem["viviendas_habitadas"] = int(dem["poblacion_estimada"] / 3.5)
    dem["viviendas_actual"]    = dem["viviendas_habitadas"]
    dem["densidad_actual"]     = dem["densidad_hab_km2"]
    dem["personas_manzana"]    = int(dem["densidad_hab_km2"] * 0.01)
    dem["ingreso_actual"]      = dem["ingreso_promedio_mensual"]
    dem["gasto_actual"]        = int(dem["ingreso_promedio_mensual"] * 0.8)
    dem["gasto_promedio_mensual"] = dem["gasto_actual"]
    return dem


def formatear_densidad(densidad_hab_km2):
    personas_manzana = int(densidad_hab_km2 * 0.01)
    if densidad_hab_km2 < 2000:
        return {"clasificacion": "Baja 📉", "personas_manzana": personas_manzana, "descripcion": "Zona suburbana o de baja densidad"}
    elif densidad_hab_km2 < 8000:
        return {"clasificacion": "Media 📊", "personas_manzana": personas_manzana, "descripcion": "Zona residencial típica"}
    elif densidad_hab_km2 < 15000:
        return {"clasificacion": "Alta 📈", "personas_manzana": personas_manzana, "descripcion": "Zona urbana densamente poblada - Ideal para comercio"}
    else:
        return {"clasificacion": "Muy Alta 🔥", "personas_manzana": personas_manzana, "descripcion": "Centro urbano de muy alta densidad"}

# ============================================
# FUNCIONES DE COMPETENCIA Y SCORING
# ============================================

def buscar_competencia_por_tipo(lat, lng, tipo_key):
    tipo = TIPOS_NEGOCIO[tipo_key]
    included_types = TYPE_MAPPING.get(tipo_key, ["restaurant", "cafe", "store"])
    keywords = tipo.get("keywords", [])
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.location,places.primaryTypeDisplayName,places.id,places.types,places.photos"
    }
    data = {
        "includedTypes": included_types,
        "maxResultCount": 20,
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 500.0}}
    }
    try:
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code != 200:
            return []
        places = resp.json().get('places', [])
        filtered = []
        for p in places:
            nombre = p.get('displayName', {}).get('text', '').lower()
            tipos  = p.get('types', [])
            if any(kw.lower() in nombre for kw in keywords) or any(t in included_types for t in tipos):
                filtered.append(p)
        return filtered
    except:
        return []


def buscar_competencia_general(lat, lng):
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.location,places.primaryTypeDisplayName,places.id,places.photos"
    }
    data = {
        "includedTypes": ["restaurant","cafe","bar","gym","pharmacy","store","bakery","book_store"],
        "maxResultCount": 20,
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 500.0}}
    }
    try:
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 200:
            return resp.json().get('places', [])
    except:
        pass
    return []


def calcular_score_competencia(competidores, tipo_key):
    """Score metodológico: densidad 50% + calidad 30% + consolidación 20%"""
    tipo  = TIPOS_NEGOCIO[tipo_key]
    n     = len(competidores)
    optimo = tipo["competencia_optima"]

    # Densidad
    if n == 0:           d = 100
    elif n <= optimo:    d = 85
    elif n <= optimo+2:  d = 65
    elif n <= optimo+4:  d = 45
    else:                d = 25

    # Calidad (ratings)
    ratings = [c.get('rating', 0) for c in competidores if c.get('rating')]
    avg_r = sum(ratings)/len(ratings) if ratings else 0
    if avg_r == 0:       q = 100
    elif avg_r < 3.5:    q = 80
    elif avg_r < 4.0:    q = 60
    elif avg_r < 4.3:    q = 40
    else:                q = 20

    # Consolidación (reseñas)
    reviews = [c.get('userRatingCount', 0) for c in competidores]
    avg_rv = sum(reviews)/len(reviews) if reviews else 0
    if avg_rv == 0:      c_score = 100
    elif avg_rv < 100:   c_score = 80
    elif avg_rv < 500:   c_score = 60
    elif avg_rv < 1500:  c_score = 40
    else:                c_score = 20

    score_final = int(d*0.50 + q*0.30 + c_score*0.20)
    return score_final, {"densidad": int(d), "calidad": int(q), "consolidacion": int(c_score),
                         "num_competidores": n, "rating_promedio": round(avg_r, 1) if avg_r else "N/A",
                         "reseñas_promedio": int(avg_rv) if avg_rv else "N/A"}


def ajustar_score_por_contexto(score_base, tipo_key, contexto):
    score = score_base
    zona  = contexto["tipo_zona"]
    pois  = [p["tipo"] for p in contexto["pois_cercanos"]]
    if "cafe" in tipo_key:
        if zona == "paso" or "gasolinera" in pois: score += 15
        elif zona == "comercial": score += 10
        elif "escuela" in pois:   score += 10
        elif zona == "residencial": score += 5
    elif tipo_key == "comida_rapida":
        if zona == "paso": score += 20
        elif "gasolinera" in pois: score += 15
        elif "escuela" in pois:    score += 10
    elif tipo_key == "restaurante_casual":
        if zona == "comercial" or "plaza" in pois: score += 15
        elif zona == "paso": score += 10
    elif tipo_key == "restaurante_fino":
        if zona == "comercial" or "plaza" in pois: score += 10
        elif zona == "paso": score -= 10
    elif "gimnasio" in tipo_key:
        if zona == "residencial": score += 15
        elif "plaza" in pois:    score += 10
        elif zona == "paso":     score -= 5
    elif tipo_key == "farmacia":
        if "hospital" in pois:   score += 20
        elif zona == "residencial": score += 10
        elif zona == "paso":     score += 5
    elif tipo_key == "bar":
        if zona == "comercial" or "plaza" in pois: score += 10
        elif zona == "paso":        score -= 15
        elif zona == "residencial": score -= 10
    elif tipo_key == "tienda_conveniencia":
        if zona == "paso" or "gasolinera" in pois: score += 15
        elif zona == "residencial": score += 10
    elif tipo_key == "guarderia":
        if zona == "residencial": score += 15
        elif zona == "comercial": score += 5
        elif zona == "paso":      score -= 10
    return max(0, min(100, int(score)))


def ajustar_score_por_demografia(score_base, tipo_key, dem):
    score = score_base
    nse   = dem["nse_predominante"]
    densidad = dem["densidad_hab_km2"]
    edad_joven = dem["distribucion_edad"]["18-35"]
    edad_ninos = dem["distribucion_edad"]["0-17"]
    if tipo_key in ["cafe_premium","restaurante_fino","gimnasio_boutique","yoga_wellness"]:
        if "A" in nse or "B" in nse: score += 15
        elif "C+" in nse:             score += 5
        elif "D" in nse or "E" in nse: score -= 20
    elif tipo_key in ["comida_rapida","tienda_conveniencia"]:
        if "C" in nse or "D" in nse:  score += 10
        elif "A" in nse or "B" in nse: score -= 5
    if densidad > 12000:
        if tipo_key != "restaurante_fino": score += 10
    elif densidad < 5000:
        score -= 10
    if tipo_key in ["cafe_premium","gimnasio_boutique","bar","comida_rapida"]:
        if edad_joven > 35:  score += 10
        elif edad_joven < 25: score -= 10
    elif tipo_key == "guarderia":
        if edad_ninos > 25:  score += 15
        elif edad_ninos < 15: score -= 15
    return max(0, min(100, int(score)))


def nivel_score(score, idioma="es"):
    if score >= 80:   return ("ALTO", "#4CAF50") if idioma == "es" else ("HIGH", "#4CAF50")
    elif score >= 65: return ("MEDIO-ALTO", "#8BC34A") if idioma == "es" else ("MEDIUM-HIGH", "#8BC34A")
    elif score >= 50: return ("MEDIO", "#FFC107") if idioma == "es" else ("MEDIUM", "#FFC107")
    else:             return ("BAJO", "#F44336") if idioma == "es" else ("LOW", "#F44336")


def recomendar_tipos_negocio(lat, lng, direccion):
    contexto  = detectar_contexto_ubicacion(lat, lng, direccion)
    demografia = obtener_demografia(lat, lng)
    recomendaciones = []
    for tipo_key, tipo_info in TIPOS_NEGOCIO.items():
        comps = buscar_competencia_por_tipo(lat, lng, tipo_key)
        score_base, desglose = calcular_score_competencia(comps, tipo_key)
        score_ctx  = ajustar_score_por_contexto(score_base, tipo_key, contexto)
        score_final = ajustar_score_por_demografia(score_ctx, tipo_key, demografia)
        recomendaciones.append({
            "tipo_key": tipo_key, "nombre": tipo_info["nombre"],
            "score": score_final, "desglose": desglose,
            "num_competidores": len(comps),
            "inversion_min": tipo_info["inversion_min"],
            "inversion_max": tipo_info["inversion_max"],
            "descripcion": tipo_info["descripcion"],
            "competidores": comps,
        })
    recomendaciones.sort(key=lambda x: x["score"], reverse=True)
    return recomendaciones, contexto, demografia

# ============================================
# ANÁLISIS CLAUDE
# ============================================

def generar_analisis_claude(ubicacion, competidores, idioma, modo, tipo_negocio=None, recomendaciones=None):
    if modo == "validar":
        tipo_info = TIPOS_NEGOCIO[tipo_negocio]
        prompt = f"""Eres analista experto en ubicaciones comerciales para {tipo_info['nombre']}.

UBICACIÓN: {ubicacion}
Descripción del negocio: {tipo_info['descripcion']}
Inversión: ${tipo_info['inversion_min']:,}–${tipo_info['inversion_max']:,} MXN

Competencia en 500m ({len(competidores)} negocios similares):
{json.dumps([{'nombre': c.get('displayName',{}).get('text','N/A'), 'rating': c.get('rating','N/A'), 'reviews': c.get('userRatingCount',0)} for c in competidores], indent=2, ensure_ascii=False)}

Responde en {idioma} con este formato EXACTO:
**Resumen:** [2-3 líneas sobre la oportunidad en esta ubicación específica]

**✅ Ventajas:**
- [ventaja 1]
- [ventaja 2]
- [ventaja 3]

**⚠️ Riesgos:**
- [riesgo 1]
- [riesgo 2]
- [riesgo 3]

**🎯 Recomendación:** [TOMAR / RECHAZAR / ANALIZAR MÁS] — [1 línea de justificación]

Sé específico. No inventes datos."""
    else:
        top5 = recomendaciones[:5]
        prompt = f"""Eres analista experto en ubicaciones comerciales.

UBICACIÓN: {ubicacion}

TOP 5 negocios viables (por score):
{json.dumps([{'tipo': r['nombre'], 'score': r['score'], 'competidores': r['num_competidores']} for r in top5], indent=2, ensure_ascii=False)}

Responde en {idioma}:
**Análisis de la zona:**
[2 líneas sobre el perfil comercial de esta ubicación]

**Por qué el #1 lidera:**
[1-2 líneas específicas]

**Oportunidad clave:**
[1 línea de la mayor oportunidad detectada]

No inventes datos demográficos."""

    try:
        msg = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"Error al generar análisis: {e}"

# ============================================
# RECOMENDACIÓN FINAL — Veredicto integrado
# ============================================

def generar_recomendacion_final(
        ubicacion, score, desglose, competidores, demografia,
        contexto, idioma, tier_key, modo,
        tipo_negocio=None, recomendaciones=None,
        trafico_data=None, mercado_data=None,
        forecast_data=None, roi_data=None):
    """
    Genera el Recomendación Final final integrando TODOS los datos disponibles.
    El prompt varía según el tier — más datos = conclusión más precisa.
    """

    # ── Datos base (todos los tiers) ──
    tipo_info = TIPOS_NEGOCIO.get(tipo_negocio, {}) if tipo_negocio else {}
    tipo_nombre = tipo_info.get('nombre', '')

    # En modo recomendar, usar el #1
    if modo == "recomendar" and recomendaciones:
        top1 = recomendaciones[0]
        tipo_nombre   = top1['nombre']
        tipo_negocio  = top1['tipo_key']
        tipo_info     = TIPOS_NEGOCIO.get(tipo_negocio, {})
        competidores  = top1.get('competidores', competidores)

    nivel_txt, _ = nivel_score(score, idioma)
    n_comp        = len(competidores or [])
    ratings       = [c.get('rating',0) for c in (competidores or []) if c.get('rating')]
    avg_rating    = round(sum(ratings)/len(ratings), 1) if ratings else 0
    n_verdes      = sum(1 for r in ratings if r >= 4.3)

    nse           = demografia.get('nse_predominante', 'C') if demografia else 'C'
    ingreso       = demografia.get('ingreso_actual', demografia.get('ingreso_promedio_mensual', 0)) if demografia else 0
    densidad      = demografia.get('densidad_actual', demografia.get('densidad_hab_km2', 0)) if demografia else 0
    pob           = demografia.get('poblacion_actual', demografia.get('poblacion_estimada', 0)) if demografia else 0
    tasa_crec     = demografia.get('tasa_crecimiento_pct', 0) if demografia else 0
    tipo_zona     = contexto.get('tipo_zona', 'mixto') if contexto else 'mixto'
    badges        = contexto.get('badges', []) if contexto else []
    inversion_min = tipo_info.get('inversion_min', 0)
    inversion_max = tipo_info.get('inversion_max', 0)

    # ── Construir contexto de datos según tier ──
    datos_base = f"""
UBICACIÓN: {ubicacion}
TIPO DE NEGOCIO: {tipo_nombre}
INVERSIÓN REQUERIDA: ${inversion_min:,} – ${inversion_max:,} MXN

SCORE DE VIABILIDAD: {score}/100 ({nivel_txt})
- Densidad competencia: {desglose.get('densidad',0)}/100 (50%)
- Calidad competencia: {desglose.get('calidad',0)}/100 (30%)
- Consolidación mercado: {desglose.get('consolidacion',0)}/100 (20%)

COMPETENCIA EN 500m:
- Total competidores: {n_comp}
- Rating promedio: {avg_rating}/5
- Competidores excelentes (≥4.3★): {n_verdes}

DEMOGRAFÍA DEL ÁREA:
- Población estimada: {pob:,} hab
- NSE predominante: {nse}
- Ingreso promedio mensual: ${ingreso:,}
- Densidad urbana: {densidad:,} hab/km²
- Crecimiento anual zona: {tasa_crec:.2f}%
- Tipo de zona: {tipo_zona}
- Características: {', '.join(badges) if badges else 'No detectadas'}"""

    datos_pro = ""
    if trafico_data:
        picos = trafico_data.get('horas_pico', [])
        pico_str = ', '.join([p['hora_str'] for p in picos[:2]]) if picos else 'N/A'
        datos_pro += f"""
TRÁFICO ESTIMADO:
- Nivel general: {trafico_data.get('nivel_general','N/A')}
- Horas pico: {pico_str}
- Mejor día: {trafico_data.get('dia_pico','N/A')}
- Día más bajo: {trafico_data.get('dia_bajo','N/A')}"""

    if mercado_data:
        datos_pro += f"""
MERCADO POTENCIAL:
- Mercado total área/mes: ${mercado_data.get('mercado_total_mensual',0):,}
- Tu captura estimada/mes: ${mercado_data.get('mercado_captura_mensual',0):,}
- Tasa de captura: {mercado_data.get('factor_captura_pct',0):.0f}%
- Clientes/día estimados: {mercado_data.get('clientes_dia_estimados',0)}"""

    if forecast_data:
        esc = forecast_data.get('escenarios', {})
        datos_pro += f"""
FORECAST DE VENTAS (año 1):
- Pesimista: ${esc.get('pesimista',{}).get('total_anual',0):,}
- Base: ${esc.get('base',{}).get('total_anual',0):,}
- Optimista: ${esc.get('optimista',{}).get('total_anual',0):,}"""

    datos_premium = ""
    if roi_data:
        datos_premium += f"""
ROI Y RECUPERACIÓN:
- ROI estimado 12 meses: {roi_data.get('roi_12m_pct',0)}%
- Meses recuperación: {roi_data.get('meses_recuperacion',0)}
- Utilidad mensual estimada: ${roi_data.get('utilidad_mensual_est',0):,}
- Clasificación ROI: {roi_data.get('clasificacion_roi','')}"""

    # ── Prompt según tier ──
    nombre_ub_principal = ubicacion[:60] if ubicacion else "ubicación principal"
    if tier_key in ["pro", "premium"]:
        contexto_datos = datos_base + datos_pro + datos_premium
        instrucciones = f"""Responde en {idioma} con este formato EXACTO. 
IMPORTANTE: Todas las referencias son EXCLUSIVAMENTE sobre la ubicación: "{nombre_ub_principal}"

**✅ RECOMENDACIÓN FINAL — {nombre_ub_principal}**

**Resumen de la oportunidad:**
[3-4 líneas que integren score, competencia, demografía, tráfico y mercado para ESTA ubicación específica]

**✅ Factores a favor:**
- [factor 1 — con dato específico de esta ubicación]
- [factor 2 — con dato específico de esta ubicación]
- [factor 3 — con dato específico de esta ubicación]

**⚠️ Factores de riesgo:**
- [riesgo 1 — con dato específico]
- [riesgo 2 — con dato específico]

**📊 Potencial comercial:**
[2 líneas sobre mercado y ventas estimadas para ESTA ubicación]

**🎯 VEREDICTO: [PROCEDER ✅ / PRECAUCIÓN 🟡 / NO PROCEDER ❌]**
[2-3 líneas de justificación integrando TODOS los datos de esta ubicación]

**Nivel de confianza: [ALTO / MEDIO / BAJO]** — [motivo en 1 línea]"""
    else:
        contexto_datos = datos_base
        instrucciones = f"""Responde en {idioma} con este formato EXACTO.
IMPORTANTE: Todo el análisis es sobre: "{nombre_ub_principal}"

**✅ RECOMENDACIÓN FINAL — {nombre_ub_principal}**

**Resumen de la oportunidad:**
[2-3 líneas sobre el potencial de esta ubicación específica]

**✅ Factores a favor:**
- [factor 1]
- [factor 2]
- [factor 3]

**⚠️ Factores de riesgo:**
- [riesgo 1]
- [riesgo 2]

**🎯 VEREDICTO: [PROCEDER ✅ / PRECAUCIÓN 🟡 / NO PROCEDER ❌]**
[1-2 líneas de justificación basada en los datos disponibles]

*Actualiza al plan {'Básico ($99)' if tier_key == 'free' else 'PRO ($299)'} para incluir tráfico, mercado y forecast en tu recomendación.*"""

    prompt = f"""Eres un analista senior de inteligencia comercial y ubicaciones.
Tu tarea es emitir el Recomendación Final final de una ubicación, integrando TODOS los datos disponibles.
NO inventes datos que no estén en el contexto. Sé directo, preciso y accionable.

DATOS DEL ANÁLISIS:
{contexto_datos}

{instrucciones}"""

    try:
        msg = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"Error al generar diagnóstico: {e}"


# ============================================
# NARRATIVA INTERPRETATIVA POR SECCIÓN (PRO+)
# ============================================

def generar_narrativa_seccion(seccion, datos, tipo_negocio_nombre, idioma="es"):
    """
    Genera 2-3 líneas interpretando los datos de una sección específica
    en el contexto del negocio a validar. Solo se llama para PDFs PRO y PREMIUM.
    """
    prompts_por_seccion = {
        "competencia": f"""Eres analista comercial. En 2-3 líneas concisas, interpreta estos datos de competencia
para un negocio tipo "{tipo_negocio_nombre}":
{json.dumps(datos, ensure_ascii=False, indent=2)}
Explica qué significan estos números para el éxito o riesgo del negocio. 
Sé directo, usa los datos específicos. NO uses bullet points. Responde en {idioma}.""",

        "demografia": f"""Eres analista comercial. En 2-3 líneas concisas, interpreta estos datos demográficos
para un negocio tipo "{tipo_negocio_nombre}":
{json.dumps(datos, ensure_ascii=False, indent=2)}
Explica qué implica este perfil de área para la viabilidad del negocio (NSE, ingreso, densidad, crecimiento).
Sé directo, usa los datos. NO uses bullet points. Responde en {idioma}.""",

        "trafico": f"""Eres analista comercial. En 2-3 líneas concisas, interpreta estos datos de tráfico
para un negocio tipo "{tipo_negocio_nombre}":
{json.dumps(datos, ensure_ascii=False, indent=2)}
Explica qué significan las horas pico y el flujo semanal para la operación del negocio.
Sé directo, usa los datos. NO uses bullet points. Responde en {idioma}.""",

        "mercado": f"""Eres analista comercial. En 2-3 líneas concisas, interpreta estos datos de mercado
para un negocio tipo "{tipo_negocio_nombre}":
{json.dumps(datos, ensure_ascii=False, indent=2)}
Explica qué representa el mercado potencial capturables y los clientes estimados en términos prácticos.
Sé directo, usa los datos. NO uses bullet points. Responde en {idioma}.""",

        "forecast": f"""Eres analista comercial. En 2-3 líneas concisas, interpreta estos datos de forecast
para un negocio tipo "{tipo_negocio_nombre}":
{json.dumps(datos, ensure_ascii=False, indent=2)}
Explica qué significan los 3 escenarios y cuál es el rango realista de ventas esperado.
Sé directo, usa los datos. NO uses bullet points. Responde en {idioma}.""",

        "roi": f"""Eres analista comercial. En 2-3 líneas concisas, interpreta estos datos de ROI
para un negocio tipo "{tipo_negocio_nombre}":
{json.dumps(datos, ensure_ascii=False, indent=2)}
Explica qué significa el retorno estimado y el tiempo de recuperación para la decisión de inversión.
Sé directo, usa los datos. NO uses bullet points. Responde en {idioma}.""",

        "mapa": f"""Eres analista comercial. En 2-3 líneas concisas, interpreta estos datos de competidores
en el mapa para un negocio tipo "{tipo_negocio_nombre}":
{json.dumps(datos, ensure_ascii=False, indent=2)}
Explica qué implica la distribución y calidad de competidores en el radio para el posicionamiento del negocio.
Sé directo, usa los datos. NO uses bullet points. Responde en {idioma}.""",
    }

    prompt = prompts_por_seccion.get(seccion)
    if not prompt:
        return ""

    try:
        msg = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except:
        return ""


def _bloque_narrativa_pdf(narrativa, s):
    """Renderiza el bloque de narrativa interpretativa en el PDF"""
    from reportlab.platypus import Table as RLTable
    from reportlab.lib import colors as rcolors
    if not narrativa:
        return []
    elements = []
    elements.append(Spacer(1, 0.08*inch))
    narr_tbl = RLTable([[narrativa]], colWidths=[5.5*inch])
    narr_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F0F7FF')),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#0047AB44')),
    ]))
    # Texto dentro de la caja
    narr_para = Paragraph(
        f'<font color="#0047AB">💬</font> <i>{narrativa}</i>',
        ParagraphStyle('narr', parent=s["base"]['Normal'],
            fontSize=9, textColor=colors.HexColor('#333333'),
            backColor=colors.HexColor('#F0F7FF'),
            borderPad=8, leading=13)
    )
    elements.append(narr_para)
    elements.append(Spacer(1, 0.08*inch))
    return elements


# ============================================
# MAPA ESTÁTICO
# ============================================

def _render_recomendacion_pdf(story, analisis, s):
    """Renderiza el bloque de Recomendación Final en el PDF con estilo consistente"""
    story.append(Paragraph("✅ Recomendación Final", s["h2"]))
    story.append(Paragraph(
        "Análisis integrado por IA — combina todos los datos del análisis en una conclusión accionable.",
        ParagraphStyle('rec_intro', parent=s["base"]['Normal'],
        fontSize=9, textColor=colors.HexColor('#666666'), spaceAfter=8)))
    for linea in analisis.split('\n'):
        linea = linea.strip()
        if not linea:
            story.append(Spacer(1, 0.04*inch))
        elif any(kw in linea for kw in ['VEREDICTO','PROCEDER ✅','PRECAUCIÓN 🟡','NO PROCEDER ❌','🎯 VEREDICTO']):
            clean = linea.replace('**','')
            v_tbl = Table([[clean]], colWidths=[5.5*inch])
            v_tbl.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#E3F2FD')),
                ('TEXTCOLOR', (0,0),(-1,-1),colors.HexColor('#0047AB')),
                ('FONTNAME',  (0,0),(-1,-1),'Helvetica-Bold'),
                ('FONTSIZE',  (0,0),(-1,-1),12),
                ('TOPPADDING',(0,0),(-1,-1),10),
                ('BOTTOMPADDING',(0,0),(-1,-1),10),
                ('LEFTPADDING',(0,0),(-1,-1),12),
                ('BOX',(0,0),(-1,-1),1.5,colors.HexColor('#0047AB')),
            ]))
            story.append(v_tbl)
            story.append(Spacer(1, 0.08*inch))
        elif 'Nivel de confianza' in linea:
            story.append(Paragraph(linea.replace('**',''), ParagraphStyle('conf_r',
                parent=s["base"]['Normal'], fontSize=9,
                textColor=colors.HexColor('#555'), fontName='Helvetica-Oblique', spaceAfter=4)))
        elif linea.startswith('**') and linea.endswith('**'):
            story.append(Paragraph(linea.replace('**',''), ParagraphStyle('sec_r',
                parent=s["base"]['Normal'], fontSize=11, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#0047AB'), spaceBefore=10, spaceAfter=4)))
        elif linea.startswith('- ') or linea.startswith('• '):
            story.append(Paragraph(f"  {linea}", ParagraphStyle('bul_r',
                parent=s["base"]['Normal'], fontSize=9.5, leftIndent=15, spaceAfter=3)))
        elif '**' in linea:
            import re as _re
            txt = _re.sub(r'\*\*(.+?)\*\*', r'<b></b>', linea)
            story.append(Paragraph(txt, s["normal"]))
        else:
            story.append(Paragraph(linea, s["normal"]))


def generar_mapa_estatico(lat, lng, competidores=None, con_competidores=False):
    """
    Genera mapa estático Google.
    Competidores coloreados: verde=rating>=4.3, naranja=3.5-4.2, rojo=<3.5 / sin rating.
    """
    base = "https://maps.googleapis.com/maps/api/staticmap"

    # Círculo de 500m
    circle_pts = []
    for i in range(0, 360, 10):
        angle = math.radians(i)
        p_lat = lat + (0.0045 * math.cos(angle))
        p_lng = lng + (0.006 * math.sin(angle))
        circle_pts.append(f"{p_lat},{p_lng}")

    params = [
        f"center={lat},{lng}",
        "zoom=16",
        "size=640x480",
        "maptype=roadmap",
        "style=feature:poi|element:labels|visibility:off",  # Quitar POIs para más limpio
        # Tu ubicación — marcador grande rojo con estrella
        f"markers=color:0xFF0000|size:large|label:★|{lat},{lng}",
        f"path=color:0x0047AB99|weight:2|fillcolor:0x0047AB15|{'|'.join(circle_pts)}",
        f"key={GOOGLE_API_KEY}"
    ]

    # Competidores en mapa con colores por rating
    if con_competidores and competidores:
        grupos = {
            "0x22C55E": [],  # verde — rating >= 4.3
            "0xF97316": [],  # naranja — rating 3.5–4.2
            "0xEF4444": [],  # rojo — rating < 3.5 o sin rating
        }
        for comp in competidores[:20]:
            loc = comp.get('location', {})
            c_lat = loc.get('latitude')
            c_lng = loc.get('longitude')
            if not c_lat or not c_lng:
                continue
            rating = comp.get('rating', 0)
            if rating >= 4.3:
                grupos["0x22C55E"].append(f"{c_lat},{c_lng}")
            elif rating >= 3.5:
                grupos["0xF97316"].append(f"{c_lat},{c_lng}")
            else:
                grupos["0xEF4444"].append(f"{c_lat},{c_lng}")

        for hex_color, locs in grupos.items():
            if locs:
                # Google Static Maps acepta múltiples marcadores en un solo param
                locs_str = "|".join(locs)
                params.append(f"markers=color:{hex_color}|size:small|{locs_str}")

    url = f"{base}?" + "&".join(params)
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return BytesIO(resp.content)
    except:
        pass
    return None


def generar_texto_interpretacion_mapa(competidores, contexto, modo_mapa="basico", idioma="es"):
    """Genera texto de interpretación debajo del mapa"""
    n_comp = len(competidores) if competidores else 0

    # Ratings de competidores
    ratings = [c.get('rating', 0) for c in (competidores or []) if c.get('rating')]
    avg_rating = round(sum(ratings)/len(ratings), 1) if ratings else 0
    n_verdes   = sum(1 for r in ratings if r >= 4.3)
    n_naranjas = sum(1 for r in ratings if 3.5 <= r < 4.3)
    n_rojos    = sum(1 for r in ratings if r < 3.5)

    tipo_zona = contexto.get('tipo_zona', 'mixto') if contexto else 'mixto'
    zona_desc = {
        'paso': 'zona de alto tráfico vehicular',
        'comercial': 'zona comercial activa',
        'residencial': 'zona residencial',
        'mixto': 'zona mixta'
    }.get(tipo_zona, 'zona urbana')

    if modo_mapa == "basico":
        return (f"📍 La ubicación analizada (marcador rojo) se encuentra en {zona_desc}. "
                f"El círculo azul representa el radio de análisis de 500 metros. "
                f"Se identificaron {n_comp} negocios similares en este radio.")
    else:
        texto = (f"📍 Mapa de competencia en 500m. Tu ubicación: marcador rojo ★. "
                 f"Competidores: 🟢 {n_verdes} excelentes (≥4.3★) · "
                 f"🟠 {n_naranjas} buenos (3.5-4.2★) · "
                 f"🔴 {n_rojos} débiles o sin datos. ")
        if n_verdes > 3:
            texto += "⚠️ Alta concentración de competidores bien calificados — diferenciación clave."
        elif n_verdes == 0 and n_comp > 0:
            texto += "💡 Ningún competidor destaca con rating alto — oportunidad de posicionarte como el mejor."
        elif n_comp == 0:
            texto += "✅ Sin competidores directos identificados en el radio — mercado sin saturar."
        return texto

# ============================================
# GENERADORES DE PDF POR TIER
# ============================================

def _estilos_pdf():
    styles = getSampleStyleSheet()
    title = ParagraphStyle('4Title', parent=styles['Heading1'], fontSize=28,
                           textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER, spaceAfter=2)
    subtitle = ParagraphStyle('4Sub', parent=styles['Normal'], fontSize=11,
                               textColor=colors.HexColor('#00D4D4'), alignment=TA_CENTER, spaceAfter=20)
    h2 = ParagraphStyle('4H2', parent=styles['Heading2'], fontSize=13,
                         textColor=colors.HexColor('#0047AB'), spaceBefore=14, spaceAfter=6)
    normal = ParagraphStyle('4Normal', parent=styles['Normal'], fontSize=10, spaceAfter=4)
    small  = ParagraphStyle('4Small', parent=styles['Normal'], fontSize=8,
                             textColor=colors.grey, alignment=TA_CENTER)
    watermark = ParagraphStyle('4WM', parent=styles['Normal'], fontSize=9,
                                textColor=colors.HexColor('#AAAAAA'), alignment=TA_CENTER)
    return {"title": title, "subtitle": subtitle, "h2": h2,
            "normal": normal, "small": small, "watermark": watermark, "base": styles}

def _tabla_competidores(competidores, t, n_max, styles):
    """Genera tabla de competidores limitada según tier"""
    data = [[t["tabla_nombre"], t["tabla_rating"], t["tabla_reseñas"]]]
    for comp in competidores[:n_max]:
        nombre  = comp.get('displayName', {}).get('text', 'N/A')[:30]
        rating  = comp.get('rating', 'N/A')
        reviews = comp.get('userRatingCount', 0)
        data.append([nombre, f"{rating}★" if rating != 'N/A' else 'N/A', str(reviews)])
    tbl = Table(data, colWidths=[3.2*inch, 1*inch, 1*inch])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0047AB')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F5F8FF')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5F8FF')]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    return tbl

def _header_pdf(story, s, tier_key, idioma):
    """Header común para todos los PDFs"""
    t = TEXTOS[idioma]
    tier = TIERS[tier_key]
    story.append(Paragraph("4SITE", s["title"]))
    story.append(Paragraph("Don't guess. Foresee.", s["subtitle"]))
    # Badge de tier
    tier_color = tier["color"]
    story.append(Paragraph(
        f"<font color='{tier_color}'><b>[ {tier['nombre'].upper()} — {tier['precio']} ]</b></font>",
        ParagraphStyle('badge', parent=s["base"]['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=10)
    ))
    story.append(Paragraph(f"{datetime.datetime.now().strftime('%d/%m/%Y')}", s["small"]))
    story.append(Spacer(1, 0.2*inch))

def _score_block(story, score, desglose, tier_key, t, s, idioma):
    """Bloque de score con desglose condicional"""
    nivel, color = nivel_score(score, idioma)
    score_data = [[f"{score}/100", nivel, TIERS[tier_key]['pdf_paginas']]]
    tbl = Table(score_data, colWidths=[1.5*inch, 1.8*inch, 2*inch])
    tbl.setStyle(TableStyle([
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE',   (0,0), (0,0), 28),
        ('FONTSIZE',   (1,0), (-1,-1), 11),
        ('FONTNAME',   (0,0), (-1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR',  (0,0), (0,0), colors.HexColor(color)),
        ('TEXTCOLOR',  (1,0), (1,0), colors.HexColor(color)),
        ('TEXTCOLOR',  (2,0), (2,0), colors.HexColor('#0047AB')),
        ('BOX',        (0,0), (-1,-1), 1.5, colors.HexColor(color)),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.15*inch))
    
    # Desglose solo en BASIC+
    if TIERS[tier_key]["muestra_score_desglose"] and desglose:
        d_data = [
            [t["densidad_comp"], f"{desglose['densidad']}/100", "50%"],
            [t["calidad_comp"],  f"{desglose['calidad']}/100",  "30%"],
            [t["consolidacion"], f"{desglose['consolidacion']}/100", "20%"],
        ]
        d_tbl = Table(d_data, colWidths=[2.5*inch, 1*inch, 0.8*inch])
        d_tbl.setStyle(TableStyle([
            ('FONTSIZE',  (0,0), (-1,-1), 8),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#555555')),
            ('TEXTCOLOR', (1,0), (1,-1), colors.HexColor('#0047AB')),
            ('FONTNAME',  (1,0), (1,-1), 'Helvetica-Bold'),
            ('GRID',      (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(Paragraph(t["desglose_score"], s["h2"]))
        story.append(d_tbl)
        story.append(Spacer(1, 0.15*inch))

def _cta_block(story, tier_key, t, s, idioma):
    """Bloque CTA al final del PDF — diferente según tier"""
    story.append(Spacer(1, 0.3*inch))
    
    if tier_key == "free":
        upgrades = [
            ("✅ Básico — $99 MXN", (
                "Recomendación Final completo · Análisis de competencia (10 negocios) · "
                "Perfil demográfico con NSE e ingreso · Desglose del score con explicación · "
                "Características de la zona · Mapa de ubicación · Análisis completo PDF"
            )),
            ("🚀 PRO — $299 MXN", (
                "Todo lo del Básico + Análisis de tráfico por hora y día · "
                "Tamaño de mercado potencial · Forecast de ventas 3 escenarios · "
                "Mapa de competidores coloreados · Heatmap de competencia · "
                "Mapa de isócronas (5-15 min) · Mapa de canibalización · "
                "Narrativa interpretativa en cada sección · Análisis PRO PDF"
            )),
            ("💎 PREMIUM — $999 MXN", (
                "Todo lo del PRO + ROI y punto de equilibrio · "
                "Dashboard ejecutivo en una página · Comparativa de hasta 3 ubicaciones · "
                "Curva de recuperación de inversión · Análisis PREMIUM PDF"
            )),
        ]
    elif tier_key == "basic":
        upgrades = [
            ("🚀 PRO — $299 MXN", (
                "Análisis de tráfico por hora y día · Tamaño de mercado potencial · "
                "Forecast 3 escenarios · 4 mapas avanzados (competidores, heatmap, isócronas, canibalización) · "
                "Narrativa interpretativa por sección · Análisis PRO PDF"
            )),
            ("💎 PREMIUM — $999 MXN", (
                "ROI + punto de equilibrio · Dashboard ejecutivo · "
                "Comparativa 3 ubicaciones · Curva de recuperación · Análisis PREMIUM PDF"
            )),
        ]
    elif tier_key == "pro":
        upgrades = [
            ("💎 PREMIUM — $999 MXN", (
                "ROI y punto de equilibrio · Dashboard ejecutivo completo · "
                "Comparativa simultánea de hasta 3 ubicaciones · "
                "Curva de recuperación de inversión · Análisis PREMIUM PDF"
            )),
        ]
    else:
        upgrades = []

    if upgrades:
        cta_style = ParagraphStyle('cta_h', parent=s["base"]['Heading2'], fontSize=12,
                                   textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER)
        story.append(Paragraph(t["cta_titulo"], cta_style))
        for nombre, desc in upgrades:
            # Usar Paragraph para que el texto haga wrap automático
            from reportlab.platypus import Paragraph as _P
            nombre_p = _P(f"<b>{nombre}</b>",
                ParagraphStyle('cta_n', parent=s["base"]['Normal'],
                fontSize=9, textColor=colors.HexColor('#00D4D4')))
            desc_p = _P(desc,
                ParagraphStyle('cta_d', parent=s["base"]['Normal'],
                fontSize=8.5, textColor=colors.HexColor('#444444')))
            row = Table([[nombre_p, desc_p]], colWidths=[1.8*inch, 3.7*inch])
            row.setStyle(TableStyle([
                ('VALIGN',  (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('LINEBELOW', (0,0), (-1,-1), 0.3, colors.HexColor('#EEEEEE')),
            ]))
            story.append(row)
        story.append(Spacer(1, 0.15*inch))

    # Footer
    story.append(Spacer(1, 0.1*inch))
    footer_style = ParagraphStyle('footer', parent=s["base"]['Normal'], fontSize=8,
                                   textColor=colors.grey, alignment=TA_CENTER)
    story.append(Paragraph("📧 hola@4site.mx  |  🌐 4site.mx", footer_style))
    story.append(Paragraph(t["footer_derechos"], footer_style))

    if TIERS[tier_key]["watermark"]:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("━" * 30, s["watermark"]))
        story.append(Paragraph(t["watermark"], s["watermark"]))
        story.append(Paragraph("━" * 30, s["watermark"]))


# ─────────────────────────────────────────────
# PDF FREE  (Análisis básico)
# ─────────────────────────────────────────────
def generar_pdf_free(ubicacion, score, desglose, analisis, competidores,
                      idioma, lat, lng, modo, tipo_negocio=None, recomendaciones=None,
                      demografia=None, contexto=None):
    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=letter,
                               leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    s     = _estilos_pdf()
    t     = TEXTOS[idioma]
    story = []
    tier  = "free"

    _header_pdf(story, s, tier, idioma)
    story.append(Paragraph(f"<b>{t['input_ubicacion']}:</b> {ubicacion}", s["normal"]))
    if modo == "validar" and tipo_negocio:
        story.append(Paragraph(f"<b>Tipo:</b> {TIPOS_NEGOCIO[tipo_negocio]['nombre']}", s["normal"]))
    story.append(Spacer(1, 0.2*inch))

    _score_block(story, score, desglose, tier, t, s, idioma)

    # Mapa (sin competidores)
    mapa = generar_mapa_estatico(lat, lng, competidores=None, con_competidores=False)
    if mapa:
        story.append(Paragraph("📍 Ubicación", s["h2"]))
        story.append(RLImage(mapa, width=4.5*inch, height=3*inch))
        story.append(Spacer(1, 0.15*inch))

    # Competidores — solo 3 filas
    if competidores:
        story.append(Paragraph(t["competencia_titulo"], s["h2"]))
        story.append(Paragraph(f"Mostrando 3 de {len(competidores)} — Actualiza para ver todos", s["small"]))
        story.append(Spacer(1, 0.1*inch))
        story.append(_tabla_competidores(competidores, t, 3, s))
        story.append(Spacer(1, 0.1*inch))

    # Demografía básica (free): solo población, viviendas y densidad
    if demografia:
        densidad_info = formatear_densidad(demografia['densidad_hab_km2'])
        story.append(Paragraph("📍 Datos del Área (500m)" if idioma == "es" else "📍 Area Data (500m)", s["h2"]))
        dem_data = [
            ["Población estimada" if idioma == "es" else "Estimated population",
             f"{demografia['poblacion_estimada']:,} hab"],
            ["Viviendas habitadas" if idioma == "es" else "Occupied housing",
             f"{demografia['viviendas_habitadas']:,}"],
            ["Densidad" if idioma == "es" else "Density",
             densidad_info['clasificacion']],
            ["Aprox. por manzana" if idioma == "es" else "Approx. per block",
             f"~{densidad_info['personas_manzana']} personas"],
        ]
        dem_tbl = Table(dem_data, colWidths=[2.8*inch, 2.2*inch])
        dem_tbl.setStyle(TableStyle([
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('FONTNAME',   (0,0), (0,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR',  (0,0), (0,-1), colors.HexColor('#0047AB')),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#F5F8FF')]),
            ('GRID',       (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(dem_tbl)
        story.append(Paragraph(densidad_info['descripcion'], s["small"]))
        story.append(Paragraph(
            "🔒 NSE, ingreso promedio y datos INEGI reales disponibles en plan Básico ($99)" if idioma == "es"
            else "🔒 NSE, average income and real INEGI data available in Basic plan ($99)",
            ParagraphStyle('lock', parent=s["base"]['Normal'], fontSize=8,
                           textColor=colors.HexColor('#888888'), fontName='Helvetica-Oblique', spaceAfter=6)
        ))
        story.append(Spacer(1, 0.1*inch))

    # PageBreak → Resumen ejecutivo simple + CTA
    story.append(PageBreak())
    story.append(Paragraph("📋 Resumen Ejecutivo", s["h2"]))
    lineas = analisis.split('\n')
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            story.append(Spacer(1, 0.04*inch))
        elif linea.startswith('**') and linea.endswith('**'):
            story.append(Paragraph(linea.replace('**',''), ParagraphStyle('re_h',
                parent=s["base"]['Normal'], fontSize=10, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#0047AB'), spaceBefore=8, spaceAfter=3)))
        elif linea.startswith('- ') or linea.startswith('• '):
            story.append(Paragraph(f"  {linea}", ParagraphStyle('re_bl',
                parent=s["base"]['Normal'], fontSize=9, leftIndent=12, spaceAfter=2)))
        elif '**' in linea:
            txt = linea
            for _ in range(linea.count('**') // 2):
                txt = txt.replace('**', '<b>', 1).replace('**', '</b>', 1)
            story.append(Paragraph(txt, s["normal"]))
        else:
            story.append(Paragraph(linea, s["normal"]))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "[ Para análisis completo con Recomendación Final, tráfico y forecast actualiza al plan Básico ($99) ]",
        ParagraphStyle('upsell_f', parent=s["base"]['Normal'], fontSize=8.5,
            textColor=colors.HexColor('#00D4D4'), fontName='Helvetica-Oblique')))

    _cta_block(story, tier, t, s, idioma)
    doc.build(story)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# PDF BASIC  (Análisis completo)
# ─────────────────────────────────────────────
def generar_pdf_basic(ubicacion, score, desglose, analisis, competidores,
                       idioma, lat, lng, modo, tipo_negocio=None,
                       recomendaciones=None, demografia=None, contexto=None):
    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=letter,
                               leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    s     = _estilos_pdf()
    t     = TEXTOS[idioma]
    story = []
    tier  = "basic"

    # ── P1: Portada ──
    _header_pdf(story, s, tier, idioma)
    story.append(Paragraph(f"<b>{t['input_ubicacion']}:</b> {ubicacion}", s["normal"]))
    if modo == "validar" and tipo_negocio:
        tipo_info = TIPOS_NEGOCIO[tipo_negocio]
        story.append(Paragraph(f"<b>Tipo:</b> {tipo_info['nombre']}", s["normal"]))
        story.append(Paragraph(f"<b>Inversión estimada:</b> ${tipo_info['inversion_min']:,}–${tipo_info['inversion_max']:,} MXN", s["normal"]))
    story.append(Spacer(1, 0.2*inch))
    _score_block(story, score, desglose, tier, t, s, idioma)

    # Badges
    if contexto and contexto.get("badges"):
        for badge in contexto["badges"]:
            story.append(Paragraph(f"  {badge}", s["normal"]))
        story.append(Spacer(1, 0.1*inch))

    # ── P2: Mapa ──
    story.append(PageBreak())
    story.append(Paragraph("📍 Mapa de Ubicación", s["h2"]))
    mapa = generar_mapa_estatico(lat, lng, competidores=None, con_competidores=False)
    if mapa:
        story.append(RLImage(mapa, width=5*inch, height=3.3*inch))
    story.append(Paragraph("Radio de análisis: 500m", s["small"]))
    story.append(Spacer(1, 0.2*inch))

    # ── P3: Competidores (10 filas) — movido, Recomendación va al final ──
    story.append(PageBreak())
    if competidores:
        story.append(Paragraph(t["competencia_titulo"], s["h2"]))
        story.append(Paragraph(f"{len(competidores)} negocios similares encontrados en 500m", s["small"]))
        story.append(Spacer(1, 0.1*inch))
        story.append(_tabla_competidores(competidores, t, 10, s))
        # Narrativa interpretativa de competencia (Basic)
        ratings_b  = [c.get('rating',0) for c in (competidores or []) if c.get('rating')]
        avg_r_b    = round(sum(ratings_b)/len(ratings_b), 1) if ratings_b else 0
        n_verde_b  = sum(1 for r in ratings_b if r >= 4.3)
        tipo_nom_b = TIPOS_NEGOCIO.get(tipo_negocio, {}).get('nombre','') if tipo_negocio else (
            recomendaciones[0]['nombre'] if recomendaciones else '')
        narr_b = generar_narrativa_seccion("competencia", {
            "total_competidores": len(competidores),
            "rating_promedio": avg_r_b,
            "competidores_excelentes": n_verde_b,
        }, tipo_nom_b, idioma)
        for el in _bloque_narrativa_pdf(narr_b, s):
            story.append(el)

    # ── P5: Demografía estimada ──
    story.append(PageBreak())
    story.append(Paragraph(t["demografía"], s["h2"]))
    story.append(Paragraph(t["datos_estimados"], s["small"]))
    story.append(Spacer(1, 0.1*inch))
    if demografia:
        densidad_info = formatear_densidad(demografia['densidad_hab_km2'])
        dem_data = [
            [t["poblacion"],    f"{demografia['poblacion_estimada']:,} hab"],
            [t["nse"],          demografia['nse_predominante']],
            [t["densidad_hab"], densidad_info['clasificacion']],
            ["Viviendas",       f"{demografia['viviendas_habitadas']:,}"],
            ["Ingreso prom. mensual", f"${demografia['ingreso_promedio_mensual']:,}"],
        ]
        dem_tbl = Table(dem_data, colWidths=[2.5*inch, 2.5*inch])
        dem_tbl.setStyle(TableStyle([
            ('FONTSIZE',  (0,0), (-1,-1), 10),
            ('FONTNAME',  (0,0), (0,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#0047AB')),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#F5F8FF')]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(dem_tbl)
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(densidad_info['descripcion'], s["small"]))

    # Nota PRO
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        "🔜 PRO: Datos INEGI reales + tamaño de mercado + forecast de ventas + mapa con competidores",
        ParagraphStyle('pro_nota', parent=s["base"]['Normal'], fontSize=9,
                       textColor=colors.HexColor('#00D4D4'), fontName='Helvetica-Oblique')
    ))

    # ── P6: Recomendación Final ──
    story.append(PageBreak())
    _render_recomendacion_pdf(story, analisis, s)

    # ── P7: CTA ──
    story.append(PageBreak())
    _cta_block(story, tier, t, s, idioma)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# PDF PRO  (Análisis PRO — con gráficas reales)
# ─────────────────────────────────────────────
def generar_pdf_pro(ubicacion, score, desglose, analisis, competidores,
                     idioma, lat, lng, modo, tipo_negocio=None,
                     recomendaciones=None, demografia=None, contexto=None):
    """PRO: portada + mapa + análisis + competidores + demografía + tráfico + mercado + forecast + CTA"""
    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=letter,
                               leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
    s     = _estilos_pdf()
    t     = TEXTOS[idioma]
    story = []
    tier  = "pro"
    tipo_info = TIPOS_NEGOCIO.get(tipo_negocio, {}) if tipo_negocio else {}

    # Resolver tipo de negocio para modo recomendar (usar top1)
    tipo_negocio_efectivo = tipo_negocio
    tipo_info_efectivo    = tipo_info
    if not tipo_negocio_efectivo and modo == "recomendar" and recomendaciones:
        tipo_negocio_efectivo = recomendaciones[0]["tipo_key"]
        tipo_info_efectivo    = TIPOS_NEGOCIO.get(tipo_negocio_efectivo, {})
        competidores = recomendaciones[0]["competidores"] or competidores

    # Calcular datos PRO si módulos disponibles
    trafico_data = None
    mercado_data = None
    forecast_data = None
    roi_data = None
    if MODULOS_OK and demografia and tipo_negocio_efectivo:
        try:
            tipo_zona = contexto.get("tipo_zona", "mixto") if contexto else "mixto"
            densidad_a = demografia.get("densidad_actual", demografia.get("densidad_hab_km2", 8000))
            trafico_data  = generar_reporte_trafico(tipo_zona, tipo_negocio_efectivo, densidad_a)
            mercado_data  = calcular_mercado_potencial(demografia, tipo_negocio_efectivo, len(competidores or []))
            forecast_data = generar_forecast(mercado_data, tipo_negocio_efectivo, score,
                                             tipo_info_efectivo.get("inversion_min", 300000))
            roi_data      = calcular_roi(forecast_data, tipo_info_efectivo.get("inversion_min", 300000),
                                         tipo_info_efectivo.get("inversion_max", 600000), tipo_negocio_efectivo)
        except:
            pass

    # ── P1: PORTADA con diseño ──
    portada_style = ParagraphStyle('portada_titulo', parent=s["base"]['Normal'],
        fontSize=32, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER, spaceAfter=4)
    tagline_style = ParagraphStyle('portada_tag', parent=s["base"]['Normal'],
        fontSize=13, textColor=colors.HexColor('#00D4D4'), alignment=TA_CENTER, spaceAfter=20)
    tier_badge = ParagraphStyle('tier_b', parent=s["base"]['Normal'],
        fontSize=11, fontName='Helvetica-Bold',
        textColor=colors.white, alignment=TA_CENTER)

    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("4SITE", portada_style))
    story.append(Paragraph("Don't guess. Foresee.", tagline_style))

    # Badge PRO
    badge_tbl = Table([[f"PRO — $299 MXN"]], colWidths=[3*inch])
    badge_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#00D4D4')),
        ('TEXTCOLOR',  (0,0), (-1,-1), colors.white),
        ('FONTNAME',   (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 12),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(badge_tbl)
    story.append(Spacer(1, 0.3*inch))

    # Info ubicación
    story.append(Paragraph(f"<b>Ubicación analizada:</b>", s["h2"]))
    story.append(Paragraph(ubicacion, ParagraphStyle('ub', parent=s["base"]['Normal'],
        fontSize=12, textColor=colors.HexColor('#333333'), spaceAfter=8)))

    # Tipo de negocio evaluado (validar o recomendar)
    tipo_nombre_pro = tipo_info_efectivo.get('nombre', tipo_info.get('nombre',''))
    if not tipo_nombre_pro and recomendaciones:
        tipo_nombre_pro = recomendaciones[0].get('nombre','')
    if tipo_nombre_pro:
        story.append(Paragraph(
            f"<b>Negocio evaluado:</b> {tipo_nombre_pro}",
            ParagraphStyle('tipo_pro', parent=s["base"]['Normal'],
            fontSize=13, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0047AB'), spaceAfter=6)))

    if tipo_negocio_efectivo:
        story.append(Paragraph(
            f"<b>Inversión estimada:</b> ${tipo_info_efectivo.get('inversion_min',0):,} – ${tipo_info_efectivo.get('inversion_max',0):,} MXN",
            s["normal"]))
    story.append(Paragraph(
        f"<b>Fecha:</b> {datetime.datetime.now().strftime('%d de %B de %Y')}", s["normal"]))
    story.append(Spacer(1, 0.2*inch))

    # Score gauge embebido
    if GRAFICAS_OK:
        nivel_txt, _ = nivel_score(score, idioma)
        gauge = grafica_score_gauge(score, nivel_txt)
        story.append(RLImage(gauge, width=3.5*inch, height=2*inch))
    else:
        _score_block(story, score, desglose, tier, t, s, idioma)

    # Características de la zona / Generadores de tráfico
    if contexto and contexto.get("badges"):
        story.append(Spacer(1, 0.12*inch))
        story.append(Paragraph("📍 Características de la Zona y Generadores de Tráfico:",
            ParagraphStyle('badges_titulo', parent=s["base"]['Normal'],
            fontSize=10, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0047AB'), spaceAfter=4)))
        BADGE_DESCRIPCIONES = {
            "🚗 Alto tráfico vehicular": "Vialidad de alto flujo — ideal para negocios de paso y visibilidad",
            "⛽ Gasolinera cercana":      "Gasolinera en 500m — genera tráfico vehicular constante",
            "🏬 Plaza comercial":         "Centro comercial cercano — concentrador de shoppers y tráfico",
            "🏥 Hospital cercano":        "Hospital/clínica en 500m — clientela cautiva de alta frecuencia",
            "🎓 Escuela/Universidad":     "Institución educativa — alto flujo estudiantil y docente",
            "🚌 Transporte público":      "Estación de transporte — alta accesibilidad peatonal",
        }
        for badge in contexto["badges"]:
            desc = BADGE_DESCRIPCIONES.get(badge, "Característica detectada en la zona")
            story.append(Paragraph(f"  {badge}  —  {desc}",
                ParagraphStyle('badge_item', parent=s["base"]['Normal'],
                fontSize=8.5, textColor=colors.HexColor('#1565C0'),
                leftIndent=8, spaceAfter=3)))

    story.append(Paragraph(f"<i>Reporte generado por 4SITE · hola@4site.mx · 4site.mx</i>",
                            ParagraphStyle('footer_p', parent=s["base"]['Normal'],
                            fontSize=8, textColor=colors.grey, alignment=TA_CENTER)))

    # ── P2: DESGLOSE SCORE ──
    # ── P5: COMPETIDORES ──
    story.append(PageBreak())
    story.append(Paragraph(t["competencia_titulo"], s["h2"]))
    story.append(Paragraph(f"{len(competidores or [])} negocios similares encontrados en radio de 500m", s["small"]))
    story.append(Spacer(1, 0.1*inch))
    if competidores:
        story.append(_tabla_competidores(competidores, t, 20, s))
        # Narrativa interpretativa de competencia
        ratings_c  = [c.get('rating',0) for c in (competidores or []) if c.get('rating')]
        n_verdes_c = sum(1 for r in ratings_c if r >= 4.3)
        avg_r_c    = round(sum(ratings_c)/len(ratings_c),1) if ratings_c else 0
        datos_comp_narr = {
            "total_competidores": len(competidores or []),
            "rating_promedio": avg_r_c,
            "competidores_excelentes": n_verdes_c,
            "tipo_negocio": tipo_negocio_efectivo or tipo_negocio or ""
        }
        narr_comp = generar_narrativa_seccion("competencia", datos_comp_narr,
                                               tipo_info_efectivo.get('nombre', tipo_info.get('nombre','')), idioma)
        for el in _bloque_narrativa_pdf(narr_comp, s):
            story.append(el)

    # ── P6: DEMOGRAFÍA ──
    story.append(PageBreak())
    story.append(Paragraph("👥 Perfil Demográfico del Área (500m)", s["h2"]))
    fuente = demografia.get('fuente', 'Estimación por zona') if demografia else ''
    story.append(Paragraph(f"📊 Fuente: {fuente}", s["small"]))
    story.append(Spacer(1, 0.1*inch))
    if demografia and GRAFICAS_OK:
        graf_dem = grafica_demografia(demografia)
        story.append(RLImage(graf_dem, width=5.5*inch, height=2.6*inch))
    if demografia:
        año_act = datetime.datetime.now().year
        densidad_info = clasificar_densidad(demografia.get('densidad_actual', 8000)) if MODULOS_OK else formatear_densidad(demografia.get('densidad_hab_km2', 8000))
        dem_rows = [
            [f"Población {año_act}", f"{demografia.get('poblacion_actual', demografia.get('poblacion_estimada',0)):,} hab",
             f"(Censo 2020: {demografia.get('poblacion_2020','-'):,})" if demografia.get('poblacion_2020') else ""],
            ["Viviendas habitadas", f"{demografia.get('viviendas_actual', demografia.get('viviendas_habitadas',0)):,}", ""],
            ["Densidad urbana", densidad_info.get('nivel', densidad_info.get('clasificacion','')),
             f"~{demografia.get('personas_manzana', densidad_info.get('personas_manzana',0))} personas/manzana"],
            ["NSE predominante", demografia.get('nse_predominante','C'), "Nivel Socioeconómico AMAI"],
            ["Ingreso prom. mensual", f"${demografia.get('ingreso_actual', demografia.get('ingreso_promedio_mensual',0)):,}", "Proyectado 2026 (INPC)"],
            ["Gasto prom. mensual", f"${demografia.get('gasto_actual', demografia.get('gasto_promedio_mensual',0)):,}", "~78% del ingreso (ENIGH)"],
            ["Crecimiento anual zona", f"{demografia.get('tasa_crecimiento_pct',0.55):.2f}%", "Tasa CONAPO 2020-2030"],
        ]
        tbl_dem = Table(dem_rows, colWidths=[2*inch, 1.8*inch, 2.2*inch])
        tbl_dem.setStyle(TableStyle([
            ('FONTNAME',   (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('TEXTCOLOR',  (0,0), (0,-1), colors.HexColor('#0047AB')),
            ('TEXTCOLOR',  (2,0), (2,-1), colors.HexColor('#888888')),
            ('FONTSIZE',   (2,0), (2,-1), 8),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#F0F4FF')]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(tbl_dem)
        # Narrativa interpretativa de demografía
        datos_dem_narr = {
            "poblacion": demografia.get('poblacion_actual', demografia.get('poblacion_estimada',0)) if demografia else 0,
            "nse": demografia.get('nse_predominante','C') if demografia else 'C',
            "ingreso_mensual": demografia.get('ingreso_actual', demografia.get('ingreso_promedio_mensual',0)) if demografia else 0,
            "densidad_hab_km2": demografia.get('densidad_actual', demografia.get('densidad_hab_km2',0)) if demografia else 0,
            "crecimiento_anual_pct": demografia.get('tasa_crecimiento_pct',0) if demografia else 0,
        }
        narr_dem = generar_narrativa_seccion("demografia", datos_dem_narr,
                                              tipo_info_efectivo.get('nombre', tipo_info.get('nombre','')), idioma)
        for el in _bloque_narrativa_pdf(narr_dem, s):
            story.append(el)

    # ── P7: TRÁFICO ──
    story.append(PageBreak())
    story.append(Paragraph("🚗 Análisis de Tráfico Estimado", s["h2"]))
    story.append(Paragraph(
        "Perfil de flujo peatonal y vehicular estimado para este tipo de negocio "
        "basado en el tipo de zona detectada y densidad poblacional.",
        s["normal"]))
    if trafico_data and GRAFICAS_OK:
        graf_trafico_h = grafica_trafico_horario(
            trafico_data["trafico_horario"],
            tipo_info.get('nombre','') if tipo_negocio else '')
        story.append(RLImage(graf_trafico_h, width=5.5*inch, height=2.8*inch))
        story.append(Spacer(1, 0.1*inch))

        graf_trafico_s = grafica_trafico_semanal(trafico_data["trafico_semanal"])
        story.append(RLImage(graf_trafico_s, width=5.5*inch, height=1.8*inch))

        # Tabla horas pico
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("🕐 Horas pico recomendadas para operar / mayor flujo:", s["normal"]))
        pico_rows = [["Horario", "Nivel de flujo", "Recomendación"]]
        for pico in trafico_data["horas_pico"]:
            rec = ("Máxima atención al cliente" if pico["flujo"] >= 80
                   else "Alta actividad" if pico["flujo"] >= 60
                   else "Flujo moderado")
            pico_rows.append([pico["hora_str"], f"{pico['nivel']} ({pico['flujo']}%)", rec])
        tbl_pico = Table(pico_rows, colWidths=[1.8*inch, 1.8*inch, 2.4*inch])
        tbl_pico.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0047AB')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F0F4FF')]),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(tbl_pico)
        # Narrativa interpretativa de tráfico
        _tipo_nom_narr = (tipo_info_efectivo.get('nombre','') if 'tipo_info_efectivo' in dir()
                         else tipo_info.get('nombre',''))
        if trafico_data:
            datos_traf_narr = {
                "nivel_general": trafico_data.get('nivel_general',''),
                "horas_pico": [p['hora_str'] for p in trafico_data.get('horas_pico',[])[:2]],
                "mejor_dia": trafico_data.get('dia_pico',''),
                "dia_bajo": trafico_data.get('dia_bajo',''),
            }
            narr_traf = generar_narrativa_seccion("trafico", datos_traf_narr,
                                                   _tipo_nom_narr, idioma)
            for el in _bloque_narrativa_pdf(narr_traf, s):
                story.append(el)
    else:
        story.append(Paragraph("🔜 Datos de tráfico no disponibles — verifica que modulos_4site.py esté instalado.", s["small"]))

    # ── P8: MERCADO + FORECAST ──
    story.append(PageBreak())
    story.append(Paragraph("📊 Tamaño de Mercado Potencial", s["h2"]))
    if mercado_data and GRAFICAS_OK:
        graf_mercado = grafica_mercado_donut(mercado_data)
        story.append(RLImage(graf_mercado, width=5*inch, height=3*inch))
        story.append(Paragraph(f"📐 Metodología: {mercado_data['metodologia']}", s["small"]))
        # Narrativa interpretativa de mercado
        narr_mercado = generar_narrativa_seccion("mercado", {
            "mercado_total_mensual": mercado_data.get('mercado_total_mensual',0),
            "mercado_captura_mensual": mercado_data.get('mercado_captura_mensual',0),
            "factor_captura_pct": mercado_data.get('factor_captura_pct',0),
            "clientes_dia": mercado_data.get('clientes_dia_estimados',0),
        }, _tipo_nom_narr if '_tipo_nom_narr' in dir() else tipo_info.get('nombre',''), idioma)
        for el in _bloque_narrativa_pdf(narr_mercado, s):
            story.append(el)

    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("📈 Forecast de Ventas — 12 Meses (3 Escenarios)", s["h2"]))
    if forecast_data and GRAFICAS_OK:
        graf_forecast = grafica_forecast(forecast_data)
        fc_rows = [["Escenario", "Ventas mes 1", "Ventas mes 9", "Total año 1", "Prom. mensual"]]
        story.append(RLImage(graf_forecast, width=5.5*inch, height=3*inch))
        for key, emoji in [("pesimista","🔴"), ("base","🔵"), ("optimista","🟢")]:
            e = forecast_data["escenarios"][key]
            fc_rows.append([
                f"{emoji} {key.capitalize()}",
                f"${e['ventas_mensuales'][0]/1000:.0f}K",
                f"${e['ventas_mensuales'][8]/1000:.0f}K",
                f"${e['total_anual']/1000:.0f}K",
                f"${e['promedio_mensual']/1000:.0f}K",
            ])
        tbl_fc = Table(fc_rows, colWidths=[1.2*inch, 1*inch, 1*inch, 1.2*inch, 1.2*inch])
        tbl_fc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0047AB')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [
                colors.HexColor('#FFEBEE'),
                colors.HexColor('#E3F2FD'),
                colors.HexColor('#E8F5E9'),
            ]),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(tbl_fc)
        story.append(Spacer(1, 0.08*inch))
        story.append(Paragraph("📋 Supuestos: " + " · ".join(forecast_data.get("supuestos",[])), s["small"]))
        # Narrativa interpretativa de forecast
        esc = forecast_data.get('escenarios',{})
        narr_fc = generar_narrativa_seccion("forecast", {
            "total_pesimista": esc.get('pesimista',{}).get('total_anual',0),
            "total_base": esc.get('base',{}).get('total_anual',0),
            "total_optimista": esc.get('optimista',{}).get('total_anual',0),
            "promedio_mensual_base": esc.get('base',{}).get('promedio_mensual',0),
        }, _tipo_nom_narr if '_tipo_nom_narr' in dir() else tipo_info.get('nombre',''), idioma)
        for el in _bloque_narrativa_pdf(narr_fc, s):
            story.append(el)

    # ── P9: Recomendación Final ──
    story.append(PageBreak())
    _render_recomendacion_pdf(story, analisis, s)


    # ── P11: CTA ──
    story.append(PageBreak())
    _cta_block(story, tier, t, s, idioma)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# PDF PREMIUM  (Análisis PREMIUM — dashboard + comparativa)
# ─────────────────────────────────────────────
def generar_pdf_premium(ubicacion, score, desglose, analisis, competidores,
                          idioma, lat, lng, modo, tipo_negocio=None,
                          recomendaciones=None, demografia=None, contexto=None):
    """PREMIUM: todo lo de PRO + dashboard página completa + ROI + comparativa"""
    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=letter,
                               leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
    s     = _estilos_pdf()
    t     = TEXTOS[idioma]
    story = []
    tier  = "premium"
    tipo_info = TIPOS_NEGOCIO.get(tipo_negocio, {}) if tipo_negocio else {}

    # Resolver tipo de negocio para modo recomendar (usar top1)
    tipo_negocio_efectivo = tipo_negocio
    tipo_info_efectivo    = tipo_info
    if not tipo_negocio_efectivo and modo == "recomendar" and recomendaciones:
        tipo_negocio_efectivo = recomendaciones[0]["tipo_key"]
        tipo_info_efectivo    = TIPOS_NEGOCIO.get(tipo_negocio_efectivo, {})
        if not competidores and recomendaciones[0].get("competidores"):
            competidores = recomendaciones[0]["competidores"]

    # Calcular datos
    trafico_data = None
    mercado_data = None
    forecast_data = None
    roi_data = None
    if MODULOS_OK and demografia and tipo_negocio_efectivo:
        try:
            tipo_zona = contexto.get("tipo_zona","mixto") if contexto else "mixto"
            densidad_a = demografia.get("densidad_actual", demografia.get("densidad_hab_km2", 8000))
            trafico_data  = generar_reporte_trafico(tipo_zona, tipo_negocio_efectivo, densidad_a)
            mercado_data  = calcular_mercado_potencial(demografia, tipo_negocio_efectivo, len(competidores or []))
            forecast_data = generar_forecast(mercado_data, tipo_negocio_efectivo, score,
                                             tipo_info_efectivo.get("inversion_min", 300000))
            roi_data      = calcular_roi(forecast_data, tipo_info_efectivo.get("inversion_min", 300000),
                                         tipo_info_efectivo.get("inversion_max", 600000), tipo_negocio_efectivo)
        except:
            pass

    # ── P1: DASHBOARD EJECUTIVO (página completa) ──
    story.append(Paragraph("💎 PREMIUM", ParagraphStyle('prem_tag', parent=s["base"]['Normal'],
        fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#FFD700'),
        alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph("4SITE — REPORTE EJECUTIVO PREMIUM",
        ParagraphStyle('prem_titulo', parent=s["base"]['Normal'],
        fontSize=20, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER, spaceAfter=6)))
    story.append(Paragraph(ubicacion, ParagraphStyle('prem_ub', parent=s["base"]['Normal'],
        fontSize=11, textColor=colors.HexColor('#555'), alignment=TA_CENTER, spaceAfter=6)))

    # Tipo de negocio destacado
    tipo_nombre_port = tipo_info_efectivo.get('nombre', tipo_info.get('nombre',''))
    if not tipo_nombre_port and recomendaciones:
        tipo_nombre_port = recomendaciones[0].get('nombre','')
    if tipo_nombre_port:
        story.append(Paragraph(tipo_nombre_port,
            ParagraphStyle('tipo_port', parent=s["base"]['Normal'],
            fontSize=16, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#00D4D4'), alignment=TA_CENTER, spaceAfter=4)))

    story.append(Paragraph(datetime.datetime.now().strftime('%d/%m/%Y'), s["small"]))
    story.append(Spacer(1, 0.15*inch))

    # Dashboard imagen completa
    if (GRAFICAS_OK and MODULOS_OK and trafico_data and mercado_data
            and forecast_data and roi_data and demografia):
        try:
            dashboard_img = grafica_dashboard_premium(
                score, desglose, mercado_data, forecast_data, roi_data,
                trafico_data, demografia,
                titulo_negocio=tipo_nombre_port if 'tipo_nombre_port' in dir() else '')
            story.append(RLImage(dashboard_img, width=6.2*inch, height=8*inch))
        except Exception as e:
            story.append(Paragraph(f"Dashboard no disponible: {e}", s["small"]))
    else:
        _score_block(story, score, desglose, tier, t, s, idioma)

    # ── P2: MAPA CON COMPETIDORES ──
    story.append(PageBreak())
    story.append(Paragraph("📍 Mapa de Ubicación y Competidores", s["h2"]))
    story.append(Paragraph("🟢 Excelente (≥4.3★)   🟠 Bueno (3.5-4.2★)   🔴 Débil/sin datos   ★ Tu ubicación",
        ParagraphStyle('ley', parent=s["base"]['Normal'], fontSize=8.5,
        textColor=colors.HexColor('#555'), spaceAfter=8)))
    mapa = generar_mapa_estatico(lat, lng, competidores=competidores, con_competidores=True)
    if mapa:
        story.append(RLImage(mapa, width=5.5*inch, height=3.7*inch))
    interp = generar_texto_interpretacion_mapa(competidores or [], contexto or {}, "competidores", idioma)
    story.append(Paragraph(interp, ParagraphStyle('interp2', parent=s["base"]['Normal'],
        fontSize=8.5, textColor=colors.HexColor('#444'), spaceAfter=6,
        backColor=colors.HexColor('#F5F8FF'), borderPad=6)))

    # ── P4: COMPETIDORES ──
    story.append(PageBreak())
    story.append(Paragraph(t["competencia_titulo"], s["h2"]))
    if competidores:
        story.append(_tabla_competidores(competidores, t, 20, s))

    # ── P5: DEMOGRAFÍA ──
    story.append(PageBreak())
    story.append(Paragraph("👥 Perfil Demográfico del Área", s["h2"]))
    if demografia:
        fuente = demografia.get('fuente','Estimación por zona')
        story.append(Paragraph(f"📊 {fuente}", s["small"]))
        if GRAFICAS_OK:
            try:
                story.append(RLImage(grafica_demografia(demografia), width=5.5*inch, height=2.6*inch))
            except:
                pass
        año_act = datetime.datetime.now().year
        densidad_info = clasificar_densidad(demografia.get('densidad_actual',8000)) if MODULOS_OK else formatear_densidad(demografia.get('densidad_hab_km2',8000))
        dem_rows = [
            [f"Población {año_act}", f"{demografia.get('poblacion_actual', demografia.get('poblacion_estimada',0)):,} hab",
             f"Censo 2020: {demografia.get('poblacion_2020','-'):,}" if demografia.get('poblacion_2020') else ""],
            ["Viviendas habitadas", f"{demografia.get('viviendas_actual', demografia.get('viviendas_habitadas',0)):,}", ""],
            ["Densidad urbana", densidad_info.get('nivel', densidad_info.get('clasificacion','')),
             f"~{demografia.get('personas_manzana', densidad_info.get('personas_manzana',0))} personas/manzana"],
            ["NSE predominante", demografia.get('nse_predominante','C'), "AMAI"],
            ["Ingreso prom/mes", f"${demografia.get('ingreso_actual', demografia.get('ingreso_promedio_mensual',0)):,}", "Proyectado 2026"],
            ["Gasto prom/mes", f"${demografia.get('gasto_actual', demografia.get('gasto_promedio_mensual',0)):,}", "78% del ingreso (ENIGH)"],
            ["Crecimiento anual", f"{demografia.get('tasa_crecimiento_pct',0.55):.2f}%", "CONAPO 2020-2030"],
        ]
        tbl_d = Table(dem_rows, colWidths=[2*inch, 1.8*inch, 2.2*inch])
        tbl_d.setStyle(TableStyle([
            ('FONTNAME', (0,0),(0,-1),'Helvetica-Bold'),
            ('FONTSIZE', (0,0),(-1,-1),9),
            ('TEXTCOLOR',(0,0),(0,-1),colors.HexColor('#0047AB')),
            ('TEXTCOLOR',(2,0),(2,-1),colors.HexColor('#888888')),
            ('FONTSIZE', (2,0),(2,-1),8),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#F0F4FF')]),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#DDDDDD')),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ]))
        story.append(tbl_d)
        # Narrativa demografía PREMIUM
        datos_dem_p = {
            "nse": demografia.get('nse_predominante','C') if demografia else 'C',
            "ingreso_mensual": demografia.get('ingreso_actual', demografia.get('ingreso_promedio_mensual',0)) if demografia else 0,
            "densidad_hab_km2": demografia.get('densidad_actual', demografia.get('densidad_hab_km2',0)) if demografia else 0,
            "crecimiento_anual_pct": demografia.get('tasa_crecimiento_pct',0) if demografia else 0,
        }
        narr_dem_p = generar_narrativa_seccion("demografia", datos_dem_p,
                                                tipo_info_efectivo.get('nombre', tipo_info.get('nombre','')), idioma)
        for el in _bloque_narrativa_pdf(narr_dem_p, s):
            story.append(el)

    # ── P6: TRÁFICO ──
    story.append(PageBreak())
    story.append(Paragraph("🚗 Análisis de Tráfico Estimado", s["h2"]))
    if trafico_data and GRAFICAS_OK:
        story.append(RLImage(grafica_trafico_horario(
            trafico_data["trafico_horario"], tipo_info.get('nombre','')),
            width=5.5*inch, height=2.8*inch))
        story.append(RLImage(grafica_trafico_semanal(trafico_data["trafico_semanal"]),
            width=5.5*inch, height=1.8*inch))
        pico_rows = [["Horario","Nivel","Recomendación"]]
        for p in trafico_data["horas_pico"]:
            pico_rows.append([p["hora_str"], f"{p['nivel']} ({p['flujo']}%)",
                "Máx. atención" if p["flujo"]>=80 else "Alta actividad"])
        tbl_p = Table(pico_rows, colWidths=[1.8*inch,1.8*inch,2.4*inch])
        tbl_p.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0047AB')),
            ('TEXTCOLOR', (0,0),(-1,0),colors.white),
            ('FONTNAME',  (0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',  (0,0),(-1,-1),9),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#DDDDDD')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F0F4FF')]),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ]))
        story.append(tbl_p)
        # Narrativa tráfico PREMIUM
        _t_nom_p = tipo_info_efectivo.get('nombre', tipo_info.get('nombre','')) if 'tipo_info_efectivo' in dir() else tipo_info.get('nombre','')
        if trafico_data:
            narr_traf_p = generar_narrativa_seccion("trafico", {
                "nivel_general": trafico_data.get('nivel_general',''),
                "horas_pico": [p['hora_str'] for p in trafico_data.get('horas_pico',[])[:2]],
                "mejor_dia": trafico_data.get('dia_pico',''),
                "dia_bajo": trafico_data.get('dia_bajo',''),
            }, _t_nom_p, idioma)
            for el in _bloque_narrativa_pdf(narr_traf_p, s):
                story.append(el)

    # ── P7: MERCADO + FORECAST ──
    story.append(PageBreak())
    story.append(Paragraph("📊 Tamaño de Mercado Potencial", s["h2"]))
    if mercado_data and GRAFICAS_OK:
        story.append(RLImage(grafica_mercado_donut(mercado_data), width=5*inch, height=3*inch))
        story.append(Paragraph(f"📐 {mercado_data['metodologia']}", s["small"]))
        # Narrativa mercado PREMIUM
        narr_merc_p = generar_narrativa_seccion("mercado", {
            "mercado_total_mensual": mercado_data.get('mercado_total_mensual',0),
            "mercado_captura_mensual": mercado_data.get('mercado_captura_mensual',0),
            "factor_captura_pct": mercado_data.get('factor_captura_pct',0),
            "clientes_dia": mercado_data.get('clientes_dia_estimados',0),
        }, _t_nom_p if '_t_nom_p' in dir() else '', idioma)
        for el in _bloque_narrativa_pdf(narr_merc_p, s):
            story.append(el)

    story.append(Spacer(1,0.15*inch))
    story.append(Paragraph("📈 Forecast de Ventas — 12 Meses", s["h2"]))
    if forecast_data and GRAFICAS_OK:
        story.append(RLImage(grafica_forecast(forecast_data), width=5.5*inch, height=3*inch))
        fc_rows = [["Escenario","Mes 1","Mes 9","Total año 1","Prom/mes"]]
        for key, emoji in [("pesimista","🔴"),("base","🔵"),("optimista","🟢")]:
            e = forecast_data["escenarios"][key]
            fc_rows.append([f"{emoji} {key.capitalize()}",
                f"${e['ventas_mensuales'][0]/1000:.0f}K",
                f"${e['ventas_mensuales'][8]/1000:.0f}K",
                f"${e['total_anual']/1000:.0f}K",
                f"${e['promedio_mensual']/1000:.0f}K"])
        tbl_fc = Table(fc_rows, colWidths=[1.2*inch,1*inch,1*inch,1.2*inch,1.2*inch])
        tbl_fc.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0047AB')),
            ('TEXTCOLOR', (0,0),(-1,0),colors.white),
            ('FONTNAME',  (0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',  (0,0),(-1,-1),9),
            ('ALIGN',     (1,0),(-1,-1),'CENTER'),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#DDDDDD')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[
                colors.HexColor('#FFEBEE'),
                colors.HexColor('#E3F2FD'),
                colors.HexColor('#E8F5E9')]),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ]))
        story.append(tbl_fc)
        # Narrativa forecast PREMIUM
        esc_p = forecast_data.get('escenarios',{})
        narr_fc_p = generar_narrativa_seccion("forecast", {
            "total_pesimista": esc_p.get('pesimista',{}).get('total_anual',0),
            "total_base": esc_p.get('base',{}).get('total_anual',0),
            "total_optimista": esc_p.get('optimista',{}).get('total_anual',0),
            "promedio_mensual_base": esc_p.get('base',{}).get('promedio_mensual',0),
        }, _t_nom_p if '_t_nom_p' in dir() else '', idioma)
        for el in _bloque_narrativa_pdf(narr_fc_p, s):
            story.append(el)

    # ── P8: ROI ──
    story.append(PageBreak())
    story.append(Paragraph("💰 ROI + Punto de Equilibrio", s["h2"]))
    story.append(Paragraph(
        "Análisis de retorno sobre inversión basado en el forecast de ventas "
        "y estructura de costos estándar para el tipo de negocio seleccionado.", s["normal"]))
    if roi_data and forecast_data and GRAFICAS_OK:
        story.append(RLImage(grafica_roi_dashboard(roi_data, forecast_data),
            width=6*inch, height=3*inch))
        roi_rows = [
            ["ROI estimado 12 meses", f"{roi_data['roi_12m_pct']}%", roi_data['clasificacion_roi']],
            ["Meses de recuperación est.", f"{roi_data['meses_recuperacion']} meses", "Escenario base"],
            ["Utilidad mensual estimada", f"${roi_data['utilidad_mensual_est']:,}", "35% margen bruto"],
            ["Punto de equilibrio", f"${roi_data['punto_eq_ventas_mes']:,}/mes", "Ventas mínimas para no perder"],
            ["Inversión mínima", f"${roi_data['inversion_min']:,}", tipo_info.get('nombre','')],
        ]
        tbl_roi = Table(roi_rows, colWidths=[2.2*inch,1.5*inch,2.3*inch])
        tbl_roi.setStyle(TableStyle([
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9),
            ('TEXTCOLOR',(0,0),(0,-1),colors.HexColor('#0047AB')),
            ('TEXTCOLOR',(2,0),(2,-1),colors.HexColor('#888888')),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#F0F4FF')]),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#DDDDDD')),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ]))
        story.append(tbl_roi)
        story.append(Paragraph("⚠️ Estimaciones con supuestos estándar. Los resultados dependen de gestión, producto y mercado real.", s["small"]))
        # Narrativa ROI PREMIUM
        if roi_data:
            narr_roi = generar_narrativa_seccion("roi", {
                "roi_12m_pct": roi_data.get('roi_12m_pct',0),
                "meses_recuperacion": roi_data.get('meses_recuperacion',0),
                "utilidad_mensual": roi_data.get('utilidad_mensual_est',0),
                "clasificacion": roi_data.get('clasificacion_roi',''),
            }, tipo_info_efectivo.get('nombre', tipo_info.get('nombre','')), idioma)
            for el in _bloque_narrativa_pdf(narr_roi, s):
                story.append(el)

    # ── P9: COMPARATIVA DE UBICACIONES ──
    story.append(PageBreak())
    story.append(Paragraph("🗺️ Comparativa de Ubicaciones", s["h2"]))

    # Datos de la ubicación principal
    ubicaciones_comp = [{
        "nombre": (ubicacion or "Ubicación principal")[:40],
        "score": score,
        "densidad_comp": desglose.get('densidad', 0) if desglose else 0,
        "calidad_comp":  desglose.get('calidad', 0) if desglose else 0,
        "consolidacion": desglose.get('consolidacion', 0) if desglose else 0,
        "poblacion":     (demografia or {}).get('poblacion_actual', (demografia or {}).get('poblacion_estimada', 0)),
        "nse":           (demografia or {}).get('nse_predominante', 'C'),
        "ingreso":       (demografia or {}).get('ingreso_actual', (demografia or {}).get('ingreso_promedio_mensual', 0)),
        "num_competidores": len(competidores or []),
    }]
    # Agregar ubicaciones comparadas si existen en session (se pasan como parámetro extra)
    # Por ahora mostrar tabla con la ubicación principal y un espacio para las comparadas
    comp_rows = [["Indicador", (ubicacion or "Ubicación principal")[:25]]]
    comp_rows += [
        ["Score viabilidad",    f"{score}/100"],
        ["NSE predominante",    (demografia or {}).get('nse_predominante','C')],
        ["Competidores 500m",   str(len(competidores or []))],
        ["Densidad comp.",      f"{desglose.get('densidad',0)}/100" if desglose else "N/A"],
        ["Calidad comp.",       f"{desglose.get('calidad',0)}/100" if desglose else "N/A"],
        ["Consolidación",       f"{desglose.get('consolidacion',0)}/100" if desglose else "N/A"],
        ["Ingreso prom. área",  f"${(demografia or {}).get('ingreso_actual', (demografia or {}).get('ingreso_promedio_mensual',0)):,}"],
    ]
    tbl_comp = Table(comp_rows, colWidths=[2.2*inch, 3.3*inch])
    tbl_comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,0), colors.HexColor('#0047AB')),
        ('TEXTCOLOR',  (0,0),(-1,0), colors.white),
        ('FONTNAME',   (0,0),(-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0),(-1,-1), 9),
        ('FONTNAME',   (0,0),(0,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR',  (0,1),(0,-1), colors.HexColor('#0047AB')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#F0F4FF')]),
        ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#DDDDDD')),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(tbl_comp)
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "💡 Para comparar ubicaciones adicionales, usa la función de comparativa en la aplicación. "
        "El análisis compara score, demografía y competencia entre todas las ubicaciones seleccionadas.",
        ParagraphStyle('comp_nota', parent=s["base"]['Normal'], fontSize=8.5,
        textColor=colors.HexColor('#555'), fontName='Helvetica-Oblique')))

    if GRAFICAS_OK and len(ubicaciones_comp) >= 1:
        try:
            graf_comp_pdf = grafica_comparativa(ubicaciones_comp)
            if graf_comp_pdf:
                story.append(Spacer(1, 0.1*inch))
                story.append(RLImage(graf_comp_pdf, width=5.5*inch, height=3.5*inch))
        except:
            pass

    # ── P10: Recomendación Final ──
    story.append(PageBreak())
    _render_recomendacion_pdf(story, analisis, s)

    # ── P11: CTA ──
    story.append(PageBreak())
    _cta_block(story, tier, t, s, idioma)

    doc.build(story)
    buffer.seek(0)
    return buffer



def generar_pdf_por_tier(tier_key, **kwargs):
    """Router central de generación de PDF"""
    if tier_key == "basic":
        return generar_pdf_basic(**kwargs)
    elif tier_key == "pro":
        return generar_pdf_pro(**kwargs)
    elif tier_key == "premium":
        return generar_pdf_premium(**kwargs)
    else:
        return generar_pdf_free(**kwargs)

# ============================================
# INTERFAZ STREAMLIT
# ============================================

# Selector idioma
idioma = st.selectbox(
    TEXTOS["es"]["selector_idioma"],
    options=["es", "en"],
    format_func=lambda x: "Español 🇲🇽" if x == "es" else "English 🇺🇸"
)
t = TEXTOS[idioma]

# Header
st.markdown(f"""
<div style='text-align:center; padding:20px;'>
    <h1 style='color:#0047AB; font-size:52px; margin:0; letter-spacing:-2px;'>4SITE</h1>
    <p style='color:#00D4D4; font-size:18px; margin:5px 0; font-style:italic;'>Don't guess. Foresee.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── SISTEMA DE CÓDIGOS ──────────────────────
st.markdown(f"### {t['ingresa_codigo']}")

col_code, col_btn = st.columns([3, 1])
with col_code:
    codigo_input = st.text_input("", placeholder=t["placeholder_codigo"],
                                  key="codigo_input", label_visibility="collapsed")
with col_btn:
    aplicar = st.button(t["validar_codigo"], use_container_width=True)

# Estado del tier en session_state
if "tier_activo" not in st.session_state:
    st.session_state.tier_activo = "free"

if aplicar and codigo_input:
    resultado = validar_codigo(codigo_input)
    if resultado is None:
        st.error(t["codigo_invalido"])
    elif resultado == "usado":
        st.error("❌ Este código ya fue utilizado. Cada código es válido para una sola consulta. Adquiere un nuevo código en hola@4site.mx")
    else:
        st.session_state.tier_activo = resultado
        st.session_state.codigo_activo = codigo_input.strip().upper()
        activar_codigo(codigo_input)
        tier_info = TIERS[resultado]
        st.success(f"{t['codigo_valido']} **{tier_info['nombre']}** — {tier_info['precio']} · {tier_info['pdf_paginas']}")

# Botón para continuar sin código
if st.button(t["sin_codigo"], use_container_width=False):
    st.session_state.tier_activo = "free"

# Mostrar tier activo
tier_key   = st.session_state.tier_activo
tier_info  = TIERS[tier_key]
tier_color = tier_info["color"]

st.markdown(f"""
<div style='padding:10px 16px; background:{tier_color}18; border-left:4px solid {tier_color};
     border-radius:6px; margin:8px 0;'>
    <b style='color:{tier_color};'>{t['tier_activo']} {tier_info['nombre']} — {tier_info['precio']}</b>
    &nbsp;·&nbsp; {tier_info['pdf_paginas']}
    &nbsp;·&nbsp; Top {tier_info['top_negocios']} negocios
    &nbsp;·&nbsp; {tier_info['competidores_mostrados']} competidores
    {'&nbsp;·&nbsp; ✅ Demografía' if tier_info['muestra_demografia'] else ''}
    {'&nbsp;·&nbsp; ✅ Desglose score' if tier_info['muestra_score_desglose'] else ''}
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── INPUT DE UBICACIÓN ──────────────────────
st.markdown(f"### {t['input_ubicacion']}")
direccion_texto = st.text_input("", placeholder=t["placeholder_direccion"],
                                 key="direccion_input", label_visibility="collapsed")

# Mapa interactivo Folium
st.markdown(f"**{'O haz click en el mapa:' if idioma == 'es' else 'Or click on the map:'}**")
try:
    import folium
    from streamlit_folium import st_folium

    m = folium.Map(location=[19.432608, -99.133209], zoom_start=12)
    m.add_child(folium.LatLngPopup())
    mapa_data = st_folium(m, width=700, height=350, key="mapa_folium")

    lat_mapa, lng_mapa, direccion_mapa = None, None, None
    if mapa_data and mapa_data.get("last_clicked"):
        lat_mapa = mapa_data["last_clicked"]["lat"]
        lng_mapa = mapa_data["last_clicked"]["lng"]
        direccion_mapa = geocodificar_inversa(lat_mapa, lng_mapa)
        st.success(f"📍 {'Seleccionado' if idioma == 'es' else 'Selected'}: {direccion_mapa}")
except ImportError:
    st.caption("💡 `pip install folium streamlit-folium` para habilitar el mapa interactivo")
    lat_mapa, lng_mapa, direccion_mapa = None, None, None

st.markdown("---")

# Modo de análisis — "Descubrir negocio" solo desde Basic+
st.markdown(f"### {t['modo_analisis']}")
if tier_key == "free":
    modo = "validar"
    st.radio("", options=["validar"],
             format_func=lambda x: t["modo_validar"],
             horizontal=True)
    st.caption("🔒 Modo **Descubrir qué negocio es mejor** disponible desde plan Básico ($99 MXN)")
else:
    modo = st.radio("", options=["validar", "recomendar"],
                    format_func=lambda x: t["modo_validar"] if x == "validar" else t["modo_recomendar"],
                    horizontal=True)

tipo_negocio_seleccionado = None
if modo == "validar":
    st.markdown(f"**{t['selecciona_tipo']}**")
    tipo_negocio_seleccionado = st.selectbox("", options=list(TIPOS_NEGOCIO.keys()),
                                              format_func=lambda x: TIPOS_NEGOCIO[x]["nombre"])

st.markdown("---")

# ── BOTÓN ANALIZAR ──────────────────────────
if st.button(t["boton_analizar"], type="primary", use_container_width=True):

    # Prioridad: click en mapa > texto
    if 'lat_mapa' in dir() and lat_mapa and lng_mapa:
        lat, lng  = lat_mapa, lng_mapa
        ubicacion = direccion_mapa or f"{lat:.6f}, {lng:.6f}"
    elif direccion_texto:
        lat, lng  = geocodificar_direccion(direccion_texto)
        ubicacion = direccion_texto
    else:
        st.error("Por favor ingresa una ubicación o haz click en el mapa." if idioma == "es"
                 else "Please enter a location or click on the map.")
        st.stop()

    if not lat or not lng:
        st.error("No se pudo geocodificar la ubicación." if idioma == "es" else "Could not geocode the location.")
        st.stop()

    with st.spinner("🔍 Analizando ubicación..."):

        # Obtener contexto y demografía
        contexto   = detectar_contexto_ubicacion(lat, lng, ubicacion)
        demografia = obtener_demografia(lat, lng, ubicacion)

        if modo == "validar":
            competidores = buscar_competencia_por_tipo(lat, lng, tipo_negocio_seleccionado)
            score_base, desglose = calcular_score_competencia(competidores, tipo_negocio_seleccionado)
            score_ctx   = ajustar_score_por_contexto(score_base, tipo_negocio_seleccionado, contexto)
            score       = ajustar_score_por_demografia(score_ctx, tipo_negocio_seleccionado, demografia)
            analisis    = generar_analisis_claude(ubicacion, competidores, idioma, "validar",
                                                  tipo_negocio=tipo_negocio_seleccionado)
            recomendaciones = None
            tipo_negocio_top1 = tipo_negocio_seleccionado
        else:
            recomendaciones, contexto, demografia = recomendar_tipos_negocio(lat, lng, ubicacion)
            competidores = recomendaciones[0]["competidores"] if recomendaciones else []
            score        = recomendaciones[0]["score"] if recomendaciones else 0
            desglose     = recomendaciones[0]["desglose"] if recomendaciones else {}
            tipo_negocio_top1 = recomendaciones[0]["tipo_key"] if recomendaciones else None
            analisis     = generar_analisis_claude(ubicacion, [], idioma, "recomendar",
                                                   recomendaciones=recomendaciones)

    # Guardar resultados en session_state para evitar re-run al interactuar con mapas
    st.session_state.resultados = {
        "ubicacion": ubicacion, "lat": lat, "lng": lng,
        "score": score, "desglose": desglose, "analisis": analisis,
        "competidores": competidores, "contexto": contexto,
        "demografia": demografia, "recomendaciones": recomendaciones,
        "modo": modo, "tipo_negocio": tipo_negocio_seleccionado,
        "tipo_negocio_top1": tipo_negocio_top1, "idioma": idioma,
    }

# ── Recuperar resultados de session_state si existen ──────────────
if "resultados" in st.session_state:
    _r = st.session_state.resultados
    ubicacion            = _r["ubicacion"]
    lat                  = _r["lat"]
    lng                  = _r["lng"]
    score                = _r["score"]
    desglose             = _r["desglose"]
    analisis             = _r["analisis"]
    competidores         = _r["competidores"]
    contexto             = _r["contexto"]
    demografia           = _r["demografia"]
    recomendaciones      = _r["recomendaciones"]
    modo                 = _r["modo"]
    tipo_negocio_seleccionado = _r["tipo_negocio"]
    tipo_negocio_top1    = _r.get("tipo_negocio_top1")
    idioma               = _r["idioma"]
    t                    = TEXTOS[idioma]
    tier_key             = st.session_state.tier_activo
    tier_info            = TIERS[tier_key]

    # ──────────────────────────────────────────
    # RESULTADOS EN PANTALLA
    # ──────────────────────────────────────────
    st.markdown(f"## {t['titulo_analisis']}")
    if modo == "validar":
        st.markdown(f"### {TIPOS_NEGOCIO[tipo_negocio_seleccionado]['nombre']}")

    # Características de la zona (Basic+)
    if tier_info["muestra_badges"] and contexto.get("badges"):
        st.markdown("**📍 Características de la zona:**")
        BADGE_DESC = {
            "🚗 Alto tráfico vehicular": "La ubicación está sobre una vialidad de alto flujo — ideal para negocios de paso",
            "⛽ Gasolinera cercana":      "Presencia de gasolinera en 500m — atrae tráfico vehicular constante",
            "🏬 Plaza comercial":         "Plaza o centro comercial cercano — genera tráfico de shoppers",
            "🏥 Hospital cercano":        "Hospital o clínica en 500m — clientela cautiva y tráfico constante",
            "🎓 Escuela/Universidad":     "Institución educativa en 500m — alto flujo estudiantil",
            "🚌 Transporte público":      "Estación de transporte cercana — alta accesibilidad peatonal",
        }
        chips_html = "<div style='display:flex; flex-wrap:wrap; gap:8px; margin:8px 0;'>"
        for badge in contexto["badges"]:
            desc = BADGE_DESC.get(badge, "Característica detectada en la zona")
            chips_html += f"""
            <div title='{desc}' style='
                background:#E3F2FD; border:1px solid #1976D2; border-radius:20px;
                padding:6px 14px; font-size:13px; color:#1565C0; cursor:help;
                font-weight:500;'>{badge}</div>"""
        chips_html += "</div>"
        chips_html += "<p style='font-size:11px; color:#888; margin:0;'>💡 Pasa el cursor sobre cada chip para ver su significado</p>"
        st.markdown(chips_html, unsafe_allow_html=True)
        st.markdown("") 

    # Score visual
    nivel, color = nivel_score(score, idioma)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style='text-align:center; padding:25px; background:linear-gradient(135deg,{color}22 0%,{color}44 100%);
             border-radius:15px; border:3px solid {color};'>
            <h1 style='color:{color}; font-size:72px; margin:0;'>{score}</h1>
            <p style='color:#555; font-size:16px; margin:4px 0;'>{t['score_viabilidad']}</p>
            <b style='color:{color}; font-size:18px;'>{nivel}</b>
        </div>""", unsafe_allow_html=True)

    # Desglose score (Basic+)
    if tier_info["muestra_score_desglose"] and desglose:
        st.markdown(f"#### {t['desglose_score']}")

        # Definir interpretaciones dinámicas
        def _interp_factor(valor, tipo):
            if tipo == "densidad":
                if valor >= 80: return "✅ Poca competencia — mercado libre"
                elif valor >= 60: return "🟡 Competencia moderada"
                elif valor >= 40: return "🟠 Zona saturada"
                else: return "🔴 Alta saturación"
            elif tipo == "calidad":
                if valor >= 80: return "✅ Competidores débiles — oportunidad"
                elif valor >= 60: return "🟡 Calidad media en la zona"
                elif valor >= 40: return "🟠 Competidores bien calificados"
                else: return "🔴 Competencia muy fuerte"
            elif tipo == "consolidacion":
                if valor >= 80: return "✅ Mercado joven — fácil de ganar"
                elif valor >= 60: return "🟡 Mercado en desarrollo"
                elif valor >= 40: return "🟠 Mercado establecido"
                else: return "🔴 Mercado muy consolidado"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(
                "Densidad de competencia (50%)",
                f"{desglose['densidad']}/100",
                help="Cuántos negocios similares hay en 500m. Mayor puntaje = menos competidores = más oportunidad."
            )
            st.caption(_interp_factor(desglose['densidad'], 'densidad'))
        with c2:
            st.metric(
                "Calidad de competencia (30%)",
                f"{desglose['calidad']}/100",
                help="Rating promedio de los competidores. Mayor puntaje = competidores con rating bajo = mercado insatisfecho."
            )
            st.caption(_interp_factor(desglose['calidad'], 'calidad'))
        with c3:
            st.metric(
                "Consolidación del mercado (20%)",
                f"{desglose['consolidacion']}/100",
                help="Volumen de reseñas de los competidores. Mayor puntaje = mercado joven con pocos reviews = más fácil de entrar."
            )
            st.caption(_interp_factor(desglose['consolidacion'], 'consolidacion'))
    elif not tier_info["muestra_score_desglose"]:
        st.caption("🔒 Desglose del score disponible en plan Básico ($99)")

    st.markdown("---")

    # ── RESUMEN / DIAGNÓSTICO según tier ──────────────────────────
    if tier_key == "free":
        # Free: resumen ejecutivo simple
        st.markdown("### 📋 Resumen Ejecutivo")
        if modo == "validar":
            st.markdown(analisis)
    else:
        # Basic+: Recomendación Final completo al FINAL (se agrega después)
        pass

    if modo == "validar" and tier_key != "free":
        with st.expander("📋 Ver análisis de competencia", expanded=False):
            st.markdown(analisis)
    elif modo != "validar":
        # Recomendador — mostrar top N según tier
        top_n = tier_info["top_negocios"]
        st.markdown(f"#### {t['top_recomendaciones']}")
        for i, rec in enumerate(recomendaciones[:top_n]):
            nivel_r, color_r = nivel_score(rec['score'], idioma)
            with st.expander(f"#{i+1} {rec['nombre']} — Score: {rec['score']}/100", expanded=(i==0)):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"""
                    <div style='padding:12px; background:{color_r}18; border-left:4px solid {color_r}; border-radius:5px;'>
                        <h2 style='color:{color_r}; margin:0;'>{rec['score']}/100</h2>
                        <p style='margin:4px 0;'>{rec['descripcion']}</p>
                    </div>""", unsafe_allow_html=True)
                    if i == 0: st.success(f"⭐ {t['mejor_opcion']}")
                    st.markdown(f"**Competidores encontrados:** {rec['num_competidores']}")
                with c2:
                    st.markdown(f"**{t['inversion_estimada']}:**")
                    st.markdown(f"${rec['inversion_min']//1000}K – ${rec['inversion_max']//1000}K MXN")

        if len(recomendaciones) > top_n:
            st.caption(f"🔒 Actualiza para ver los {len(recomendaciones) - top_n} tipos de negocio restantes")

        st.markdown("---")
        st.markdown(f"### 🤖 {t['resumen']}")
        st.markdown(analisis)

        # Negocios a evitar
        st.markdown(f"### {t['evitar']}")
        evitar_data = [{"Tipo": r['nombre'], "Score": f"{r['score']}/100"} for r in recomendaciones[-3:]]
        st.dataframe(evitar_data, use_container_width=True)

    st.markdown("---")

    # Competidores
    if competidores:
        n_mostrados = tier_info["competidores_mostrados"]
        st.markdown(f"### {t['competencia_titulo']}")
        comp_data = []
        for comp in competidores[:n_mostrados]:
            comp_data.append({
                t["tabla_nombre"]:  comp.get('displayName', {}).get('text', 'N/A'),
                t["tabla_rating"]:  f"{comp.get('rating','N/A')}★" if comp.get('rating') else 'N/A',
                t["tabla_reseñas"]: comp.get('userRatingCount', 0)
            })
        st.dataframe(comp_data, use_container_width=True)
        if len(competidores) > n_mostrados:
            st.caption(f"🔒 Mostrando {n_mostrados} de {len(competidores)} — actualiza tu plan para ver todos")

    st.markdown("---")

    # Demografía — free básico, Basic+ completo
    st.markdown(f"### {t['demografía']}")
    st.caption(t["datos_estimados"])
    densidad_info = formatear_densidad(demografia['densidad_hab_km2'])

    if tier_info["muestra_demografia"]:
        # Basic+: datos completos con INEGI
        fuente = demografia.get('fuente', 'Estimación por zona')
        st.caption(f"📊 Fuente: {fuente}")

        c1, c2, c3, c4 = st.columns(4)
        pob_actual = demografia.get('poblacion_actual', demografia.get('poblacion_estimada', 0))
        pob_2020   = demografia.get('poblacion_2020', 0)
        delta_pob  = f"+{pob_actual - pob_2020:,}" if pob_2020 else None

        c1.metric("👥 Población " + str(datetime.datetime.now().year),
                  f"{pob_actual:,} hab", delta_pob)
        c2.metric("🏠 Viviendas habitadas",
                  f"{demografia.get('viviendas_actual', demografia.get('viviendas_habitadas',0)):,}")
        c3.metric("🏙️ Densidad",
                  densidad_info.get('nivel', densidad_info.get('clasificacion','N/A')))
        c4.metric("📐 Aprox/manzana",
                  f"~{demografia.get('personas_manzana', densidad_info.get('personas_manzana',0))} personas")

        st.caption(densidad_info.get('descripcion',''))

        # NSE + ingreso + gasto — tarjetas visuales
        st.markdown("---")
        st.markdown("**💰 Perfil Económico del Área**")
        e1, e2, e3, e4 = st.columns(4)
        nse = demografia.get('nse_predominante','C')
        nse_colores = {"A":"#7B1FA2","A/B":"#9C27B0","B":"#1976D2","B/C+":"#0097A7",
                       "C+":"#2E7D32","C":"#558B2F","C/D+":"#F57F17","D+":"#E65100","D/E":"#B71C1C"}
        nse_color = nse_colores.get(nse, "#555555")
        e1.markdown(f"""<div style='background:{nse_color}18; border-left:3px solid {nse_color};
            padding:10px; border-radius:6px;'>
            <b style='color:{nse_color}; font-size:22px;'>{nse}</b><br>
            <span style='font-size:11px; color:#666;'>NSE Predominante</span></div>""",
            unsafe_allow_html=True)
        e2.metric("💵 Ingreso prom/mes",
                  f"${demografia.get('ingreso_actual', demografia.get('ingreso_promedio_mensual',0)):,}")
        e3.metric("🛒 Gasto prom/mes",
                  f"${demografia.get('gasto_actual', demografia.get('gasto_promedio_mensual',0)):,}")
        tasa = demografia.get('tasa_crecimiento_pct', 0.55)
        e4.metric("📈 Crec. anual zona", f"{tasa:.2f}%")

        if tier_key in ["pro", "premium"]:
            fuente_str = demografia.get('fuente', 'INEGI Censo 2020 · Proyección CONAPO') if demografia else ''
            if fuente_str:
                st.caption(f"📊 Fuente: {fuente_str}")
    else:
        # Free: solo básico
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Población",     f"{demografia.get('poblacion_estimada',0):,} hab")
        c2.metric("Viviendas",     f"{demografia.get('viviendas_habitadas',0):,}")
        c3.metric("Densidad",      densidad_info.get('nivel', densidad_info.get('clasificacion','N/A')))
        c4.metric("Aprox/manzana", f"~{demografia.get('personas_manzana', densidad_info.get('personas_manzana',0))} personas")
        st.caption(densidad_info.get('descripcion',''))
        st.caption("🔒 NSE, ingreso promedio y análisis completo disponibles en plan Básico ($99 MXN)")

    # ── PRO: Tráfico + Mercado + Forecast ──────────────────────────
    # Se muestra tanto en "validar" como en "recomendar" (usando el #1 recomendado)
    tipo_para_pro = tipo_negocio_seleccionado if modo == "validar" else (
        tipo_negocio_top1 if 'tipo_negocio_top1' in dir() else None)
    if tier_key in ["pro", "premium"] and MODULOS_OK and tipo_para_pro:
        st.markdown("---")

        tipo_zona = contexto.get("tipo_zona", "mixto")
        densidad_a = demografia.get("densidad_actual", demografia.get("densidad_hab_km2", 8000))

        # Mostrar qué negocio se usa como base si es modo recomendar
        if modo == "recomendar" and recomendaciones:
            top1 = recomendaciones[0]
            st.info(f"📊 Análisis PRO basado en tu negocio con mayor oportunidad: **{top1['nombre']}** (Score: {top1['score']}/100)")

        # ── TRÁFICO ──
        st.markdown("### 🚗 Análisis de Tráfico Estimado")
        trafico_data = generar_reporte_trafico(tipo_zona, tipo_para_pro, densidad_a)

        t1, t2, t3 = st.columns(3)
        t1.metric("📊 Flujo general",   trafico_data["nivel_general"])
        t2.metric("📅 Mejor día",        trafico_data["dia_pico"])
        t3.metric("📅 Día más bajo",     trafico_data["dia_bajo"])

        st.markdown("**🕐 Horas pico para tu tipo de negocio:**")
        for pico in trafico_data["horas_pico"]:
            color_p = "#4CAF50" if pico["flujo"] >= 80 else "#FFC107" if pico["flujo"] >= 60 else "#9E9E9E"
            st.markdown(f"""<div style='display:inline-block; margin:4px; padding:8px 16px;
                background:{color_p}22; border:1px solid {color_p}; border-radius:8px; font-size:13px;'>
                <b>{pico["hora_str"]}</b> — {pico["nivel"]} ({pico["flujo"]}%)
                </div>""", unsafe_allow_html=True)
        st.markdown("")

        # Gráfica horaria con barras ASCII → visual con HTML
        st.markdown("**📈 Perfil de flujo horario (0h – 23h):**")
        horas_html = "<div style='display:flex; align-items:flex-end; gap:2px; height:80px; margin:8px 0;'>"
        for hora, val in enumerate(trafico_data["trafico_horario"]):
            color_b = "#0047AB" if val >= 70 else "#00D4D4" if val >= 45 else "#E0E0E0"
            tooltip = f"{hora:02d}h: {val}%"
            horas_html += f"""<div title='{tooltip}' style='
                flex:1; background:{color_b}; height:{val}%;
                border-radius:2px 2px 0 0; min-height:3px;'></div>"""
        horas_html += "</div>"
        horas_html += "<div style='display:flex; justify-content:space-between; font-size:10px; color:#888;'><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div>"
        st.markdown(horas_html, unsafe_allow_html=True)

        # Tráfico semanal
        st.markdown("**📅 Flujo por día de la semana:**")
        dias_html = "<div style='display:flex; gap:6px; margin:8px 0;'>"
        for i, (dia, val) in enumerate(zip(DIAS_SEMANA, trafico_data["trafico_semanal"])):
            color_d = "#0047AB" if val >= 85 else "#00D4D4" if val >= 65 else "#E0E0E0"
            txt_color = "white" if val >= 65 else "#555"
            dias_html += f"""<div style='flex:1; background:{color_d}; color:{txt_color};
                text-align:center; padding:8px 4px; border-radius:6px; font-size:11px; font-weight:bold;'>
                {dia[:3]}<br><span style='font-size:13px;'>{val}%</span></div>"""
        dias_html += "</div>"
        st.markdown(dias_html, unsafe_allow_html=True)
        st.caption("⚠️ Estimación basada en perfil de zona + tipo de negocio. No refleja datos de tráfico en tiempo real.")

        st.markdown("---")

        # ── MERCADO POTENCIAL ──
        st.markdown("### 📊 Tamaño de Mercado Potencial")
        mercado = calcular_mercado_potencial(demografia, tipo_para_pro, len(competidores))

        m1, m2, m3 = st.columns(3)
        m1.metric("🏪 Mercado total área/mes", f"${mercado['mercado_total_mensual']:,}")
        m2.metric(f"🎯 Tu captura estimada ({mercado['factor_captura_pct']:.0f}%)",
                  f"${mercado['mercado_captura_mensual']:,}/mes")
        m3.metric("👤 Clientes/día estimados", str(mercado["clientes_dia_estimados"]))
        st.caption(f"📐 Metodología: {mercado['metodologia']}")

        st.markdown("---")

        # ── FORECAST ──
        tipo_info_fc = TIPOS_NEGOCIO[tipo_para_pro]
        forecast = generar_forecast(mercado, tipo_para_pro, score,
                                    tipo_info_fc["inversion_min"])
        roi_data = calcular_roi(forecast, tipo_info_fc["inversion_min"],
                                tipo_info_fc["inversion_max"], tipo_para_pro)

        st.markdown("### 📈 Forecast de Ventas — 12 Meses (3 Escenarios)")
        f1, f2, f3 = st.columns(3)

        for col, escenario, color_e, emoji_e in [
            (f1, "pesimista", "#F44336", "🔴"),
            (f2, "base",      "#2196F3", "🔵"),
            (f3, "optimista", "#4CAF50", "🟢"),
        ]:
            datos_e = forecast["escenarios"][escenario]
            col.markdown(f"""<div style='background:{color_e}11; border:1px solid {color_e};
                border-radius:10px; padding:14px; text-align:center;'>
                <div style='font-size:13px; color:{color_e}; font-weight:bold;'>{emoji_e} {escenario.upper()}</div>
                <div style='font-size:22px; font-weight:bold; color:{color_e}; margin:6px 0;'>
                    ${datos_e["total_anual"]:,}</div>
                <div style='font-size:11px; color:#666;'>año 1 total</div>
                <div style='font-size:13px; margin-top:6px;'>
                    ${datos_e["promedio_mensual"]:,}/mes prom.</div>
                </div>""", unsafe_allow_html=True)

        # Gráfica de barras 12 meses
        st.markdown("**Ventas mensuales — escenario base:**")
        meses = forecast["escenarios"]["base"]["ventas_mensuales"]
        max_v = max(meses) or 1
        bars_html = "<div style='display:flex; align-items:flex-end; gap:3px; height:70px; margin:8px 0;'>"
        for i, v in enumerate(meses):
            pct = int(v / max_v * 100)
            bars_html += f"""<div style='flex:1; display:flex; flex-direction:column; align-items:center;'>
                <div style='background:#0047AB; width:100%; height:{pct}%; border-radius:3px 3px 0 0; min-height:3px;'></div>
                <div style='font-size:9px; color:#888; margin-top:2px;'>M{i+1}</div></div>"""
        bars_html += "</div>"
        st.markdown(bars_html, unsafe_allow_html=True)

        with st.expander("📋 Supuestos del forecast"):
            for sup in forecast["supuestos"]:
                st.caption(f"• {sup}")

        st.markdown("---")

        # ── ROI ── (PREMIUM)
        if tier_key == "premium":
            st.markdown("### 💰 ROI + Punto de Equilibrio")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("📊 ROI estimado 12m", f"{roi_data['roi_12m_pct']}%")
            r2.metric("⏱️ Recuperación est.", f"{roi_data['meses_recuperacion']} meses")
            r3.metric("💵 Utilidad mensual est.", f"${roi_data['utilidad_mensual_est']:,}")
            r4.metric("⚖️ Punto de equilibrio", f"${roi_data['punto_eq_ventas_mes']:,}/mes")
            st.markdown(f"**Clasificación:** {roi_data['clasificacion_roi']}")
            st.caption("⚠️ Estimaciones con supuestos estándar. Los resultados reales dependen de gestión, producto y mercado.")

    # ── MAPAS AVANZADOS (PRO y PREMIUM) — fuera del bloque de cálculo ──
    if tier_key in ["pro", "premium"]:
        st.markdown("---")
        st.markdown("### 🗺️ Mapas Avanzados")
        # Asegurar que competidores y coordenadas están disponibles
        _comp_mapas = competidores or []
        _tipo_mapas = (tipo_para_pro if 'tipo_para_pro' in dir() and tipo_para_pro
                       else tipo_negocio_seleccionado or
                       (recomendaciones[0]['tipo_key'] if recomendaciones else None))

        if MAPAS_OK and lat and lng:
            tab_comp, tab_heat, tab_iso, tab_cani = st.tabs([
                "📍 Competidores", "🔥 Heatmap", "⏱️ Isócronas", "⚠️ Canibalización"
            ])

            with tab_comp:
                st.caption("Competidores coloreados por rating en tu radio de 500m")
                try:
                    tipo_nombre_m = TIPOS_NEGOCIO.get(_tipo_mapas, {}).get('nombre','') if _tipo_mapas else ''
                    mapa_c, interp_c = crear_mapa_competidores(
                        lat, lng, _comp_mapas, tipo_nombre_m, idioma)
                    render_mapa_con_interpretacion(mapa_c, interp_c, altura=420)
                except Exception as e_mc:
                    st.error(f"Error en mapa de competidores: {e_mc}")

            with tab_heat:
                st.caption("Densidad de competencia ponderada por rating y número de reseñas")
                try:
                    mapa_h, interp_h = crear_heatmap_competencia(lat, lng, _comp_mapas, idioma)
                    render_mapa_con_interpretacion(mapa_h, interp_h, altura=420)
                except Exception as e_mh:
                    st.error(f"Error en heatmap: {e_mh}")

            with tab_iso:
                perfil_iso = st.radio("Modo de desplazamiento:",
                    ["foot-walking", "driving-car"],
                    format_func=lambda x: "🚶 A pie" if x == "foot-walking" else "🚗 En auto",
                    horizontal=True, key="radio_iso")
                if not ORS_API_KEY:
                    st.info("💡 Mostrando isócronas estimadas por distancia. Para isócronas reales "
                            "por red vial agrega `ORS_API_KEY` a tu `.env` (gratis en openrouteservice.org).")
                try:
                    mapa_iso, interp_iso = crear_mapa_isocronas(
                        lat, lng, ORS_API_KEY, [5, 10, 15], perfil_iso, _comp_mapas, idioma)
                    render_mapa_con_interpretacion(mapa_iso, interp_iso, altura=420)
                except Exception as e_iso:
                    st.error(f"Error en isócronas: {e_iso}")

            with tab_cani:
                st.caption("Identifica competidores que comparten tu área de influencia inmediata")
                try:
                    mapa_cani, interp_cani, datos_cani = crear_mapa_canibalizacion(
                        lat, lng, _comp_mapas, 500, idioma)
                    render_mapa_con_interpretacion(mapa_cani, interp_cani, altura=400)
                    if datos_cani["muy_cercanos"]:
                        st.markdown("**⚠️ Competidores críticos (≤150m) — riesgo alto de canibalización:**")
                        crit_data = [{
                            "Nombre": c.get('displayName',{}).get('text','N/A')[:25],
                            "Distancia": f"{c.get('_distancia_m',0)}m",
                            "Rating": c.get('rating','N/A'),
                            "Reseñas": c.get('userRatingCount',0)
                        } for c in datos_cani["muy_cercanos"]]
                        st.dataframe(crit_data, use_container_width=True)
                    elif not datos_cani["muy_cercanos"] and not datos_cani["cercanos"]:
                        st.success("✅ Sin riesgo de canibalización — no hay competidores directos en los primeros 300m")
                except Exception as e_cani:
                    st.error(f"Error en mapa de canibalización: {e_cani}")
        elif not MAPAS_OK:
            st.warning("Instala `streamlit-folium` para ver mapas avanzados: `pip install streamlit-folium folium`")

    # ── COMPARATIVA (solo PREMIUM) ──
    if tier_key == "premium":
        st.markdown("---")
        st.markdown("### 🗺️ Comparativa de Ubicaciones")
        st.caption("Analiza hasta 3 ubicaciones en paralelo y encuentra la mejor opción.")

        if "ubicaciones_comparativa" not in st.session_state:
            st.session_state.ubicaciones_comparativa = []

        with st.expander("➕ Agregar ubicaciones para comparar", expanded=True):
            col_a, col_b = st.columns([3,1])
            with col_a:
                nueva_ub = st.text_input("Dirección adicional a comparar:",
                    placeholder="Ej: Av. Reforma 222, CDMX", key="nueva_ub_input")
            with col_b:
                if st.button("Agregar", key="btn_agregar_ub"):
                    if not nueva_ub:
                        st.warning("Escribe una dirección primero")
                    elif len(st.session_state.ubicaciones_comparativa) >= 2:
                        st.warning("Máximo 2 ubicaciones adicionales (3 en total)")
                    else:
                        with st.spinner(f"Analizando {nueva_ub[:30]}..."):
                            try:
                                lat2, lng2 = geocodificar_direccion(nueva_ub)
                                if not lat2 or not lng2:
                                    st.error("No se pudo geocodificar la dirección")
                                else:
                                    # Tipo de negocio para comparar
                                    tipo_comp = tipo_para_pro if 'tipo_para_pro' in dir() else tipo_negocio_seleccionado
                                    dem2   = obtener_demografia(lat2, lng2, nueva_ub)
                                    comps2 = buscar_competencia_por_tipo(lat2, lng2, tipo_comp) if tipo_comp else []
                                    score2_b, desglose2 = calcular_score_competencia(comps2, tipo_comp) if (tipo_comp and comps2) else (0, {})
                                    ctx2   = detectar_contexto_ubicacion(lat2, lng2, nueva_ub)
                                    score2_c = ajustar_score_por_contexto(score2_b, tipo_comp, ctx2) if tipo_comp else score2_b
                                    score2   = ajustar_score_por_demografia(score2_c, tipo_comp, dem2) if tipo_comp else score2_c
                                    st.session_state.ubicaciones_comparativa.append({
                                        "nombre": nueva_ub[:25],
                                        "score": score2,
                                        "densidad_comp": desglose2.get("densidad", 0),
                                        "calidad_comp":  desglose2.get("calidad", 0),
                                        "consolidacion": desglose2.get("consolidacion", 0),
                                        "poblacion":     dem2.get("poblacion_actual", dem2.get("poblacion_estimada", 0)),
                                        "nse":           dem2.get("nse_predominante", "C"),
                                        "ingreso":       dem2.get("ingreso_actual", dem2.get("ingreso_promedio_mensual", 0)),
                                        "num_competidores": len(comps2),
                                    })
                                    st.success(f"✅ Agregada: {nueva_ub[:30]} — Score: {score2}/100")
                                    st.rerun()
                            except Exception as e_comp:
                                st.error(f"Error al analizar: {e_comp}")

        # Mostrar comparativa si hay ubicaciones
        todas_ubs = [{
            "nombre": ubicacion[:25],
            "score": score,
            "densidad_comp": desglose.get("densidad",0),
            "calidad_comp": desglose.get("calidad",0),
            "consolidacion": desglose.get("consolidacion",0),
            "poblacion": demografia.get("poblacion_actual", demografia.get("poblacion_estimada",0)),
            "nse": demografia.get("nse_predominante","C"),
            "ingreso": demografia.get("ingreso_actual", demografia.get("ingreso_promedio_mensual",0)),
            "num_competidores": len(competidores),
        }] + st.session_state.ubicaciones_comparativa

        if len(todas_ubs) > 1 and GRAFICAS_OK:
            try:
                graf_comp = grafica_comparativa(todas_ubs)
                if graf_comp:
                    st.image(graf_comp, use_container_width=True,
                             caption="Análisis comparativo — radar y barras por ubicación")
            except Exception as e_graf:
                st.caption(f"Gráfica comparativa no disponible: {e_graf}")

            # Tabla resumen
            comp_table_data = []
            for ub in todas_ubs:
                nivel_c, _ = nivel_score(ub['score'], idioma)
                comp_table_data.append({
                    "Ubicación": ub['nombre'],
                    "Score": f"{ub['score']}/100",
                    "Nivel": nivel_c,
                    "Competidores": ub['num_competidores'],
                    "NSE": ub['nse'],
                    "Ingreso prom": f"${ub['ingreso']:,}",
                })
            st.dataframe(comp_table_data, use_container_width=True)

            # Recomendación automática
            mejor = max(todas_ubs, key=lambda x: x['score'])
            st.success(f"✅ **Recomendación:** La mejor ubicación es **{mejor['nombre']}** con score {mejor['score']}/100")

        if st.button("🗑️ Limpiar comparativa", key="btn_limpiar"):
            st.session_state.ubicaciones_comparativa = []
            st.rerun()

    st.markdown("---")

    # ── DIAGNÓSTICO COMERCIAL AL FINAL (Basic, PRO, PREMIUM) ──────
    if tier_key != "free":
        st.markdown("### ✅ Recomendación Final")

        _trafico_diag = _mercado_diag = _forecast_diag = _roi_diag = None
        if tier_key in ["pro", "premium"] and MODULOS_OK:
            _tipo_diag = tipo_para_pro if 'tipo_para_pro' in dir() and tipo_para_pro else tipo_negocio_seleccionado
            if _tipo_diag:
                try:
                    _tz  = contexto.get("tipo_zona", "mixto")
                    _den = demografia.get("densidad_actual", demografia.get("densidad_hab_km2", 8000))
                    _trafico_diag  = generar_reporte_trafico(_tz, _tipo_diag, _den)
                    _mercado_diag  = calcular_mercado_potencial(demografia, _tipo_diag, len(competidores))
                    _tipo_info_d   = TIPOS_NEGOCIO.get(_tipo_diag, {})
                    _forecast_diag = generar_forecast(_mercado_diag, _tipo_diag, score,
                                                       _tipo_info_d.get("inversion_min", 300000))
                    _roi_diag      = calcular_roi(_forecast_diag,
                                                   _tipo_info_d.get("inversion_min", 300000),
                                                   _tipo_info_d.get("inversion_max", 600000), _tipo_diag)
                except:
                    pass

        with st.spinner("🏆 Generando Recomendación Final..."):
            diagnostico = generar_recomendacion_final(
                ubicacion=ubicacion, score=score, desglose=desglose,
                competidores=competidores, demografia=demografia,
                contexto=contexto, idioma=idioma, tier_key=tier_key, modo=modo,
                tipo_negocio=tipo_negocio_seleccionado if modo == "validar" else None,
                recomendaciones=recomendaciones,
                trafico_data=_trafico_diag, mercado_data=_mercado_diag,
                forecast_data=_forecast_diag, roi_data=_roi_diag,
            )

        # Renderizar con estilo destacado
        import re as _re
        def md_to_html(txt):
            # Convierte **texto** a <b>texto</b> y saltos de línea a <br>
            txt = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', txt)
            txt = txt.replace('\n', '<br>')
            return txt

        st.markdown(f"""
        <div style='background:linear-gradient(135deg,#0047AB08 0%,#00D4D415 100%);
             border:2px solid #0047AB55; border-radius:12px;
             padding:22px 26px; margin:10px 0;'>
        {md_to_html(diagnostico)}
        </div>""", unsafe_allow_html=True)

        st.markdown("---")

    # ── DESCARGA PDF ──
    pdf_kwargs = dict(
        ubicacion=ubicacion, score=score, desglose=desglose,
        analisis=analisis, competidores=competidores,
        idioma=idioma, lat=lat, lng=lng, modo=modo,
        tipo_negocio=tipo_negocio_seleccionado,
        recomendaciones=recomendaciones,
        demografia=demografia, contexto=contexto
    )
    # Pasar el diagnóstico al PDF para Basic+
    if tier_key != "free" and 'diagnostico' in dir():
        pdf_kwargs['analisis'] = diagnostico  # El PDF usa el diagnóstico como texto principal
    pdf_buffer = generar_pdf_por_tier(tier_key, **pdf_kwargs)

    st.download_button(
        label=t["descargar_pdf"],
        data=pdf_buffer,
        file_name=f"4site_{tier_key}_{ubicacion[:20].replace(' ','_')}.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary"
    )

# ── CTA BOTTOM ──────────────────────────────
st.markdown("---")
st.markdown(f"""
<div style='text-align:center; padding:35px; background:linear-gradient(135deg,#0047AB 0%,#00D4D4 100%);
     border-radius:15px; color:white;'>
    <h2>{t['cta_titulo']}</h2>
    <p style='font-size:16px;'>{t['cta_intro']}</p>
    <table style='margin:0 auto; text-align:left; color:white; font-size:14px;'>
        <tr><td>✅ <b>Básico $99</b></td><td>&nbsp;→ Análisis completo + demografía + 6 págs PDF</td></tr>
        <tr><td>🚀 <b>PRO $299</b></td><td>&nbsp;→ Mapa con competidores + forecast + mercado</td></tr>
        <tr><td>💎 <b>PREMIUM $999</b></td><td>&nbsp;→ ROI + comparativa + dashboard interactivo</td></tr>
    </table>
    <p style='font-size:13px; margin-top:15px; opacity:0.9;'>📧 hola@4site.mx</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.markdown(f"""
<div style='text-align:center; color:#999; font-size:13px;'>
    {t['footer_derechos']}<br>{t['footer_contacto']}
</div>
""", unsafe_allow_html=True)