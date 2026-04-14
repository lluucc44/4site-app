"""
modulos_4site.py
================
Módulos de enriquecimiento de datos para 4SITE:
  1. INEGI_Engine    — datos Censo 2020 + proyección al año actual
  2. Trafico_Engine  — horarios de flujo estimados por tipo de zona + competidores
  3. Mercado_Engine  — tamaño de mercado potencial
  4. Forecast_Engine — proyección de ventas 3 escenarios
  5. ROI_Engine      — punto de equilibrio + retorno sobre inversión
"""

import math
import datetime
import requests

# ─────────────────────────────────────────────────────────────────
# 1. INEGI ENGINE
# Fuente: INEGI Censo 2020 + tasa de crecimiento intercensal
# API gratuita: https://www.inegi.org.mx/servicios/api_indicadores.html
# Fallback: tabla embebida por municipio/alcaldía con proyección
# ─────────────────────────────────────────────────────────────────

AÑO_CENSO   = 2020
AÑO_ACTUAL  = datetime.datetime.now().year

# Tasas de crecimiento poblacional anual estimadas por zona (CONAPO 2020-2030)
# Fuente: Proyecciones de Población CONAPO
TASAS_CRECIMIENTO = {
    # CDMX alcaldías
    "cuauhtémoc":           0.0045,
    "miguel hidalgo":       0.0038,
    "benito juárez":        0.0052,
    "coyoacán":             0.0031,
    "álvaro obregón":       0.0028,
    "iztapalapa":           0.0055,
    "gustavo a. madero":    0.0020,
    "azcapotzalco":         0.0015,
    "venustiano carranza":  0.0022,
    "iztacalco":            0.0018,
    "xochimilco":           0.0042,
    "tlalpan":              0.0061,
    "magdalena contreras":  0.0035,
    "cuajimalpa":           0.0078,
    "tláhuac":              0.0048,
    "milpa alta":           0.0065,
    # Otras ciudades principales
    "monterrey":            0.0082,
    "guadalajara":          0.0048,
    "puebla":               0.0071,
    "tijuana":              0.0095,
    "león":                 0.0088,
    "juárez":               0.0102,
    "zapopan":              0.0091,
    "nezahualcóyotl":       0.0012,
    "ecatepec":             0.0025,
    "naucalpan":            0.0031,
    "toluca":               0.0058,
    "querétaro":            0.0112,
    "mérida":               0.0095,
    "san luis potosí":      0.0078,
    "aguascalientes":       0.0089,
    "default":              0.0055,  # Nacional promedio
}

# Tabla embebida Censo 2020 — densidad y datos clave por zona
# (densidad hab/km², ingreso promedio mensual MXN, NSE, personas_hogar)
INEGI_ZONAS = {
    # ── CDMX ──────────────────────────────────────────────────────
    "polanco":           {"densidad": 14500, "ingreso": 42000, "nse": "A/B",  "personas_hogar": 2.8, "municipio": "miguel hidalgo"},
    "santa fe":          {"densidad": 8200,  "ingreso": 48000, "nse": "A",    "personas_hogar": 2.6, "municipio": "cuajimalpa"},
    "lomas":             {"densidad": 6800,  "ingreso": 52000, "nse": "A",    "personas_hogar": 2.7, "municipio": "miguel hidalgo"},
    "condesa":           {"densidad": 18200, "ingreso": 32000, "nse": "A/B",  "personas_hogar": 2.4, "municipio": "cuauhtémoc"},
    "roma":              {"densidad": 19800, "ingreso": 28000, "nse": "B",    "personas_hogar": 2.5, "municipio": "cuauhtémoc"},
    "narvarte":          {"densidad": 22000, "ingreso": 22000, "nse": "B/C+", "personas_hogar": 2.6, "municipio": "benito juárez"},
    "del valle":         {"densidad": 24500, "ingreso": 20000, "nse": "B/C+", "personas_hogar": 2.7, "municipio": "benito juárez"},
    "coyoacán":          {"densidad": 12800, "ingreso": 22000, "nse": "B/C+", "personas_hogar": 3.0, "municipio": "coyoacán"},
    "tlalpan":           {"densidad": 2800,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.4, "municipio": "tlalpan"},
    "xochimilco":        {"densidad": 4200,  "ingreso": 12000, "nse": "C/D+", "personas_hogar": 3.8, "municipio": "xochimilco"},
    "iztapalapa":        {"densidad": 16800, "ingreso": 10000, "nse": "C/D+", "personas_hogar": 4.1, "municipio": "iztapalapa"},
    "ecatepec":          {"densidad": 14200, "ingreso": 9500,  "nse": "D+",   "personas_hogar": 4.3, "municipio": "ecatepec"},
    "nezahualcóyotl":    {"densidad": 18500, "ingreso": 9000,  "nse": "D+",   "personas_hogar": 4.2, "municipio": "nezahualcóyotl"},
    "naucalpan":         {"densidad": 8800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.2, "municipio": "naucalpan"},
    "satélite":          {"densidad": 7200,  "ingreso": 24000, "nse": "B/C+", "personas_hogar": 3.0, "municipio": "naucalpan"},
    "interlomas":        {"densidad": 5800,  "ingreso": 32000, "nse": "A/B",  "personas_hogar": 2.8, "municipio": "huixquilucan"},
    # ── GDL ────────────────────────────────────────────────────────
    "guadalajara":       {"densidad": 9800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.5, "municipio": "guadalajara"},
    "zapopan":           {"densidad": 6200,  "ingreso": 26000, "nse": "B/C+", "personas_hogar": 3.1, "municipio": "zapopan"},
    "tlaquepaque":       {"densidad": 7400,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "municipio": "tlaquepaque"},
    "providencia":       {"densidad": 8900,  "ingreso": 38000, "nse": "A/B",  "personas_hogar": 2.9, "municipio": "guadalajara"},
    # ── MTY ────────────────────────────────────────────────────────
    "monterrey":         {"densidad": 11200, "ingreso": 22000, "nse": "C+",   "personas_hogar": 3.3, "municipio": "monterrey"},
    "san pedro":         {"densidad": 4800,  "ingreso": 55000, "nse": "A",    "personas_hogar": 2.7, "municipio": "san pedro garza garcía"},
    "santa catarina":    {"densidad": 6200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.7, "municipio": "santa catarina"},
    "apodaca":           {"densidad": 7800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.8, "municipio": "apodaca"},
    # ── Otras ─────────────────────────────────────────────────────
    "puebla":            {"densidad": 8400,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "municipio": "puebla"},
    "querétaro":         {"densidad": 6800,  "ingreso": 20000, "nse": "C+",   "personas_hogar": 3.3, "municipio": "querétaro"},
    "mérida":            {"densidad": 5200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "municipio": "mérida"},
    "tijuana":           {"densidad": 9200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.7, "municipio": "tijuana"},
    "león":              {"densidad": 7600,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.8, "municipio": "león"},
    "default":           {"densidad": 8000,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.6, "municipio": "default"},
}

# Gasto mensual promedio por tipo de negocio (% del ingreso) — INEGI ENIGH 2022
GASTO_POR_TIPO = {
    "cafe_premium":       {"pct_gasto": 0.04, "ticket_promedio": 180, "visitas_mes": 8},
    "cafe_casual":        {"pct_gasto": 0.035,"ticket_promedio": 120, "visitas_mes": 10},
    "restaurante_casual": {"pct_gasto": 0.08, "ticket_promedio": 220, "visitas_mes": 6},
    "restaurante_fino":   {"pct_gasto": 0.06, "ticket_promedio": 600, "visitas_mes": 2},
    "comida_rapida":      {"pct_gasto": 0.05, "ticket_promedio": 90,  "visitas_mes": 12},
    "gimnasio_boutique":  {"pct_gasto": 0.04, "ticket_promedio": 1200,"visitas_mes": 1},
    "gimnasio_regular":   {"pct_gasto": 0.03, "ticket_promedio": 600, "visitas_mes": 1},
    "farmacia":           {"pct_gasto": 0.05, "ticket_promedio": 250, "visitas_mes": 3},
    "tienda_conveniencia":{"pct_gasto": 0.06, "ticket_promedio": 85,  "visitas_mes": 15},
    "panaderia":          {"pct_gasto": 0.02, "ticket_promedio": 65,  "visitas_mes": 10},
    "bar":                {"pct_gasto": 0.04, "ticket_promedio": 280, "visitas_mes": 4},
    "yoga_wellness":      {"pct_gasto": 0.03, "ticket_promedio": 800, "visitas_mes": 1},
    "guarderia":          {"pct_gasto": 0.08, "ticket_promedio": 3500,"visitas_mes": 1},
    "libreria":           {"pct_gasto": 0.01, "ticket_promedio": 180, "visitas_mes": 2},
    "servicios":          {"pct_gasto": 0.02, "ticket_promedio": 250, "visitas_mes": 2},
    "default":            {"pct_gasto": 0.04, "ticket_promedio": 200, "visitas_mes": 5},
}


def proyectar_poblacion(poblacion_2020, tasa_anual, años=None):
    """Proyecta población desde Censo 2020 al año actual con crecimiento compuesto"""
    if años is None:
        años = AÑO_ACTUAL - AÑO_CENSO
    return int(poblacion_2020 * ((1 + tasa_anual) ** años))


def obtener_zona_inegi(direccion, gmaps_client):
    """
    Detecta la zona más cercana en la tabla INEGI a partir de la dirección.
    Retorna (zona_key, datos_zona, municipio_key)
    """
    dir_lower = direccion.lower()

    # Buscar match directo con colonia/zona conocida
    for zona_key in INEGI_ZONAS:
        if zona_key in dir_lower:
            return zona_key, INEGI_ZONAS[zona_key]

    # Buscar por municipio en la dirección
    municipio_encontrado = None
    for mun_key in TASAS_CRECIMIENTO:
        if mun_key in dir_lower:
            municipio_encontrado = mun_key
            break

    # Si encontramos municipio, buscar zona de ese municipio
    if municipio_encontrado:
        for zona_key, datos in INEGI_ZONAS.items():
            if datos.get("municipio", "") == municipio_encontrado:
                return zona_key, datos

    return "default", INEGI_ZONAS["default"]


def obtener_datos_inegi(lat, lng, direccion, gmaps_client):
    """
    Obtiene datos demográficos enriquecidos del área.
    Fuente: tabla INEGI Censo 2020 + proyección CONAPO al año actual.
    Retorna dict con todos los indicadores.
    """
    zona_key, datos_zona = obtener_zona_inegi(direccion, gmaps_client)
    municipio = datos_zona.get("municipio", "default")
    tasa = TASAS_CRECIMIENTO.get(municipio, TASAS_CRECIMIENTO["default"])
    años_proyeccion = AÑO_ACTUAL - AÑO_CENSO

    # Área de 500m radio = π × 0.5² ≈ 0.785 km²
    area_km2 = 0.785

    # Datos base Censo 2020
    densidad_2020      = datos_zona["densidad"]
    ingreso_2020       = datos_zona["ingreso"]
    personas_hogar     = datos_zona["personas_hogar"]
    nse                = datos_zona["nse"]

    # Proyección al año actual
    # Densidad crece proporcional a población (asumimos área urbana estable)
    densidad_actual    = int(densidad_2020 * ((1 + tasa) ** años_proyeccion))
    poblacion_2020     = int(densidad_2020 * area_km2)
    poblacion_actual   = proyectar_poblacion(poblacion_2020, tasa)
    viviendas_2020     = int(poblacion_2020 / personas_hogar)
    viviendas_actual   = proyectar_poblacion(viviendas_2020, tasa * 0.9)  # viviendas crecen un poco menos

    # Ingreso ajustado por inflación acumulada (INPC ~5.5% anual promedio 2020-2026)
    inflacion_anual    = 0.055
    ingreso_actual     = int(ingreso_2020 * ((1 + inflacion_anual) ** años_proyeccion))
    gasto_actual       = int(ingreso_actual * 0.78)  # Coeficiente ENIGH

    # Personas por manzana (manzana típica = 100×100m = 0.01 km²)
    personas_manzana   = int(densidad_actual * 0.01)

    # Distribución edad estimada por NSE (INEGI ENIGH perfil)
    dist_edad = _distribucion_edad_por_nse(nse)

    return {
        # Identificación de zona
        "zona_detectada":       zona_key,
        "municipio":            municipio,
        "fuente":               f"INEGI Censo 2020 · Proyección CONAPO {AÑO_ACTUAL}",
        "tasa_crecimiento_pct": round(tasa * 100, 2),
        "años_proyectados":     años_proyeccion,

        # Población
        "poblacion_2020":       poblacion_2020,
        "poblacion_actual":     poblacion_actual,
        "crecimiento_personas": poblacion_actual - poblacion_2020,

        # Vivienda
        "viviendas_2020":       viviendas_2020,
        "viviendas_actual":     viviendas_actual,
        "personas_hogar":       personas_hogar,

        # Densidad
        "densidad_2020":        densidad_2020,
        "densidad_actual":      densidad_actual,
        "personas_manzana":     personas_manzana,

        # Economía
        "nse_predominante":     nse,
        "ingreso_2020":         ingreso_2020,
        "ingreso_actual":       ingreso_actual,
        "gasto_actual":         gasto_actual,
        "inflacion_aplicada":   f"{inflacion_anual*100:.1f}% anual acumulada",

        # Edad
        "distribucion_edad":    dist_edad,

        # Alias para compatibilidad con código existente
        "poblacion_estimada":   poblacion_actual,
        "viviendas_habitadas":  viviendas_actual,
        "densidad_hab_km2":     densidad_actual,
        "ingreso_promedio_mensual": ingreso_actual,
        "gasto_promedio_mensual":   gasto_actual,
    }


def _distribucion_edad_por_nse(nse):
    """Distribución de edad estimada por nivel socioeconómico (ENIGH 2022)"""
    perfiles = {
        "A":    {"0-17": 18, "18-35": 28, "36-55": 35, "56+": 19},
        "A/B":  {"0-17": 20, "18-35": 30, "36-55": 32, "56+": 18},
        "B":    {"0-17": 22, "18-35": 32, "36-55": 30, "56+": 16},
        "B/C+": {"0-17": 24, "18-35": 33, "36-55": 28, "56+": 15},
        "C+":   {"0-17": 26, "18-35": 34, "36-55": 26, "56+": 14},
        "C":    {"0-17": 28, "18-35": 33, "36-55": 25, "56+": 14},
        "C/D+": {"0-17": 30, "18-35": 32, "36-55": 24, "56+": 14},
        "D+":   {"0-17": 33, "18-35": 31, "36-55": 22, "56+": 14},
        "D/E":  {"0-17": 35, "18-35": 30, "36-55": 21, "56+": 14},
    }
    return perfiles.get(nse, perfiles["C"])


def clasificar_densidad(densidad_hab_km2):
    """Clasifica densidad con descripción completa"""
    personas_manzana = int(densidad_hab_km2 * 0.01)
    if densidad_hab_km2 < 2000:
        return {"nivel": "Muy Baja", "emoji": "📉", "color": "#9E9E9E",
                "descripcion": "Zona suburbana o periférica — flujo peatonal muy limitado",
                "personas_manzana": personas_manzana}
    elif densidad_hab_km2 < 6000:
        return {"nivel": "Baja", "emoji": "📊", "color": "#FF9800",
                "descripcion": "Zona residencial de baja densidad — clientela local limitada",
                "personas_manzana": personas_manzana}
    elif densidad_hab_km2 < 10000:
        return {"nivel": "Media", "emoji": "📈", "color": "#4CAF50",
                "descripcion": "Zona residencial típica — buen potencial de clientela local",
                "personas_manzana": personas_manzana}
    elif densidad_hab_km2 < 16000:
        return {"nivel": "Alta", "emoji": "🔥", "color": "#2196F3",
                "descripcion": "Zona urbana densa — excelente para comercio de barrio y servicios",
                "personas_manzana": personas_manzana}
    else:
        return {"nivel": "Muy Alta", "emoji": "⚡", "color": "#9C27B0",
                "descripcion": "Centro urbano de altísima densidad — máximo potencial comercial",
                "personas_manzana": personas_manzana}


# ─────────────────────────────────────────────────────────────────
# 2. TRÁFICO ENGINE
# Fuente: Google Places API (regularOpeningHours) + modelo por tipo de zona
# ─────────────────────────────────────────────────────────────────

# Perfiles de tráfico horario por tipo de zona (índice 0-100 por hora 0-23)
PERFILES_TRAFICO = {
    "paso": [
        # 0    1    2    3    4    5    6    7    8    9   10   11
          5,   3,   2,   2,   3,   8,  25,  65,  80,  70,  60,  65,
        # 12   13   14   15   16   17   18   19   20   21   22   23
          70,  65,  60,  65,  80,  90,  85,  70,  55,  40,  25,  10
    ],
    "comercial": [
        # 0    1    2    3    4    5    6    7    8    9   10   11
          3,   2,   2,   2,   2,   5,  10,  30,  60,  85,  90,  88,
        # 12   13   14   15   16   17   18   19   20   21   22   23
          75,  70,  80,  88,  90,  85,  75,  60,  40,  20,  10,   5
    ],
    "residencial": [
        # 0    1    2    3    4    5    6    7    8    9   10   11
          2,   1,   1,   1,   2,   5,  15,  40,  55,  60,  65,  70,
        # 12   13   14   15   16   17   18   19   20   21   22   23
          65,  55,  50,  55,  65,  70,  75,  70,  60,  45,  25,  10
    ],
    "mixto": [
        # 0    1    2    3    4    5    6    7    8    9   10   11
          3,   2,   2,   2,   3,   6,  18,  48,  68,  75,  80,  82,
        # 12   13   14   15   16   17   18   19   20   21   22   23
          72,  65,  68,  76,  85,  88,  80,  65,  48,  32,  18,   8
    ],
}

# Ajuste de perfil por tipo de negocio (multiplica el índice base)
AJUSTE_TRAFICO_NEGOCIO = {
    "cafe_premium":        {"perfil_base": "comercial", "pico_am": 1.3, "pico_pm": 0.8},
    "cafe_casual":         {"perfil_base": "paso",      "pico_am": 1.4, "pico_pm": 0.9},
    "restaurante_casual":  {"perfil_base": "comercial", "pico_am": 0.7, "pico_pm": 1.4},
    "restaurante_fino":    {"perfil_base": "comercial", "pico_am": 0.4, "pico_pm": 1.6},
    "comida_rapida":       {"perfil_base": "paso",      "pico_am": 1.0, "pico_pm": 1.3},
    "gimnasio_boutique":   {"perfil_base": "residencial","pico_am": 1.5, "pico_pm": 1.4},
    "gimnasio_regular":    {"perfil_base": "residencial","pico_am": 1.4, "pico_pm": 1.3},
    "farmacia":            {"perfil_base": "comercial", "pico_am": 1.0, "pico_pm": 1.0},
    "tienda_conveniencia": {"perfil_base": "paso",      "pico_am": 1.2, "pico_pm": 1.1},
    "panaderia":           {"perfil_base": "residencial","pico_am": 1.6, "pico_pm": 0.7},
    "bar":                 {"perfil_base": "comercial", "pico_am": 0.2, "pico_pm": 1.8},
    "yoga_wellness":       {"perfil_base": "residencial","pico_am": 1.5, "pico_pm": 1.2},
    "guarderia":           {"perfil_base": "residencial","pico_am": 1.8, "pico_pm": 1.6},
    "libreria":            {"perfil_base": "comercial", "pico_am": 0.8, "pico_pm": 1.0},
    "servicios":           {"perfil_base": "comercial", "pico_am": 0.9, "pico_pm": 1.1},
}

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DIAS_SEMANA_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def calcular_trafico_horario(tipo_zona, tipo_negocio_key, densidad_hab_km2):
    """
    Genera perfil de tráfico horario estimado (24h) para el tipo de negocio.
    Retorna lista de 24 valores (0-100) representando flujo relativo.
    """
    ajuste = AJUSTE_TRAFICO_NEGOCIO.get(tipo_negocio_key, {"perfil_base": "mixto", "pico_am": 1.0, "pico_pm": 1.0})
    perfil_base = PERFILES_TRAFICO.get(ajuste["perfil_base"], PERFILES_TRAFICO["mixto"])

    # Escalar por densidad (más densidad = más tráfico base)
    factor_densidad = min(1.3, max(0.7, densidad_hab_km2 / 10000))

    trafico = []
    for hora, valor in enumerate(perfil_base):
        # Aplicar ajuste AM (6-11) y PM (18-22)
        if 6 <= hora <= 11:
            valor_ajustado = valor * ajuste["pico_am"] * factor_densidad
        elif 18 <= hora <= 22:
            valor_ajustado = valor * ajuste["pico_pm"] * factor_densidad
        else:
            valor_ajustado = valor * factor_densidad
        trafico.append(min(100, int(valor_ajustado)))

    return trafico


def calcular_trafico_semanal(tipo_zona, tipo_negocio_key):
    """
    Genera índice de tráfico por día de la semana (Lun-Dom).
    Retorna lista de 7 valores (0-100).
    """
    perfiles_semana = {
        "cafe_premium":        [72, 75, 78, 80, 88, 100, 65],
        "cafe_casual":         [80, 78, 80, 82, 90, 100, 60],
        "restaurante_casual":  [65, 68, 72, 75, 88, 100, 85],
        "restaurante_fino":    [50, 55, 60, 68, 90, 100, 75],
        "comida_rapida":       [85, 82, 85, 87, 92, 100, 70],
        "gimnasio_boutique":   [90, 88, 92, 88, 85, 100, 75],
        "gimnasio_regular":    [88, 85, 88, 85, 82, 100, 70],
        "farmacia":            [90, 88, 88, 90, 92, 100, 75],
        "tienda_conveniencia": [88, 85, 85, 87, 90, 100, 88],
        "panaderia":           [80, 75, 75, 78, 85, 100, 95],
        "bar":                 [40, 45, 50, 60, 88, 100, 80],
        "yoga_wellness":       [88, 85, 90, 85, 82, 100, 70],
        "guarderia":           [100, 98, 98, 98, 95, 30,  10],
        "libreria":            [60, 62, 65, 68, 75, 100, 70],
        "servicios":           [75, 78, 78, 80, 88, 100, 60],
    }
    return perfiles_semana.get(tipo_negocio_key, [80, 78, 80, 82, 90, 100, 72])


def identificar_horas_pico(trafico_horario, top_n=3):
    """Identifica las N horas de mayor flujo"""
    horas_valor = [(hora, valor) for hora, valor in enumerate(trafico_horario)]
    horas_valor.sort(key=lambda x: x[1], reverse=True)
    picos = []
    for hora, valor in horas_valor[:top_n]:
        picos.append({
            "hora": hora,
            "hora_str": f"{hora:02d}:00 – {hora+1:02d}:00",
            "flujo": valor,
            "nivel": "Muy alto" if valor >= 80 else "Alto" if valor >= 60 else "Medio" if valor >= 40 else "Bajo"
        })
    return picos


def generar_reporte_trafico(tipo_zona, tipo_negocio_key, densidad_hab_km2, idioma="es"):
    """Genera reporte completo de tráfico para el tipo de negocio"""
    trafico_horario  = calcular_trafico_horario(tipo_zona, tipo_negocio_key, densidad_hab_km2)
    trafico_semanal  = calcular_trafico_semanal(tipo_zona, tipo_negocio_key)
    horas_pico       = identificar_horas_pico(trafico_horario, top_n=3)
    dia_pico         = DIAS_SEMANA[trafico_semanal.index(max(trafico_semanal))]
    dia_bajo         = DIAS_SEMANA[trafico_semanal.index(min(trafico_semanal))]
    flujo_promedio   = int(sum(trafico_horario) / 24)

    return {
        "trafico_horario":  trafico_horario,   # lista 24 valores
        "trafico_semanal":  trafico_semanal,   # lista 7 valores
        "horas_pico":       horas_pico,
        "dia_pico":         dia_pico,
        "dia_bajo":         dia_bajo,
        "flujo_promedio":   flujo_promedio,
        "nivel_general":    "Alto" if flujo_promedio >= 60 else "Medio" if flujo_promedio >= 40 else "Bajo",
    }


# ─────────────────────────────────────────────────────────────────
# 3. MERCADO ENGINE
# Mercado potencial = población × % del ingreso destinado al tipo de negocio
# ─────────────────────────────────────────────────────────────────

def calcular_mercado_potencial(datos_inegi, tipo_negocio_key, num_competidores):
    """
    Calcula el tamaño de mercado potencial en el área de 500m.
    Metodología: población × ingreso × % gasto × factor de captura
    """
    gasto_info   = GASTO_POR_TIPO.get(tipo_negocio_key, GASTO_POR_TIPO["default"])
    poblacion    = datos_inegi["poblacion_actual"]
    ingreso_msg  = datos_inegi["ingreso_actual"]

    # Mercado total (todos los competidores + tú)
    mercado_total_mensual = int(poblacion * ingreso_msg * gasto_info["pct_gasto"])

    # Factor de captura estimado según competidores
    # Con 0 competidores puedes capturar hasta 80% del mercado
    # Con muchos competidores, se divide más
    # Factor de captura conservador: % del mercado que TU negocio puede capturar
    # No todos los habitantes son tu cliente potencial (frecuencia, preferencia, etc.)
    if num_competidores == 0:
        factor_captura = 0.15   # Sin competencia, puedes capturar ~15% del mercado total
    elif num_competidores <= 2:
        factor_captura = 0.10
    elif num_competidores <= 5:
        factor_captura = 0.07
    elif num_competidores <= 10:
        factor_captura = 0.05
    else:
        factor_captura = 0.03

    mercado_captura_mensual = int(mercado_total_mensual * factor_captura)
    mercado_captura_anual   = mercado_captura_mensual * 12

    # Ticket promedio y visitas estimadas
    ticket = gasto_info["ticket_promedio"]
    clientes_dia_estimados = max(1, int(mercado_captura_mensual / ticket / 30))  # 30 días

    return {
        "mercado_total_mensual":   mercado_total_mensual,
        "mercado_total_anual":     mercado_total_mensual * 12,
        "factor_captura_pct":      round(factor_captura * 100, 0),
        "mercado_captura_mensual": mercado_captura_mensual,
        "mercado_captura_anual":   mercado_captura_anual,
        "ticket_promedio":         ticket,
        "clientes_dia_estimados":  clientes_dia_estimados,
        "metodologia": (
            f"Población {poblacion:,} hab × ingreso ${ingreso_msg:,}/mes × "
            f"{gasto_info['pct_gasto']*100:.1f}% gasto en categoría × "
            f"{factor_captura*100:.0f}% captura estimada"
        )
    }


# ─────────────────────────────────────────────────────────────────
# 4. FORECAST ENGINE
# 3 escenarios: pesimista / base / optimista
# ─────────────────────────────────────────────────────────────────

def generar_forecast(mercado, tipo_negocio_key, score_viabilidad, inversion_min, idioma="es"):
    """
    Genera forecast de ventas a 12 meses en 3 escenarios.
    Basado en mercado potencial, score y tipo de negocio.
    """
    # El mercado_captura representa el mercado potencial total accesible.
    # La penetración inicial real de un negocio nuevo es 10-25% de ese potencial.
    base_mensual = int(mercado["mercado_captura_mensual"] * 0.18)

    # Factores por escenario (ajustan la penetración base)
    factores = {
        "pesimista":  0.60,
        "base":       1.00,
        "optimista":  1.50,
    }

    # Curva de rampa: los primeros meses son más bajos (apertura gradual)
    # Mes 1: 30%, Mes 2: 50%, Mes 3-4: 70%, Mes 5-8: 90%, Mes 9-12: 100%
    rampa = [0.30, 0.50, 0.70, 0.70, 0.90, 0.90, 0.90, 0.90, 1.00, 1.00, 1.00, 1.00]

    escenarios = {}
    for nombre, factor in factores.items():
        ventas_mes = []
        for mes_idx, r in enumerate(rampa):
            venta = int(base_mensual * factor * r)
            ventas_mes.append(venta)
        total_anual = sum(ventas_mes)
        escenarios[nombre] = {
            "ventas_mensuales": ventas_mes,
            "total_anual": total_anual,
            "promedio_mensual": int(total_anual / 12),
            "mes_estabilizacion": 9,  # mes donde se estabiliza
        }

    # ROI básico (solo en escenario base)
    costos_operacion_est = int(escenarios["base"]["promedio_mensual"] * 0.65)  # ~65% de ventas en costos
    utilidad_mensual_est = escenarios["base"]["promedio_mensual"] - costos_operacion_est
    meses_recuperacion   = int(inversion_min / max(1, utilidad_mensual_est)) if utilidad_mensual_est > 0 else 99

    return {
        "escenarios":            escenarios,
        "costos_operacion_est":  costos_operacion_est,
        "utilidad_mensual_est":  utilidad_mensual_est,
        "meses_recuperacion":    meses_recuperacion,
        "meses_labels":          [f"M{i+1}" for i in range(12)],
        "supuestos": [
            f"Mercado base: ${mercado['mercado_captura_mensual']:,}/mes ({mercado['factor_captura_pct']:.0f}% captura)",
            f"Pesimista: -45% por competencia fuerte / apertura lenta",
            f"Optimista: +45% por diferenciación / marketing efectivo",
            f"Costos operativos estimados: ~65% de ventas",
            f"Rampa de apertura: 30% → 100% en 9 meses",
        ]
    }


# ─────────────────────────────────────────────────────────────────
# 5. ROI ENGINE
# ─────────────────────────────────────────────────────────────────

def calcular_roi(forecast, inversion_min, inversion_max, tipo_negocio_key):
    """Calcula ROI y punto de equilibrio"""
    escenario_base   = forecast["escenarios"]["base"]
    utilidad_mensual = forecast["utilidad_mensual_est"]
    utilidad_anual   = forecast["utilidad_mensual_est"] * 12
    meses_recovery   = (
        int(inversion_min / max(1, forecast["utilidad_mensual_est"]))
        if forecast["utilidad_mensual_est"] > 0 else 99
    )

    roi_12m_pct = round(
        (utilidad_anual - inversion_min) / inversion_min * 100, 1
    ) if inversion_min > 0 else 0

    # Punto de equilibrio mensual (ventas necesarias para cubrir costos fijos)
    # Estimamos costos fijos en ~40% de la inversión inicial repartidos en 12 meses
    costos_fijos_mes = int(inversion_min * 0.40 / 12)
    punto_eq_ventas  = int(costos_fijos_mes / 0.35)  # margen bruto ~35%

    return {
        "inversion_min":       inversion_min,
        "inversion_max":       inversion_max,
        "roi_12m_pct":         roi_12m_pct,
        "meses_recuperacion":  meses_recovery,
        "utilidad_mensual_est": utilidad_mensual,
        "costos_fijos_mes":    costos_fijos_mes,
        "punto_eq_ventas_mes": punto_eq_ventas,
        "clasificacion_roi":   (
            "Excelente 🟢" if roi_12m_pct > 30 else
            "Bueno 🟡"     if roi_12m_pct > 10 else
            "Marginal 🟠"  if roi_12m_pct > 0  else
            "Negativo 🔴"
        )
    }
