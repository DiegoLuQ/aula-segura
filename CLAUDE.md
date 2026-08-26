# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Sistema Aula Segura" — a school disciplinary-process tracker for Colegio Macaya (and other schools, e.g. Colegio Diego Portales) in Chile. Lawyers/admins register students under the "Aula Segura" disciplinary process (or a lighter "Otras Medidas" process), attach PDF documents, and trigger email notifications to staff at various stages of the process. All domain text, DB fields, and UI are in Spanish.

Stack: FastAPI (Python) backend + MySQL via SQLAlchemy, plain HTML/Tailwind(CDN)/vanilla-JS frontend (no build step, no framework).

## Commands

Backend (from `backend/`, with venv activated):
```
uvicorn main:app --reload --port 8010
python seed.py         # one-time: creates roles, colegios, and test users
python clean_data.py   # wipes operational data (students, documents, otras medidas); keeps roles/colegios/users — has interactive confirmation
```
There is no test suite in this repo (no pytest config, no `tests/` dir) — don't assume one exists.

Docker (production): `docker-compose up` builds backend (uvicorn on :8000 internally, image `my-python-fastapi:1.1` base) and frontend (nginx serving static files), both attached to an external network `red_produccion` expected to be created by a reverse-proxy stack (nginx-proxy + letsencrypt, via `VIRTUAL_HOST`/`LETSENCRYPT_HOST` env vars). Local dev typically runs the backend directly on port 8010 (per `otros_docs/configuracion_sistema.txt`) instead of Docker's 8000 — check which port the frontend's `API_URL` detection expects before assuming one.

Required env vars (`backend/.env`): `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `SMTP_SERVER`/`SMTP_PORT`, and per-colegio sender credentials `MC_SENDER_EMAIL`/`MC_SENDER_PASSWORD` (Macaya), `DP_SENDER_EMAIL`/`DP_SENDER_PASSWORD` (Diego Portales/"Portales").

## Architecture

### Backend is one flat FastAPI app, not a router-per-resource design
`backend/main.py` contains essentially every endpoint (students, otras-medidas, documents, users, destinatarios, grupos, plantillas, notificaciones) as top-level `@app.*` handlers — there's no `APIRouter` split. When adding endpoints, follow this file's existing pattern rather than introducing a new module structure unless asked.

### Schema management is NOT Alembic-driven in practice
Even though `backend/alembic/` exists (one migration), the app actually manages schema at startup in `main.py`:
1. `models.Base.metadata.create_all(bind=database.engine)` creates missing tables.
2. `_ensure_columns()` runs a hardcoded list of `ALTER TABLE ... ADD COLUMN` statements wrapped in try/except (ignoring "already exists" errors) to patch existing tables with new columns.

When adding a new column to an existing table, the established pattern is to add it to the model **and** add a corresponding `ALTER TABLE` line to `_ensure_columns()` in `main.py` — not to write a new Alembic revision.

### Role-based access control is inline, not centralized
Roles: `viewer` (sees only their own colegio's data), `super_viewer` (sees all colegios, read-only), `lawyer` (full CRUD, only role allowed to delete), `admin` (full CRUD + user management). There's no permission decorator/dependency — each endpoint checks `current_user["rol"]` inline (see `_require_editor()` in `main.py` for the destinatarios/grupos/plantillas/notificaciones section, and ad-hoc checks elsewhere). Auth itself is JWT via `auth.get_current_user`, which accepts the token from the `Authorization` header or a `?token=` query param (the latter exists specifically so PDF `<iframe>` previews can authenticate).

### Two parallel process pipelines
- **Estudiante** (`models.Estudiante`) — the main "Aula Segura" process with many stage-date fields (notificación medida, apelación, consejo de profesores, notificación final, envío SIE, etc.), documents (`Documento`), and full notification support.
- **OtraMedida** (`models.OtraMedida`) — a simpler alternate-measures process with its own documents (`DocumentoOtraMedida`), CRUD, and Excel bulk upload, mirroring the Estudiante endpoints but without the multi-stage date tracking.
Table names are prefixed `pro_aula_segura_*` throughout `models.py`.

### Notification system (`backend/notifications.py`)
- `Notificacion` is a recurring "job" tied to a student; modes: `una_vez` (send once), `paulatino` (daily until cancelled), `cada_3_dias` (every 3 days, max 3x), `fecha_indicada` (one send on a specific date), `dias_habiles` (send on specific business-day offsets from the etapa's date). The UI always sends `dias_habiles`; the other modes remain for API/legacy use.
- The base date of a `dias_habiles` plan is `Notificacion.fecha_base` = the etapa's date already saved on the student (`ETAPA_FECHA_ATTR` in `main.py` maps etapa → field). `crear_notificacion` never overwrites a date the user saved; it only fills it in when the etapa had none. The frontend enforces this too: each phase button in `registro.html` shows "Actualizar" until the date is saved, then "Enviar Notificación", then "Revisar" once a notification exists for that etapa.
- `dias_habiles` mode materializes each planned send into its own `EnvioProgramado` row (with a frozen JSON snapshot of recipients and body/subject at creation time) rather than being computed on the fly — so edits to a `Destinatario`/`Grupo` after the job starts don't retroactively affect already-scheduled sends. `EnvioProgramado.estado` is `pendiente | enviado | fallido | cancelado` (`enviado` only when the mail actually went out).
- Business days skip weekends **and** `Feriado` rows (`backend/feriados_cl.py` computes the permanent Chilean holidays — Easter, Ley 19.973/20.299 shifts; `POST /feriados/importar` pulls the official `apis.digital.gob.cl` list when the server has internet; `frontend/feriados.html` is the CRUD page). `notifications.cargar_feriados()` caches them in memory — call `notifications.invalidar_feriados()` after mutating the table, and `asegurar_feriados_anio()` before any date math that may cross into an unseeded year.
- Overdue reminders never fire retroactively in bulk: if several planned sends are due at once, `enviar_programados_vencidos` sends only the most recent and cancels the older ones.
- A daemon thread (`iniciar_scheduler`, started in `main.py`'s startup event, ticking every 60s) drives both plain `Notificacion` due-checks (`revisar_pendientes`) and `EnvioProgramado` due-checks (`revisar_envios_programados`).
- The SMTP sender account is chosen per-colegio by `get_sender_for_colegio()` (name-matching on "macaya" / "portales"/"diego") — a new colegio needs a matching branch there plus its own env-var credentials, it isn't data-driven.
- Recipients (`Destinatario`) can be targeted directly by colegio/`todos_colegios`, or filtered via `Grupo` membership (`DestinatarioGrupo`) when `grupo_ids` is passed.
- Email bodies support placeholder substitution (`{nombre}`, `{rut}`, `{curso}`, `{causa}`, `{fecha_inicio}`, `{medida}`/`{estado}`, `{fecha_medida}`, `{colegio}`) via `_aplicar_placeholders`, used both for custom bodies (`PlantillaCorreo` / ad-hoc `cuerpo_personalizado`) and default per-etapa templates in `construir_mensaje`.

### PDF document handling
Uploaded PDFs are compressed via `pikepdf` (`compress_pdf()` in `main.py`) and renamed to `TIPO_COLEGIO_FECHA_ID_RANDOM.pdf` before being stored under `backend/uploads/` and linked from `Documento`/`DocumentoOtraMedida`. See `.agent/skills/gestion_pdf_aula_segura/SKILL.md` for the documented rules (PDF-only, compression mandatory, physical file deleted on record delete, inline `<iframe>` preview via `/documentos/{id}/view` rather than forced download).

### Frontend: no shared JS module actually wired up
Each page in `frontend/*.html` is self-contained: it defines its own inline `<script>`, its own `API_URL` detection logic (identical boilerplate duplicated in every file), and its own DOM logic. `frontend/js/app.js` contains what looks like shared login/dashboard logic but **is not `<script src="">`-included by any HTML file** — treat it as dead/orphaned code, not the live implementation, unless you first verify a page has been wired to it.

### `.agent/skills/`
This repo uses a custom Spanish-language "Skills" convention for an agent framework (Antigravity), under `.agent/skills/<name>/SKILL.md`. `creator_de_habilidades` documents how to add a new skill folder (`SKILL.md` with YAML frontmatter `name`/`description`, optional `scripts/`, `examples/`, `resources/` subfolders, content in Spanish). This is unrelated to Claude Code's own skill system — don't conflate the two when asked to "create a skill" in this repo; confirm which system the user means.
