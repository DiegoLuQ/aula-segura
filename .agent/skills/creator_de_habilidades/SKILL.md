---
name: creador_de_habilidades
description: Una habilidad diseñada para crear otras habilidades siguiendo las mejores prácticas y en idioma español.
---

# Creador de Habilidades

Esta habilidad permite al agente Antigravity generar nuevas "Skills" (habilidades) para extender sus propias capacidades. Cada habilidad debe seguir una estructura de archivos estricta y estar documentada principalmente en español.

## Instrucciones para crear una nueva Habilidad

Cuando se te pida crear una nueva habilidad, sigue estos pasos:

1.  **Directorio**: Crea una nueva carpeta dentro de `.agent/skills/` con un nombre descriptivo en minúsculas y usando guiones bajos (ej. `gestor_datos_fiscales`).
2.  **Archivo SKILL.md (Obligatorio)**: Crea un archivo llamado `SKILL.md` en la raíz de la nueva carpeta. Este archivo **debe** contener:
    *   Un frontmatter YAML con `name` y `description`.
    *   Una sección de introducción que explique el propósito de la habilidad.
    *   Instrucciones detalladas sobre cómo usar la habilidad.
    *   Cualquier regla o restricción específica.
3.  **Scripts (Opcional)**: Si la habilidad requiere scripts de automatización, colócalos en una subcarpeta `scripts/`.
4.  **Ejemplos (Recomendado)**: Proporciona ejemplos de uso o plantillas en una subcarpeta `examples/`.
5.  **Recursos (Opcional)**: Cualquier otro archivo necesario debe ir en `resources/`.

## Formato del SKILL.md

```markdown
---
name: nombre_de_la_habilidad
description: Breve descripción de lo que hace.
---

# [Título de la Habilidad]

[Descripción detallada]

## Instrucciones
[Pasos para usarla]

## Reglas
- [Regla 1]
- [Regla 2]
```

## Consideraciones de Idioma
Todas las descripciones e instrucciones dirigidas al usuario o para el funcionamiento interno del agente dentro de los archivos `.md` deben estar en **español**, a menos que se trate de términos técnicos universales o código fuente.
