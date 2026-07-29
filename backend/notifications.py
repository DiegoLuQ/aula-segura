"""
Lógica de envío de correos de notificación (recordatorios) para los procesos
de Aula Segura.

- El remitente se elige según el COLEGIO del estudiante (credenciales del .env).
- Los destinatarios son los que pertenecen al colegio del estudiante MÁS los que
  tienen el privilegio `todos_colegios`, siempre que estén activos (estado=True).
- Un hilo en segundo plano (scheduler) revisa periódicamente las notificaciones
  programadas y envía los correos que estén vencidos.

Modos:
- 'una_vez'       -> 1 envío inmediato.
- 'paulatino'     -> recordatorio diario hasta que se cancele.
- 'cada_3_dias'   -> envío cada 3 días, máximo 3 veces.
- 'fecha_indicada'-> 1 envío en la fecha indicada.
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

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))


def _parse_hora(valor, default=(8, 0)):
    """Convierte 'HH:MM' en (hora, minuto). Si es inválido, retorna default (08:00)."""
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

    El día 1 corresponde al MISMO día de inicio del proceso (offset 0), el día 3 a
    2 días hábiles después, etc. Se combina con la hora de envío configurada.
    """
    if not estudiante or not estudiante.fecha_inicio_proceso:
        return []
    if not notificacion.dias_habiles_envio:
        return []
    try:
        dias_objetivo = sorted(
            int(x.strip())
            for x in notificacion.dias_habiles_envio.split(",")
            if x.strip().isdigit()
        )
    except Exception:
        return []
    # El "día 1" es el día de inicio; si cae en fin de semana, se mueve al siguiente día hábil
    # para que ningún recordatorio quede agendado un sábado o domingo.
    base = estudiante.fecha_inicio_proceso
    if isinstance(base, datetime):
        base = base.date()
    while base.weekday() >= 5:  # 5 = sábado, 6 = domingo
        base += timedelta(days=1)

    hh, mm = _parse_hora(getattr(notificacion, "hora_envio", None))
    objetivos = []
    for d in dias_objetivo:
        fecha = obtener_fecha_dia_habil(base, d - 1)
        if fecha:
            objetivos.append(datetime.combine(fecha, dtime(hh, mm)))
    objetivos.sort()
    return objetivos


def obtener_fecha_dia_habil(fecha_inicio: date, n_dias_habiles: int) -> date:
    """Retorna la fecha resultante de sumarle n_dias_habiles hábiles (lunes a viernes) a la fecha_inicio."""
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
        if curr.weekday() < 5:  # Lunes a Viernes
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


def _aplicar_placeholders(texto, estudiante, nombre_colegio):
    """Reemplaza las etiquetas {..} por los datos del estudiante. {estado} = la medida/estado elegido."""
    if not texto:
        return texto
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
    }
    for placeholder, val in replacements.items():
        texto = texto.replace(placeholder, str(val))
    return texto


def construir_mensaje(estudiante, nombre_colegio, etapa="inicio_proceso", cuerpo_personalizado=None, asunto_personalizado=None):
    """Resumen del proceso (asunto + cuerpo HTML), según la etapa."""
    if cuerpo_personalizado:
        texto = _aplicar_placeholders(cuerpo_personalizado, estudiante, nombre_colegio)

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
            asunto = _aplicar_placeholders(asunto_personalizado, estudiante, nombre_colegio)

        cuerpo = f"""
        <div style="font-family: Arial, sans-serif; color:#1e293b; max-width:600px;">
          <h2 style="color:#312e81;">Notificación de Proceso Aula Segura</h2>
          <p>Estimado/a,</p>
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
      <table style="border-collapse:collapse; width:100%; margin:16px 0;">
        {''.join(filas)}
      </table>
      <p>Por favor revise el expediente y realice las gestiones que correspondan.</p>
      <p style="color:#64748b; font-size:12px;">Mensaje automático del Sistema Aula Segura. No responder a este correo.</p>
    </div>
    """
    if asunto_personalizado:
        asunto = _aplicar_placeholders(asunto_personalizado, estudiante, nombre_colegio)
    return asunto, cuerpo


def enviar_correos(db, estudiante, notificacion):
    """Envía el correo a todos los destinatarios del estudiante y registra el log.
    Devuelve (enviados, fallidos)."""
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

    for d in destinatarios:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = f"{_remitente} <{sender_email}>"
            msg["To"] = d.email
            msg.attach(MIMEText(cuerpo, "html"))
            server.sendmail(sender_email, d.email, msg.as_string())
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
    """Si la fecha cae sábado o domingo, la mueve al lunes siguiente."""
    while fecha.weekday() >= 5:  # 5 = sábado, 6 = domingo
        fecha += timedelta(days=1)
    return fecha


def calcular_fechas_dias_habiles(base_date, dias_envio_str, incluir_dia1=True):
    """Devuelve [(dia_numero, fecha), ...] para el modo días hábiles.

    - El día 1 es la fecha base (hoy). Si incluir_dia1=True, siempre se agrega.
    - día N -> base + (N-1) días corridos; si cae fin de semana, se mueve al lunes.
    """
    try:
        dias = {int(x.strip()) for x in str(dias_envio_str).split(",") if x.strip().isdigit()}
    except Exception:
        dias = set()
    if incluir_dia1:
        dias = dias | {1}
    resultado = []
    for n in sorted(d for d in dias if d >= 1):
        fecha = base_date + timedelta(days=n - 1)
        fecha = _proxima_fecha_habil(fecha)
        resultado.append((n, fecha))
    return resultado


def programar_envios_dias_habiles(db, notificacion, estudiante, base_date=None):
    """Crea una fila en envios_programados por cada día de envío (con snapshot de correos)."""
    base = base_date or datetime.now().date()
    pares = calcular_fechas_dias_habiles(base, notificacion.dias_habiles_envio, incluir_dia1=True)
    hora = notificacion.hora_envio or "08:00"

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
    notif.ultimo_envio = datetime.now()
    if pendientes:
        prox = pendientes[0]
        hh, mm = _parse_hora(prox.hora)
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

    asunto, cuerpo = construir_mensaje(
        estudiante, nombre_colegio, env.etapa or "inicio_proceso", env.cuerpo, env.asunto
    )

    enviados, fallidos = 0, 0

    def _cerrar(estado="enviado"):
        env.estado = estado
        env.enviado = True
        env.fecha_envio_real = datetime.now()
        db.commit()
        _actualizar_notificacion_padre(db, env.notificacion_id)

    if not destinatarios:
        _cerrar()
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
        _cerrar()
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
        _cerrar()
        return (enviados, fallidos)

    for d in destinatarios:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = f"{remitente} <{sender_email}>"
            msg["To"] = d.get("email")
            msg.attach(MIMEText(cuerpo, "html"))
            server.sendmail(sender_email, d.get("email"), msg.as_string())
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

    _cerrar()
    return (enviados, fallidos)


def enviar_programados_vencidos(db, notif_id=None):
    """Envía los envios_programados pendientes cuya fecha+hora ya pasó.

    Si notif_id se indica, solo procesa los de esa notificación (útil al crearla).
    """
    ahora = datetime.now()
    q = db.query(models.EnvioProgramado).filter(models.EnvioProgramado.estado == "pendiente")
    if notif_id is not None:
        q = q.filter(models.EnvioProgramado.notificacion_id == notif_id)
    enviados_total, fallidos_total = 0, 0
    for env in q.all():
        hh, mm = _parse_hora(env.hora)
        if ahora >= datetime.combine(env.fecha, dtime(hh, mm)):
            e, f = _enviar_programado(db, env)
            enviados_total += e
            fallidos_total += f
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
        ahora = datetime.now()
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
