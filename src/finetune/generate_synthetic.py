"""
OVD Platform — Generador de datos sintéticos para fine-tuning (SM1.B)
Copyright 2026 Omar Robles

Genera ejemplos de entrenamiento sintéticos llamando a la Claude API.
Cada escenario produce hasta 3 ejemplos (analyze_fr, generate_sdd, qa_review).

Stacks cubiertos:
  - Oracle 12c / 19c  (legacy enterprise, mayor restricciones)
  - PostgreSQL 14/15  (moderno, RLS nativo)
  - Python/FastAPI    (microservicios)
  - Java Spring Boot  (enterprise JVM)
  - TypeScript/Next   (frontend/BFF)

Uso:
  python generate_synthetic.py --output data/synthetic.jsonl --count 350
  python generate_synthetic.py --output data/synthetic.jsonl --count 50 --stack oracle
  python generate_synthetic.py --output data/synthetic.jsonl --dry-run --count 10
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import NamedTuple

import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("OVD_SYNTH_MODEL", "claude-haiku-4-5-20251001")

# Tokens target por llamada (input+output combinado)
MAX_TOKENS_RESPONSE = 2048

# Cuántos escenarios generar en paralelo
# Plan básico Anthropic: 5 req/min, 4k tokens/min en Opus.
# Con Haiku los límites son mayores; mantener 1 para seguridad.
CONCURRENCY = 1

# Delay entre llamadas API (segundos) para respetar rate limits
# 15s = máximo ~4 req/min con margen de seguridad
CALL_DELAY_SECS = float(os.environ.get("OVD_SYNTH_DELAY", "15"))

# ---------------------------------------------------------------------------
# Prompts del sistema (mismos que el engine real)
# ---------------------------------------------------------------------------

SYSTEM_ANALYZE_FR = (
    "Eres un arquitecto de software senior en Omar Robles. "
    "Analiza el Feature Request y extrae: tipo exacto (bug/feature/refactor/security/performance), "
    "componentes afectados, riesgos, si involucra Oracle, complejidad y un resumen conciso. "
    "Responde en JSON estructurado."
)

SYSTEM_GENERATE_SDD = (
    "Eres un arquitecto siguiendo la metodología Spec-Driven Development (SDD). "
    "Genera una especificación completa con: requirements, design, constraints y tasks. "
    "Formato Markdown, estructura clara y concisa."
)

SYSTEM_QA_REVIEW = (
    "Eres un revisor QA/Security senior. Evalúa el resultado de implementación contra: "
    "1) Requisitos del SDD, 2) Seguridad OWASP, 3) Multi-tenancy (org_id), "
    "4) Compatibilidad Oracle 12c/19c si aplica. "
    "Responde en JSON estructurado con: passed, score, issues, owasp_concerns, rls_compliant, oracle_compat, summary."
)

# ---------------------------------------------------------------------------
# Catálogo de escenarios seed
# ---------------------------------------------------------------------------

class Scenario(NamedTuple):
    stack: str
    fr: str
    context: str          # descripción del proyecto para el prompt de generación
    has_oracle: bool
    negative: bool = False  # True = escenario negativo (ambiguo, imposible, escalación)


SCENARIOS: list[Scenario] = [
    # ── Oracle 12c ──────────────────────────────────────────────────────────
    Scenario(
        stack="oracle12c",
        fr="Agregar campo `last_login_ts` a la tabla USUARIOS y actualizar el login service",
        context="Sistema hospitalario legacy con Oracle 12c. Sin sequences modernas, sin CTEs recursivas.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle12c",
        fr="Corregir bug: la consulta de facturas tarda >30s cuando el cliente tiene más de 500 pedidos",
        context="ERP financiero Oracle 12c. Performance crítico, tablas con millones de filas.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle12c",
        fr="Implementar exportación masiva de contratos en PDF con firma digital",
        context="Sistema de contratos Oracle 12c + Java EE. Restricción: sin LOBs > 4GB en una transacción.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle12c",
        fr="Migrar stored procedure SP_CALCULAR_COMISIONES a lógica en capa de negocio Python",
        context="CRM Oracle 12c en proceso de modernización. El SP tiene 800 líneas con cursores implícitos.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle12c",
        fr="Agregar auditoría de cambios en tabla PRODUCTOS con detalle de campo modificado y usuario",
        context="Inventario Oracle 12c. Compliance requiere rastrear cada UPDATE con before/after values.",
        has_oracle=True,
    ),

    # ── Oracle 19c ──────────────────────────────────────────────────────────
    Scenario(
        stack="oracle19c",
        fr="Implementar particionado por rango en tabla VENTAS para mejorar queries de reportes anuales",
        context="Data warehouse Oracle 19c. Tabla VENTAS con 200M+ filas, queries anuales lentas.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c",
        fr="Agregar soporte multi-idioma (i18n) al módulo de notificaciones",
        context="Plataforma SaaS Oracle 19c + Python FastAPI. Soportar ES/EN/PT inicialmente.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c",
        fr="Refactorizar módulo de reportes para usar materialized views con refresh on demand",
        context="BI interno Oracle 19c. Los reportes bloquean la DB durante refresh cada hora.",
        has_oracle=True,
    ),

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    Scenario(
        stack="postgresql",
        fr="Implementar RLS (Row Level Security) en tablas de documentos para aislamiento por org_id",
        context="SaaS multi-tenant PostgreSQL 15 + FastAPI. Cada organización debe ver solo sus documentos.",
        has_oracle=False,
    ),
    Scenario(
        stack="postgresql",
        fr="Agregar índice GIN para búsqueda full-text en campo `contenido` de tabla ARTICULOS",
        context="CMS PostgreSQL 14. Búsqueda por palabras clave en contenido de artículos (ES/EN).",
        has_oracle=False,
    ),
    Scenario(
        stack="postgresql",
        fr="Migrar columna `metadata` de TEXT a JSONB y agregar índices para queries frecuentes",
        context="Plataforma de eventos PostgreSQL 15. metadata almacena JSON serializado como texto actualmente.",
        has_oracle=False,
    ),
    Scenario(
        stack="postgresql",
        fr="Implementar sistema de colas con SKIP LOCKED para procesamiento asíncrono de emails",
        context="Microservicio de notificaciones PostgreSQL 15 + Python. Alto volumen: ~10k emails/hora.",
        has_oracle=False,
    ),
    Scenario(
        stack="postgresql",
        fr="Corregir N+1 query en endpoint GET /usuarios/:id/proyectos",
        context="API REST PostgreSQL 14 + Django. El endpoint hace una query por cada proyecto del usuario.",
        has_oracle=False,
    ),

    # ── Python FastAPI ───────────────────────────────────────────────────────
    Scenario(
        stack="python_fastapi",
        fr="Agregar rate limiting por API key en todos los endpoints públicos",
        context="API pública FastAPI + Redis. Límite: 1000 req/min por key, 429 con Retry-After header.",
        has_oracle=False,
    ),
    Scenario(
        stack="python_fastapi",
        fr="Implementar webhook system para notificar eventos de ciclo completado a sistemas externos",
        context="OVD Platform FastAPI. Los clientes necesitan recibir notificaciones HTTP POST en sus sistemas.",
        has_oracle=False,
    ),
    Scenario(
        stack="python_fastapi",
        fr="Refactorizar autenticación para soportar OAuth2 con providers externos (Google, GitHub)",
        context="SaaS FastAPI + SQLAlchemy. Actualmente solo email/password con JWT propio.",
        has_oracle=False,
    ),
    Scenario(
        stack="python_fastapi",
        fr="Agregar validación de esquema JSON en body de POST /sesiones con errores descriptivos",
        context="API interna FastAPI. Los errores actuales de Pydantic son difíciles de interpretar por los clientes.",
        has_oracle=False,
    ),
    Scenario(
        stack="python_fastapi",
        fr="Implementar caché de respuestas con Redis para endpoints de reportes (TTL 5 minutos)",
        context="Dashboard analytics FastAPI + Redis. Los reportes tardan 2-8s y se consultan frecuentemente.",
        has_oracle=False,
    ),

    # ── Java Spring Boot ─────────────────────────────────────────────────────
    Scenario(
        stack="java_spring",
        fr="Migrar configuración de datasource a HikariCP con pool tunning para carga alta",
        context="Microservicio Spring Boot 3 + Oracle 19c. Pool actual con defaults, saturación en pico.",
        has_oracle=True,
    ),
    Scenario(
        stack="java_spring",
        fr="Implementar circuit breaker con Resilience4j en llamadas al servicio de pagos externo",
        context="Gateway de pagos Spring Boot 3. El servicio externo tiene SLA 99.5%, necesitamos fallback.",
        has_oracle=False,
    ),
    Scenario(
        stack="java_spring",
        fr="Agregar soporte para exportación de reportes en formato Excel (XLSX) con streaming",
        context="ERP Spring Boot 3 + JPA. Reportes de hasta 100k filas, sin cargar todo en memoria.",
        has_oracle=False,
    ),
    Scenario(
        stack="java_spring",
        fr="Corregir memory leak en procesamiento de archivos XML grandes (>100MB)",
        context="ETL Spring Boot 3. El parser DOM carga el XML completo en memoria, OutOfMemoryError en producción.",
        has_oracle=False,
    ),

    # ── TypeScript/Next ──────────────────────────────────────────────────────
    Scenario(
        stack="typescript_next",
        fr="Implementar lazy loading de imágenes y optimización de Core Web Vitals en landing page",
        context="E-commerce Next.js 14 + TypeScript. LCP > 4s en mobile, imágenes sin optimizar.",
        has_oracle=False,
    ),
    Scenario(
        stack="typescript_next",
        fr="Agregar modo oscuro persistente con localStorage y respeto a prefers-color-scheme",
        context="Dashboard Next.js 14 + Tailwind. Los usuarios piden modo oscuro que persista entre sesiones.",
        has_oracle=False,
    ),
    Scenario(
        stack="typescript_next",
        fr="Implementar virtualización de lista con react-virtual para tabla de 50k+ registros",
        context="Admin panel Next.js 14. La tabla de logs renderiza todos los items, browser se congela.",
        has_oracle=False,
    ),
    Scenario(
        stack="typescript_next",
        fr="Refactorizar fetch de datos para usar React Query con optimistic updates",
        context="SaaS dashboard Next.js 14. El patrón actual useEffect+useState causa race conditions.",
        has_oracle=False,
    ),

    # ── HHMM Honorarios Médicos — Clínica Alemana (casos reales) ────────────
    # Dominio: sistema hospitalario multi-sucursal (CAS/CAT/CAV), Oracle 19c (migrado 12c),
    # Java Struts 1.3 + iBATIS 2.3, API REST Python paralela, integraciones: SAP SOAP,
    # dblinks Oracle (@acajas.alemana.cl, @asgparametros.alemana.cl, @saludnew), WebLogic 12c.
    # Esquemas: HONORARIOS_CAS (PSOL7/Exadata), HONORARIOS_CAT (PSOL8/Exadata), HONORARIOS_CAV.

    Scenario(
        stack="oracle19c_java_struts",
        fr="Corregir duplicación de solicitudes de liquidación en proceso masivo CCPH ambulatorio: "
           "1.150 solicitudes duplicadas en CAS con CodSolLiq consecutivos, diferencia de $411M enviada a SAP",
        context="Sistema HHMM Honorarios Médicos, Oracle 19c (PSOL7 Exadata), Java Struts 1.3 + iBATIS. "
                "Proceso 'Generacion y envio a CCPH' ejecutado en modo asíncrono con retry generó dobles "
                "inserciones en INTERFAZ_CCPH_CABECERA e INTERFAZ_CCPH_DETALLE usando SEQ_INTERFAZ_CCPH_NUMSOLLIQ. "
                "El bug ocurre cuando el thread WTC se queda stuck y el retry reejecutó el proceso completo. "
                "Impacto financiero directo: registros ya enviados a SAP en estado 'Pendiente de pago'. "
                "Multi-sucursal: CAS (1.150 dup) y CAT (90 dup). Requiere rollback quirúrgico en Oracle.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_exadata",
        fr="Optimizar query de Reporte Carga Honorarios Ambulatorios que genera crecimiento excesivo "
           "del tablespace TEMP en PSOL8 (Exadata) durante ejecución desde menú Reportes > Pagos",
        context="Sistema HHMM, esquema HONORARIOS_CAT en Oracle 19c Exadata (PSOL8). "
                "La query usa SELECT * con 9 tablas en JOIN (prestacion, prestacion_ambulatoria, "
                "DETALLE_PAGO_AMBULATORIO, cajtB_ERP_flujo@acajas.alemana.cl, cajt_ticket@acajas.alemana.cl, "
                "part_previsiones@asgparametros.alemana.cl, saludnew.raf_pagos) sin índices en columnas de filtro. "
                "Detectado por DBA Mario Guerra. La query no tiene hints ni partición por fecha. "
                "El mapper iBATIS está en ReportePagoAmbulatorioMapper.xml. "
                "Restricción: no modificar dblinks existentes, solo optimizar query y agregar índices.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_java_struts",
        fr="Corregir caída del sistema después de procesar 7.208 prestaciones hospitalizadas "
           "en interfaz 'Obtener Prestaciones Hospitalizados' para empresa Servicios Clínica Alemana Ltda.",
        context="Sistema HHMM, módulo Interfaz Hospitalizado, Oracle 19c. "
                "El proceso completa exitosamente la obtención y creación de 7.208 registros, "
                "pero la aplicación J2EE cae en un paso posterior (importar distribución, exportar Excel o reprocesar). "
                "No hay mensaje de error visible al usuario. Logs del servidor no disponibles aún. "
                "Antecedente: caso previo liq4077 con mismo patrón. Entorno WebLogic 12c.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_ibatis",
        fr="Corregir descuadre entre vista Participaciones > Ingresos/Costos y el detalle al hacer "
           "click en un contrato: los montos de distribución no coinciden con ingresos/costos del periodo",
        context="Sistema HHMM, módulo Participaciones, Oracle 19c (esquema HONORARIOS), Java Struts + iBATIS. "
                "Arquitectura DDD sin PL/SQL: toda la lógica está en ContratoParticipacionImpl.java (~52KB). "
                "La vista Ingresos/Costos suma MONTO_FINAL de ITEM_MARGEN_PERIODO (INDICADOR_ES_ABONO). "
                "El detalle de distribución usa MatrizPeriodoParticipacion.xml. "
                "No hay triggers en el flujo principal (solo 3 en INGRESO_MANUAL_*). "
                "Reportado por Francisco Rajas Iturra. La query selectMontosIngresoPorEmpresaSucursalServicio "
                "podría estar excluyendo ajustes manuales del periodo.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_java_itext",
        fr="Corregir NullPointerException en generación de PDF ambulatorio para prestaciones tipo_5 "
           "(ajustes manuales) con campo nombrePaciente nulo",
        context="Sistema HHMM, módulo generación PDF ambulatorio, Oracle 19c + Java + iText. "
                "Las prestaciones tipo_5 son ajustes manuales que no siempre tienen nombrePaciente poblado. "
                "El proceso batch PDF falla con NPE en la clase que construye el documento iText. "
                "Fix requerido: proteger campo nombrePaciente nulo antes de pasarlo a iText. "
                "El proceso batch corre en preprod con PKG y debe validarse en ambiente de certificación. "
                "No modificar la lógica de cálculo de montos, solo el manejo del campo nullable.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_python_api",
        fr="Implementar endpoint REST Python que reemplaza servicio Tuxedo ObtenerPrestaciones: "
           "recibir parámetros de búsqueda y retornar prestaciones desde Oracle con trazabilidad "
           "de fecha_prestacion (fecha sisalud) vs fecha_pago_op",
        context="Sistema HHMM, API REST Python (api-hhmm) que reemplaza integración Tuxedo WTC. "
                "El servicio Tuxedo original (profesi-honorari-tuxedo, ya no activo) consumía desde "
                "SALUDNEW via dblink. El nuevo API Python debe conectar a Oracle 19c directamente. "
                "Hallazgo crítico: en PrestacionCromImpl.java línea 1203 y 1566, fechaPagoOp se graba "
                "en PRESTACIONES.fecha_prestacion (bug histórico). La fecha real está en fecha_sisalud "
                "de las tablas hijas (PRESTACIONES_ESPECIALISTAS, PRESTACIONES_AMBULATORIAS). "
                "El nuevo endpoint debe exponer ambas fechas correctamente para no perpetuar el bug.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_java_struts",
        fr="Implementar auditoría de cambios campo a campo en módulo Participaciones: "
           "registrar before/after de cada UPDATE en CONTRATO_PARTICIPACIONES y tablas relacionadas "
           "para cumplir compliance Ley 20.584 (datos sensibles salud)",
        context="Sistema HHMM, módulo Participaciones, Oracle 19c. "
                "La Ley 20.584 (derechos de pacientes) exige trazabilidad completa de modificaciones "
                "en datos que afectan honorarios médicos. "
                "No usar triggers Oracle (política del proyecto: lógica en Java). "
                "La auditoría debe registrar: usuario LDAP, timestamp, tabla, campo, valor_anterior, valor_nuevo. "
                "Stack: Struts Actions + CromImpl + iBATIS. No hay ORM, los updates son SQL directos en XML mappers.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_exadata",
        fr="Migrar tabla PRESTACIONES (200M+ filas) a particionado por rango en campo fecha_prestacion "
           "para mejorar performance de queries de liquidación mensual en Oracle 19c Exadata",
        context="Sistema HHMM, esquema HONORARIOS_CAS, Oracle 19c Exadata (PSOL7). "
                "La tabla PRESTACIONES tiene 200M+ filas sin particionado. "
                "Los reportes de liquidación mensual filtran siempre por rango de fechas pero sin usar particiones. "
                "Restricciones: migración en línea (online redefinition) sin downtime, "
                "mantener dblinks existentes, no romper foreign keys de tablas hijas "
                "(PRESTACIONES_ESPECIALISTAS, PRESTACIONES_AMBULATORIAS, PRESTACIONES_HOSPITALIZADOS). "
                "El particionado debe ser por RANGE en fecha_prestacion con particiones mensuales.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_java_struts",
        fr="Refactorizar lógica de negocio de Actions Struts hacia capa de servicio CromImpl "
           "en módulo Participaciones: DistribucionParticipantesHeadAction tiene lógica de estado "
           "y flags que debería estar en IngresoCostoImpl",
        context="Sistema HHMM, módulo Participaciones, Java Struts 1.3 + Spring 2.5. "
                "Problema identificado en SDD: lógica de negocio está en la capa de presentación. "
                "DistribucionParticipantesHeadAction.buscar() tiene lógica de flags de estado. "
                "IngresoCostoParticipacionesDetalleAction tiene cálculos de montos. "
                "La refactorización debe ser incremental: no romper funcionalidad existente, "
                "no hay tests automáticos (P03 del SDD). Solo mover lógica, no cambiar SQL ni iBATIS XML. "
                "El sistema está en producción activa, refactor debe ser seguro.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_python_api",
        fr="Agregar manejo de timeout y retry con backoff en llamadas a dblinks Oracle "
           "(@acajas.alemana.cl, @asgparametros.alemana.cl) desde API Python HHMM",
        context="Sistema HHMM, API REST Python, Oracle 19c con dblinks a múltiples esquemas externos. "
                "Los dblinks a @acajas y @asgparametros fallan ocasionalmente por latencia de red interna. "
                "Sin retry, el error propaga al usuario como 500. "
                "La API Python usa cx_Oracle/oracledb para conexión. "
                "El retry debe implementarse en la capa de repositorio con backoff exponencial (3 intentos). "
                "Contexto multi-sucursal: misma API sirve a CAS, CAT y CAV con conexiones distintas.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_java_struts",
        fr="Corregir IndexOutOfBoundsException en método findEspecialidadByNumeroDocumento "
           "cuando el RUT del profesional no tiene especialidad registrada en el sistema",
        context="Sistema HHMM, módulo búsqueda de profesionales, Java Struts + iBATIS + Oracle 19c. "
                "El método retorna una lista vacía cuando no hay especialidad, y el código llamador "
                "accede a lista.get(0) sin verificar si está vacía. "
                "Fix requerido: proteger el acceso al índice 0, retornar Optional o valor por defecto. "
                "El método es usado en múltiples flujos: liquidación ambulatoria, hospitalizada y participaciones. "
                "Agregar @SerializedName en DominioPrestacionParse para mapeo correcto si aplica.",
        has_oracle=True,
    ),
    Scenario(
        stack="oracle19c_configuracion",
        fr="Corregir que operaciones ESENCIAL no son detectadas por el módulo de Honorarios: "
           "las OPs de tipo ESENCIAL no aparecen en el reporte de prestaciones pendientes",
        context="Sistema HHMM, módulo configuración de descuentos y tipos de operación, Oracle 19c. "
                "Las operaciones de tipo ESENCIAL están configuradas en SGPARAMETROS (esquema externo "
                "vía @asgparametros.alemana.cl). El filtro del sistema usa un código de tipo que no "
                "incluye ESENCIAL en la tabla de parámetros locales. "
                "No es un bug de código: es una configuración faltante en tablas de parámetros. "
                "La solución requiere INSERT en tablas de configuración + validación de que el código "
                "ESENCIAL queda mapeado correctamente en la lógica de detección de OPs.",
        has_oracle=True,
    ),

    # ── Escenarios negativos — el modelo aprende a NO inventar soluciones ───
    # Estos escenarios enseñan: cuándo pedir clarificación, cuándo escalar,
    # cuándo rechazar una implementación con bugs críticos.

    Scenario(
        stack="oracle19c_java_struts",
        fr="La interfaz se cayó otra vez, igual que antes",
        context="Sistema HHMM. El usuario reporta 'la interfaz se cayó' sin especificar: "
                "qué interfaz (hospitalizado, ambulatorio, CCPH, participaciones), "
                "qué acción estaba ejecutando, cuándo ocurrió, qué mensaje de error vio, "
                "qué ambiente (CAS/CAT/CAV), qué versión está en producción. "
                "No hay logs adjuntos. El antecedente más reciente es liq4078 (interfaz hospitalizado). "
                "Caso negativo: el modelo debe solicitar información mínima antes de proceder.",
        has_oracle=True,
        negative=True,
    ),
    Scenario(
        stack="oracle12c",
        fr="Implementar CTE recursiva para calcular jerarquía de contratos de participación "
           "con profundidad ilimitada usando WITH RECURSIVE en Oracle 12c",
        context="Sistema HHMM legacy en Oracle 12c (aún no migrado a 19c en este ambiente). "
                "El desarrollador solicita usar WITH RECURSIVE (sintaxis PostgreSQL/estándar SQL:1999). "
                "Oracle 12c soporta CTEs pero NO la cláusula RECURSIVE — usa CONNECT BY en su lugar. "
                "Caso negativo: la implementación solicitada es técnicamente imposible en este stack. "
                "El modelo debe identificar la incompatibilidad y proponer la alternativa correcta "
                "con CONNECT BY PRIOR o CTE sin RECURSIVE.",
        has_oracle=True,
        negative=True,
    ),
    Scenario(
        stack="oracle19c_ibatis",
        fr="Implementar búsqueda dinámica de prestaciones por múltiples filtros opcionales "
           "usando concatenación de strings en el mapper iBATIS con $paramName$ para evitar "
           "el problema de los PreparedStatement con parámetros opcionales",
        context="Sistema HHMM, mapper iBATIS 2.3, Oracle 19c. "
                "El desarrollador propone usar $paramName$ (sustitución directa) en vez de #paramName# "
                "(PreparedStatement) para manejar filtros opcionales dinámicamente. "
                "Caso negativo de qa_review: la implementación introduce SQL injection crítica. "
                "En iBATIS, $param$ inserta el valor directamente en el SQL sin escape. "
                "Con datos de pacientes y montos económicos, esto es una vulnerabilidad OWASP A03 crítica. "
                "El modelo debe rechazar el código, score < 40, marcar OWASP A03:Injection.",
        has_oracle=True,
        negative=True,
    ),
    Scenario(
        stack="oracle19c_java_struts",
        fr="Reescribir completamente el sistema HHMM en microservicios Spring Boot + React "
           "en un sprint de 2 semanas para eliminar la deuda técnica de Struts 1.3",
        context="Sistema HHMM, 20+ años de desarrollo, ~500K líneas de código Java, "
                "159 clases ADO generadas por EMPUSA, 8 módulos principales (Participaciones, "
                "Liquidación Ambulatoria, Hospitalizado, CCPH, Reportes, etc.), "
                "integraciones activas con SAP, LDAP, Tuxedo API Python, dblinks Oracle. "
                "Caso negativo: el FR es irreal en el tiempo propuesto y sin análisis de riesgo. "
                "El modelo debe escalar, NO generar un SDD de reescritura total. "
                "Debe proponer un análisis faseado: inventario, priorización, migración incremental "
                "módulo por módulo, sin downtime para producción activa.",
        has_oracle=True,
        negative=True,
    ),
]

# ---------------------------------------------------------------------------
# Generador de prompts para Claude
# ---------------------------------------------------------------------------

def _prompt_analyze_fr(scenario: Scenario) -> str:
    if scenario.negative:
        return f"""Genera un ejemplo de entrenamiento para el tipo "analyze_fr" con un FR problemático.

El FR es ambiguo, imposible técnicamente o irreal en su alcance. El modelo debe aprender a
identificar el problema y solicitar clarificación o rechazar en lugar de inventar una solución.

Feature Request:
{scenario.fr}

Contexto del proyecto: {scenario.context}

Instrucciones:
1. El campo "user" debe ser el Feature Request tal cual (sin modificar).
2. El campo "assistant" debe ser un JSON con:
   - fr_type: "unclear" (si es ambiguo) | "impossible" (si es técnicamente inviable) | "escalation" (si el alcance es irreal)
   - complexity: "unknown" (si no hay suficiente info) | "critical" (si requiere escalación)
   - components: lista vacía o con los componentes que se pueden inferir
   - oracle_involved: {str(scenario.has_oracle).lower()}
   - risks: lista con los riesgos de proceder sin más información
   - needs_clarification: lista de strings con las preguntas específicas que se deben hacer antes de continuar
   - summary: explicación de por qué no se puede proceder tal como está el FR

Responde SOLO con el JSON del ejemplo:
{{
  "messages": [
    {{"role": "user", "content": "<el FR completo>"}},
    {{"role": "assistant", "content": "<JSON como string escapado>"}}
  ]
}}"""

    return f"""Genera un ejemplo realista de entrenamiento para el tipo "analyze_fr".

El ejemplo debe simular exactamente la respuesta que daría un arquitecto senior al analizar este Feature Request:

Feature Request:
{scenario.fr}

Contexto del proyecto: {scenario.context}

Instrucciones:
1. El campo "user" debe ser el Feature Request tal cual (sin modificar).
2. El campo "assistant" debe ser un JSON válido con exactamente estos campos:
   - fr_type: "bug" | "feature" | "refactor" | "security" | "performance"
   - complexity: "low" | "medium" | "high"
   - components: lista de strings con nombres de componentes afectados (2-5 items)
   - oracle_involved: {str(scenario.has_oracle).lower()}
   - risks: lista de strings con riesgos identificados (1-4 items, específicos y técnicos)
   - summary: resumen técnico conciso de máximo 200 caracteres

Responde SOLO con el JSON del ejemplo, sin explicaciones:
{{
  "messages": [
    {{"role": "user", "content": "<el FR completo>"}},
    {{"role": "assistant", "content": "<JSON como string escapado>"}}
  ]
}}"""


def _prompt_generate_sdd(scenario: Scenario) -> str:
    """
    Devuelve SOLO el contenido Markdown (SDD o respuesta negativa).
    El wrapper JSON lo construye _generate_scenario_examples para evitar
    que el modelo tenga que escapar Markdown dentro de strings JSON.
    """
    if scenario.negative:
        return f"""Eres un arquitecto senior de Omar Robles. Recibes este Feature Request problemático:

Feature Request: {scenario.fr}

Contexto del proyecto: {scenario.context}

El FR tiene un problema fundamental (ambigüedad, imposibilidad técnica o alcance irreal).
NO generes un SDD normal. Escribe una respuesta en Markdown con exactamente estas secciones:

## Problema Identificado
(explica por qué no se puede proceder tal como está el FR)

## Por qué no se puede generar el SDD
(detalla la limitación concreta: falta de información, restricción técnica del stack, o alcance desproporcionado)

## Propuesta Alternativa
(qué debe ocurrir primero: preguntas a responder, alternativa técnica viable, o fases de alcance reducido)

Sé específico, técnico y conciso. No inventes datos que no están en el FR."""

    oracle_constraints = f"Oracle {scenario.stack.replace('oracle', '').replace('_', ' ').strip()}" if scenario.has_oracle else "PostgreSQL/estándar"
    return f"""Eres un arquitecto senior de Omar Robles siguiendo metodología Spec-Driven Development.

Feature Request: {scenario.fr}

Contexto del proyecto: {scenario.context}

Genera un SDD completo y específico para este stack. Usa exactamente estas secciones Markdown:

## Objetivo
(qué problema resuelve y cuál es el resultado esperado)

## Requisitos funcionales
1. (3-5 requisitos concretos y verificables)

## Requisitos no-funcionales
- (2-3 items: incluir seguridad, performance, y compatibilidad de stack)

## Diseño técnico
(enfoque de implementación: clases/tablas/endpoints a modificar, patrones a usar)

## Constraints técnicas — {oracle_constraints}
(restricciones específicas del stack: versiones, limitaciones Oracle/DB, integraciones existentes)

## Tasks
1. (4-7 pasos ordenados de implementación, específicos y accionables)

Sé específico con el stack descrito en el contexto. No uses placeholders genéricos."""


def _user_msg_for_sdd(scenario: Scenario) -> str:
    """Construye el mensaje de usuario para ejemplos generate_sdd."""
    if scenario.negative:
        return (
            f"Feature Request:\n{scenario.fr}\n\n"
            f"Análisis previo:\nFR clasificado como problemático — requiere clarificación o "
            f"redefinición antes de proceder con el SDD."
        )
    return (
        f"Feature Request:\n{scenario.fr}\n\n"
        f"Análisis previo:\nStack: {scenario.stack}. "
        f"Oracle involucrado: {'sí' if scenario.has_oracle else 'no'}. "
        f"Contexto: {scenario.context[:150]}"
    )


def _prompt_qa_review(scenario: Scenario) -> str:
    """
    Devuelve SOLO el JSON del resultado QA (sin wrapper externo).
    El wrapper de messages lo construye _generate_scenario_examples.
    """
    if scenario.negative:
        score = random.randint(10, 45)
        return f"""Eres el revisor QA de Omar Robles. Evalúas una implementación con bugs críticos.

Feature Request: {scenario.fr}
Stack: {scenario.context}

La implementación tiene problemas graves (SQL injection, violación de restricciones del stack,
bug lógico crítico, o vulnerabilidad de seguridad). Debes rechazarla.

Genera SOLO el JSON de resultado QA (sin markdown, sin explicación extra):

{{
  "passed": false,
  "score": {score},
  "issues": ["<issue 1 específico con archivo/clase/patrón concreto>", "<issue 2>", "<issue 3>"],
  "owasp_concerns": ["<categoría OWASP violada con descripción breve>"],
  "rls_compliant": false,
  "oracle_compat": false,
  "summary": "<evaluación técnica de por qué se rechaza, máx 200 chars>"
}}"""

    passed = random.random() > 0.25  # 75% de ejemplos pasan QA
    score = random.randint(82, 97) if passed else random.randint(55, 74)
    issues_hint = "[]" if passed else '["<issue específico>"]'
    owasp_hint = "[]" if passed else '["<concern OWASP si aplica>"]'
    return f"""Eres el revisor QA de Omar Robles siguiendo metodología Spec-Driven Development.

Feature Request: {scenario.fr}
Stack: {scenario.context}

Evalúas el resultado de implementación de un agente de código.

Genera SOLO el JSON de resultado QA (sin markdown, sin explicación extra):

{{
  "passed": {str(passed).lower()},
  "score": {score},
  "issues": {issues_hint},
  "owasp_concerns": {owasp_hint},
  "rls_compliant": {"true" if not scenario.has_oracle else "true"},
  "oracle_compat": {str(scenario.has_oracle).lower()},
  "summary": "<evaluación técnica concisa, máx 200 chars>"
}}

El JSON debe ser específico para el stack descrito. No uses placeholders genéricos."""


def _user_msg_for_qa(scenario: Scenario) -> str:
    """Construye el mensaje de usuario para ejemplos qa_review."""
    prefix = "SDD aprobado:\n## Objetivo\nImplementar " + scenario.fr[:100]
    if scenario.negative:
        suffix = "\n\nResultado de implementación a revisar:\n<implementación con el problema descrito en el contexto del escenario>"
    else:
        suffix = "\n\nResultado de implementación a revisar:\n<agente completó la implementación según el SDD>"
    return prefix + suffix


# ---------------------------------------------------------------------------
# Llamadas a Claude API
# ---------------------------------------------------------------------------

async def _call_claude(client: anthropic.AsyncAnthropic, system: str, user_prompt: str) -> str | None:
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_RESPONSE,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Throttle para respetar rate limits del plan
        await asyncio.sleep(CALL_DELAY_SECS)
        return response.content[0].text if response.content else None
    except Exception as e:
        print(f"  [ERROR] Claude API: {e}", file=sys.stderr)
        # En caso de 429, esperar más antes de continuar
        if "429" in str(e) or "rate_limit" in str(e):
            print(f"  [RATE LIMIT] Esperando 60s antes de continuar...", file=sys.stderr)
            await asyncio.sleep(60)
        return None


def _parse_example(raw: str) -> dict | None:
    """Extrae el JSON del ejemplo de la respuesta de Claude."""
    # Intentar parsear directamente
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Buscar bloque JSON entre ```
    import re
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Buscar primer { ... } en el texto
    m = re.search(r"(\{.*\})", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return None


def _validate_example(example: dict) -> bool:
    """Valida que el ejemplo tenga la estructura mínima requerida."""
    messages = example.get("messages", [])
    if len(messages) < 2:
        return False
    if messages[0].get("role") != "user" or not messages[0].get("content"):
        return False
    if messages[1].get("role") != "assistant" or not messages[1].get("content"):
        return False
    return True


async def _generate_scenario_examples(
    client: anthropic.AsyncAnthropic,
    scenario: Scenario,
    example_types: list[str],
) -> list[dict]:
    """Genera hasta 3 ejemplos para un escenario dado."""
    results = []

    type_to_system = {
        "analyze_fr":    SYSTEM_ANALYZE_FR,
        "generate_sdd":  SYSTEM_GENERATE_SDD,
        "qa_review":     SYSTEM_QA_REVIEW,
    }
    type_to_prompt = {
        "analyze_fr":   _prompt_analyze_fr,
        "generate_sdd": _prompt_generate_sdd,
        "qa_review":    _prompt_qa_review,
    }

    for ex_type in example_types:
        raw = await _call_claude(
            client,
            type_to_system[ex_type],
            type_to_prompt[ex_type](scenario),
        )
        if not raw:
            continue

        if ex_type == "generate_sdd":
            # Prompt devuelve Markdown directo — wrapper construido en Python
            sdd_content = raw.strip()
            if len(sdd_content) < 50:
                print(f"  [SKIP] {scenario.stack}/{ex_type}: respuesta demasiado corta", file=sys.stderr)
                continue
            example = {
                "system": type_to_system[ex_type],
                "messages": [
                    {"role": "user",      "content": _user_msg_for_sdd(scenario)},
                    {"role": "assistant", "content": sdd_content},
                ],
            }
        elif ex_type == "qa_review":
            # Prompt devuelve JSON del QA directo — wrapper construido en Python
            import re as _re
            qa_raw = raw.strip()
            # Quitar markdown code fences si los hay
            qa_raw = _re.sub(r"```(?:json)?\s*", "", qa_raw).replace("```", "").strip()
            # Intentar raw_decode desde el primer '{'
            qa_payload = None
            first_brace = qa_raw.find("{")
            if first_brace >= 0:
                try:
                    qa_payload, _ = json.JSONDecoder().raw_decode(qa_raw[first_brace:])
                except json.JSONDecodeError:
                    pass
            # Fallback: regex greedy
            if qa_payload is None:
                m = _re.search(r"\{.*\}", qa_raw, _re.DOTALL)
                if m:
                    try:
                        qa_payload = json.loads(m.group(0))
                    except json.JSONDecodeError:
                        pass
            if qa_payload is None:
                print(f"  [SKIP] {scenario.stack}/{ex_type}: JSON QA inválido", file=sys.stderr)
                continue
            example = {
                "system": type_to_system[ex_type],
                "messages": [
                    {"role": "user",      "content": _user_msg_for_qa(scenario)},
                    {"role": "assistant", "content": json.dumps(qa_payload, ensure_ascii=False)},
                ],
            }
        else:
            example = _parse_example(raw)
            if not example or not _validate_example(example):
                print(f"  [SKIP] {scenario.stack}/{ex_type}: JSON inválido", file=sys.stderr)
                continue
            example["system"] = type_to_system[ex_type]

        results.append(example)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def generate(args: argparse.Namespace) -> None:
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY no configurada", file=sys.stderr)
        sys.exit(1)

    target = args.count
    stack_filter = getattr(args, "stack", None)
    example_types = args.types.split(",") if args.types else ["analyze_fr", "generate_sdd", "qa_review"]

    # Filtrar escenarios por stack si se especificó
    pool = [s for s in SCENARIOS if not stack_filter or stack_filter in s.stack]
    if not pool:
        print(f"ERROR: no hay escenarios para stack='{stack_filter}'", file=sys.stderr)
        sys.exit(1)

    print(f"Generando ~{target} ejemplos sintéticos con {MODEL}")
    print(f"  Escenarios disponibles: {len(pool)}")
    print(f"  Tipos de ejemplo: {', '.join(example_types)}")
    if args.dry_run:
        print("  [DRY-RUN] No se llamará a la API — mostrando escenarios que se usarían")
        for i, s in enumerate(pool[:5], 1):
            print(f"    {i}. [{s.stack}] {s.fr[:70]}...")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    written = 0
    errors = 0

    async def bounded_generate(scenario: Scenario) -> list[dict]:
        async with semaphore:
            return await _generate_scenario_examples(client, scenario, example_types)

    with output_path.open("w", encoding="utf-8") as f:
        # Repetir el pool aleatoriamente hasta alcanzar el target
        random.seed(42)
        scenarios_to_run: list[Scenario] = []
        while len(scenarios_to_run) * len(example_types) < target:
            shuffled = pool[:]
            random.shuffle(shuffled)
            scenarios_to_run.extend(shuffled)

        # Limitar a los necesarios
        max_scenarios = (target // len(example_types)) + len(pool)
        scenarios_to_run = scenarios_to_run[:max_scenarios]

        # Procesar en batches del tamaño de CONCURRENCY
        batch_size = CONCURRENCY
        for i in range(0, len(scenarios_to_run), batch_size):
            if written >= target:
                break

            batch = scenarios_to_run[i:i + batch_size]
            tasks = [bounded_generate(s) for s in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for scenario, result in zip(batch, results):
                if isinstance(result, Exception):
                    errors += 1
                    print(f"  [ERROR] {scenario.stack}: {result}", file=sys.stderr)
                    continue
                for example in result:
                    if written >= target:
                        break
                    line = json.dumps(example, ensure_ascii=False)
                    f.write(line + "\n")
                    written += 1

            progress = min(written, target)
            print(f"  Progreso: {progress}/{target} ejemplos...", end="\r")

    print(f"\n  {written} ejemplos escritos en {output_path}")
    if errors:
        print(f"  {errors} errores de API")

    if written == 0:
        print("\nWARNING: no se generó ningún ejemplo. Verifica ANTHROPIC_API_KEY.")
        sys.exit(1)

    size_kb = output_path.stat().st_size / 1024
    print(f"\nDataset sintético listo: {output_path} ({size_kb:.1f} KB)")
    print("Siguiente paso: python validate_dataset.py --input", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera datos sintéticos para fine-tuning OVD")
    parser.add_argument("--output", default="data/synthetic.jsonl", help="Archivo JSONL de salida")
    parser.add_argument("--count", type=int, default=350, help="Número de ejemplos a generar (default: 350)")
    parser.add_argument(
        "--stack",
        choices=["oracle12c", "oracle19c", "postgresql", "python_fastapi", "java_spring", "typescript_next"],
        help="Filtrar por stack (default: todos)",
    )
    parser.add_argument(
        "--types",
        default="analyze_fr,generate_sdd,qa_review",
        help="Tipos de ejemplo a generar, separados por coma (default: todos)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Mostrar escenarios sin llamar a la API")
    args = parser.parse_args()
    asyncio.run(generate(args))
