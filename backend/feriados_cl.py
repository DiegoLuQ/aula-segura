"""Feriados legales de Chile.

Se usan para el cálculo de DÍAS HÁBILES de los recordatorios: un día hábil es
lunes a viernes que además no sea feriado.

Fuentes de datos (en orden de confianza):
1. Importación desde la API oficial `https://apis.digital.gob.cl/fl/feriados/{año}`
   (requiere salida a internet desde el servidor).
2. Cálculo local con las reglas de este módulo (`generar_feriados_anio`).
3. Carga manual desde la pantalla "Feriados".

El cálculo local cubre los feriados legales permanentes. NO incluye feriados
excepcionales que se fijan por ley cada año (elecciones, censos, días adicionales
de Fiestas Patrias, etc.): esos se agregan a mano en la pantalla de Feriados.
"""
from datetime import date, timedelta

# (mes, día, nombre, irrenunciable)
FERIADOS_FIJOS = [
    (1, 1, "Año Nuevo", True),
    (5, 1, "Día Nacional del Trabajo", True),
    (5, 21, "Día de las Glorias Navales", False),
    (6, 21, "Día Nacional de los Pueblos Indígenas", False),
    (7, 16, "Virgen del Carmen", False),
    (8, 15, "Asunción de la Virgen", False),
    (9, 18, "Independencia Nacional", True),
    (9, 19, "Día de las Glorias del Ejército", True),
    (11, 1, "Día de Todos los Santos", False),
    (12, 8, "Inmaculada Concepción", False),
    (12, 25, "Navidad", True),
]

# Feriados que se trasladan según la Ley 19.973
FERIADOS_TRASLADABLES = [
    (6, 29, "San Pedro y San Pablo"),
    (10, 12, "Encuentro de Dos Mundos"),
]


def domingo_de_pascua(anio: int) -> date:
    """Domingo de Resurrección (algoritmo de Gauss/Meeus para el calendario gregoriano)."""
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _trasladar_ley_19973(fecha: date) -> date:
    """Ley 19.973: si el feriado cae martes, miércoles o jueves se traslada al lunes
    de esa misma semana; si cae viernes, al lunes de la semana siguiente.
    Sábado, domingo y lunes se mantienen en su fecha."""
    dow = fecha.weekday()  # 0 = lunes ... 6 = domingo
    if dow in (1, 2, 3):          # martes, miércoles, jueves
        return fecha - timedelta(days=dow)
    if dow == 4:                  # viernes
        return fecha + timedelta(days=3)
    return fecha


def _dia_iglesias_evangelicas(anio: int) -> date:
    """Ley 20.299: el 31 de octubre se traslada al viernes anterior si cae martes,
    y al viernes siguiente si cae miércoles."""
    base = date(anio, 10, 31)
    dow = base.weekday()
    if dow == 1:      # martes -> viernes anterior (27 de octubre)
        return base - timedelta(days=4)
    if dow == 2:      # miércoles -> viernes siguiente (2 de noviembre)
        return base + timedelta(days=2)
    return base


def generar_feriados_anio(anio: int):
    """Devuelve [{fecha, nombre, irrenunciable}] con los feriados legales del año."""
    items = []

    for mes, dia, nombre, irren in FERIADOS_FIJOS:
        items.append({"fecha": date(anio, mes, dia), "nombre": nombre, "irrenunciable": irren})

    pascua = domingo_de_pascua(anio)
    items.append({"fecha": pascua - timedelta(days=2), "nombre": "Viernes Santo", "irrenunciable": False})
    items.append({"fecha": pascua - timedelta(days=1), "nombre": "Sábado Santo", "irrenunciable": False})

    for mes, dia, nombre in FERIADOS_TRASLADABLES:
        original = date(anio, mes, dia)
        movida = _trasladar_ley_19973(original)
        sufijo = "" if movida == original else f" (trasladado del {original.strftime('%d-%m')})"
        items.append({"fecha": movida, "nombre": nombre + sufijo, "irrenunciable": False})

    evangelicas = _dia_iglesias_evangelicas(anio)
    sufijo = "" if evangelicas.day == 31 and evangelicas.month == 10 else " (trasladado del 31-10)"
    items.append({
        "fecha": evangelicas,
        "nombre": "Día de las Iglesias Evangélicas y Protestantes" + sufijo,
        "irrenunciable": False,
    })

    # Un solo feriado por fecha, ordenados
    unicos = {}
    for it in items:
        unicos.setdefault(it["fecha"], it)
    return [unicos[f] for f in sorted(unicos)]
