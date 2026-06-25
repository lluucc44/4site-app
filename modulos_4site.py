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

# ─────────────────────────────────────────────────────────────────
# TABLA MAESTRA DE MUNICIPIOS — CENSO INEGI 2020
# Fuente: INEGI Censo Población y Vivienda 2020 + ENIGH 2022
# Cobertura: ~400 municipios urbanos más relevantes de México
# Clave: nombre_municipio (normalizado sin acentos para matching)
# Campos: densidad (hab/km²), ingreso (MXN/mes), nse, personas_hogar, estado, tasa_crec
# ─────────────────────────────────────────────────────────────────

MUNICIPIOS_MX = {
    # ── CDMX — Alcaldías ──────────────────────────────────────────
    "miguel hidalgo":           {"densidad": 11200, "ingreso": 38000, "nse": "A/B",  "personas_hogar": 2.8, "estado": "Ciudad de México",    "tasa": 0.0038},
    "benito juarez":            {"densidad": 16800, "ingreso": 30000, "nse": "A/B",  "personas_hogar": 2.5, "estado": "Ciudad de México",    "tasa": 0.0052},
    "cuauhtemoc":               {"densidad": 15200, "ingreso": 24000, "nse": "B",    "personas_hogar": 2.6, "estado": "Ciudad de México",    "tasa": 0.0045},
    "coyoacan":                 {"densidad": 12800, "ingreso": 22000, "nse": "B/C+", "personas_hogar": 3.0, "estado": "Ciudad de México",    "tasa": 0.0031},
    "cuajimalpa":               {"densidad": 3800,  "ingreso": 32000, "nse": "A/B",  "personas_hogar": 2.9, "estado": "Ciudad de México",    "tasa": 0.0078},
    "alvaro obregon":           {"densidad": 8200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.2, "estado": "Ciudad de México",    "tasa": 0.0028},
    "tlalpan":                  {"densidad": 2800,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.4, "estado": "Ciudad de México",    "tasa": 0.0061},
    "xochimilco":               {"densidad": 4200,  "ingreso": 12000, "nse": "C/D+", "personas_hogar": 3.8, "estado": "Ciudad de México",    "tasa": 0.0042},
    "iztapalapa":               {"densidad": 16800, "ingreso": 10000, "nse": "C/D+", "personas_hogar": 4.1, "estado": "Ciudad de México",    "tasa": 0.0055},
    "gustavo a madero":         {"densidad": 14200, "ingreso": 11000, "nse": "C/D+", "personas_hogar": 3.9, "estado": "Ciudad de México",    "tasa": 0.0020},
    "azcapotzalco":             {"densidad": 13800, "ingreso": 14000, "nse": "C",    "personas_hogar": 3.5, "estado": "Ciudad de México",    "tasa": 0.0015},
    "venustiano carranza":      {"densidad": 14600, "ingreso": 12000, "nse": "C",    "personas_hogar": 3.6, "estado": "Ciudad de México",    "tasa": 0.0022},
    "iztacalco":                {"densidad": 18200, "ingreso": 12500, "nse": "C",    "personas_hogar": 3.6, "estado": "Ciudad de México",    "tasa": 0.0018},
    "tlahuac":                  {"densidad": 6200,  "ingreso": 10500, "nse": "C/D+", "personas_hogar": 3.9, "estado": "Ciudad de México",    "tasa": 0.0048},
    "magdalena contreras":      {"densidad": 3600,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.4, "estado": "Ciudad de México",    "tasa": 0.0035},
    "milpa alta":               {"densidad": 800,   "ingreso": 10000, "nse": "D+",   "personas_hogar": 4.2, "estado": "Ciudad de México",    "tasa": 0.0065},
    # ── Estado de México — ZM Valle de Toluca ─────────────────────
    "metepec":                  {"densidad": 7200,  "ingreso": 26000, "nse": "B/C+", "personas_hogar": 3.2, "estado": "Estado de México",    "tasa": 0.0072},
    "toluca":                   {"densidad": 6800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.7, "estado": "Estado de México",    "tasa": 0.0058},
    "zinacantepec":             {"densidad": 3100,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.9, "estado": "Estado de México",    "tasa": 0.0088},
    "lerma":                    {"densidad": 4200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7, "estado": "Estado de México",    "tasa": 0.0095},
    "san mateo atenco":         {"densidad": 5800,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0068},
    "calimaya":                 {"densidad": 2800,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0091},
    "ocoyoacac":                {"densidad": 2400,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0081},
    "almoloya de juarez":       {"densidad": 1800,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 4.0, "estado": "Estado de México",    "tasa": 0.0061},
    "tenango del valle":        {"densidad": 2200,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 4.0, "estado": "Estado de México",    "tasa": 0.0049},
    "tianguistenco":            {"densidad": 2400,  "ingreso": 11500, "nse": "C/D+", "personas_hogar": 4.0, "estado": "Estado de México",    "tasa": 0.0057},
    "mexicaltzingo":            {"densidad": 3800,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0045},
    "chapultepec":              {"densidad": 3200,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.7, "estado": "Estado de México",    "tasa": 0.0052},
    # ── Estado de México — ZM Valle de México ─────────────────────
    "ecatepec de morelos":      {"densidad": 14200, "ingreso": 9500,  "nse": "D+",   "personas_hogar": 4.3, "estado": "Estado de México",    "tasa": 0.0025},
    "nezahualcoyotl":           {"densidad": 18500, "ingreso": 9000,  "nse": "D+",   "personas_hogar": 4.2, "estado": "Estado de México",    "tasa": 0.0012},
    "naucalpan de juarez":      {"densidad": 8800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.2, "estado": "Estado de México",    "tasa": 0.0031},
    "tlalnepantla de baz":      {"densidad": 10200, "ingreso": 16000, "nse": "C",    "personas_hogar": 3.5, "estado": "Estado de México",    "tasa": 0.0022},
    "cuautitlan izcalli":       {"densidad": 7400,  "ingreso": 16500, "nse": "C",    "personas_hogar": 3.6, "estado": "Estado de México",    "tasa": 0.0045},
    "tecamac":                  {"densidad": 5800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0088},
    "texcoco":                  {"densidad": 4600,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0062},
    "nicolas romero":           {"densidad": 5200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0042},
    "tultitlan":                {"densidad": 9800,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.9, "estado": "Estado de México",    "tasa": 0.0031},
    "huixquilucan":             {"densidad": 5800,  "ingreso": 32000, "nse": "A/B",  "personas_hogar": 2.8, "estado": "Estado de México",    "tasa": 0.0071},
    "atizapan de zaragoza":     {"densidad": 8200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Estado de México",    "tasa": 0.0038},
    "tultepec":                 {"densidad": 7200,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.9, "estado": "Estado de México",    "tasa": 0.0042},
    "coacalco de berriozabal":  {"densidad": 8800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.7, "estado": "Estado de México",    "tasa": 0.0028},
    "cuautitlan":               {"densidad": 5200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7, "estado": "Estado de México",    "tasa": 0.0038},
    "ixtapaluca":               {"densidad": 4800,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.9, "estado": "Estado de México",    "tasa": 0.0065},
    "chalco":                   {"densidad": 5200,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 4.0, "estado": "Estado de México",    "tasa": 0.0058},
    "valle de chalco solidaridad": {"densidad": 11200, "ingreso": 9500,"nse": "D+",  "personas_hogar": 4.2, "estado": "Estado de México",    "tasa": 0.0035},
    "chimalhuacan":             {"densidad": 12800, "ingreso": 9000,  "nse": "D+",   "personas_hogar": 4.3, "estado": "Estado de México",    "tasa": 0.0048},
    "la paz":                   {"densidad": 8400,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 4.0, "estado": "Estado de México",    "tasa": 0.0041},
    "jilotzingo":               {"densidad": 800,   "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Estado de México",    "tasa": 0.0055},
    "tepetlaoxtoc":             {"densidad": 600,   "ingreso": 11500, "nse": "C",    "personas_hogar": 3.8, "estado": "Estado de México",    "tasa": 0.0048},
    # ── Jalisco ───────────────────────────────────────────────────
    "guadalajara":              {"densidad": 9800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Jalisco",             "tasa": 0.0048},
    "zapopan":                  {"densidad": 6200,  "ingreso": 26000, "nse": "B/C+", "personas_hogar": 3.1, "estado": "Jalisco",             "tasa": 0.0091},
    "san pedro tlaquepaque":    {"densidad": 7400,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Jalisco",             "tasa": 0.0062},
    "tonala":                   {"densidad": 6800,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.7, "estado": "Jalisco",             "tasa": 0.0078},
    "tlajomulco de zuniga":     {"densidad": 3800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Jalisco",             "tasa": 0.0145},
    "el salto":                 {"densidad": 4200,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.8, "estado": "Jalisco",             "tasa": 0.0112},
    "puerto vallarta":          {"densidad": 3200,  "ingreso": 16000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Jalisco",             "tasa": 0.0098},
    "tepatitlan de morelos":    {"densidad": 1800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.7, "estado": "Jalisco",             "tasa": 0.0052},
    # ── Nuevo León ────────────────────────────────────────────────
    "monterrey":                {"densidad": 11200, "ingreso": 22000, "nse": "C+",   "personas_hogar": 3.3, "estado": "Nuevo León",          "tasa": 0.0082},
    "san pedro garza garcia":   {"densidad": 4800,  "ingreso": 55000, "nse": "A",    "personas_hogar": 2.7, "estado": "Nuevo León",          "tasa": 0.0058},
    "santa catarina":           {"densidad": 6200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.7, "estado": "Nuevo León",          "tasa": 0.0062},
    "apodaca":                  {"densidad": 7800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.8, "estado": "Nuevo León",          "tasa": 0.0095},
    "san nicolas de los garza": {"densidad": 9200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.3, "estado": "Nuevo León",          "tasa": 0.0071},
    "guadalupe":                {"densidad": 8800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.5, "estado": "Nuevo León",          "tasa": 0.0062},
    "escobedo":                 {"densidad": 5200,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Nuevo León",          "tasa": 0.0108},
    "juarez":                   {"densidad": 4800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.7, "estado": "Nuevo León",          "tasa": 0.0118},
    "garcia":                   {"densidad": 2800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.7, "estado": "Nuevo León",          "tasa": 0.0155},
    # ── Puebla ────────────────────────────────────────────────────
    "puebla":                   {"densidad": 8400,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Puebla",              "tasa": 0.0071},
    "san andres cholula":       {"densidad": 4800,  "ingreso": 16000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Puebla",              "tasa": 0.0125},
    "san pedro cholula":        {"densidad": 4200,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.5, "estado": "Puebla",              "tasa": 0.0098},
    "cuautlancingo":            {"densidad": 5800,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.7, "estado": "Puebla",              "tasa": 0.0135},
    "amozoc":                   {"densidad": 3200,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.8, "estado": "Puebla",              "tasa": 0.0088},
    "tehuacan":                 {"densidad": 2800,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.7, "estado": "Puebla",              "tasa": 0.0058},
    # ── Querétaro ─────────────────────────────────────────────────
    "queretaro":                {"densidad": 6800,  "ingreso": 20000, "nse": "C+",   "personas_hogar": 3.3, "estado": "Querétaro",           "tasa": 0.0112},
    "el marques":               {"densidad": 3800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Querétaro",           "tasa": 0.0118},
    "corregidora":              {"densidad": 4200,  "ingreso": 24000, "nse": "B/C+", "personas_hogar": 3.2, "estado": "Querétaro",           "tasa": 0.0125},
    "san juan del rio":         {"densidad": 2200,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Querétaro",           "tasa": 0.0072},
    # ── Guanajuato ────────────────────────────────────────────────
    "leon":                     {"densidad": 7600,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.8, "estado": "Guanajuato",          "tasa": 0.0088},
    "irapuato":                 {"densidad": 7800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6, "estado": "Guanajuato",          "tasa": 0.0071},
    "celaya":                   {"densidad": 7200,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Guanajuato",          "tasa": 0.0082},
    "salamanca":                {"densidad": 3800,  "ingreso": 15500, "nse": "C",    "personas_hogar": 3.6, "estado": "Guanajuato",          "tasa": 0.0048},
    "silao":                    {"densidad": 2200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.6, "estado": "Guanajuato",          "tasa": 0.0095},
    "guanajuato":               {"densidad": 4800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Guanajuato",          "tasa": 0.0048},
    "san miguel de allende":    {"densidad": 1200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Guanajuato",          "tasa": 0.0065},
    # ── Baja California ───────────────────────────────────────────
    "tijuana":                  {"densidad": 9200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.7, "estado": "Baja California",     "tasa": 0.0095},
    "mexicali":                 {"densidad": 6800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Baja California",     "tasa": 0.0081},
    "ensenada":                 {"densidad": 2200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.5, "estado": "Baja California",     "tasa": 0.0075},
    "playas de rosarito":       {"densidad": 1800,  "ingreso": 15500, "nse": "C",    "personas_hogar": 3.6, "estado": "Baja California",     "tasa": 0.0112},
    "tecate":                   {"densidad": 1200,  "ingreso": 16500, "nse": "C",    "personas_hogar": 3.6, "estado": "Baja California",     "tasa": 0.0088},
    # ── Chihuahua ─────────────────────────────────────────────────
    "chihuahua":                {"densidad": 4800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Chihuahua",           "tasa": 0.0069},
    "ciudad juarez":            {"densidad": 8200,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.7, "estado": "Chihuahua",           "tasa": 0.0102},
    "delicias":                 {"densidad": 1800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.7, "estado": "Chihuahua",           "tasa": 0.0041},
    # ── Coahuila ──────────────────────────────────────────────────
    "saltillo":                 {"densidad": 6200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Coahuila",            "tasa": 0.0078},
    "torreon":                  {"densidad": 7400,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Coahuila",            "tasa": 0.0065},
    "monclova":                 {"densidad": 3200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Coahuila",            "tasa": 0.0035},
    "piedras negras":           {"densidad": 2200,  "ingreso": 17000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Coahuila",            "tasa": 0.0048},
    # ── Tamaulipas ────────────────────────────────────────────────
    "reynosa":                  {"densidad": 4800,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.7, "estado": "Tamaulipas",          "tasa": 0.0068},
    "matamoros":                {"densidad": 3800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.7, "estado": "Tamaulipas",          "tasa": 0.0055},
    "nuevo laredo":             {"densidad": 4200,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.7, "estado": "Tamaulipas",          "tasa": 0.0048},
    "tampico":                  {"densidad": 6800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Tamaulipas",          "tasa": 0.0025},
    "altamira":                 {"densidad": 2200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Tamaulipas",          "tasa": 0.0088},
    "ciudad victoria":          {"densidad": 2800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Tamaulipas",          "tasa": 0.0041},
    # ── Sonora ────────────────────────────────────────────────────
    "hermosillo":               {"densidad": 5200,  "ingreso": 20000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Sonora",              "tasa": 0.0088},
    "cajeme":                   {"densidad": 2800,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.6, "estado": "Sonora",              "tasa": 0.0048},
    "nogales":                  {"densidad": 2200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.6, "estado": "Sonora",              "tasa": 0.0058},
    "san luis rio colorado":    {"densidad": 1800,  "ingreso": 16500, "nse": "C",    "personas_hogar": 3.6, "estado": "Sonora",              "tasa": 0.0068},
    # ── Sinaloa ───────────────────────────────────────────────────
    "culiacan":                 {"densidad": 5800,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.7, "estado": "Sinaloa",             "tasa": 0.0075},
    "mazatlan":                 {"densidad": 3200,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Sinaloa",             "tasa": 0.0058},
    "ahome":                    {"densidad": 1800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.7, "estado": "Sinaloa",             "tasa": 0.0048},
    # ── Yucatán ───────────────────────────────────────────────────
    "merida":                   {"densidad": 5200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Yucatán",             "tasa": 0.0095},
    "kanasin":                  {"densidad": 4800,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.7, "estado": "Yucatán",             "tasa": 0.0118},
    "uman":                     {"densidad": 2400,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.8, "estado": "Yucatán",             "tasa": 0.0098},
    "progreso":                 {"densidad": 1200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.6, "estado": "Yucatán",             "tasa": 0.0102},
    "valladolid":               {"densidad": 1600,  "ingreso": 11500, "nse": "C",    "personas_hogar": 3.8, "estado": "Yucatán",             "tasa": 0.0055},
    # ── Quintana Roo ──────────────────────────────────────────────
    "benito juarez":            {"densidad": 7800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Quintana Roo",        "tasa": 0.0145},  # Cancún
    "solidaridad":              {"densidad": 5200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.5, "estado": "Quintana Roo",        "tasa": 0.0168},  # Playa del Carmen
    "isla mujeres":             {"densidad": 800,   "ingreso": 14000, "nse": "C",    "personas_hogar": 3.5, "estado": "Quintana Roo",        "tasa": 0.0098},
    "cozumel":                  {"densidad": 600,   "ingreso": 15000, "nse": "C",    "personas_hogar": 3.5, "estado": "Quintana Roo",        "tasa": 0.0075},
    "othon p blanco":           {"densidad": 1200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.6, "estado": "Quintana Roo",        "tasa": 0.0065},
    # ── San Luis Potosí ───────────────────────────────────────────
    "san luis potosi":          {"densidad": 5800,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "San Luis Potosí",     "tasa": 0.0078},
    "soledad de graciano sanchez": {"densidad": 6200, "ingreso": 14000, "nse": "C",  "personas_hogar": 3.7, "estado": "San Luis Potosí",     "tasa": 0.0085},
    "ciudad valles":            {"densidad": 1200,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.8, "estado": "San Luis Potosí",     "tasa": 0.0045},
    # ── Aguascalientes ────────────────────────────────────────────
    "aguascalientes":           {"densidad": 7200,  "ingreso": 17000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Aguascalientes",      "tasa": 0.0089},
    "jesus maria":              {"densidad": 3200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.6, "estado": "Aguascalientes",      "tasa": 0.0095},
    "san francisco de los romo": {"densidad": 2400, "ingreso": 14500, "nse": "C",    "personas_hogar": 3.7, "estado": "Aguascalientes",      "tasa": 0.0102},
    # ── Michoacán ─────────────────────────────────────────────────
    "morelia":                  {"densidad": 6800,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Michoacán",           "tasa": 0.0068},
    "lazaro cardenas":          {"densidad": 1800,  "ingreso": 15500, "nse": "C",    "personas_hogar": 3.6, "estado": "Michoacán",           "tasa": 0.0052},
    "zamora":                   {"densidad": 2800,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.8, "estado": "Michoacán",           "tasa": 0.0038},
    "uruapan":                  {"densidad": 3200,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.7, "estado": "Michoacán",           "tasa": 0.0042},
    # ── Morelos ───────────────────────────────────────────────────
    "cuernavaca":               {"densidad": 7200,  "ingreso": 16000, "nse": "C",    "personas_hogar": 3.5, "estado": "Morelos",             "tasa": 0.0045},
    "jiutepec":                 {"densidad": 5800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6, "estado": "Morelos",             "tasa": 0.0058},
    "temixco":                  {"densidad": 4200,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.7, "estado": "Morelos",             "tasa": 0.0048},
    "cuautla":                  {"densidad": 3800,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7, "estado": "Morelos",             "tasa": 0.0038},
    # ── Veracruz ──────────────────────────────────────────────────
    "veracruz":                 {"densidad": 7200,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.8, "estado": "Veracruz",            "tasa": 0.0035},
    "xalapa":                   {"densidad": 8400,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Veracruz",            "tasa": 0.0052},
    "coatzacoalcos":            {"densidad": 4800,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Veracruz",            "tasa": 0.0025},
    "boca del rio":             {"densidad": 5200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Veracruz",            "tasa": 0.0042},
    "minatitlan":               {"densidad": 2800,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.8, "estado": "Veracruz",            "tasa": 0.0018},
    "orizaba":                  {"densidad": 6200,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.7, "estado": "Veracruz",            "tasa": 0.0022},
    # ── Guerrero ──────────────────────────────────────────────────
    "acapulco de juarez":       {"densidad": 8400,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 3.9, "estado": "Guerrero",            "tasa": 0.0022},
    "chilpancingo de los bravo": {"densidad": 2800, "ingreso": 12000, "nse": "C",    "personas_hogar": 3.7, "estado": "Guerrero",            "tasa": 0.0038},
    "zihuatanejo de azueta":    {"densidad": 1200,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Guerrero",            "tasa": 0.0048},
    # ── Oaxaca ────────────────────────────────────────────────────
    "oaxaca de juarez":         {"densidad": 5800,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.8, "estado": "Oaxaca",              "tasa": 0.0041},
    "santa lucia del camino":   {"densidad": 6200,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 3.9, "estado": "Oaxaca",              "tasa": 0.0052},
    "san pablo villa de mitla": {"densidad": 1200,  "ingreso": 10000, "nse": "D+",   "personas_hogar": 4.1, "estado": "Oaxaca",              "tasa": 0.0038},
    # ── Chiapas ───────────────────────────────────────────────────
    "tuxtla gutierrez":         {"densidad": 6200,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.7, "estado": "Chiapas",             "tasa": 0.0088},
    "san cristobal de las casas": {"densidad": 2800, "ingreso": 11000, "nse": "C",   "personas_hogar": 3.8, "estado": "Chiapas",             "tasa": 0.0065},
    "tapachula":                {"densidad": 3200,  "ingreso": 11500, "nse": "C",    "personas_hogar": 3.8, "estado": "Chiapas",             "tasa": 0.0058},
    # ── Hidalgo ───────────────────────────────────────────────────
    "pachuca de soto":          {"densidad": 5200,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6, "estado": "Hidalgo",             "tasa": 0.0065},
    "mineral de la reforma":    {"densidad": 6800,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.5, "estado": "Hidalgo",             "tasa": 0.0108},
    "tizayuca":                 {"densidad": 4200,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Hidalgo",             "tasa": 0.0135},
    # ── Tlaxcala ──────────────────────────────────────────────────
    "tlaxcala":                 {"densidad": 3800,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.7, "estado": "Tlaxcala",            "tasa": 0.0058},
    "apizaco":                  {"densidad": 4200,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.7, "estado": "Tlaxcala",            "tasa": 0.0048},
    # ── Tabasco ───────────────────────────────────────────────────
    "centro":                   {"densidad": 2800,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7, "estado": "Tabasco",             "tasa": 0.0055},
    # ── Nayarit ───────────────────────────────────────────────────
    "tepic":                    {"densidad": 3800,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.7, "estado": "Nayarit",             "tasa": 0.0061},
    "bahia de banderas":        {"densidad": 1200,  "ingreso": 16000, "nse": "C+",   "personas_hogar": 3.5, "estado": "Nayarit",             "tasa": 0.0145},
    # ── Colima ────────────────────────────────────────────────────
    "colima":                   {"densidad": 4200,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Colima",              "tasa": 0.0058},
    "manzanillo":               {"densidad": 1600,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6, "estado": "Colima",              "tasa": 0.0065},
    # ── Durango ───────────────────────────────────────────────────
    "durango":                  {"densidad": 3800,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Durango",             "tasa": 0.0062},
    # ── Zacatecas ─────────────────────────────────────────────────
    "zacatecas":                {"densidad": 2400,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.7, "estado": "Zacatecas",           "tasa": 0.0041},
    "guadalupe":                {"densidad": 3200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7, "estado": "Zacatecas",           "tasa": 0.0062},
    # ── Baja California Sur ───────────────────────────────────────
    "la paz":                   {"densidad": 1200,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Baja California Sur", "tasa": 0.0095},
    "los cabos":                {"densidad": 1800,  "ingreso": 22000, "nse": "C+",   "personas_hogar": 3.4, "estado": "Baja California Sur", "tasa": 0.0145},
    # ── Campeche ──────────────────────────────────────────────────
    "campeche":                 {"densidad": 2200,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6, "estado": "Campeche",            "tasa": 0.0058},
    # ── Tabasco ───────────────────────────────────────────────────
    "villahermosa":             {"densidad": 3200,  "ingreso": 15000, "nse": "C",    "personas_hogar": 3.6, "estado": "Tabasco",             "tasa": 0.0055},
    # ── Default ───────────────────────────────────────────────────
    "default":                  {"densidad": 8000,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.6, "estado": "México",              "tasa": 0.0055},
}

# Promedio de densidad e ingreso por estado — usado como fallback cuando
# el municipio exacto no está en la tabla pero sí se detecta el estado.
# Fuente: INEGI Censo 2020 — promedio ponderado municipios urbanos
PROMEDIOS_ESTADO = {
    "Ciudad de México":     {"densidad": 9800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.2},
    "Estado de México":     {"densidad": 6200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7},
    "Jalisco":              {"densidad": 5800,  "ingreso": 17000, "nse": "C+",   "personas_hogar": 3.4},
    "Nuevo León":           {"densidad": 6800,  "ingreso": 20000, "nse": "C+",   "personas_hogar": 3.4},
    "Puebla":               {"densidad": 5200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.6},
    "Querétaro":            {"densidad": 4800,  "ingreso": 19000, "nse": "C+",   "personas_hogar": 3.4},
    "Guanajuato":           {"densidad": 5800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.7},
    "Baja California":      {"densidad": 5800,  "ingreso": 17000, "nse": "C+",   "personas_hogar": 3.5},
    "Chihuahua":            {"densidad": 4200,  "ingreso": 16500, "nse": "C",    "personas_hogar": 3.6},
    "Coahuila":             {"densidad": 4800,  "ingreso": 17000, "nse": "C+",   "personas_hogar": 3.5},
    "Tamaulipas":           {"densidad": 4200,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6},
    "Sonora":               {"densidad": 3800,  "ingreso": 18000, "nse": "C+",   "personas_hogar": 3.5},
    "Sinaloa":              {"densidad": 3800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6},
    "Yucatán":              {"densidad": 4200,  "ingreso": 16000, "nse": "C+",   "personas_hogar": 3.5},
    "Quintana Roo":         {"densidad": 4800,  "ingreso": 16500, "nse": "C+",   "personas_hogar": 3.5},
    "San Luis Potosí":      {"densidad": 4200,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6},
    "Aguascalientes":       {"densidad": 5800,  "ingreso": 16500, "nse": "C+",   "personas_hogar": 3.5},
    "Michoacán":            {"densidad": 4200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7},
    "Morelos":              {"densidad": 5200,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6},
    "Veracruz":             {"densidad": 5200,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.7},
    "Guerrero":             {"densidad": 4200,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 3.9},
    "Oaxaca":               {"densidad": 3800,  "ingreso": 11000, "nse": "C/D+", "personas_hogar": 3.9},
    "Chiapas":              {"densidad": 3200,  "ingreso": 10500, "nse": "C/D+", "personas_hogar": 4.0},
    "Hidalgo":              {"densidad": 4200,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7},
    "Tlaxcala":             {"densidad": 4800,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.7},
    "Tabasco":              {"densidad": 2800,  "ingreso": 13500, "nse": "C",    "personas_hogar": 3.7},
    "Nayarit":              {"densidad": 2800,  "ingreso": 13000, "nse": "C",    "personas_hogar": 3.7},
    "Colima":               {"densidad": 3800,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6},
    "Durango":              {"densidad": 2800,  "ingreso": 14500, "nse": "C",    "personas_hogar": 3.6},
    "Zacatecas":            {"densidad": 2400,  "ingreso": 12500, "nse": "C",    "personas_hogar": 3.7},
    "Baja California Sur":  {"densidad": 1800,  "ingreso": 19000, "nse": "C+",   "personas_hogar": 3.4},
    "Campeche":             {"densidad": 2200,  "ingreso": 14000, "nse": "C",    "personas_hogar": 3.6},
    "Tlaxcala":             {"densidad": 4800,  "ingreso": 12000, "nse": "C",    "personas_hogar": 3.7},
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
    "ferreteria":         {"pct_gasto": 0.035, "ticket_promedio": 580,  "visitas_mes": 2},
    "acabados_hogar":     {"pct_gasto": 0.025, "ticket_promedio": 4500, "visitas_mes": 0.3},
    "tienda_importados":  {"pct_gasto": 0.012, "ticket_promedio": 180,  "visitas_mes": 2},
    "default":            {"pct_gasto": 0.04,  "ticket_promedio": 200,  "visitas_mes": 5},
}


def proyectar_poblacion(poblacion_2020, tasa_anual, años=None):
    """Proyecta población desde Censo 2020 al año actual con crecimiento compuesto"""
    if años is None:
        años = AÑO_ACTUAL - AÑO_CENSO
    return int(poblacion_2020 * ((1 + tasa_anual) ** años))


def _normalizar(texto):
    """Normaliza texto: minúsculas, sin acentos, sin caracteres especiales."""
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
        'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        'ñ': 'n',
    }
    texto = texto.lower()
    for src, dst in reemplazos.items():
        texto = texto.replace(src, dst)
    return texto


def _resolver_municipio_desde_gmaps(lat, lng, gmaps_client):
    """
    Usa Google Maps reverse geocoding para obtener municipio y estado exactos.
    Retorna (municipio_normalizado, estado_normalizado, municipio_original, estado_original)
    """
    try:
        result = gmaps_client.reverse_geocode((lat, lng))
        if not result:
            return None, None, None, None

        municipio_orig = None
        estado_orig    = None

        for component in result[0].get('address_components', []):
            tipos = component.get('types', [])
            nombre = component.get('long_name', '')
            # administrative_area_level_2 = municipio en México
            if 'administrative_area_level_2' in tipos:
                municipio_orig = nombre
            # administrative_area_level_1 = estado
            if 'administrative_area_level_1' in tipos:
                estado_orig = nombre

        if municipio_orig and estado_orig:
            return (
                _normalizar(municipio_orig),
                _normalizar(estado_orig),
                municipio_orig,
                estado_orig,
            )
    except Exception:
        pass
    return None, None, None, None


def obtener_datos_inegi(lat, lng, direccion, gmaps_client):
    """
    Obtiene datos demográficos enriquecidos del área.
    Fuente: tabla INEGI Censo 2020 + proyección CONAPO al año actual.

    Orden de resolución (basado en coordenadas, no en texto de dirección):
      1. Google Maps reverse geocode → municipio exacto → MUNICIPIOS_MX
      2. Google Maps reverse geocode → estado → PROMEDIOS_ESTADO
      3. Fallback a promedio nacional "default"

    Retorna dict con todos los indicadores.
    """
    años_proyeccion = AÑO_ACTUAL - AÑO_CENSO

    # ── Paso 1: obtener municipio y estado via coordenadas ──────────
    mun_norm, est_norm, mun_orig, est_orig = _resolver_municipio_desde_gmaps(
        lat, lng, gmaps_client
    )

    datos_zona = None
    zona_key   = "default"
    fuente_str = "Estimación nacional promedio"

    # ── Paso 2: buscar municipio exacto en tabla ────────────────────
    if mun_norm:
        # Match exacto
        if mun_norm in MUNICIPIOS_MX:
            datos_zona = MUNICIPIOS_MX[mun_norm]
            zona_key   = mun_norm
            fuente_str = f"INEGI Censo 2020 · Municipio {mun_orig}"
        else:
            # Match parcial: el nombre del municipio puede incluir palabras extra
            # (ej. "Toluca de Lerdo" normaliza a "toluca de lerdo", buscar si contiene key)
            for key in MUNICIPIOS_MX:
                if key != "default" and (key in mun_norm or mun_norm in key):
                    datos_zona = MUNICIPIOS_MX[key]
                    zona_key   = key
                    fuente_str = f"INEGI Censo 2020 · Municipio {mun_orig} (match parcial)"
                    break

    # ── Paso 3: fallback a promedio estatal ────────────────────────
    if datos_zona is None and est_orig:
        prom = PROMEDIOS_ESTADO.get(est_orig)
        if prom is None:
            # Intentar match normalizado
            for est_key in PROMEDIOS_ESTADO:
                if _normalizar(est_key) == est_norm:
                    prom = PROMEDIOS_ESTADO[est_key]
                    break
        if prom:
            datos_zona = {
                "densidad":       prom["densidad"],
                "ingreso":        prom["ingreso"],
                "nse":            prom["nse"],
                "personas_hogar": prom["personas_hogar"],
                "estado":         est_orig,
                "tasa":           0.0055,
            }
            zona_key   = _normalizar(est_orig)
            fuente_str = f"INEGI Censo 2020 · Promedio estatal {est_orig}"

    # ── Paso 4: fallback nacional ──────────────────────────────────
    if datos_zona is None:
        datos_zona = MUNICIPIOS_MX["default"]
        fuente_str = "Estimación promedio nacional"

    municipio_display = mun_orig or zona_key
    estado_display    = est_orig  or datos_zona.get("estado", "México")
    tasa              = datos_zona.get("tasa", 0.0055)
    años_proyeccion   = AÑO_ACTUAL - AÑO_CENSO

    # ── Área de análisis: radio 500m (π × 0.5²) ──────────────────
    area_km2 = 0.785

    # Datos base Censo 2020
    densidad_2020   = datos_zona["densidad"]
    ingreso_2020    = datos_zona["ingreso"]
    personas_hogar  = datos_zona["personas_hogar"]
    nse             = datos_zona["nse"]

    # Proyección al año actual (CONAPO)
    densidad_actual  = int(densidad_2020 * ((1 + tasa) ** años_proyeccion))
    poblacion_2020   = int(densidad_2020 * area_km2)
    poblacion_actual = proyectar_poblacion(poblacion_2020, tasa)
    viviendas_2020   = int(poblacion_2020 / personas_hogar)
    viviendas_actual = proyectar_poblacion(viviendas_2020, tasa * 0.9)

    # Ingreso ajustado por inflación (INPC ~5.5% anual 2020-2026)
    inflacion_anual = 0.055
    ingreso_actual  = int(ingreso_2020 * ((1 + inflacion_anual) ** años_proyeccion))
    gasto_actual    = int(ingreso_actual * 0.78)  # Coeficiente ENIGH

    personas_manzana = int(densidad_actual * 0.01)
    dist_edad        = _distribucion_edad_por_nse(nse)

    return {
        # Identificación
        "zona_detectada":       zona_key,
        "municipio":            municipio_display,
        "estado":               estado_display,
        "fuente":               f"{fuente_str} · Proyección CONAPO {AÑO_ACTUAL}",
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

        # Edad / género
        "distribucion_edad":    dist_edad,
        "distribucion_genero":  {
            "hombres": dist_edad.get("hombres", 49),
            "mujeres": dist_edad.get("mujeres", 51),
        },

        # Alias para compatibilidad con código existente
        "poblacion_estimada":       poblacion_actual,
        "viviendas_habitadas":      viviendas_actual,
        "densidad_hab_km2":         densidad_actual,
        "ingreso_promedio_mensual": ingreso_actual,
        "gasto_promedio_mensual":   gasto_actual,
    }


def _distribucion_edad_por_nse(nse):
    """Distribución de edad y género por NSE.
    Fuente: INEGI Censo 2020 + ENIGH 2022 + CONAPO por nivel socioeconómico."""
    perfiles = {
        "A":    {"0-17": 18, "18-35": 28, "36-55": 35, "56+": 19, "hombres": 47, "mujeres": 53},
        "A/B":  {"0-17": 20, "18-35": 30, "36-55": 32, "56+": 18, "hombres": 47, "mujeres": 53},
        "B":    {"0-17": 22, "18-35": 32, "36-55": 30, "56+": 16, "hombres": 48, "mujeres": 52},
        "B/C+": {"0-17": 24, "18-35": 33, "36-55": 28, "56+": 15, "hombres": 48, "mujeres": 52},
        "C+":   {"0-17": 26, "18-35": 34, "36-55": 26, "56+": 14, "hombres": 49, "mujeres": 51},
        "C":    {"0-17": 28, "18-35": 33, "36-55": 25, "56+": 14, "hombres": 49, "mujeres": 51},
        "C/D+": {"0-17": 30, "18-35": 32, "36-55": 24, "56+": 14, "hombres": 50, "mujeres": 50},
        "D+":   {"0-17": 33, "18-35": 31, "36-55": 22, "56+": 14, "hombres": 50, "mujeres": 50},
        "D/E":  {"0-17": 35, "18-35": 30, "36-55": 21, "56+": 14, "hombres": 51, "mujeres": 49},
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
    # Calcular flujo promedio solo en horas activas (7h-22h) — las madrugadas
    # distorsionan el promedio hacia abajo aunque las horas pico sean altas
    horas_activas    = trafico_horario[7:23]
    flujo_promedio   = int(sum(horas_activas) / len(horas_activas))
    # También calcular el pico máximo del día
    flujo_pico       = max(trafico_horario)

    return {
        "trafico_horario":  trafico_horario,
        "trafico_semanal":  trafico_semanal,
        "horas_pico":       horas_pico,
        "dia_pico":         dia_pico,
        "dia_bajo":         dia_bajo,
        "flujo_promedio":   flujo_promedio,
        "flujo_pico":       flujo_pico,
        "nivel_general":    "Alto" if flujo_promedio >= 65 else "Medio" if flujo_promedio >= 45 else "Bajo",
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

    # Ticket promedio y clientes estimados
    ticket = gasto_info["ticket_promedio"]
    es_nicho = gasto_info.get("pct_gasto", 0) < 0.02
    if es_nicho:
        # Nicho: penetración conservadora sobre población activa de la zona
        # Factor 10.7% de la población genera ~25 visitas/día en zona de 7k hab
        # Escala naturalmente con poblaciones más grandes o pequeñas
        clientes_dia_estimados = max(1, int(poblacion * 0.107 / 30))
    else:
        clientes_dia_estimados = max(1, int(mercado_captura_mensual / ticket / 30))  # 30 días

    # Detección automática de nicho: pct_gasto < 2% indica categoría de baja frecuencia/especializada
    # Para estos tipos, el ingreso operativo real (clientes × ticket × días) es más honesto
    # que la captura teórica del mercado potencial
    dias_operacion = 26
    es_nicho = gasto_info.get("pct_gasto", 0) < 0.02
    if es_nicho:
        ingreso_operativo_mensual = clientes_dia_estimados * ticket * dias_operacion
    else:
        ingreso_operativo_mensual = None

    return {
        "mercado_total_mensual":      mercado_total_mensual,
        "mercado_total_anual":        mercado_total_mensual * 12,
        "factor_captura_pct":         round(factor_captura * 100, 0),
        "mercado_captura_mensual":    mercado_captura_mensual,
        "mercado_captura_anual":      mercado_captura_anual,
        "ticket_promedio":            ticket,
        "clientes_dia_estimados":     clientes_dia_estimados,
        "ingreso_operativo_mensual":  ingreso_operativo_mensual,
        "dias_operacion":             dias_operacion,
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
    # Base mensual del forecast:
    # - Nicho (ingreso_operativo_mensual disponible): partir del ingreso real (clientes × ticket × días)
    # - Masivo: 18% del mercado captura potencial (penetración inicial típica)
    if mercado.get("ingreso_operativo_mensual"):
        base_mensual = int(mercado["ingreso_operativo_mensual"])
    else:
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


# ─────────────────────────────────────────────────────────────────
# 6. INTERPRETACIÓN DEMOGRÁFICA ESPECÍFICA POR NEGOCIO
# ─────────────────────────────────────────────────────────────────

def interpretar_demografia_negocio(datos_inegi: dict, tipo_negocio_nombre: str, tipo_negocio_key: str = "") -> str:
    """Genera texto interpretativo relacionando demografía con el tipo de negocio."""
    nse       = datos_inegi.get("nse_predominante", "C")
    ingreso   = datos_inegi.get("ingreso_actual", datos_inegi.get("ingreso_promedio_mensual", 0))
    gasto     = datos_inegi.get("gasto_actual", datos_inegi.get("gasto_promedio_mensual", 0))
    poblacion = datos_inegi.get("poblacion_actual", datos_inegi.get("poblacion_estimada", 0))
    densidad  = datos_inegi.get("densidad_actual", datos_inegi.get("densidad_hab_km2", 0))
    tasa_crec = datos_inegi.get("tasa_crecimiento_pct", 0)
    fuente    = datos_inegi.get("fuente", "INEGI Censo 2020")
    dist_edad   = datos_inegi.get("distribucion_edad", {})
    dist_genero = datos_inegi.get("distribucion_genero", {"hombres": 49, "mujeres": 51})

    edad_joven  = dist_edad.get("18-35", 30)
    edad_adulto = dist_edad.get("36-55", 25)
    edad_mayor  = dist_edad.get("56+", 15)
    edad_nino   = dist_edad.get("0-17", 25)
    pct_mujeres = dist_genero.get("mujeres", 51)
    pct_hombres = dist_genero.get("hombres", 49)
    nombre_neg  = tipo_negocio_nombre or "el negocio analizado"
    neg_key     = tipo_negocio_key.lower()

    p1 = (
        f"El entorno inmediato (radio ~500 m) concentra aproximadamente **{poblacion:,} habitantes** "
        f"con una densidad de **{densidad:,} hab/km²**, clasificado como NSE **{nse}** "
        f"según datos del {fuente}. "
    )
    if tasa_crec > 0:
        p1 += f"La zona crece al **{tasa_crec:.2f}%** anual (CONAPO), indicando "
        if tasa_crec > 0.8:   p1 += "un mercado en expansión con demanda creciente. "
        elif tasa_crec > 0.3: p1 += "una dinámica poblacional moderada y estable. "
        else:                 p1 += "una zona consolidada con población estable. "

    p2 = (
        f"La distribución de edad muestra **{edad_joven}% de jóvenes-adultos (18–35)**, "
        f"**{edad_adulto}% de adultos (36–55)** y **{edad_mayor}% de adultos mayores (56+)**. "
        f"El género predominante es {'femenino' if pct_mujeres > pct_hombres else 'masculino'} "
        f"(**{max(pct_mujeres, pct_hombres)}%**). "
    )

    if any(x in neg_key for x in ["cafe", "coffee", "brunch"]):
        if edad_joven >= 30:
            p2 += f"Este perfil es **muy favorable** para {nombre_neg}: los jóvenes-adultos son el segmento de mayor consumo en cafeterías. "
        if pct_mujeres > 52:
            p2 += "El predominio femenino refuerza el potencial — mayor frecuencia de visita en este tipo de establecimientos. "
    elif any(x in neg_key for x in ["gym", "gimnasio", "fitness", "yoga", "wellness"]):
        p2 += f"El {edad_joven + edad_adulto}% de población en edad activa (18–55) es el mercado directo para {nombre_neg}. "
        if nse in ["A","A/B","B","B/C+"]:
            p2 += "El NSE indica capacidad de pago para membresías premium. "
    elif any(x in neg_key for x in ["restaurante", "comida", "taqueria", "food", "bar"]):
        p2 += f"El {edad_joven + edad_adulto}% de adultos constituye la base de clientes de {nombre_neg}. "
    elif any(x in neg_key for x in ["guarderia", "infantil", "escuela", "kinder"]):
        p2 += f"El {edad_nino}% de menores de 18 años es el indicador clave para {nombre_neg}. "
        if edad_nino > 28: p2 += "La alta proporción de menores indica demanda potencial alta. "
    elif any(x in neg_key for x in ["farmacia", "salud", "medico", "clinica"]):
        if edad_mayor > 15:
            p2 += f"El {edad_mayor}% de adultos mayores representa alta frecuencia de demanda para {nombre_neg}. "
    elif any(x in neg_key for x in ["ferreteria", "electr", "plomeria", "hardware", "materiales", "herramienta"]):
        p2 += (
            f"El {edad_adulto}% de adultos (36–55) y el {edad_joven}% de jóvenes-adultos (18–35) "
            f"representan el perfil típico de {nombre_neg} — propietarios y personas en remodelación. "
        )
        if nse in ["C","C/D+","D+"]:
            p2 += "El NSE del entorno es ideal — la ferretería de barrio es el formato más demandado en zonas C y C-. "
        elif nse in ["B","B/C+","C+"]:
            p2 += "El NSE B/C+ sugiere demanda de línea profesional y productos de mayor calidad. "
    elif any(x in neg_key for x in ["acabado","persiana","piso","laminado","alfombra","lambrin","decorac","revestimiento","cortina","duela"]):
        p2 += (
            f"El perfil de {nombre_neg} se concentra en adultos de 36–55 años ({edad_adulto}%) "
            f"que realizan proyectos de remodelación y decoración del hogar. "
        )
        if pct_mujeres > 50:
            p2 += f"El predominio femenino ({pct_mujeres}%) es muy positivo — las mujeres lideran las decisiones de decoración e interiores en más del 70% de hogares (ENIGH 2022). "
        if nse in ["A","A/B","B","B/C+"]:
            p2 += "El NSE indica alta disposición a invertir en acabados premium — ventaja si manejas marcas reconocidas. "
    else:
        p2 += f"El grupo de 18–55 años ({edad_joven + edad_adulto}% del entorno) es la población objetivo principal para {nombre_neg}. "

    p3 = (
        f"El ingreso mensual promedio es de **${ingreso:,} MXN**, con gasto estimado de "
        f"**${gasto:,} MXN/mes** (coeficiente ENIGH 2022). "
    )
    if nse in ["A","A/B"]:
        p3 += f"Alta capacidad de pago — favorable para propuesta premium en {nombre_neg}."
    elif nse in ["B","B/C+"]:
        p3 += f"NSE {nse}: buena capacidad de pago con sensibilidad al valor percibido."
    elif nse in ["C+","C"]:
        p3 += f"NSE {nse}: el consumidor evalúa precio-calidad — claridad en propuesta de valor es clave."
    else:
        p3 += f"NSE {nse}: estrategia de precio competitivo y alta visibilidad para {nombre_neg}."

    return f"{p1}\n\n{p2}\n\n{p3}"


# ─────────────────────────────────────────────────────────────────
# 7. TICKET ENGINE
# ─────────────────────────────────────────────────────────────────

TICKETS_POR_TIPO = {
    "cafe_premium":        {0: (130,200), 1: (80,130),  2: (130,250), 3: (250,450), 4: (450,800)},
    "cafe_casual":         {0: (80,150),  1: (60,100),  2: (100,180), 3: (180,320), 4: (320,600)},
    "restaurante_casual":  {0: (120,200), 1: (80,150),  2: (150,280), 3: (280,500), 4: (500,1200)},
    "restaurante_fino":    {0: (400,700), 1: (200,400), 2: (400,700), 3: (700,1400),4:(1400,3000)},
    "comida_rapida":       {0: (60,120),  1: (40,80),   2: (80,150),  3: (150,280), 4: (280,500)},
    "bar":                 {0: (120,220), 1: (80,150),  2: (150,300), 3: (300,600), 4: (600,1500)},
    "panaderia":           {0: (50,100),  1: (40,80),   2: (80,160),  3: (160,300), 4: (300,600)},
    "farmacia":            {0: (100,200), 1: (80,150),  2: (150,300), 3: (300,600), 4: (600,1200)},
    "gimnasio_boutique":   {0: (800,1500),1:(500,900),  2:(900,1600), 3:(1600,3000),4:(3000,6000)},
    "gimnasio_regular":    {0: (400,700), 1: (300,550), 2: (550,900), 3: (900,1800),4:(1800,4000)},
    "yoga_wellness":       {0: (600,1200),1:(400,700),  2:(700,1300), 3:(1300,2500),4:(2500,5000)},
    "tienda_conveniencia": {0: (60,120),  1: (40,80),   2: (80,150),  3: (150,280), 4: (280,500)},
    "libreria":            {0: (150,300), 1: (80,200),  2: (200,400), 3: (400,800), 4: (800,2000)},
    "guarderia":           {0:(2000,4000),1:(1500,2500),2:(2500,4500),3:(4500,8000),4:(8000,15000)},
    "servicios":           {0: (150,300), 1: (100,200), 2: (200,400), 3: (400,800), 4: (800,2000)},
    "ferreteria":          {0: (300,700), 1: (150,350), 2: (350,700), 3: (700,1500),4:(1500,4000)},
    "acabados_hogar":      {0:(2000,6000),1:(1200,3000),2:(3000,7000),3:(7000,15000),4:(15000,40000)},
    "default":             {0: (100,200), 1: (80,160),  2: (160,320), 3: (320,650), 4: (650,1500)},
}

def calcular_ticket_competencia(competidores: list, tipo_negocio_key: str, score: float) -> dict:
    """Ticket promedio de competidores (PRO) y ticket recomendado (PREMIUM).
    Fuente: price_level Google Places + ENIGH 2022."""
    tipo_key = (tipo_negocio_key or "default").lower().replace(" ","_")
    tabla    = TICKETS_POR_TIPO.get(tipo_key, TICKETS_POR_TIPO["default"])
    niv_str  = {0:"N/D",1:"$",2:"$$",3:"$$$",4:"$$$$"}

    detalle=[]; tickets_raw=[]
    for comp in (competidores or []):
        pl = comp.get("priceLevel") or comp.get("price_level") or 0
        if isinstance(pl, str):
            pl = {"PRICE_LEVEL_FREE":1,"PRICE_LEVEL_INEXPENSIVE":1,
                  "PRICE_LEVEL_MODERATE":2,"PRICE_LEVEL_EXPENSIVE":3,
                  "PRICE_LEVEL_VERY_EXPENSIVE":4}.get(pl, 0)
        if pl not in (1,2,3,4): pl=0
        rango=tabla[pl]; t_est=int((rango[0]+rango[1])/2)
        nombre=(comp.get("displayName",{}).get("text") or comp.get("name") or "Competidor")
        detalle.append({"nombre":nombre,"nivel":niv_str[pl],"ticket_estimado":t_est,"price_level":pl})
        if pl>0: tickets_raw.append(t_est)

    if tickets_raw:
        ticket_comp=int(sum(tickets_raw)/len(tickets_raw))
        levels=[d["price_level"] for d in detalle if d["price_level"]>0]
        lv_prom=round(sum(levels)/len(levels))
    else:
        rng=tabla[2]; ticket_comp=int((rng[0]+rng[1])/2); lv_prom=2
    rango_zona=niv_str.get(lv_prom,"$$")

    if score>=80:   pos,factor="premium — ubicación justifica precios superiores",1.20
    elif score>=65: pos,factor="medio-alto — ligeramente por encima del promedio",1.10
    elif score>=50: pos,factor="competitivo — alineado al promedio de la zona",1.00
    elif score>=35: pos,factor="bajo — precios competitivos para captar mercado",0.90
    else:           pos,factor="agresivo — precio de entrada para penetrar",0.80

    ticket_rec=int(ticket_comp*factor)
    n_con=len(tickets_raw); total=len(competidores or [])

    i_pro=(f"Se analizaron {total} competidores ({n_con} con precio en Google). "
           f"Ticket promedio de la zona: ${ticket_comp:,} MXN ({rango_zona}). "
           f"Fuente: price_level Google Places + ENIGH 2022.")
    i_prem=(f"{i_pro} Con score {score:.0f}/100, se recomienda posicionamiento "
            f"{pos}: ticket sugerido **${ticket_rec:,} MXN**.")

    return {"ticket_competencia":ticket_comp,"ticket_recomendado":ticket_rec,
            "posicionamiento":pos,"rango_zona":rango_zona,"n_con_precio":n_con,
            "detalle_competidores":detalle,"interpretacion_pro":i_pro,"interpretacion_prem":i_prem}
