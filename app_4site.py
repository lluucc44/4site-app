import streamlit as st
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import googlemaps
from anthropic import Anthropic
import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import folium
from streamlit_folium import st_folium
from io import BytesIO

load_dotenv()

# Configuración de página
st.set_page_config(
    page_title="4SITE - Location Analysis",
    page_icon="📍",
    layout="wide"
)

# Inicializar APIs
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_API_KEY"))
claude = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 48px;
        font-weight: bold;
        color: #0047AB;
        text-align: center;
        margin-bottom: 10px;
    }
    .tagline {
        font-size: 20px;
        color: #666;
        text-align: center;
        margin-bottom: 30px;
    }
    .stButton>button {
        background-color: #00D4D4;
        color: white;
        font-size: 18px;
        padding: 15px 30px;
        border-radius: 5px;
        border: none;
        font-weight: bold;
    }
    .score-box {
        background-color: #f0f8ff;
        border: 3px solid #00D4D4;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
    }
    .score-number {
        font-size: 48px;
        font-weight: bold;
        color: #00D4D4;
    }
</style>
""", unsafe_allow_html=True)

# Textos bilingües
TEXTOS = {
    "es": {
        "header": "4SITE",
        "tagline": "Don't guess. Foresee.",
        "descripcion": "Análisis con IA para validar tu ubicación comercial antes de firmar contrato",
        "selector_idioma": "Idioma / Language",
        "metodo_input": "¿Cómo quieres ingresar la ubicación?",
        "opcion_texto": "📝 Escribir dirección",
        "opcion_mapa": "📍 Seleccionar en mapa",
        "placeholder_direccion": "Ej: Av. Insurgentes 234, Roma, CDMX",
        "instruccion_mapa": "Click en el mapa para seleccionar la ubicación",
        "boton_analizar": "🔍 Analizar Ubicación",
        "analizando": "🤖 Analizando ubicación...",
        "resultados": "📊 RESULTADOS DEL ANÁLISIS",
        "score_titulo": "Score de Viabilidad",
        "titulo_analisis": "ANÁLISIS DE UBICACIÓN",
        "tipo": "Tipo: Cafetería",
        "fecha": "Fecha",
        "score_viabilidad": "SCORE DE VIABILIDAD",
        "resumen": "RESUMEN RÁPIDO",
        "competencia_titulo": "COMPETENCIA CERCANA (500m)",
        "watermark": "REPORTE GRATIS",
        "cta_titulo": "¿QUIERES EL ANÁLISIS COMPLETO?",
        "cta_intro": "Con el reporte PRO ($99 pesos) recibes:",
        "beneficios": [
            "✓ Top 3 riesgos específicos + cómo mitigarlos",
            "✓ Top 3 oportunidades accionables",
            "✓ Forecast realista de ventas",
            "✓ Análisis profundo de tráfico por hora",
            "✓ Recomendación final: TOMAR/RECHAZAR",
            "✓ Comparativa vs benchmarks de zona",
            "✓ Reporte completo de 10-12 páginas"
        ],
        "ventajas": "✅ Ventajas",
        "riesgos": "⚠️ Riesgos",
        "competencia": "🏪 Competencia Cercana (500m)",
        "tabla_nombre": "Nombre",
        "tabla_reseñas": "Reseñas",
        "descargar_pdf": "📄 Descargar Reporte PDF Completo",
        "error_ubicacion": "⚠️ Por favor ingresa una ubicación válida",
        "procesando": "Procesando análisis...",
        "generando_pdf": "Generando PDF...",
        "pdf_listo": "✅ PDF generado correctamente",
        "footer_derechos": "© 2026 4site - Análisis de ubicaciones con IA"
    },
    "en": {
        "header": "4SITE",
        "tagline": "Don't guess. Foresee.",
        "descripcion": "AI-powered analysis to validate your commercial location before signing",
        "selector_idioma": "Language / Idioma",
        "metodo_input": "How do you want to enter the location?",
        "opcion_texto": "📝 Write address",
        "opcion_mapa": "📍 Select on map",
        "placeholder_direccion": "Ex: 123 Main St, New York, NY",
        "instruccion_mapa": "Click on map to select location",
        "boton_analizar": "🔍 Analyze Location",
        "analizando": "🤖 Analyzing location...",
        "resultados": "📊 ANALYSIS RESULTS",
        "score_titulo": "Viability Score",
        "titulo_analisis": "LOCATION ANALYSIS",
        "tipo": "Type: Coffee Shop",
        "fecha": "Date",
        "score_viabilidad": "VIABILITY SCORE",
        "resumen": "QUICK SUMMARY",
        "competencia_titulo": "NEARBY COMPETITION (500m)",
        "watermark": "FREE REPORT",
        "cta_titulo": "WANT THE COMPLETE ANALYSIS?",
        "cta_intro": "With the PRO report ($99 pesos) you get:",
        "beneficios": [
            "✓ Top 3 specific risks + how to mitigate them",
            "✓ Top 3 actionable opportunities",
            "✓ Realistic sales forecast",
            "✓ Deep traffic analysis by hour",
            "✓ Final recommendation: TAKE/REJECT",
            "✓ Comparison vs area benchmarks",
            "✓ Complete 10-12 page report"
        ],
        "ventajas": "✅ Advantages",
        "riesgos": "⚠️ Risks",
        "competencia": "🏪 Nearby Competition (500m)",
        "tabla_nombre": "Name",
        "tabla_reseñas": "Reviews",
        "descargar_pdf": "📄 Download Complete PDF Report",
        "error_ubicacion": "⚠️ Please enter a valid location",
        "procesando": "Processing analysis...",
        "generando_pdf": "Generating PDF...",
        "pdf_listo": "✅ PDF generated successfully",
        "footer_derechos": "© 2026 4site - Location analysis with AI"
    }
}

# Funciones del backend (simplificadas para Streamlit)

def geocodificar(direccion):
    """Convierte dirección en coordenadas"""
    try:
        resultado = gmaps.geocode(direccion)
        if resultado:
            coords = resultado[0]["geometry"]["location"]
            return coords["lat"], coords["lng"], resultado[0]["formatted_address"]
    except:
        pass
    return None, None, None

def reverse_geocode(lat, lng):
    """Convierte coordenadas en dirección"""
    try:
        resultado = gmaps.reverse_geocode((lat, lng))
        if resultado:
            return resultado[0]["formatted_address"]
    except:
        pass
    return f"{lat}, {lng}"

def buscar_competencia_con_fotos(lat, lng):
    """Busca cafeterías cercanas"""
    url = "https://places.googleapis.com/v1/places:searchNearby"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.photos"
    }
    
    data = {
        "includedTypes": ["cafe"],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 500.0
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        resultados = response.json()
        
        competidores = []
        if "places" in resultados:
            for lugar in resultados["places"]:
                competidores.append({
                    "nombre": lugar.get("displayName", {}).get("text", "Sin nombre"),
                    "rating": lugar.get("rating", 0),
                    "total_ratings": lugar.get("userRatingCount", 0)
                })
        
        return competidores
    except:
        return []

def calcular_score_competencia(competidores):
    """Calcula score metodológico"""
    num_competidores = len(competidores)
    
    # Densidad (50%)
    if num_competidores == 0:
        densidad_score = 100
    elif num_competidores <= 2:
        densidad_score = 85
    elif num_competidores <= 5:
        densidad_score = 65
    elif num_competidores <= 8:
        densidad_score = 45
    else:
        densidad_score = 25
    
    # Calidad (30%)
    if num_competidores > 0:
        ratings_validos = [c['rating'] for c in competidores if c['rating'] > 0]
        rating_promedio = sum(ratings_validos) / len(ratings_validos) if ratings_validos else 3.5
    else:
        rating_promedio = 0
    
    if rating_promedio == 0:
        calidad_score = 100
    elif rating_promedio < 3.5:
        calidad_score = 80
    elif rating_promedio < 4.0:
        calidad_score = 60
    elif rating_promedio < 4.3:
        calidad_score = 40
    else:
        calidad_score = 20
    
    # Consolidación (20%)
    if num_competidores > 0:
        reseñas_validas = [c['total_ratings'] for c in competidores if c['total_ratings'] > 0]
        reseñas_promedio = sum(reseñas_validas) / len(reseñas_validas) if reseñas_validas else 0
    else:
        reseñas_promedio = 0
    
    if reseñas_promedio == 0:
        consolidacion_score = 100
    elif reseñas_promedio < 100:
        consolidacion_score = 80
    elif reseñas_promedio < 500:
        consolidacion_score = 60
    elif reseñas_promedio < 1500:
        consolidacion_score = 40
    else:
        consolidacion_score = 20
    
    score_final = int(
        densidad_score * 0.50 +
        calidad_score * 0.30 +
        consolidacion_score * 0.20
    )
    
    if score_final >= 80:
        nivel = "ALTO" if st.session_state.idioma == "es" else "HIGH"
    elif score_final >= 65:
        nivel = "MEDIO-ALTO" if st.session_state.idioma == "es" else "MEDIUM-HIGH"
    elif score_final >= 50:
        nivel = "MEDIO" if st.session_state.idioma == "es" else "MEDIUM"
    else:
        nivel = "BAJO" if st.session_state.idioma == "es" else "LOW"
    
    return {
        "score": score_final,
        "nivel": nivel,
        "desglose": {
            "densidad": int(densidad_score),
            "calidad": int(calidad_score),
            "consolidacion": int(consolidacion_score),
            "num_competidores": num_competidores,
            "rating_promedio": round(rating_promedio, 1) if rating_promedio > 0 else "N/A",
            "reseñas_promedio": int(reseñas_promedio) if reseñas_promedio > 0 else "N/A"
        }
    }

def generar_analisis_claude(direccion, competencia, score_info, idioma):
    """Claude genera análisis"""
    comp_texto = json.dumps(competencia[:5], indent=2, ensure_ascii=False) if competencia else "No competition"
    
    if idioma == "es":
        prompt = f"""Ubicación: {direccion}
Score: {score_info['score']}/100
Competencia: {score_info['desglose']['num_competidores']} cafés
{comp_texto}

JSON:
{{
  "ventajas": ["Ventaja 1 (máx 20 palabras)", "Ventaja 2 (máx 20 palabras)"],
  "riesgos": ["Riesgo 1 (máx 20 palabras)", "Riesgo 2 (máx 20 palabras)"]
}}
SOLO JSON en español."""
    else:
        prompt = f"""Location: {direccion}
Score: {score_info['score']}/100
Competition: {score_info['desglose']['num_competidores']} cafes
{comp_texto}

JSON:
{{
  "ventajas": ["Advantage 1 (max 20 words)", "Advantage 2 (max 20 words)"],
  "riesgos": ["Risk 1 (max 20 words)", "Risk 2 (max 20 words)"]
}}
ONLY JSON in English."""
    
    try:
        mensaje = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        
        texto = mensaje.content[0].text.strip()
        if texto.startswith("```"):
            texto = texto.split("\n", 1)[1]
        if texto.endswith("```"):
            texto = texto.rsplit("\n", 1)[0]
        
        return json.loads(texto)
    except:
        if idioma == "es":
            return {
                "ventajas": ["Ubicación comercial viable", "Potencial de mercado"],
                "riesgos": ["Competencia existente", "Requiere diferenciación"]
            }
        else:
            return {
                "ventajas": ["Viable commercial location", "Market potential"],
                "riesgos": ["Existing competition", "Requires differentiation"]
            }

def generar_pdf_simple(direccion, lat, lng, competencia, score_info, analisis, idioma):
    """Genera PDF simple en memoria para descarga"""
    from io import BytesIO
    
    t_pdf = TEXTOS[idioma]
    
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    story = []
    
    # Estilos
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontSize=24,
        textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER, spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'], fontSize=11,
        textColor=colors.grey, alignment=TA_CENTER, spaceAfter=20
    )
    header_style = ParagraphStyle(
        'Header', parent=styles['Heading2'], fontSize=14,
        textColor=colors.HexColor('#0047AB'), spaceAfter=10, spaceBefore=15
    )
    
    # Header
    story.append(Paragraph("4SITE", title_style))
    story.append(Paragraph("Don't guess. Foresee.", subtitle_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Info
    story.append(Paragraph(t_pdf["titulo_analisis"], header_style))
    story.append(Paragraph(direccion, styles['Normal']))
    story.append(Paragraph(f"{t_pdf['fecha']}: {datetime.now().strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Score
    story.append(Paragraph(t_pdf["score_viabilidad"], header_style))
    score_data = [[f"{score_info['score']}/100", score_info['nivel']]]
    score_table = Table(score_data, colWidths=[2*inch, 2*inch])
    score_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (0, 0), 32),
        ('FONTSIZE', (1, 0), (1, 0), 14),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#00D4D4')),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#00D4D4')),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Resumen
    story.append(Paragraph(t_pdf["resumen"], header_style))
    for ventaja in analisis['ventajas']:
        story.append(Paragraph(f"✓ {ventaja}", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    for riesgo in analisis['riesgos']:
        story.append(Paragraph(f"⚠ {riesgo}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Competencia
    story.append(Paragraph(t_pdf["competencia_titulo"], header_style))
    if competencia:
        comp_data = [[t_pdf["tabla_nombre"], "Rating", t_pdf["tabla_reseñas"]]]
        for comp in competencia[:5]:
            comp_data.append([
                comp['nombre'][:30],
                str(comp['rating']) if comp['rating'] > 0 else "N/A",
                str(comp['total_ratings'])
            ])
        
        comp_table = Table(comp_data, colWidths=[2.5*inch, 1*inch, 1*inch])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00D4D4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(Spacer(1, 0.1*inch))
        story.append(comp_table)
    
    # Watermark
    story.append(Spacer(1, 0.5*inch))
    watermark_style = ParagraphStyle(
        'Watermark', parent=styles['Normal'], fontSize=10,
        textColor=colors.grey, alignment=TA_CENTER
    )
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━", watermark_style))
    story.append(Paragraph(t_pdf["watermark"], watermark_style))
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━", watermark_style))
    
    # CTA
    story.append(PageBreak())
    story.append(Spacer(1, 0.5*inch))
    cta_style = ParagraphStyle(
        'CTA', parent=styles['Heading2'], fontSize=16,
        textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER, spaceAfter=20
    )
    story.append(Paragraph(t_pdf["cta_titulo"], cta_style))
    story.append(Paragraph(t_pdf["cta_intro"], styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    
    for beneficio in t_pdf["beneficios"]:
        story.append(Paragraph(beneficio, styles['Normal']))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'], fontSize=9,
        textColor=colors.grey, alignment=TA_CENTER
    )
    story.append(Paragraph("📧 hola@4site.mx | 🌐 4site.mx", footer_style))
    story.append(Paragraph(t_pdf["footer_derechos"], footer_style))
    
    # Generar
    pdf.build(story)
    buffer.seek(0)
    return buffer

# INTERFAZ PRINCIPAL

# Inicializar session state
if 'idioma' not in st.session_state:
    st.session_state.idioma = 'es'
if 'lat_seleccionado' not in st.session_state:
    st.session_state.lat_seleccionado = None
if 'lng_seleccionado' not in st.session_state:
    st.session_state.lng_seleccionado = None

# Header
st.markdown('<div class="main-header">4SITE</div>', unsafe_allow_html=True)
st.markdown('<div class="tagline">Don\'t guess. Foresee.</div>', unsafe_allow_html=True)

# Selector de idioma
col_izq, col_centro, col_der = st.columns([1,2,1])
with col_centro:
    idioma_sel = st.selectbox(
        TEXTOS[st.session_state.idioma]["selector_idioma"],
        options=["🇲🇽 Español", "🇺🇸 English"],
        index=0 if st.session_state.idioma == "es" else 1
    )
    st.session_state.idioma = "es" if "Español" in idioma_sel else "en"

t = TEXTOS[st.session_state.idioma]

st.markdown(f"<p style='text-align: center; color: #666;'>{t['descripcion']}</p>", unsafe_allow_html=True)
st.markdown("---")

# Método de input
metodo = st.radio(
    t["metodo_input"],
    options=[t["opcion_texto"], t["opcion_mapa"]],
    horizontal=True
)

lat_final, lng_final, direccion_final = None, None, None

if t["opcion_texto"] in metodo:
    # Input por texto
    direccion_input = st.text_input(
        t["opcion_texto"],
        placeholder=t["placeholder_direccion"]
    )
    
    if direccion_input:
        lat_final, lng_final, direccion_final = geocodificar(direccion_input)

else:
    # Input por mapa
    st.info(t["instruccion_mapa"])
    
    # Mapa interactivo centrado en CDMX por defecto
    m = folium.Map(
        location=[19.4326, -99.1332],
        zoom_start=12
    )
    
    # Mostrar mapa y capturar clicks
    map_data = st_folium(m, width=700, height=500)
    
    if map_data and map_data.get("last_clicked"):
        st.session_state.lat_seleccionado = map_data["last_clicked"]["lat"]
        st.session_state.lng_seleccionado = map_data["last_clicked"]["lng"]
    
    if st.session_state.lat_seleccionado and st.session_state.lng_seleccionado:
        lat_final = st.session_state.lat_seleccionado
        lng_final = st.session_state.lng_seleccionado
        direccion_final = reverse_geocode(lat_final, lng_final)
        
        st.success(f"📍 {direccion_final}")

# Botón analizar
st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1,2,1])
with col2:
    analizar_btn = st.button(t["boton_analizar"], use_container_width=True)

# Procesar análisis
if analizar_btn:
    if not lat_final or not lng_final:
        st.error(t["error_ubicacion"])
    else:
        with st.spinner(t["analizando"]):
            # Buscar competencia
            competencia = buscar_competencia_con_fotos(lat_final, lng_final)
            
            # Calcular score
            score_info = calcular_score_competencia(competencia)
            
            # Análisis Claude
            analisis = generar_analisis_claude(direccion_final, competencia, score_info, st.session_state.idioma)
            
            # Mostrar resultados
            st.markdown("---")
            st.markdown(f"## {t['resultados']}")
            
            # Score
            st.markdown(f"""
            <div class="score-box">
                <h3>{t['score_titulo']}</h3>
                <div class="score-number">{score_info['score']}/100</div>
                <p style='font-size: 20px; color: #0047AB; font-weight: bold;'>{score_info['nivel']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Ventajas y Riesgos
            col_v, col_r = st.columns(2)
            
            with col_v:
                st.markdown(f"### {t['ventajas']}")
                for ventaja in analisis['ventajas']:
                    st.write(f"✓ {ventaja}")
            
            with col_r:
                st.markdown(f"### {t['riesgos']}")
                for riesgo in analisis['riesgos']:
                    st.write(f"⚠️ {riesgo}")
            
            # Competencia
            st.markdown(f"### {t['competencia']}")
            if competencia:
                comp_df = []
                for comp in competencia[:5]:
                    comp_df.append({
                        t["tabla_nombre"] if st.session_state.idioma == "es" else "Name": comp['nombre'],
                        "Rating": f"{comp['rating']}⭐" if comp['rating'] > 0 else "N/A",
                        t["tabla_reseñas"] if st.session_state.idioma == "es" else "Reviews": comp['total_ratings']
                    })
                st.dataframe(comp_df, use_container_width=True)
            
            # Generar PDF para descarga
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Generar PDF en memoria
            pdf_buffer = generar_pdf_simple(
                direccion_final, 
                lat_final, 
                lng_final, 
                competencia, 
                score_info, 
                analisis, 
                st.session_state.idioma
            )
            
            # Botón de descarga
            st.download_button(
                label=f"📥 {t['descargar_pdf']}",
                data=pdf_buffer,
                file_name=f"4site_reporte_gratis_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
            st.info("💎 **Upgrade al reporte PRO ($99 MXN)** para obtener: Mapa, fotos de competencia, análisis profundo, forecast de ventas y más.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📧 hola@4site.mx | 🌐 4site.mx</p>
    <p>© 2026 4site - Análisis de ubicaciones con IA</p>
</div>
""", unsafe_allow_html=True)