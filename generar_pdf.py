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
from io import BytesIO

load_dotenv()

# Inicializar APIs
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_API_KEY"))
claude = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Textos bilingües
TEXTOS = {
    "es": {
        "titulo_analisis": "ANÁLISIS DE UBICACIÓN",
        "tipo": "Tipo: Cafetería",
        "fecha": "Fecha",
        "score_viabilidad": "SCORE DE VIABILIDAD",
        "metodologia": "Análisis basado en metodología cuantitativa",
        "resumen": "RESUMEN RÁPIDO",
        "competencia_titulo": "COMPETENCIA CERCANA (500m)",
        "competencia_identificada": "negocios similares identificados",
        "tabla_nombre": "Nombre",
        "tabla_rating": "Rating",
        "tabla_reseñas": "Reseñas",
        "mapa_ubicacion": "MAPA DE LA UBICACIÓN",
        "area_analisis": "Área de análisis: 500m radio",
        "imagenes_competencia": "IMÁGENES DE LA COMPETENCIA",
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
        "cta_boton": "COMPRAR ANÁLISIS COMPLETO - $99 MXN",
        "footer_derechos": "© 2026 4site - Análisis de ubicaciones con IA"
    },
    "en": {
        "titulo_analisis": "LOCATION ANALYSIS",
        "tipo": "Type: Coffee Shop",
        "fecha": "Date",
        "score_viabilidad": "VIABILITY SCORE",
        "metodologia": "Analysis based on quantitative methodology",
        "resumen": "QUICK SUMMARY",
        "competencia_titulo": "NEARBY COMPETITION (500m)",
        "competencia_identificada": "similar businesses identified",
        "tabla_nombre": "Name",
        "tabla_rating": "Rating",
        "tabla_reseñas": "Reviews",
        "mapa_ubicacion": "LOCATION MAP",
        "area_analisis": "Analysis area: 500m radius",
        "imagenes_competencia": "COMPETITION IMAGES",
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
        "cta_boton": "BUY COMPLETE ANALYSIS - $99 MXN",
        "footer_derechos": "© 2026 4site - Location analysis with AI"
    }
}

def geocodificar(direccion, idioma="es"):
    """Convierte dirección en coordenadas"""
    if idioma == "es":
        print(f"\n📍 Geocodificando: {direccion}")
    else:
        print(f"\n📍 Geocoding: {direccion}")
    
    resultado = gmaps.geocode(direccion)
    if resultado:
        coords = resultado[0]["geometry"]["location"]
        print(f"   ✅ {coords['lat']}, {coords['lng']}")
        return coords["lat"], coords["lng"], resultado[0]["formatted_address"]
    else:
        print("   ❌ Location not found" if idioma == "en" else "   ❌ No se encontró la ubicación")
        return None, None, None

def obtener_mapa_estatico(lat, lng, archivo_salida="mapa_ubicacion.png"):
    """Descarga mapa estático de Google con pin y círculo de 500m"""
    print("\n🗺️  Generando mapa estático..." if idioma == "es" else "\n🗺️  Generating static map...")
    
    # URL de Google Static Maps API
    url = "https://maps.googleapis.com/maps/api/staticmap"
    
    params = {
        "center": f"{lat},{lng}",
        "zoom": 15,
        "size": "600x400",
        "maptype": "roadmap",
        "markers": f"color:red|{lat},{lng}",
        "path": f"color:0x0000FF80|weight:2|fillcolor:0x0000FF20|enc:{codificar_circulo(lat, lng, 500)}",
        "key": GOOGLE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        with open(archivo_salida, 'wb') as f:
            f.write(response.content)
        
        print(f"   ✅ Mapa guardado: {archivo_salida}")
        return archivo_salida
    except Exception as e:
        print(f"   ⚠️  Error descargando mapa: {e}")
        return None

def codificar_circulo(lat, lng, radio_metros):
    """Genera puntos para círculo en formato encoded polyline"""
    import math
    puntos = []
    num_puntos = 32
    
    # Radio de la Tierra en metros
    R = 6378137
    
    for i in range(num_puntos + 1):
        angulo = (2 * math.pi * i) / num_puntos
        dx = radio_metros * math.cos(angulo)
        dy = radio_metros * math.sin(angulo)
        
        nueva_lat = lat + (dy / R) * (180 / math.pi)
        nueva_lng = lng + (dx / R) * (180 / math.pi) / math.cos(lat * math.pi / 180)
        
        puntos.append(f"{nueva_lat},{nueva_lng}")
    
    return "|".join(puntos)

def buscar_competencia_con_fotos(lat, lng):
    """Busca cafeterías cercanas incluyendo referencias a fotos"""
    print("\n🏪 Buscando cafés cercanos...")
    
    url = "https://places.googleapis.com/v1/places:searchNearby"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.photos,places.id"
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
                photo_ref = None
                if "photos" in lugar and len(lugar["photos"]) > 0:
                    photo_ref = lugar["photos"][0].get("name")
                
                competidores.append({
                    "nombre": lugar.get("displayName", {}).get("text", "Sin nombre"),
                    "rating": lugar.get("rating", 0),
                    "total_ratings": lugar.get("userRatingCount", 0),
                    "photo_reference": photo_ref
                })
        
        print(f"   ✅ Encontrados: {len(competidores)} competidores")
        return competidores
    
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        return []

def descargar_foto_lugar(photo_name, archivo_salida, max_width=400):
    """Descarga foto de un lugar usando Places API (New)"""
    if not photo_name:
        return None
    
    url = f"https://places.googleapis.com/v1/{photo_name}/media"
    
    params = {
        "maxWidthPx": max_width,
        "key": GOOGLE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        with open(archivo_salida, 'wb') as f:
            f.write(response.content)
        
        return archivo_salida
    except Exception as e:
        print(f"   ⚠️  Error descargando foto: {e}")
        return None

def descargar_fotos_competencia(competidores, max_fotos=3):
    """Descarga fotos de los top competidores"""
    print("\n📸 Descargando fotos de competencia...")
    
    fotos_descargadas = []
    contador = 0
    
    for comp in competidores[:max_fotos]:
        if comp['photo_reference'] and contador < max_fotos:
            archivo = f"comp_foto_{contador}.jpg"
            resultado = descargar_foto_lugar(comp['photo_reference'], archivo)
            if resultado:
                fotos_descargadas.append({
                    "archivo": archivo,
                    "nombre": comp['nombre']
                })
                contador += 1
                print(f"   ✅ Foto {contador}: {comp['nombre'][:30]}")
    
    print(f"   ✅ Total fotos descargadas: {len(fotos_descargadas)}")
    return fotos_descargadas

def calcular_score_competencia(competidores):
    """Calcula score basado en metodología matemática"""
    print("\n📊 Calculando score metodológico...")
    
    num_competidores = len(competidores)
    
    # FACTOR 1: DENSIDAD (50%)
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
    
    # FACTOR 2: CALIDAD (30%)
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
    
    # FACTOR 3: CONSOLIDACIÓN (20%)
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
    
    # SCORE FINAL
    score_final = int(
        densidad_score * 0.50 +
        calidad_score * 0.30 +
        consolidacion_score * 0.20
    )
    
    # NIVEL
    if score_final >= 80:
        nivel = "ALTO" if idioma == "es" else "HIGH"
    elif score_final >= 65:
        nivel = "MEDIO-ALTO" if idioma == "es" else "MEDIUM-HIGH"
    elif score_final >= 50:
        nivel = "MEDIO" if idioma == "es" else "MEDIUM"
    else:
        nivel = "BAJO" if idioma == "es" else "LOW"
    
    print(f"   ✅ Score: {score_final}/100 ({nivel})")
    print(f"      - Densidad: {densidad_score:.0f} pts (50%)")
    print(f"      - Calidad: {calidad_score:.0f} pts (30%)")
    print(f"      - Consolidación: {consolidacion_score:.0f} pts (20%)")
    
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

def generar_analisis_claude(direccion, competencia, score_info, idioma="es"):
    """Claude genera ventajas/riesgos en el idioma especificado"""
    print(f"\n🤖 Generando análisis ({idioma})...")
    
    comp_texto = json.dumps(competencia[:5], indent=2, ensure_ascii=False) if competencia else "No competition found"
    
    if idioma == "es":
        prompt = f"""Eres analista experto en ubicaciones comerciales.

Ubicación: {direccion}

Score YA CALCULADO: {score_info['score']}/100 ({score_info['nivel']})

Desglose:
- Densidad: {score_info['desglose']['densidad']}/100
- Calidad: {score_info['desglose']['calidad']}/100
- Consolidación: {score_info['desglose']['consolidacion']}/100

Competencia ({score_info['desglose']['num_competidores']} cafés en 500m):
{comp_texto}

Genera en formato JSON:
{{
  "ventajas": [
    "Ventaja 1 (máx 20 palabras)",
    "Ventaja 2 (máx 20 palabras)"
  ],
  "riesgos": [
    "Riesgo 1 (máx 20 palabras)",
    "Riesgo 2 (máx 20 palabras)"
  ]
}}

Responde SOLO el JSON en ESPAÑOL."""
    else:
        prompt = f"""You are an expert in commercial location analysis.

Location: {direccion}

Score ALREADY CALCULATED: {score_info['score']}/100 ({score_info['nivel']})

Breakdown:
- Density: {score_info['desglose']['densidad']}/100
- Quality: {score_info['desglose']['calidad']}/100
- Consolidation: {score_info['desglose']['consolidacion']}/100

Competition ({score_info['desglose']['num_competidores']} cafes within 500m):
{comp_texto}

Generate in JSON format:
{{
  "ventajas": [
    "Advantage 1 (max 20 words)",
    "Advantage 2 (max 20 words)"
  ],
  "riesgos": [
    "Risk 1 (max 20 words)",
    "Risk 2 (max 20 words)"
  ]
}}

Respond ONLY the JSON in ENGLISH."""
    
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
    
    try:
        analisis = json.loads(texto)
        print("   ✅ Análisis generado")
        return analisis
    except:
        print("   ⚠️  Usando estructura por defecto")
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

def generar_pdf(direccion, lat, lng, competencia, score_info, analisis_claude, 
                archivo_mapa, fotos_comp, idioma, archivo_salida):
    """Genera PDF completo con mapa, fotos y bilingüe"""
    print(f"\n📄 Generando PDF ({idioma}): {archivo_salida}")
    
    t = TEXTOS[idioma]
    
    pdf = SimpleDocTemplate(
        archivo_salida,
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
        textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER, spaceAfter=5
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'], fontSize=11,
        textColor=colors.grey, alignment=TA_CENTER, spaceAfter=20
    )
    header_style = ParagraphStyle(
        'Header', parent=styles['Heading2'], fontSize=14,
        textColor=colors.HexColor('#0047AB'), spaceAfter=10, spaceBefore=15
    )
    
    # ========== PÁGINA 1 ==========
    
    # Logo
    if os.path.exists("logo_4site.png"):
        try:
            logo_img = Image("logo_4site.png", width=2.5*inch, height=1*inch)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
            story.append(Spacer(1, 0.1*inch))
        except:
            story.append(Paragraph("4SITE", title_style))
    else:
        story.append(Paragraph("4SITE", title_style))
    
    story.append(Paragraph("Don't guess. Foresee.", subtitle_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Info
    story.append(Paragraph(t["titulo_analisis"], header_style))
    story.append(Paragraph(direccion, styles['Normal']))
    story.append(Paragraph(t["tipo"], styles['Normal']))
    story.append(Paragraph(f"{t['fecha']}: {datetime.now().strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Score
    story.append(Paragraph(t["score_viabilidad"], header_style))
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
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph(t["metodologia"], styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Resumen
    story.append(Paragraph(t["resumen"], header_style))
    for ventaja in analisis_claude['ventajas']:
        story.append(Paragraph(f"✓ {ventaja}", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    for riesgo in analisis_claude['riesgos']:
        story.append(Paragraph(f"⚠ {riesgo}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Competencia tabla
    story.append(Paragraph(t["competencia_titulo"], header_style))
    story.append(Paragraph(f"🏪 {len(competencia)} {t['competencia_identificada']}", styles['Normal']))
    
    if competencia:
        comp_data = [[t["tabla_nombre"], t["tabla_rating"], t["tabla_reseñas"]]]
        for comp in competencia[:3]:
            comp_data.append([
                comp['nombre'][:25],
                str(comp['rating']) if comp['rating'] > 0 else "N/A",
                str(comp['total_ratings'])
            ])
        
        comp_table = Table(comp_data, colWidths=[2.2*inch, 1*inch, 1*inch])
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
    
    # ========== PÁGINA 2 ==========
    story.append(PageBreak())
    
    # Mapa
    if archivo_mapa and os.path.exists(archivo_mapa):
        story.append(Paragraph(t["mapa_ubicacion"], header_style))
        story.append(Paragraph(t["area_analisis"], styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        try:
            mapa_img = Image(archivo_mapa, width=5*inch, height=3.3*inch)
            mapa_img.hAlign = 'CENTER'
            story.append(mapa_img)
            story.append(Spacer(1, 0.2*inch))
        except:
            pass
    
    # Fotos competencia
    if fotos_comp:
        story.append(Paragraph(t["imagenes_competencia"], header_style))
        story.append(Spacer(1, 0.1*inch))
        
        for foto in fotos_comp[:3]:
            if os.path.exists(foto['archivo']):
                try:
                    story.append(Paragraph(f"• {foto['nombre'][:40]}", styles['Normal']))
                    comp_img = Image(foto['archivo'], width=4*inch, height=2.7*inch)
                    comp_img.hAlign = 'CENTER'
                    story.append(comp_img)
                    story.append(Spacer(1, 0.15*inch))
                except:
                    pass
    
    # Watermark
    story.append(Spacer(1, 0.2*inch))
    watermark_style = ParagraphStyle(
        'Watermark', parent=styles['Normal'], fontSize=10,
        textColor=colors.grey, alignment=TA_CENTER
    )
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━", watermark_style))
    story.append(Paragraph(t["watermark"], watermark_style))
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━", watermark_style))
    
    # ========== PÁGINA 3 ==========
    story.append(PageBreak())
    
    story.append(Spacer(1, 0.5*inch))
    cta_style = ParagraphStyle(
        'CTA', parent=styles['Heading2'], fontSize=16,
        textColor=colors.HexColor('#0047AB'), alignment=TA_CENTER, spaceAfter=20
    )
    story.append(Paragraph(t["cta_titulo"], cta_style))
    
    story.append(Paragraph(t["cta_intro"], styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    
    for beneficio in t["beneficios"]:
        story.append(Paragraph(beneficio, styles['Normal']))
    
    story.append(Spacer(1, 0.3*inch))
    
    # CTA Button
    cta_data = [[t["cta_boton"]]]
    cta_table = Table(cta_data, colWidths=[5*inch])
    cta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('FONTSIZE', (0, 0), (0, 0), 14),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#00D4D4')),
        ('BOX', (0, 0), (0, 0), 2, colors.HexColor('#00D4D4')),
        ('TOPPADDING', (0, 0), (0, 0), 15),
        ('BOTTOMPADDING', (0, 0), (0, 0), 15),
    ]))
    story.append(cta_table)
    story.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'], fontSize=9,
        textColor=colors.grey, alignment=TA_CENTER
    )
    story.append(Paragraph("📧 hola@4site.mx", footer_style))
    story.append(Paragraph("🌐 4site.mx", footer_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(t["footer_derechos"], footer_style))
    
    pdf.build(story)
    print(f"   ✅ PDF generado: {archivo_salida}")

def main():
    global idioma
    
    print("="*60)
    print("🎯 4SITE - GENERADOR COMPLETO DE REPORTES")
    print("   • Scoring metodológico")
    print("   • Mapa estático")
    print("   • Imágenes de competencia")
    print("   • Bilingüe (ES/EN)")
    print("="*60)
    
    # Selección de idioma
    print("\n🌐 Language / Idioma:")
    print("1. Español")
    print("2. English")
    idioma_input = input("Selecciona / Select (1/2): ").strip()
    idioma = "es" if idioma_input == "1" else "en"
    
    # Dirección
    if idioma == "es":
        direccion = input("\nIngresa la dirección a analizar: ")
    else:
        direccion = input("\nEnter address to analyze: ")
    
    # Paso 1: Geocodificar
    lat, lng, dir_formateada = geocodificar(direccion, idioma)
    if not lat:
        return
    
    # Paso 2: Mapa estático
    archivo_mapa = obtener_mapa_estatico(lat, lng)
    
    # Paso 3: Buscar competencia con fotos
    competencia = buscar_competencia_con_fotos(lat, lng)
    
    # Paso 4: Descargar fotos
    fotos_comp = descargar_fotos_competencia(competencia, max_fotos=3)
    
    # Paso 5: Calcular score
    score_info = calcular_score_competencia(competencia)
    
    # Paso 6: Análisis Claude
    analisis_claude = generar_analisis_claude(dir_formateada, competencia, score_info, idioma)
    
    # Paso 7: Generar PDF
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_pdf = f"4site_reporte_{idioma}_{timestamp}.pdf"
    
    generar_pdf(dir_formateada, lat, lng, competencia, score_info, analisis_claude,
                archivo_mapa, fotos_comp, idioma, archivo_pdf)
    
    print("\n" + "="*60)
    print(f"✅ REPORTE COMPLETO GENERADO: {archivo_pdf}")
    print("="*60)
    print(f"\n📊 Score: {score_info['score']}/100 ({score_info['nivel']})")
    print(f"   Competidores: {score_info['desglose']['num_competidores']}")
    print(f"   Rating promedio: {score_info['desglose']['rating_promedio']}")
    print(f"🗺️  Mapa: {'✅' if archivo_mapa else '❌'}")
    print(f"📸 Fotos: {len(fotos_comp)} descargadas")
    print(f"🌐 Idioma: {'Español' if idioma == 'es' else 'English'}")

if __name__ == "__main__":
    main()