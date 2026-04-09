import streamlit as st
import googlemaps
import os
from anthropic import Anthropic
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import requests
from PIL import Image
import folium
from streamlit_folium import st_folium

# ============================================
# CONFIGURACIÓN
# ============================================

st.set_page_config(
    page_title="4SITE - Location Analysis",
    page_icon="📍",
    layout="wide"
)

# Google Analytics
GA_MEASUREMENT_ID = "G-WW1XFBQ1PN"

ga_script = f"""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA_MEASUREMENT_ID}');
</script>
"""

st.markdown(ga_script, unsafe_allow_html=True)

# APIs

# APIs - usando Streamlit Secrets
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    CLAUDE_API_KEY = st.secrets["CLAUDE_API_KEY"]
except:
    st.error("⚠️ API keys no configuradas. Configura los Secrets en Streamlit Cloud.")
    st.stop()

gmaps = googlemaps.Client(key=GOOGLE_API_KEY)
claude = Anthropic(api_key=CLAUDE_API_KEY)

# ============================================
# DEFINICIÓN DE TIPOS DE NEGOCIO
# ============================================

TIPOS_NEGOCIO = {
    "cafe_premium": {
        "nombre": "☕ Cafetería Premium/Specialty",
        "keywords": ["cafe", "coffee", "specialty coffee", "cafetería"],
        "inversion_min": 300000,
        "inversion_max": 600000,
        "competencia_optima": 2,
        "descripcion": "Café de especialidad, third wave, ambiente trendy"
    },
    "cafe_casual": {
        "nombre": "☕ Cafetería Casual/Cadena",
        "keywords": ["cafe", "coffee", "starbucks", "italian coffee"],
        "inversion_min": 400000,
        "inversion_max": 800000,
        "competencia_optima": 3,
        "descripcion": "Café estilo cadena, servicio rápido"
    },
    "restaurante_casual": {
        "nombre": "🍕 Restaurante Casual",
        "keywords": ["restaurant", "restaurante", "comida", "food"],
        "inversion_min": 500000,
        "inversion_max": 1000000,
        "competencia_optima": 4,
        "descripcion": "Restaurante familiar, menú variado"
    },
    "restaurante_fino": {
        "nombre": "🍽️ Restaurante Fino/Gourmet",
        "keywords": ["restaurant", "fine dining", "gourmet"],
        "inversion_min": 1000000,
        "inversion_max": 3000000,
        "competencia_optima": 1,
        "descripcion": "Alta cocina, experiencia premium"
    },
    "comida_rapida": {
        "nombre": "🌮 Comida Rápida/Fast Food",
        "keywords": ["fast food", "taco", "burger", "torta", "comida rápida"],
        "inversion_min": 200000,
        "inversion_max": 500000,
        "competencia_optima": 5,
        "descripcion": "Servicio rápido, alto volumen"
    },
    "gimnasio_boutique": {
        "nombre": "🏋️ Gimnasio Boutique/Crossfit",
        "keywords": ["gym", "gimnasio", "crossfit", "fitness boutique"],
        "inversion_min": 800000,
        "inversion_max": 1500000,
        "competencia_optima": 1,
        "descripcion": "Fitness especializado, clases grupales"
    },
    "gimnasio_regular": {
        "nombre": "🏋️ Gimnasio Regular/Cadena",
        "keywords": ["gym", "gimnasio", "fitness", "sportium"],
        "inversion_min": 1500000,
        "inversion_max": 3000000,
        "competencia_optima": 2,
        "descripcion": "Gym completo, equipamiento variado"
    },
    "farmacia": {
        "nombre": "💊 Farmacia",
        "keywords": ["pharmacy", "farmacia", "drogueria"],
        "inversion_min": 400000,
        "inversion_max": 800000,
        "competencia_optima": 2,
        "descripcion": "Venta de medicamentos y productos de salud"
    },
    "tienda_conveniencia": {
        "nombre": "🏪 Tienda de Conveniencia",
        "keywords": ["convenience store", "oxxo", "7-eleven", "minisuper"],
        "inversion_min": 300000,
        "inversion_max": 600000,
        "competencia_optima": 2,
        "descripcion": "Productos básicos 24/7"
    },
    "panaderia": {
        "nombre": "🥖 Panadería/Repostería",
        "keywords": ["bakery", "panaderia", "pastry", "reposteria"],
        "inversion_min": 250000,
        "inversion_max": 500000,
        "competencia_optima": 3,
        "descripcion": "Pan artesanal, pasteles, café"
    },
    "bar": {
        "nombre": "🍺 Bar/Cantina",
        "keywords": ["bar", "pub", "cantina", "cerveceria"],
        "inversion_min": 600000,
        "inversion_max": 1200000,
        "competencia_optima": 3,
        "descripcion": "Bebidas alcohólicas, ambiente social"
    },
    "yoga_wellness": {
        "nombre": "🧘 Yoga/Wellness Studio",
        "keywords": ["yoga", "wellness", "spa", "pilates"],
        "inversion_min": 400000,
        "inversion_max": 800000,
        "competencia_optima": 1,
        "descripcion": "Clases de yoga, meditación, bienestar"
    },
    "guarderia": {
        "nombre": "👶 Guardería/Kinder",
        "keywords": ["daycare", "guarderia", "kinder", "preescolar"],
        "inversion_min": 500000,
        "inversion_max": 1000000,
        "competencia_optima": 2,
        "descripcion": "Cuidado infantil, educación temprana"
    },
    "libreria": {
        "nombre": "📚 Librería/Papelería",
        "keywords": ["bookstore", "libreria", "papeleria", "stationery"],
        "inversion_min": 300000,
        "inversion_max": 600000,
        "competencia_optima": 2,
        "descripcion": "Libros, útiles escolares, regalos"
    },
    "servicios": {
        "nombre": "💇 Servicios (Peluquería/Tintorería)",
        "keywords": ["salon", "peluqueria", "barberia", "tintoreria", "lavanderia"],
        "inversion_min": 200000,
        "inversion_max": 400000,
        "competencia_optima": 3,
        "descripcion": "Servicios personales del día a día"
    }
}

# ============================================
# DICCIONARIO BILINGÜE
# ============================================

TEXTOS = {
    "es": {
        "titulo": "4SITE - Análisis de Ubicaciones con IA",
        "subtitulo": "Don't guess. Foresee.",
        "selector_idioma": "Idioma / Language",
        "input_ubicacion": "📍 Ingresa la ubicación que quieres analizar",
        "placeholder_direccion": "Ej: Av. Insurgentes Sur 1458, CDMX",
        "o_usa_mapa": "O haz click en el mapa:",
        "boton_analizar": "🔍 Analizar Ubicación",
        "modo_analisis": "🎯 ¿Qué quieres hacer?",
        "modo_validar": "Validar mi idea de negocio",
        "modo_recomendar": "Descubrir qué negocio es mejor",
        "selecciona_tipo": "Selecciona el tipo de negocio:",
        "titulo_analisis": "📊 Análisis de Ubicación",
        "score_viabilidad": "Score de Viabilidad",
        "resumen": "Resumen",
        "competencia_titulo": "Competencia Cercana (500m)",
        "beneficios": ["Ventajas", "Oportunidades", "Puntos Fuertes"],
        "riesgos": ["Riesgos", "Desafíos", "Consideraciones"],
        "watermark": "Versión gratuita - Para reportes completos visita 4site.mx",
        "cta_titulo": "🚀 ¿Quieres el análisis completo?",
        "cta_intro": "Obtén un reporte profesional de 10-12 páginas con:",
        "cta_bullets": [
            "• Análisis demográfico detallado",
            "• Estimación de ventas y ROI",
            "• Top 3 riesgos con plan de mitigación",
            "• Forecast a 12 meses",
            "• Recomendación ejecutiva: TOMAR o RECHAZAR"
        ],
        "cta_precio": "Solo $99 MXN",
        "footer_derechos": "© 2026 4SITE - Todos los derechos reservados",
        "footer_contacto": "Contacto: hola@4site.mx",
        "tabla_nombre": "Nombre",
        "tabla_rating": "Rating",
        "tabla_reseñas": "Reseñas",
        "descargar_pdf": "📄 Descargar Reporte PDF",
        "top_recomendaciones": "🎯 TOP 5 NEGOCIOS RECOMENDADOS",
        "mejor_opcion": "⭐ MEJOR OPCIÓN",
        "inversion_estimada": "💰 Inversión estimada",
        "evitar": "❌ Evitar"
    },
    "en": {
        "titulo": "4SITE - AI-Powered Location Analysis",
        "subtitulo": "Don't guess. Foresee.",
        "selector_idioma": "Language / Idioma",
        "input_ubicacion": "📍 Enter the location you want to analyze",
        "placeholder_direccion": "Ex: 1458 Insurgentes Sur Ave, Mexico City",
        "o_usa_mapa": "Or click on the map:",
        "boton_analizar": "🔍 Analyze Location",
        "modo_analisis": "🎯 What do you want to do?",
        "modo_validar": "Validate my business idea",
        "modo_recomendar": "Discover which business is best",
        "selecciona_tipo": "Select business type:",
        "titulo_analisis": "📊 Location Analysis",
        "score_viabilidad": "Viability Score",
        "resumen": "Summary",
        "competencia_titulo": "Nearby Competition (500m)",
        "beneficios": ["Advantages", "Opportunities", "Strengths"],
        "riesgos": ["Risks", "Challenges", "Considerations"],
        "watermark": "Free version - For complete reports visit 4site.mx",
        "cta_titulo": "🚀 Want the complete analysis?",
        "cta_intro": "Get a professional 10-12 page report with:",
        "cta_bullets": [
            "• Detailed demographic analysis",
            "• Sales and ROI estimation",
            "• Top 3 risks with mitigation plan",
            "• 12-month forecast",
            "• Executive recommendation: GO or NO-GO"
        ],
        "cta_precio": "Only $99 MXN",
        "footer_derechos": "© 2026 4SITE - All rights reserved",
        "footer_contacto": "Contact: hello@4site.mx",
        "tabla_nombre": "Name",
        "tabla_rating": "Rating",
        "tabla_reseñas": "Reviews",
        "descargar_pdf": "📄 Download PDF Report",
        "top_recomendaciones": "🎯 TOP 5 RECOMMENDED BUSINESSES",
        "mejor_opcion": "⭐ BEST OPTION",
        "inversion_estimada": "💰 Estimated investment",
        "evitar": "❌ Avoid"
    }
}

# ============================================
# FUNCIONES AUXILIARES
# ============================================

def geocodificar_direccion(direccion):
    """Geocodifica una dirección usando Google Maps"""
    try:
        result = gmaps.geocode(direccion)
        if result:
            location = result[0]['geometry']['location']
            return location['lat'], location['lng']
    except Exception as e:
        st.error(f"Error al geocodificar: {e}")
    return None, None

def geocodificar_inversa(lat, lng):
    """Convierte coordenadas a dirección"""
    try:
        result = gmaps.reverse_geocode((lat, lng))
        if result:
            return result[0]['formatted_address']
    except Exception as e:
        return f"{lat:.6f}, {lng:.6f}"
    return f"{lat:.6f}, {lng:.6f}"

# ============================================
# FUNCIONES DE CONTEXTO GEOGRÁFICO Y DEMOGRAFÍA
# Estas funciones se integran en app_4site.py
# ============================================

import requests
import streamlit as st

def detectar_contexto_ubicacion(lat, lng, direccion, GOOGLE_API_KEY):
    """Detecta el contexto de la ubicación: tipo de zona, POIs cercanos, tráfico"""
    
    contexto = {
        "tipo_zona": "residencial",
        "pois_cercanos": [],
        "trafico": "medio",
        "badges": []
    }
    
    # 1. DETECTAR TIPO DE VIALIDAD
    direccion_lower = direccion.lower()
    
    avenidas_principales = ["calzada", "autopista", "periférico", "circuito", "anillo", 
                           "viaducto", "eje", "insurgentes", "reforma", "constituyentes"]
    
    if any(av in direccion_lower for av in avenidas_principales):
        contexto["tipo_zona"] = "paso"
        contexto["trafico"] = "alto"
        contexto["badges"].append("🚗 Alto tráfico vehicular")
    elif "calle" in direccion_lower or "privada" in direccion_lower:
        contexto["tipo_zona"] = "residencial"
        contexto["trafico"] = "bajo"
    elif "avenida" in direccion_lower or "av." in direccion_lower:
        contexto["tipo_zona"] = "comercial"
        contexto["trafico"] = "medio"
    
    # 2. BUSCAR POIs CERCANOS
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.types"
    }
    
    data = {
        "includedTypes": ["gas_station", "shopping_mall", "hospital", "school", 
                         "university", "transit_station", "park"],
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 500.0
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            places = result.get('places', [])
            
            for place in places:
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


def obtener_demografia_inegi(lat, lng, gmaps):
    """Obtiene datos demográficos aproximados del área"""
    
    demografia = {
        "poblacion_estimada": 0,
        "densidad_hab_km2": 0,
        "nse_predominante": "C",
        "distribucion_edad": {
            "0-17": 25,
            "18-35": 35,
            "36-55": 25,
            "56+": 15
        },
        "viviendas_habitadas": 0,
        "ingreso_promedio_mensual": 15000,
        "gasto_promedio_mensual": 12000
    }
    
    try:
        result = gmaps.reverse_geocode((lat, lng))
        if result:
            address_components = result[0].get('address_components', [])
            
            for component in address_components:
                types = component.get('types', [])
                name = component.get('long_name', '').lower()
                
                if 'locality' in types or 'administrative_area_level_1' in types:
                    # CDMX - zonas premium
                    if any(x in name for x in ['polanco', 'condesa', 'roma', 'santa fe', 'lomas']):
                        demografia["nse_predominante"] = "A/B"
                        demografia["ingreso_promedio_mensual"] = 35000
                        demografia["densidad_hab_km2"] = 15000
                    # CDMX - zonas medias
                    elif 'ciudad de méxico' in name or 'cdmx' in name:
                        demografia["nse_predominante"] = "C+"
                        demografia["ingreso_promedio_mensual"] = 18000
                        demografia["densidad_hab_km2"] = 12000
                    # GDL / MTY
                    elif any(x in name for x in ['guadalajara', 'monterrey', 'zapopan', 'san pedro']):
                        demografia["nse_predominante"] = "B/C+"
                        demografia["ingreso_promedio_mensual"] = 20000
                        demografia["densidad_hab_km2"] = 10000
                    # Otras ciudades
                    elif any(x in name for x in ['querétaro', 'puebla', 'león', 'mérida']):
                        demografia["nse_predominante"] = "C"
                        demografia["ingreso_promedio_mensual"] = 15000
                        demografia["densidad_hab_km2"] = 8000
                    # EdoMex / Toluca
                    elif any(x in name for x in ['estado de méxico', 'edomex', 'toluca']):
                        demografia["nse_predominante"] = "C/D+"
                        demografia["ingreso_promedio_mensual"] = 12000
                        demografia["densidad_hab_km2"] = 9000
    except:
        pass
    
    # Calcular población en 500m (0.785 km²)
    area_km2 = 0.785
    demografia["poblacion_estimada"] = int(demografia["densidad_hab_km2"] * area_km2)
    demografia["viviendas_habitadas"] = int(demografia["poblacion_estimada"] / 3.5)
    demografia["gasto_promedio_mensual"] = int(demografia["ingreso_promedio_mensual"] * 0.8)
    
    return demografia


def ajustar_score_por_contexto(score_base, tipo_negocio_key, contexto):
    """Ajusta score según contexto geográfico"""
    
    score = score_base
    tipo_zona = contexto["tipo_zona"]
    pois = [poi["tipo"] for poi in contexto["pois_cercanos"]]
    
    # CAFETERÍAS
    if "cafe" in tipo_negocio_key:
        if tipo_zona == "paso" and "gasolinera" in pois:
            score += 15
        elif tipo_zona == "comercial":
            score += 10
        elif "escuela" in pois:
            score += 10
        elif tipo_zona == "residencial":
            score += 5
    
    # COMIDA RÁPIDA
    elif tipo_negocio_key == "comida_rapida":
        if tipo_zona == "paso":
            score += 20
        elif "gasolinera" in pois:
            score += 15
        elif "escuela" in pois:
            score += 10
    
    # RESTAURANTE CASUAL
    elif tipo_negocio_key == "restaurante_casual":
        if tipo_zona == "comercial" or "plaza" in pois:
            score += 15
        elif tipo_zona == "paso":
            score += 10
    
    # RESTAURANTE FINO
    elif tipo_negocio_key == "restaurante_fino":
        if tipo_zona == "comercial" or "plaza" in pois:
            score += 10
        elif tipo_zona == "paso":
            score -= 10
    
    # GIMNASIO
    elif "gimnasio" in tipo_negocio_key:
        if tipo_zona == "residencial":
            score += 15
        elif "plaza" in pois:
            score += 10
        elif tipo_zona == "paso":
            score -= 5
    
    # FARMACIA
    elif tipo_negocio_key == "farmacia":
        if "hospital" in pois:
            score += 20
        elif tipo_zona == "residencial":
            score += 10
        elif tipo_zona == "paso":
            score += 5
    
    # BAR
    elif tipo_negocio_key == "bar":
        if tipo_zona == "comercial" or "plaza" in pois:
            score += 10
        elif tipo_zona == "paso":
            score -= 15
        elif tipo_zona == "residencial":
            score -= 10
    
    # PANADERÍA
    elif tipo_negocio_key == "panaderia":
        if tipo_zona == "residencial":
            score += 10
        elif tipo_zona == "comercial":
            score += 5
    
    # TIENDA
    elif tipo_negocio_key == "tienda_conveniencia":
        if tipo_zona == "paso" or "gasolinera" in pois:
            score += 15
        elif tipo_zona == "residencial":
            score += 10
    
    # GUARDERÍA
    elif tipo_negocio_key == "guarderia":
        if tipo_zona == "residencial":
            score += 15
        elif tipo_zona == "comercial":
            score += 5
        elif tipo_zona == "paso":
            score -= 10
    
    # YOGA/WELLNESS
    elif tipo_negocio_key == "yoga_wellness":
        if tipo_zona == "residencial" or "plaza" in pois:
            score += 10
        elif tipo_zona == "paso":
            score -= 5
    
    return max(0, min(100, int(score)))


def ajustar_score_por_demografia(score_base, tipo_negocio_key, demografia):
    """Ajusta score según demografía"""
    
    score = score_base
    nse = demografia["nse_predominante"]
    densidad = demografia["densidad_hab_km2"]
    edad_joven = demografia["distribucion_edad"]["18-35"]
    edad_ninos = demografia["distribucion_edad"]["0-17"]
    
    # NEGOCIOS PREMIUM
    if tipo_negocio_key in ["cafe_premium", "restaurante_fino", "gimnasio_boutique", "yoga_wellness"]:
        if "A" in nse or "B" in nse:
            score += 15
        elif "C+" in nse:
            score += 5
        elif "D" in nse or "E" in nse:
            score -= 20
    
    # NEGOCIOS MASIVOS
    elif tipo_negocio_key in ["comida_rapida", "tienda_conveniencia"]:
        if "C" in nse or "D" in nse:
            score += 10
        elif "A" in nse or "B" in nse:
            score -= 5
    
    # DENSIDAD
    if densidad > 12000:
        if tipo_negocio_key not in ["restaurante_fino"]:
            score += 10
    elif densidad < 5000:
        score -= 10
    
    # EDAD - Negocios jóvenes
    if tipo_negocio_key in ["cafe_premium", "gimnasio_boutique", "bar", "comida_rapida"]:
        if edad_joven > 35:
            score += 10
        elif edad_joven < 25:
            score -= 10
    
    # GUARDERÍA
    elif tipo_negocio_key == "guarderia":
        if edad_ninos > 25:
            score += 15
        elif edad_ninos < 15:
            score -= 15
    
    return max(0, min(100, int(score)))
def buscar_competencia_por_tipo(lat, lng, tipo_negocio_key):
    """Busca competencia específica para un tipo de negocio"""
    tipo = TIPOS_NEGOCIO[tipo_negocio_key]
    
    # Mapeo amplio - SOLO tipos válidos de Google Places API
    # Lista oficial: https://developers.google.com/maps/documentation/places/web-service/place-types
    type_mapping = {
        "cafe_premium": ["cafe", "restaurant"],
        "cafe_casual": ["cafe", "restaurant"],
        "restaurante_casual": ["restaurant", "meal_delivery", "meal_takeaway"],
        "restaurante_fino": ["restaurant"],
        "comida_rapida": ["restaurant", "meal_takeaway"],
        "gimnasio_boutique": ["gym"],
        "gimnasio_regular": ["gym", "sports_complex"],
        "farmacia": ["pharmacy", "drugstore"],  # Removido "health" que es inválido
        "tienda_conveniencia": ["convenience_store", "supermarket"],
        "panaderia": ["bakery", "cafe", "restaurant"],
        "bar": ["bar", "night_club"],
        "yoga_wellness": ["gym", "spa", "beauty_salon"],
        "guarderia": ["school", "primary_school"],
        "libreria": ["book_store"],
        "servicios": ["beauty_salon", "hair_care", "laundry", "spa"]
    }
    
    included_types = type_mapping.get(tipo_negocio_key, ["restaurant", "cafe", "store"])
    keywords = tipo.get("keywords", [])
    
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.location,places.primaryTypeDisplayName,places.id,places.types"
    }
    data = {
        "includedTypes": included_types,
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": 500.0
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        # Solo mostrar error si falla
        if response.status_code != 200:
            st.error(f"❌ Error buscando competencia (status {response.status_code})")
            return []
        
        result = response.json()
        places = result.get('places', [])
        
        # Filtro adicional por keywords en el nombre (más flexible)
        filtered_places = []
        for place in places:
            nombre = place.get('displayName', {}).get('text', '').lower()
            tipos = place.get('types', [])
            
            # Incluir si el nombre contiene keywords relevantes O tiene los tipos correctos
            match_nombre = any(kw.lower() in nombre for kw in keywords)
            match_tipo = any(t in included_types for t in tipos)
            
            if match_nombre or match_tipo:
                filtered_places.append(place)
        
        return filtered_places
    except Exception as e:
        st.error(f"Error buscando competencia: {e}")
    
    return []

def buscar_competencia_general(lat, lng):
    """Busca competencia general (todos los negocios)"""
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.location,places.primaryTypeDisplayName,places.id,places.photos"
    }
    data = {
        "includedTypes": ["restaurant", "cafe", "bar", "gym", "pharmacy", "store", "bakery", "book_store"],
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": 500.0
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            return result.get('places', [])
    except Exception as e:
        st.error(f"Error buscando competencia: {e}")
    
    return []

def calcular_score_tipo_negocio(competidores, tipo_negocio_key):
    """Calcula score para un tipo específico de negocio"""
    tipo = TIPOS_NEGOCIO[tipo_negocio_key]
    
    # Contar competidores del mismo tipo
    num_competidores = len(competidores)
    
    # Score de densidad (basado en competencia óptima)
    competencia_optima = tipo["competencia_optima"]
    if num_competidores == 0:
        score_densidad = 100
    elif num_competidores <= competencia_optima:
        score_densidad = 85
    elif num_competidores <= competencia_optima + 2:
        score_densidad = 65
    elif num_competidores <= competencia_optima + 4:
        score_densidad = 45
    else:
        score_densidad = 25
    
    # Score de calidad (rating promedio de competidores)
    if competidores:
        ratings = [c.get('rating', 3.5) for c in competidores if c.get('rating')]
        avg_rating = sum(ratings) / len(ratings) if ratings else 3.5
    else:
        avg_rating = 0
    
    if avg_rating == 0:
        score_calidad = 100
    elif avg_rating < 3.5:
        score_calidad = 80
    elif avg_rating < 4.0:
        score_calidad = 60
    elif avg_rating < 4.3:
        score_calidad = 40
    else:
        score_calidad = 20
    
    # Score de consolidación (reseñas promedio)
    if competidores:
        reviews = [c.get('userRatingCount', 0) for c in competidores]
        avg_reviews = sum(reviews) / len(reviews) if reviews else 0
    else:
        avg_reviews = 0
    
    if avg_reviews == 0:
        score_consolidacion = 100
    elif avg_reviews < 100:
        score_consolidacion = 80
    elif avg_reviews < 500:
        score_consolidacion = 60
    elif avg_reviews < 1500:
        score_consolidacion = 40
    else:
        score_consolidacion = 20
    
    # Score final ponderado
    score_final = (score_densidad * 0.5) + (score_calidad * 0.3) + (score_consolidacion * 0.2)
    
    return int(score_final)

def recomendar_tipos_negocio(lat, lng, direccion):
    """Recomienda los mejores tipos de negocio con scoring multivariable"""
    
    # 1. OBTENER CONTEXTO Y DEMOGRAFÍA
    contexto = detectar_contexto_ubicacion(lat, lng, direccion, GOOGLE_API_KEY)
    demografia = obtener_demografia_inegi(lat, lng, gmaps)
    
    recomendaciones = []
    
    for tipo_key, tipo_info in TIPOS_NEGOCIO.items():
        # Buscar competencia específica para este tipo
        competidores = buscar_competencia_por_tipo(lat, lng, tipo_key)
        
        # Score base (solo competencia)
        score_base = calcular_score_tipo_negocio(competidores, tipo_key)
        
        # Ajustar por contexto geográfico
        score_contexto = ajustar_score_por_contexto(score_base, tipo_key, contexto)
        
        # Ajustar por demografía
        score_final = ajustar_score_por_demografia(score_contexto, tipo_key, demografia)
        
        recomendaciones.append({
            "tipo_key": tipo_key,
            "nombre": tipo_info["nombre"],
            "score": score_final,
            "score_base": score_base,
            "num_competidores": len(competidores),
            "inversion_min": tipo_info["inversion_min"],
            "inversion_max": tipo_info["inversion_max"],
            "descripcion": tipo_info["descripcion"],
            "competidores": competidores,
            "badges": contexto["badges"]
        })
    
    # Ordenar por score (mayor a menor)
    recomendaciones.sort(key=lambda x: x["score"], reverse=True)
    
    return recomendaciones, contexto, demografia

def generar_analisis_claude(ubicacion, competidores, idioma, modo, tipo_negocio=None, recomendaciones=None):
    """Genera análisis usando Claude"""
    
    if modo == "validar":
        # Modo: Validar idea específica
        tipo_info = TIPOS_NEGOCIO[tipo_negocio]
        prompt = f"""Analiza esta ubicación ESPECÍFICA para un negocio tipo: {tipo_info['nombre']}

UBICACIÓN EXACTA A ANALIZAR: {ubicacion}
IMPORTANTE: Basa tu análisis ÚNICAMENTE en esta ubicación. NO menciones otras zonas, colonias o ciudades que no sean la ubicación exacta proporcionada arriba.

Descripción del tipo de negocio: {tipo_info['descripcion']}
Inversión estimada: ${tipo_info['inversion_min']:,} - ${tipo_info['inversion_max']:,} MXN

Competencia encontrada en un radio de 500m de {ubicacion}:
Total: {len(competidores)} negocios similares

Lista de competidores:
{json.dumps([{
    'nombre': c.get('displayName', {}).get('text', 'N/A'),
    'rating': c.get('rating', 'N/A'),
    'reviews': c.get('userRatingCount', 0)
} for c in competidores], indent=2)}

Genera un análisis en {idioma} con:
1. Resumen ejecutivo (2-3 líneas) - menciona SOLO la ubicación específica: {ubicacion}
2. 3-4 ventajas clave (bullets cortos) - basado en los datos de competencia arriba
3. 3-4 riesgos principales (bullets cortos) - basado en los datos de competencia arriba

CRÍTICO: NO inventes información sobre la zona. Usa SOLO los datos de competencia proporcionados arriba.
Sé específico y accionable."""

    else:
        # Modo: Recomendador
        top_5 = recomendaciones[:5]
        bottom_3 = recomendaciones[-3:]
        
        prompt = f"""Analiza esta ubicación ESPECÍFICA para recomendar tipos de negocio.

UBICACIÓN EXACTA: {ubicacion}
IMPORTANTE: Basa tu análisis ÚNICAMENTE en esta ubicación. NO menciones otras zonas o ciudades.

TOP 5 NEGOCIOS MÁS VIABLES para {ubicacion}:
{json.dumps([{
    'tipo': r['nombre'],
    'score': r['score'],
    'competidores': r['num_competidores'],
    'inversion': f"${r['inversion_min']:,}-${r['inversion_max']:,} MXN"
} for r in top_5], indent=2)}

NEGOCIOS A EVITAR:
{json.dumps([{
    'tipo': r['nombre'],
    'score': r['score']
} for r in bottom_3], indent=2)}

Genera en {idioma}:
1. Para cada TOP 5: Justificación breve (1-2 líneas) de por qué tiene ese score basado en el número de competidores
2. Insight general de la zona (1-2 líneas) - menciona la ubicación {ubicacion}

CRÍTICO: NO inventes datos demográficos o características de la zona. Basa tu análisis SOLO en los scores y número de competidores arriba.
Sé conciso y específico."""

    try:
        message = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text
    except Exception as e:
        return f"Error al generar análisis: {e}"

def generar_mapa_estatico(lat, lng):
    """Genera mapa estático de Google"""
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": f"{lat},{lng}",
        "zoom": 16,
        "size": "600x400",
        "markers": f"color:red|{lat},{lng}",
        "key": GOOGLE_API_KEY,
        "path": f"color:0x0000ff|weight:2|fillcolor:0x0000ff33|{lat},{lng}|{lat+0.0045},{lng}|{lat+0.0045},{lng+0.006}|{lat},{lng+0.006}|{lat},{lng}"
    }
    
    # Círculo aproximado
    circle_points = []
    import math
    for i in range(0, 360, 10):
        angle = math.radians(i)
        point_lat = lat + (0.0045 * math.cos(angle))
        point_lng = lng + (0.006 * math.sin(angle))
        circle_points.append(f"{point_lat},{point_lng}")
    
    params["path"] = f"color:0x4285F4|weight:2|fillcolor:0x4285F433|{'|'.join(circle_points)}"
    
    url = f"{base_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return BytesIO(response.content)
    except:
        pass
    
    return None

def generar_pdf_simple(ubicacion, score, analisis, competidores, idioma, lat, lng, modo, tipo_negocio=None, recomendaciones=None):
    """Genera PDF simple en memoria"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0047AB'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    t = TEXTOS[idioma]
    
    elements.append(Paragraph("4SITE", title_style))
    elements.append(Paragraph(t["subtitulo"], styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Ubicación
    elements.append(Paragraph(f"<b>{t['input_ubicacion']}:</b> {ubicacion}", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    if modo == "validar":
        # Modo: Validar idea específica
        tipo_info = TIPOS_NEGOCIO[tipo_negocio]
        elements.append(Paragraph(f"<b>Tipo de negocio:</b> {tipo_info['nombre']}", styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Score
        elements.append(Paragraph(f"<b>{t['score_viabilidad']}:</b> {score}/100", styles['Heading2']))
        elements.append(Spacer(1, 0.3*inch))
        
    else:
        # Modo: Recomendador
        elements.append(Paragraph(t["top_recomendaciones"], styles['Heading2']))
        elements.append(Spacer(1, 0.2*inch))
    
    # Mapa
    mapa_img = generar_mapa_estatico(lat, lng)
    if mapa_img:
        try:
            img = RLImage(mapa_img, width=4*inch, height=2.6*inch)
            elements.append(img)
            elements.append(Spacer(1, 0.3*inch))
        except:
            pass
    
    # Análisis
    elements.append(Paragraph(f"<b>{t['resumen']}:</b>", styles['Heading3']))
    elements.append(Spacer(1, 0.1*inch))
    for linea in analisis.split('\n'):
        if linea.strip():
            elements.append(Paragraph(linea, styles['Normal']))
    
    elements.append(Spacer(1, 0.3*inch))
    
    if modo == "validar":
        # Tabla de competencia
        if competidores:
            elements.append(Paragraph(f"<b>{t['competencia_titulo']}</b>", styles['Heading3']))
            elements.append(Spacer(1, 0.1*inch))
            
            data = [[t["tabla_nombre"], t["tabla_rating"], t["tabla_reseñas"]]]
            for comp in competidores[:10]:
                nombre = comp.get('displayName', {}).get('text', 'N/A')
                rating = comp.get('rating', 'N/A')
                reviews = comp.get('userRatingCount', 0)
                data.append([nombre, f"{rating}★" if rating != 'N/A' else 'N/A', str(reviews)])
            
            tabla = Table(data, colWidths=[3*inch, 1*inch, 1*inch])
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0047AB')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black)
            ]))
            
            elements.append(tabla)
    
    else:
        # Tabla de recomendaciones
        if recomendaciones:
            top_5 = recomendaciones[:5]
            
            data = [["Tipo de Negocio", "Score", "Inversión"]]
            for rec in top_5:
                inversion = f"${rec['inversion_min']//1000}K-${rec['inversion_max']//1000}K"
                data.append([rec['nombre'], f"{rec['score']}/100", inversion])
            
            tabla = Table(data, colWidths=[3*inch, 1*inch, 1.5*inch])
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0047AB')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black)
            ]))
            
            elements.append(tabla)
    
    # Watermark
    elements.append(Spacer(1, 0.5*inch))
    watermark_style = ParagraphStyle(
        'Watermark',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(t["watermark"], watermark_style))
    
    # Generar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ============================================
# INTERFAZ STREAMLIT
# ============================================

# Selector de idioma
idioma = st.selectbox(
    TEXTOS["es"]["selector_idioma"],
    options=["es", "en"],
    format_func=lambda x: "Español 🇲🇽" if x == "es" else "English 🇺🇸"
)

t = TEXTOS[idioma]

# Logo y título
st.markdown(
    """
    <div style='text-align: center; padding: 20px;'>
        <h1 style='color: #0047AB; font-size: 48px; margin: 0;'>4SITE</h1>
        <p style='color: #00D4D4; font-size: 18px; margin: 5px 0;'>Don't guess. Foresee.</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# Input de ubicación
st.markdown(f"### {t['input_ubicacion']}")

col1, col2 = st.columns([1, 1])

with col1:
    direccion_texto = st.text_input(
        "",
        placeholder=t["placeholder_direccion"],
        key="direccion_input"
    )

with col2:
    st.markdown(f"**{t['o_usa_mapa']}**")

# Mapa interactivo
m = folium.Map(location=[19.432608, -99.133209], zoom_start=12)
m.add_child(folium.LatLngPopup())

mapa_data = st_folium(m, width=700, height=400, key="mapa")

# Detectar click en mapa
lat_mapa, lng_mapa = None, None
direccion_mapa = None
if mapa_data and mapa_data.get("last_clicked"):
    lat_mapa = mapa_data["last_clicked"]["lat"]
    lng_mapa = mapa_data["last_clicked"]["lng"]
    direccion_mapa = geocodificar_inversa(lat_mapa, lng_mapa)
    st.success(f"📍 Ubicación seleccionada: {direccion_mapa}")

st.markdown("---")

# Selector de modo de análisis
st.markdown(f"### {t['modo_analisis']}")

modo = st.radio(
    "",
    options=["validar", "recomendar"],
    format_func=lambda x: t["modo_validar"] if x == "validar" else t["modo_recomendar"],
    horizontal=True
)

# Si modo validar, mostrar dropdown de tipos
tipo_negocio_seleccionado = None
if modo == "validar":
    st.markdown(f"**{t['selecciona_tipo']}**")
    tipo_negocio_seleccionado = st.selectbox(
        "",
        options=list(TIPOS_NEGOCIO.keys()),
        format_func=lambda x: TIPOS_NEGOCIO[x]["nombre"]
    )

st.markdown("---")

# Botón de análisis
if st.button(t["boton_analizar"], type="primary", use_container_width=True):
    
    # Determinar ubicación
    if lat_mapa and lng_mapa:
        lat, lng = lat_mapa, lng_mapa
        ubicacion = geocodificar_inversa(lat, lng)  # Convertir coordenadas a dirección
    elif direccion_texto:
        lat, lng = geocodificar_direccion(direccion_texto)
        ubicacion = direccion_texto
    else:
        st.error("Por favor ingresa una ubicación o selecciona en el mapa")
        st.stop()
    
    if not lat or not lng:
        st.error("No se pudo geocodificar la ubicación")
        st.stop()
    
    with st.spinner("🔍 Analizando ubicación..."):
        
        if modo == "validar":
            # MODO: Validar idea específica
            competidores = buscar_competencia_por_tipo(lat, lng, tipo_negocio_seleccionado)
            
            # Obtener contexto y demografía
            contexto = detectar_contexto_ubicacion(lat, lng, ubicacion, GOOGLE_API_KEY)
            demografia = obtener_demografia_inegi(lat, lng, gmaps)
            
            # Calcular score multivariable
            score_base = calcular_score_tipo_negocio(competidores, tipo_negocio_seleccionado)
            score_contexto = ajustar_score_por_contexto(score_base, tipo_negocio_seleccionado, contexto)
            score = ajustar_score_por_demografia(score_contexto, tipo_negocio_seleccionado, demografia)
            
            analisis = generar_analisis_claude(ubicacion, competidores, idioma, "validar", tipo_negocio=tipo_negocio_seleccionado)
            
            # Mostrar resultados
            st.markdown(f"## {t['titulo_analisis']}")
            st.markdown(f"### {TIPOS_NEGOCIO[tipo_negocio_seleccionado]['nombre']}")
            
            # Mostrar badges de contexto
            if contexto.get("badges"):
                st.info(" ".join(contexto["badges"]))
            
            # Score visual
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                color = "#4CAF50" if score >= 70 else "#FFC107" if score >= 50 else "#F44336"
                st.markdown(
                    f"""
                    <div style='text-align: center; padding: 30px; background: linear-gradient(135deg, {color}22 0%, {color}44 100%); border-radius: 15px; border: 3px solid {color};'>
                        <h1 style='color: {color}; font-size: 72px; margin: 0;'>{score}</h1>
                        <p style='color: #666; font-size: 18px; margin: 5px 0;'>{t['score_viabilidad']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            st.markdown("---")
            
            # Análisis
            st.markdown(f"### {t['resumen']}")
            st.markdown(analisis)
            
            st.markdown("---")
            
            # Competencia
            if competidores:
                st.markdown(f"### {t['competencia_titulo']}")
                
                comp_data = []
                for comp in competidores[:10]:
                    comp_data.append({
                        t["tabla_nombre"]: comp.get('displayName', {}).get('text', 'N/A'),
                        t["tabla_rating"]: f"{comp.get('rating', 'N/A')}★" if comp.get('rating') else 'N/A',
                        t["tabla_reseñas"]: comp.get('userRatingCount', 0)
                    })
                
                st.dataframe(comp_data, use_container_width=True)
            
            st.markdown("---")
            
            # Demografía del área (VERSIÓN BÁSICA $99)
            st.markdown("### 📊 Datos Demográficos del Área (500m)")
            st.info("💡 Datos estimados. Actualiza a PRO ($299) para datos INEGI reales + análisis de ingreso/gasto.")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Población", f"{demografia['poblacion_estimada']:,}")
            
            with col2:
                st.metric("NSE Predominante", demografia['nse_predominante'])
            
            with col3:
                st.metric("Densidad", f"{demografia['densidad_hab_km2']:,} hab/km²")
            
            # Generar PDF
            pdf_buffer = generar_pdf_simple(ubicacion, score, analisis, competidores, idioma, lat, lng, "validar", tipo_negocio=tipo_negocio_seleccionado)
            
            st.markdown("---")
            st.download_button(
                label=t["descargar_pdf"],
                data=pdf_buffer,
                file_name=f"4site_analisis_{ubicacion[:20]}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        else:
            # MODO: Recomendador
            recomendaciones, contexto, demografia = recomendar_tipos_negocio(lat, lng, ubicacion)
            analisis = generar_analisis_claude(ubicacion, [], idioma, "recomendar", recomendaciones=recomendaciones)
            
            # Mostrar resultados
            st.markdown(f"## {t['top_recomendaciones']}")
            
            # Mostrar badges de contexto
            if contexto.get("badges"):
                st.info(" ".join(contexto["badges"]))
            
            # Top 5
            for i, rec in enumerate(recomendaciones[:5]):
                with st.expander(f"#{i+1} {rec['nombre']} - Score: {rec['score']}/100", expanded=(i==0)):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Score visual
                        color = "#4CAF50" if rec['score'] >= 70 else "#FFC107" if rec['score'] >= 50 else "#F44336"
                        st.markdown(
                            f"""
                            <div style='padding: 15px; background: {color}22; border-left: 4px solid {color}; border-radius: 5px;'>
                                <h2 style='color: {color}; margin: 0;'>{rec['score']}/100</h2>
                                <p style='margin: 5px 0;'>{rec['descripcion']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        if i == 0:
                            st.success(f"⭐ {t['mejor_opcion']}")
                        
                        st.markdown(f"**Competidores cercanos:** {rec['num_competidores']}")
                    
                    with col2:
                        st.markdown(f"**{t['inversion_estimada']}:**")
                        st.markdown(f"${rec['inversion_min']//1000}K - ${rec['inversion_max']//1000}K MXN")
            
            st.markdown("---")
            
            # Análisis
            st.markdown(f"### {t['resumen']}")
            st.markdown(analisis)
            
            st.markdown("---")
            
            # Demografía del área (VERSIÓN BÁSICA $99)
            st.markdown("### 📊 Datos Demográficos del Área (500m)")
            st.info("💡 Datos estimados. Actualiza a PRO ($299) para datos INEGI reales + análisis de ingreso/gasto.")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Población", f"{demografia['poblacion_estimada']:,}")
            
            with col2:
                st.metric("NSE Predominante", demografia['nse_predominante'])
            
            with col3:
                st.metric("Densidad", f"{demografia['densidad_hab_km2']:,} hab/km²")
            
            st.markdown("---")
            
            # Negocios a evitar
            st.markdown(f"### {t['evitar']}")
            evitar_data = []
            for rec in recomendaciones[-3:]:
                evitar_data.append({
                    "Tipo": rec['nombre'],
                    "Score": f"{rec['score']}/100"
                })
            st.dataframe(evitar_data, use_container_width=True)
            
            # Generar PDF
            pdf_buffer = generar_pdf_simple(ubicacion, 0, analisis, [], idioma, lat, lng, "recomendar", recomendaciones=recomendaciones)
            
            st.markdown("---")
            st.download_button(
                label=t["descargar_pdf"],
                data=pdf_buffer,
                file_name=f"4site_recomendaciones_{ubicacion[:20]}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# CTA
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; padding: 40px; background: linear-gradient(135deg, #0047AB 0%, #00D4D4 100%); border-radius: 15px; color: white;'>
        <h2>{t['cta_titulo']}</h2>
        <p style='font-size: 18px;'>{t['cta_intro']}</p>
        <ul style='text-align: left; display: inline-block; font-size: 16px;'>
            {''.join([f'<li>{bullet}</li>' for bullet in t['cta_bullets']])}
        </ul>
        <h3 style='font-size: 32px; margin: 20px 0;'>{t['cta_precio']}</h3>
        <p style='font-size: 14px; opacity: 0.9;'>Próximamente disponible</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Footer
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; padding: 20px; color: #666;'>
        <p>{t['footer_derechos']}</p>
        <p>{t['footer_contacto']}</p>
    </div>
    """,
    unsafe_allow_html=True
)
