"""
Lógica de envío de correos de notificación (recordatorios) para los procesos
de Aula Segura.

- El remitente se elige según el COLEGIO del estudiante (credenciales del .env).
- Los destinatarios son los que pertenecen al colegio del estudiante MÁS los que
  tienen el privilegio `todos_colegios`, siempre que estén activos (estado=True).
  Van siempre en COPIA OCULTA (no se ven entre sí).
- Un hilo en segundo plano (scheduler) revisa periódicamente las notificaciones
  programadas y envía los correos que estén vencidos.
- El switch global `ConfigEmail.envio_activo` detiene todos los envíos.

Modos:
- 'una_vez'       -> 1 envío inmediato.
- 'paulatino'     -> recordatorio diario hasta que se cancele.
- 'cada_3_dias'   -> envío cada 3 días, máximo 3 veces.
- 'fecha_indicada'-> 1 envío en la fecha indicada.
- 'dias_habiles'  -> plan de recordatorios contados en DÍAS HÁBILES desde la fecha de
                     la etapa (`Notificacion.fecha_base`), materializado en
                     `EnvioProgramado`. Es el modo que usa el sistema desde la ficha.
"""
import os
import ssl
import json
import smtplib
import threading
import time
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, date, time as dtime

from dotenv import load_dotenv

import models
import database
import feriados_cl

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))


def get_config_email(db):
    """Obtiene o inicializa la configuración global de correo en BD."""
    conf = db.query(models.ConfigEmail).first()
    if not conf:
        conf = models.ConfigEmail(
            envio_activo=True,
            smtp_host=SMTP_SERVER,
            smtp_port=SMTP_PORT,
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=True,
            remitente_nombre="Aula Segura",
            remitente_email=os.getenv("SMTP_USER", ""),
        )
        db.add(conf)
        db.commit()
        db.refresh(conf)
    return conf



from zoneinfo import ZoneInfo

SANTIAGO_TZ = ZoneInfo("America/Santiago")


def obtener_ahora_santiago():
    """Devuelve datetime.now() en zona horaria Santiago de Chile (naive para DB)."""
    return datetime.now(SANTIAGO_TZ).replace(tzinfo=None)


def _parse_hora(valor, default=(9, 0)):
    """Convierte 'HH:MM' en (hora, minuto). Si es inválido, retorna default (09:00)."""
    if not valor:
        return default
    try:
        partes = str(valor).split(":")
        hh = int(partes[0])
        mm = int(partes[1]) if len(partes) > 1 else 0
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return (hh, mm)
    except Exception:
        pass
    return default


def _objetivos_dias_habiles(notificacion, estudiante):
    """Lista ordenada de datetimes en que esta notificación 'días hábiles' debe enviarse.

    La base es la fecha de la etapa (`notificacion.fecha_base`); el día 0 es esa misma
    fecha y el día N son N días hábiles después. Se combina con la hora de envío.
    """
    base = getattr(notificacion, "fecha_base", None)
    if not base and estudiante:
        base = estudiante.fecha_inicio_proceso
    if not base:
        return []
    if not notificacion.dias_habiles_envio:
        return []

    hh, mm = _parse_hora(getattr(notificacion, "hora_envio", None))
    objetivos = [
        datetime.combine(fecha, dtime(hh, mm))
        for _n, fecha in calcular_fechas_dias_habiles(base, notificacion.dias_habiles_envio)
        if fecha
    ]
    objetivos.sort()
    return objetivos


# ---------- FERIADOS ----------
# Caché en memoria de los feriados registrados (tabla pro_aula_segura_feriados).
# Un día hábil es lunes a viernes que además no sea feriado.
_FERIADOS = set()
_FERIADOS_TS = 0.0
_FERIADOS_TTL = 300  # segundos


def invalidar_feriados():
    """Fuerza la recarga del caché de feriados (se llama al crear/editar/borrar uno)."""
    global _FERIADOS_TS
    _FERIADOS_TS = 0.0


def cargar_feriados(db, forzar=False):
    """Refresca el caché de feriados desde la base de datos."""
    global _FERIADOS, _FERIADOS_TS
    if not forzar and _FERIADOS_TS and (time.time() - _FERIADOS_TS) < _FERIADOS_TTL:
        return _FERIADOS
    try:
        _FERIADOS = {f.fecha for f in db.query(models.Feriado).all() if f.fecha}
        _FERIADOS_TS = time.time()
    except Exception:
        traceback.print_exc()
    return _FERIADOS


def asegurar_feriados_anio(db, anio):
    """Genera los feriados legales de un año si todavía no hay ninguno registrado.

    Evita que un plan de recordatorios cruce a un año sin feriados cargados y trate
    esos días como hábiles.
    """
    try:
        hay = (
            db.query(models.Feriado)
            .filter(models.Feriado.fecha >= date(anio, 1, 1), models.Feriado.fecha <= date(anio, 12, 31))
            .count()
        )
        if hay:
            return 0
        creados = 0
        for it in feriados_cl.generar_feriados_anio(anio):
            db.add(models.Feriado(
                fecha=it["fecha"],
                nombre=it["nombre"],
                tipo="nacional",
                irrenunciable=bool(it["irrenunciable"]),
                origen="sistema",
            ))
            creados += 1
        db.commit()
        invalidar_feriados()
        return creados
    except Exception:
        traceback.print_exc()
        return 0


_FERIADOS_CHECK_DIA = None


def asegurar_feriados_vigentes(db):
    """Chequeo diario: que existan los feriados del año en curso y del siguiente."""
    global _FERIADOS_CHECK_DIA
    hoy = obtener_ahora_santiago().date()
    if _FERIADOS_CHECK_DIA == hoy:
        return
    _FERIADOS_CHECK_DIA = hoy
    asegurar_feriados_anio(db, hoy.year)
    asegurar_feriados_anio(db, hoy.year + 1)


def es_dia_habil(fecha) -> bool:
    """Lunes a viernes y que no sea feriado registrado."""
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    return fecha.weekday() < 5 and fecha not in _FERIADOS


def obtener_fecha_dia_habil(fecha_inicio: date, n_dias_habiles: int) -> date:
    """Suma n_dias_habiles (lunes a viernes, saltando feriados) a la fecha_inicio."""
    if not fecha_inicio:
        return None
    if isinstance(fecha_inicio, datetime):
        curr = fecha_inicio.date()
    else:
        curr = fecha_inicio

    if n_dias_habiles <= 0:
        return curr

    dias_contados = 0
    while dias_contados < n_dias_habiles:
        curr += timedelta(days=1)
        if es_dia_habil(curr):
            dias_contados += 1
    return curr


def get_sender_for_colegio(nombre_colegio: str):
    """Devuelve (email, password, nombre_visible) del remitente según el colegio."""
    n = (nombre_colegio or "").lower()
    if "macaya" in n:
        return (
            os.getenv("MC_SENDER_EMAIL"),
            os.getenv("MC_SENDER_PASSWORD"),
            "Colegio Macaya",
        )
    if "portales" in n or "diego" in n:
        return (
            os.getenv("DP_SENDER_EMAIL"),
            os.getenv("DP_SENDER_PASSWORD"),
            "Colegio Diego Portales",
        )
    return (None, None, nombre_colegio or "")


def _parse_grupo_ids(valor):
    """Convierte '1,3,5' (o lista) en una lista de enteros."""
    if not valor:
        return []
    if isinstance(valor, (list, tuple)):
        return [int(x) for x in valor]
    return [int(x) for x in str(valor).split(",") if str(x).strip().isdigit()]


def get_destinatarios_para_estudiante(db, estudiante, grupo_ids=None):
    """Destinatarios activos a notificar.

    - Si se indican grupo_ids: los miembros activos de esos grupos.
    - Si no: los del colegio del estudiante + los de todos_colegios.
    """
    grupos = _parse_grupo_ids(grupo_ids)
    if grupos:
        return (
            db.query(models.Destinatario)
            .join(
                models.DestinatarioGrupo,
                models.DestinatarioGrupo.destinatario_id == models.Destinatario.id,
            )
            .filter(
                models.Destinatario.estado == True,
                models.DestinatarioGrupo.grupo_id.in_(grupos),
            )
            .distinct()
            .all()
        )
    return (
        db.query(models.Destinatario)
        .filter(
            models.Destinatario.estado == True,
            (
                (models.Destinatario.id_colegio == estudiante.id_colegio)
                | (models.Destinatario.todos_colegios == True)
            ),
        )
        .all()
    )


def _fmt_fecha(value):
    if not value:
        return "Sin registrar"
    try:
        return value.strftime("%d-%m-%Y")
    except Exception:
        return str(value)


def _aplicar_placeholders(texto, estudiante, nombre_colegio, dia_numero=0, plazo_total=10):
    """Reemplaza las etiquetas {..} por los datos del estudiante y el progreso del plazo."""
    if not texto:
        return texto
    
    dia_actual = int(dia_numero) if dia_numero is not None else 0
    plazo_max = int(plazo_total) if plazo_total is not None else 10
    dias_restantes = max(0, plazo_max - dia_actual)

    replacements = {
        "{rut}": estudiante.rut or "-",
        "{nombre}": estudiante.nombre_estudiante or "-",
        "{curso}": estudiante.curso or "-",
        "{causa}": estudiante.causa or "-",
        "{fecha_inicio}": _fmt_fecha(estudiante.fecha_inicio_proceso),
        "{medida}": estudiante.medida or "-",
        "{estado}": estudiante.medida or "-",
        "{fecha_medida}": _fmt_fecha(estudiante.fecha_notificacion_medida),
        "{colegio}": nombre_colegio or "-",
        "{dia_numero}": str(dia_actual),
        "{dias_transcurridos}": str(dia_actual),
        "{plazo_total}": str(plazo_max),
        "{dias_restantes}": str(dias_restantes),
    }
    for placeholder, val in replacements.items():
        texto = texto.replace(placeholder, str(val))
    return texto


def construir_mensaje(
    estudiante,
    nombre_colegio,
    etapa="inicio_proceso",
    cuerpo_personalizado=None,
    asunto_personalizado=None,
    dia_numero=0,
    plazo_total=10,
):
    """Resumen del proceso (asunto + cuerpo HTML), según la etapa e incluyendo el avance del plazo."""
    banner_plazo = f"""
    <div style="background:#eef2ff; border:1px solid #c7d2fe; border-left:4px solid #4f46e5; border-radius:8px; padding:12px 16px; margin:16px 0; color:#1e1b4b;">
        <p style="margin:0; font-size:13px; font-weight:bold;">
            ⏱️ Progreso del Plazo: Acaban de pasar {dia_numero} de {plazo_total} días
        </p>
        <p style="margin:4px 0 0 0; font-size:12px; color:#4338ca;">
            Te recordamos que esta fase es importante dentro del proceso de Aula Segura.
        </p>
    </div>
    """

    if cuerpo_personalizado:
        texto = _aplicar_placeholders(
            cuerpo_personalizado, estudiante, nombre_colegio, dia_numero, plazo_total
        )

        asunto = f"Notificación del Proceso - {estudiante.nombre_estudiante or 'Estudiante'}"
        if etapa == "medida":
            asunto = f"Notificación de Medida y Apelación - {estudiante.nombre_estudiante or 'Estudiante'}"
        elif etapa == "apelacion":
            asunto = f"Recepción de Carta de Apelación - {estudiante.nombre_estudiante or 'Estudiante'}"
        elif etapa == "consejo":
            asunto = f"Consejo de Profesores - {estudiante.nombre_estudiante or 'Estudiante'}"
        elif etapa == "final_medida":
            asunto = f"Notificación Final de la Medida - {estudiante.nombre_estudiante or 'Estudiante'}"
        if asunto_personalizado:
            asunto = _aplicar_placeholders(
                asunto_personalizado, estudiante, nombre_colegio, dia_numero, plazo_total
            )

        cuerpo = f"""
        <div style="font-family: Arial, sans-serif; color:#1e293b; max-width:600px;">
          <h2 style="color:#312e81;">Notificación de Proceso Aula Segura</h2>
          <p>Estimado/a,</p>
          {banner_plazo}
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; margin:16px 0; line-height:1.6; white-space: pre-line;">
            {texto}
          </div>
          <p style="color:#64748b; font-size:12px;">Mensaje automático del Sistema Aula Segura. No responder a este correo.</p>
        </div>
        """
        return asunto, cuerpo


    fila = (
        '<tr><td style="padding:6px 10px; font-weight:bold; background:#eef2ff;">{k}</td>'
        '<td style="padding:6px 10px;">{v}</td></tr>'
    )
    filas = [
        fila.format(k="Estudiante", v=estudiante.nombre_estudiante or "-"),
        fila.format(k="Curso", v=estudiante.curso or "-"),
        fila.format(k="Colegio", v=nombre_colegio or "-"),
        fila.format(k="Causa", v=estudiante.causa or "-"),
    ]

    if etapa == "medida":
        titulo = "Notificación de Medida y Apelación"
        asunto = f"Notificación de Medida y Apelación - {estudiante.nombre_estudiante or 'Estudiante'}"
        intro = ("Le informamos sobre la <strong>medida y apelación</strong> del proceso "
                 "de Aula Segura que se detalla a continuación:")
        filas.append(fila.format(k="Medida Aplicada", v=estudiante.medida or "-"))
        filas.append(fila.format(
            k="Fecha Notificación Medida y Apelación",
            v=_fmt_fecha(estudiante.fecha_notificacion_medida),
        ))
    elif etapa == "apelacion":
        titulo = "Recepción de Carta de Apelación"
        asunto = f"Recepción de Carta de Apelación - {estudiante.nombre_estudiante or 'Estudiante'}"
        intro = ("Le informamos respecto de la <strong>recepción de la carta de apelación</strong> "
                 "del proceso de Aula Segura que se detalla a continuación:")
        filas.append(fila.format(
            k="Fecha Recepción CARTA Apelación",
            v=_fmt_fecha(estudiante.fecha_recepcion_apelacion),
        ))
    elif etapa == "consejo":
        titulo = "Confirmación Consejo de Profesores"
        asunto = f"Consejo de Profesores - {estudiante.nombre_estudiante or 'Estudiante'}"
        intro = ("Le informamos que se ha <strong>confirmado el Consejo de Profesores</strong> "
                 "del proceso de Aula Segura que se detalla a continuación:")
        filas.append(fila.format(
            k="Fecha Consejo Profesores",
            v=_fmt_fecha(estudiante.fecha_consejo_profesores),
        ))
    elif etapa == "final_medida":
        titulo = 'Notificación Final de la Medida'
        asunto = f"Notificación Final de la Medida - {estudiante.nombre_estudiante or 'Estudiante'}"
        intro = ('Le informamos la <strong>notificación final de la medida</strong> '
                 'del proceso de Aula Segura que se detalla a continuación:')
        filas.append(fila.format(k="Medida Aplicada", v=estudiante.medida or "-"))
        filas.append(fila.format(
            k='Fecha Notificación Final "MEDIDA"',
            v=_fmt_fecha(estudiante.fecha_notificacion_final),
        ))
    else:
        titulo = "Recordatorio de Proceso Aula Segura"
        asunto = f"Recordatorio Proceso Aula Segura - {estudiante.nombre_estudiante or 'Estudiante'}"
        intro = ("Le recordamos que existe un proceso de <strong>Aula Segura</strong> en curso "
                 "que requiere su atención. A continuación el resumen:")
        filas.append(fila.format(
            k="Fecha Notificación Inicio Proceso",
            v=_fmt_fecha(estudiante.fecha_inicio_proceso),
        ))

    cuerpo = f"""
    <div style="font-family: Arial, sans-serif; color:#1e293b; max-width:600px;">
      <h2 style="color:#312e81;">{titulo}</h2>
      <p>Estimado/a,</p>
      <p>{intro}</p>
      {banner_plazo}
      <table style="border-collapse:collapse; width:100%; margin:16px 0;">
        {''.join(filas)}
      </table>
      <p>Por favor revise el expediente y realice las gestiones que correspondan.</p>
      <p style="color:#64748b; font-size:12px;">Mensaje automático del Sistema Aula Segura. No responder a este correo.</p>
    </div>
    """
    if asunto_personalizado:
        asunto = _aplicar_placeholders(
            asunto_personalizado, estudiante, nombre_colegio, dia_numero, plazo_total
        )

    return asunto, cuerpo


def enviar_correos(db, estudiante, notificacion):
    """Envía el correo a todos los destinatarios del estudiante y registra el log.
    Devuelve (enviados, fallidos)."""
    conf = get_config_email(db)
    if not conf.envio_activo:
        print("[correos] Envío pausado por el switch global (ConfigEmail.envio_activo).")
        return (0, 0)

    colegio = (
        db.query(models.Colegio)
        .filter(models.Colegio.id == estudiante.id_colegio)
        .first()
    )
    nombre_colegio = colegio.nombre if colegio else ""
    sender_email, sender_pass, _remitente = get_sender_for_colegio(nombre_colegio)

    destinatarios = get_destinatarios_para_estudiante(db, estudiante, notificacion.grupo_ids)
    asunto, cuerpo = construir_mensaje(
        estudiante,
        nombre_colegio,
        getattr(notificacion, "etapa", "inicio_proceso"),
        getattr(notificacion, "cuerpo_personalizado", None),
        getattr(notificacion, "asunto_personalizado", None),
    )

    enviados, fallidos = 0, 0

    if not destinatarios:
        return enviados, fallidos

    if not sender_email or not sender_pass:
        # No hay credenciales para el colegio: registrar el fallo
        for d in destinatarios:
            db.add(models.NotificacionLog(
                notificacion_id=notificacion.id,
                estudiante_id=estudiante.id,
                destinatario_email=d.email,
                destinatario_nombre=d.nombre,
                exito=False,
                detalle="Sin credenciales de remitente para el colegio",
            ))
            fallidos += 1
        db.commit()
        return enviados, fallidos

    context = ssl.create_default_context()
    server = None
    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
        server.login(sender_email, sender_pass)
    except Exception as e:
        for d in destinatarios:
            db.add(models.NotificacionLog(
                notificacion_id=notificacion.id,
                estudiante_id=estudiante.id,
                destinatario_email=d.email,
                destinatario_nombre=d.nombre,
                exito=False,
                detalle=f"Error de conexión SMTP: {e}"[:255],
            ))
            fallidos += 1
        db.commit()
        if server:
            try:
                server.quit()
            except Exception:
                pass
        return enviados, fallidos

    emails_list = [d.email for d in destinatarios if d.email]

    if emails_list:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = f"{_remitente} <{sender_email}>"
            # Los destinatarios van en copia oculta: el header 'To' apunta al remitente y
            # la entrega real se hace por el sobre SMTP (sendmail), así no se ven entre sí.
            msg["To"] = f"{_remitente} <{sender_email}>"
            msg.attach(MIMEText(cuerpo, "html"))
            server.sendmail(sender_email, emails_list, msg.as_string())
            for d in destinatarios:
                db.add(models.NotificacionLog(
                    notificacion_id=notificacion.id,
                    estudiante_id=estudiante.id,
                    destinatario_email=d.email,
                    destinatario_nombre=d.nombre,
                    exito=True,
                    detalle="Enviado",
                ))
                enviados += 1
        except Exception as e:
            for d in destinatarios:
                db.add(models.NotificacionLog(
                    notificacion_id=notificacion.id,
                    estudiante_id=estudiante.id,
                    destinatario_email=d.email,
                    destinatario_nombre=d.nombre,
                    exito=False,
                    detalle=str(e)[:255],
                ))
                fallidos += 1

    try:
        server.quit()
    except Exception:
        pass

    db.commit()
    return enviados, fallidos


def procesar_notificacion(db, notificacion):
    """Ejecuta un envío de la notificación y actualiza su programación."""
    estudiante = (
        db.query(models.Estudiante)
        .filter(models.Estudiante.id == notificacion.estudiante_id)
        .first()
    )
    if not estudiante:
        notificacion.estado = "cancelado"
        db.commit()
        return (0, 0)

    enviados, fallidos = enviar_correos(db, estudiante, notificacion)

    notificacion.veces_enviado = (notificacion.veces_enviado or 0) + 1
    notificacion.ultimo_envio = datetime.now()

    # ¿Terminó?
    if notificacion.modo == "dias_habiles":
        objetivos = _objetivos_dias_habiles(notificacion, estudiante)
        max_envios = len(objetivos) or 1

        if notificacion.veces_enviado >= max_envios:
            notificacion.estado = "completado"
            notificacion.proximo_envio = None
        else:
            # El próximo objetivo aún no enviado (veces_enviado ya viene incrementado).
            idx = notificacion.veces_enviado
            notificacion.proximo_envio = objetivos[idx] if idx < len(objetivos) else (datetime.now() + timedelta(days=1))
    else:
        if notificacion.max_envios and notificacion.veces_enviado >= notificacion.max_envios:
            notificacion.estado = "completado"
            notificacion.proximo_envio = None
        else:
            notificacion.proximo_envio = datetime.now() + timedelta(
                days=notificacion.intervalo_dias or 1
            )
    db.commit()
    return (enviados, fallidos)


def _due(notificacion, ahora, estudiante):
    """¿Le toca enviarse a esta notificación activa?"""
    if notificacion.estado != "activo":
        return False
    if notificacion.modo == "fecha_indicada":
        if notificacion.veces_enviado and notificacion.veces_enviado > 0:
            return False
        if not notificacion.fecha_programada:
            return False
        return ahora.date() >= notificacion.fecha_programada

    if notificacion.modo == "dias_habiles":
        # Los envíos de días hábiles están materializados en envios_programados
        # y los procesa revisar_envios_programados(), no esta vía.
        return False

    # Resto de modos usan proximo_envio
    if not notificacion.proximo_envio:
        return False
    return ahora >= notificacion.proximo_envio


def _proxima_fecha_habil(fecha):
    """Si la fecha cae sábado, domingo o feriado, la mueve al siguiente día hábil."""
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    while not es_dia_habil(fecha):
        fecha += timedelta(days=1)
    return fecha


def calcular_fechas_dias_habiles(base_date, dias_envio_str, incluir_dia1=False):
    """Devuelve [(dia_numero, fecha), ...] para el modo días hábiles.

    - `base_date` es la fecha de la etapa (la guardada en la ficha del estudiante).
      Si cae sábado o domingo, se corre al lunes siguiente.
    - El día 0 es la fecha base y cada día N se cuenta como N DÍAS HÁBILES
      (lunes a viernes) después de la base, nunca días corridos.
    """
    try:
        dias = {int(x.strip()) for x in str(dias_envio_str).split(",") if x.strip().isdigit()}
    except Exception:
        dias = set()
    if incluir_dia1 and not dias:
        dias = {0}
    if isinstance(base_date, datetime):
        base_date = base_date.date()
    base = _proxima_fecha_habil(base_date)
    resultado = []
    for n in sorted(d for d in dias if d >= 0):
        resultado.append((n, obtener_fecha_dia_habil(base, n)))
    return resultado


def programar_envios_dias_habiles(db, notificacion, estudiante, base_date=None):
    """Crea una fila en envios_programados por cada día de envío (con snapshot de correos).

    La base del plan es la fecha de la etapa (`notificacion.fecha_base`); solo si no
    existe se usa el día de hoy. Los días hábiles saltan fines de semana y feriados.
    """
    base = base_date or getattr(notificacion, "fecha_base", None) or obtener_ahora_santiago().date()
    if isinstance(base, datetime):
        base = base.date()
    # El plan puede cruzar de año: asegurar que existan los feriados de ambos.
    asegurar_feriados_anio(db, base.year)
    asegurar_feriados_anio(db, base.year + 1)
    cargar_feriados(db, forzar=True)
    pares = calcular_fechas_dias_habiles(base, notificacion.dias_habiles_envio, incluir_dia1=True)
    hora = notificacion.hora_envio or "09:00"

    # Snapshot de los destinatarios actuales (se congelan)
    dests = get_destinatarios_para_estudiante(db, estudiante, notificacion.grupo_ids)
    snapshot = json.dumps(
        [{"nombre": d.nombre, "email": d.email} for d in dests],
        ensure_ascii=False,
    )

    creados = []
    for (n, fecha) in pares:
        env = models.EnvioProgramado(
            notificacion_id=notificacion.id,
            estudiante_id=estudiante.id,
            etapa=notificacion.etapa,
            asunto=notificacion.asunto_personalizado,
            cuerpo=notificacion.cuerpo_personalizado,
            destinatarios=snapshot,
            fecha=fecha,
            hora=hora,
            dia_numero=n,
            estado="pendiente",
            enviado=False,
        )
        db.add(env)
        creados.append(env)
    db.commit()
    return creados


def _actualizar_notificacion_padre(db, notif_id):
    """Sincroniza la notificación 'job' con el avance de sus envíos programados."""
    if not notif_id:
        return
    notif = db.query(models.Notificacion).filter(models.Notificacion.id == notif_id).first()
    if not notif:
        return
    enviados = (
        db.query(models.EnvioProgramado)
        .filter(
            models.EnvioProgramado.notificacion_id == notif_id,
            models.EnvioProgramado.estado == "enviado",
        )
        .count()
    )
    pendientes = (
        db.query(models.EnvioProgramado)
        .filter(
            models.EnvioProgramado.notificacion_id == notif_id,
            models.EnvioProgramado.estado == "pendiente",
        )
        .order_by(models.EnvioProgramado.fecha.asc())
        .all()
    )
    notif.veces_enviado = enviados
    notif.ultimo_envio = obtener_ahora_santiago()
    if pendientes:
        prox = pendientes[0]
        hh, mm = _parse_hora(prox.hora, default=(9, 0))
        notif.proximo_envio = datetime.combine(prox.fecha, dtime(hh, mm))
    else:
        notif.proximo_envio = None
        if notif.estado == "activo":
            notif.estado = "completado"
    db.commit()


def _enviar_programado(db, env):
    """Envía un envío programado concreto a sus destinatarios congelados. Devuelve (enviados, fallidos)."""
    estudiante = (
        db.query(models.Estudiante).filter(models.Estudiante.id == env.estudiante_id).first()
    )
    conf = get_config_email(db)
    if not conf.envio_activo:
        print("[correos] Envío pausado por el switch global (ConfigEmail.envio_activo).")
        return (0, 0)

    if not estudiante:
        env.estado = "cancelado"
        db.commit()
        return (0, 0)

    colegio = (
        db.query(models.Colegio).filter(models.Colegio.id == estudiante.id_colegio).first()
    )
    nombre_colegio = colegio.nombre if colegio else ""
    sender_email, sender_pass, remitente = get_sender_for_colegio(nombre_colegio)

    try:
        destinatarios = json.loads(env.destinatarios) if env.destinatarios else []
    except Exception:
        destinatarios = []

    etapa_key = env.etapa or "inicio_proceso"
    cfg = db.query(models.ConfigFase).filter(models.ConfigFase.etapa == etapa_key).first()
    plazo_max = cfg.plazo_dias if cfg else 10
    dia_num = env.dia_numero if env.dia_numero is not None else 0

    asunto, cuerpo = construir_mensaje(
        estudiante,
        nombre_colegio,
        etapa_key,
        env.cuerpo,
        env.asunto,
        dia_numero=dia_num,
        plazo_total=plazo_max,
    )


    enviados, fallidos = 0, 0

    def _cerrar(estado="enviado"):
        """Cierra el envío programado. 'enviado' solo si realmente salió el correo."""
        env.estado = estado
        env.enviado = (estado == "enviado")
        env.fecha_envio_real = obtener_ahora_santiago() if estado == "enviado" else None
        db.commit()
        _actualizar_notificacion_padre(db, env.notificacion_id)

    if not destinatarios:
        # Nada que enviar: se cierra como cancelado (no como enviado) para no
        # mostrar un correo que nunca salió.
        _cerrar("cancelado")
        return (0, 0)

    if not sender_email or not sender_pass:
        for d in destinatarios:
            db.add(models.NotificacionLog(
                notificacion_id=env.notificacion_id,
                estudiante_id=estudiante.id,
                destinatario_email=d.get("email"),
                destinatario_nombre=d.get("nombre"),
                exito=False,
                detalle="Sin credenciales de remitente para el colegio",
            ))
            fallidos += 1
        _cerrar("fallido")
        return (enviados, fallidos)

    context = ssl.create_default_context()
    server = None
    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
        server.login(sender_email, sender_pass)
    except Exception as e:
        for d in destinatarios:
            db.add(models.NotificacionLog(
                notificacion_id=env.notificacion_id,
                estudiante_id=estudiante.id,
                destinatario_email=d.get("email"),
                destinatario_nombre=d.get("nombre"),
                exito=False,
                detalle=f"Error de conexión SMTP: {e}"[:255],
            ))
            fallidos += 1
        if server:
            try:
                server.quit()
            except Exception:
                pass
        _cerrar("fallido")
        return (enviados, fallidos)

    emails_list = [d.get("email") for d in destinatarios if d.get("email")]

    if emails_list:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = f"{remitente} <{sender_email}>"
            # Copia oculta: el header 'To' apunta al remitente y la entrega real se hace
            # por el sobre SMTP (sendmail), así los destinatarios no se ven entre sí.
            msg["To"] = f"{remitente} <{sender_email}>"
            msg.attach(MIMEText(cuerpo, "html"))
            server.sendmail(sender_email, emails_list, msg.as_string())
            for d in destinatarios:
                db.add(models.NotificacionLog(
                    notificacion_id=env.notificacion_id,
                    estudiante_id=estudiante.id,
                    destinatario_email=d.get("email"),
                    destinatario_nombre=d.get("nombre"),
                    exito=True,
                    detalle="Enviado",
                ))
                enviados += 1
        except Exception as e:
            for d in destinatarios:
                db.add(models.NotificacionLog(
                    notificacion_id=env.notificacion_id,
                    estudiante_id=estudiante.id,
                    destinatario_email=d.get("email"),
                    destinatario_nombre=d.get("nombre"),
                    exito=False,
                    detalle=str(e)[:255],
                ))
                fallidos += 1

    try:
        server.quit()
    except Exception:
        pass

    if enviados > 0:
        _cerrar("enviado")
    else:
        # Ningún correo salió (error de envío): queda registrado como fallido.
        _cerrar("fallido")

    return (enviados, fallidos)


def enviar_programados_vencidos(db, notif_id=None, forzar_primer_envio=False):
    """Envía los envios_programados pendientes cuya fecha+hora ya pasó.

    Regla anti-ráfaga: si una notificación tiene VARIOS recordatorios vencidos a la vez
    (porque la fecha de la etapa es anterior a hoy, o porque el servidor estuvo detenido),
    solo se envía el MÁS RECIENTE; los vencidos anteriores se marcan 'cancelado' para no
    mandar correos retroactivos. Los envíos futuros quedan pendientes para el scheduler.

    `forzar_primer_envio=True` (al crear la notificación) permite mandar de inmediato el
    recordatorio de hoy sin esperar a su hora programada; los días futuros nunca se adelantan.
    """
    ahora = obtener_ahora_santiago()
    q = db.query(models.EnvioProgramado).filter(models.EnvioProgramado.estado == "pendiente")
    if notif_id is not None:
        q = q.filter(models.EnvioProgramado.notificacion_id == notif_id)

    items = q.all()
    if not items:
        return 0, 0

    # Agrupar por notificación para decidir por plan, no por fila suelta.
    por_notif = {}
    for env in items:
        por_notif.setdefault(env.notificacion_id, []).append(env)

    enviados_total, fallidos_total = 0, 0
    for nid, envios in por_notif.items():
        vencidos = []
        for env in envios:
            hh, mm = _parse_hora(env.hora, default=(9, 0))
            fecha_hora_prog = datetime.combine(env.fecha, dtime(hh, mm))
            if ahora >= fecha_hora_prog:
                vencidos.append((fecha_hora_prog, env))
            elif forzar_primer_envio and env.fecha <= ahora.date():
                # Recordatorio de hoy: se adelanta a su hora al crear la notificación.
                vencidos.append((fecha_hora_prog, env))

        if not vencidos:
            continue

        vencidos.sort(key=lambda par: par[0])
        # Descartar los recordatorios atrasados: no se envían correos retroactivos.
        for _fh, env in vencidos[:-1]:
            env.estado = "cancelado"
        if len(vencidos) > 1:
            db.commit()

        e, f = _enviar_programado(db, vencidos[-1][1])
        enviados_total += e
        fallidos_total += f
        if len(vencidos) > 1:
            _actualizar_notificacion_padre(db, nid)
    return enviados_total, fallidos_total



def revisar_envios_programados():
    """Una pasada del scheduler para los envíos programados (días hábiles)."""
    db = database.SessionLocal()
    try:
        enviar_programados_vencidos(db)
    except Exception:
        traceback.print_exc()
    finally:
        db.close()


def revisar_pendientes():
    """Una pasada del scheduler: envía todas las notificaciones vencidas."""
    db = database.SessionLocal()
    try:
        asegurar_feriados_vigentes(db)
        cargar_feriados(db)
        ahora = obtener_ahora_santiago()
        pendientes = (
            db.query(models.Notificacion)
            .filter(models.Notificacion.estado == "activo")
            .all()
        )
        for n in pendientes:
            estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == n.estudiante_id).first()
            if _due(n, ahora, estudiante):
                procesar_notificacion(db, n)
    except Exception:
        traceback.print_exc()
    finally:
        db.close()


def _scheduler_loop(intervalo_seg=60):
    while True:
        try:
            revisar_pendientes()
        except Exception:
            traceback.print_exc()
        try:
            revisar_envios_programados()
        except Exception:
            traceback.print_exc()
        time.sleep(intervalo_seg)


_scheduler_started = False


def iniciar_scheduler():
    """Lanza el hilo del scheduler una sola vez."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    t = threading.Thread(target=_scheduler_loop, args=(60,), daemon=True)
    t.start()
    print("[notifications] Scheduler de recordatorios iniciado.")
