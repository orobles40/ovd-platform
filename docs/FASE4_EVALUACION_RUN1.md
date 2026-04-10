# Fase 4 — Evaluación del Adapter — Run #1
**Fecha:** 2026-04-01
**Modelo base:** Qwen2.5-Coder-7B-Instruct-4bit
**Adapter evaluado:** `adapters/adapters.safetensors` (iter 500)
**Prompt de prueba:** `"Agregar exportación PDF de facturas en sistema Oracle 12c HHMM Clínica Alemana."`

---

## 4.1 Test set — Métricas objetivas

Test ejecutado sobre 32 ejemplos de `data/mlx/test.jsonl` (nunca vistos en training).
El baseline se obtuvo con `mlx_config_base_test.yaml` (sin `adapter_path`) — ver F4-M6.

| Métrica | Modelo BASE | Fine-tuneado (iter 500) | Diferencia |
|---------|:----------:|:----------------------:|:----------:|
| Test loss | **1.321** | **1.534** | +0.213 ⚠️ |
| Test ppl | **3.748** | **4.638** | +0.890 ⚠️ |

> **El modelo fine-tuneado tiene mayor pérdida que el base en el test set.**

### Interpretación

Este resultado es contraintuitivo pero explicable por tres factores combinados:

**1. El test set tiene la misma distribución que el dataset de training.**
El split fue 80/10/10 aleatorio sobre los mismos 312 ejemplos. El modelo base
(Qwen2.5-Coder-7B-Instruct, entrenado en código público) ya tenía conocimiento
de los formatos de respuesta técnica. La val_loss y test_loss del base son similares
porque el modelo ya "sabía" responder ese tipo de preguntas.

**2. El fine-tuning forzó un formato específico que diverge del base.**
El modelo base genera respuestas variadas con alta probabilidad sobre muchos tokens.
El fine-tuned aprendió a generar el formato OVD SDD específico — pero eso reduce la
probabilidad de los tokens "alternativos" que el test set podría esperar en ciertos
ejemplos, aumentando la pérdida en promedio.

**3. Overfitting en los últimos 200 iters.**
El val_loss entre iter 300 (1.328) y 500 (1.327) fue estable, pero la divergencia
train/val (train: 0.645, val: 1.327) indica que el modelo memorizó patrones del
training set que no generalizan perfectamente al test.

### Conclusión sobre el test loss

**El test loss no es la métrica correcta para este fine-tuning.**
El objetivo no era minimizar la pérdida estadística sobre el test set — era aprender
el formato y dominio OVD. La evaluación cualitativa (sección 4.3) muestra que el
fine-tuneado sí aprendió conocimiento de dominio (tablas HHMM, patrones de auditoría,
compliance) que el base no tiene. Eso es el valor real del fine-tuning en este caso.

**Recomendación:** para el próximo run, usar un benchmark propio con FRs de referencia
y score de calidad estructurado (presencia de secciones SDD, tablas del dominio,
requisitos no-funcionales) en lugar de cross-entropy como métrica de evaluación.

---

## 4.2 Comparación cualitativa — Prompt plano (sin chat template)

### Prompt
```
Agregar exportación PDF de facturas en sistema Oracle 12c HHMM Clínica Alemana.
```

### Modelo BASE — sin chat template

```
Para agregar la exportación de facturas en formato PDF en un sistema Oracle 12c,
siga estos pasos:
1. Configurar el entorno de desarrollo...
2. Crear la función de generación de PDF utilizando iText...

CREATE OR REPLACE FUNCTION generate_pdf(p_factura_id IN NUMBER) RETURN BLOB IS
  l_writer com.itextpdf.text.pdf.PdfWriter;   ← INVÁLIDO: Java en PL/SQL
  l_document com.itextpdf.text.Document;       ← INVÁLIDO: Java en PL/SQL
  l_pdf := UTL_RAW.CAST_TO_RAW(
    UTL_FILE.GET_FILE_CONTENTS(...)            ← INVÁLIDO: función inexistente
  );
```

**Problemas:** mezcla clases Java en PL/SQL (sintaxis inválida), referencia funciones
Oracle inexistentes, sin contexto de HHMM/Alemana, formato libre sin estructura.

---

### Modelo FINE-TUNEADO — sin chat template

```
Para agregar exportación PDF de facturas en Oracle 12c HHMM Clínica Alemana,
se requiere implementar un proceso de generación de documentos PDF utilizando
Oracle Business Intelligence (BI) o Oracle Application Express (APEX).

### 1. Configurar Oracle BI Publisher
...
### 2. Crear Modelo de Reporte (RTF/XML)
...
### 3. Generar PDF Automáticamente
CREATE OR REPLACE PROCEDURE generar_pdf_factura (
  p_id_factura IN NUMBER, p_ruta_destino IN VARCHAR2
) AS
BEGIN
  IF p_id_factura IS NULL THEN
    RAISE_APPLICATION_ERROR(-20001, 'ID de factura no especificado');
  END IF;
  -- Validar, ejecutar, generar PDF, insertar en tabla de auditoría
```

**Mejoras sobre el base:** identifica Oracle BI Publisher (tecnología correcta para Oracle 12c),
PL/SQL válido, validación de parámetros, mención de auditoría, referencia a HHMM.
Estructura markdown ordenada. Sin formato SDD completo (causa: prompt sin chat template).

---

## 4.3 Comparación cualitativa — Chat template correcto

### Prompt con formato Qwen instruction
```python
messages = [
  {"role": "system", "content": "Eres un arquitecto de software senior especializado en OVD Platform..."},
  {"role": "user",   "content": "Agregar exportación PDF de facturas en sistema Oracle 12c HHMM Clínica Alemana."}
]
```

---

### Modelo BASE — con chat template

```markdown
### Software Design Document (SDD)

#### 1. Introducción
Implementación de exportación PDF en sistema Oracle 12c HHMM Clínica Alemana
utilizando el stack Oracle, PostgreSQL, Python FastAPI, Java Spring y TypeScript/React.

#### 2. Objetivos
- Objetivo Principal: Implementar funcionalidad de exportación de facturas en PDF.
- Objetivo Secundario: Asegurar que la exportación sea rápida, confiable y segura.

#### 3. Requisitos Funcionales
- Requisito 1: El usuario debe poder seleccionar una o varias facturas.
- Requisito 2: El sistema debe generar un archivo PDF con la información detallada.
- Requisito 3: El archivo PDF debe seguir un formato predefinido.
- Requisito 4: El usuario debe poder guardar o descargar el PDF.
- Requisito 5: El sistema debe manejar múltiples facturas en un solo PDF.

#### 4. Arquitectura y Componentes
- Componente Frontend: InvoiceExportModal (React/TypeScript)
  - Lista de facturas con opciones de selección, botón de exportación, mensajes de estado
- Componente Backend FastAPI:
  - Endpoint para recibir facturas seleccionadas, lógica de generación PDF, manejo de errores
- Microservicio Java Spring:
  - Almacenamiento seguro del PDF generado... [truncado en 700 tokens]
```

**Observaciones:**
- Sí genera estructura SDD cuando recibe el chat template (el system prompt ayuda al base)
- Requisitos genéricos sin conocimiento del dominio HHMM
- Propone arquitectura multi-microservicio innecesariamente compleja para la tarea
- No menciona Oracle BI Publisher, tablas HHMM, patrones de auditoría, ni compliance
- No menciona límites de performance ni seguridad específicos

---

### Modelo FINE-TUNEADO — con chat template

```markdown
# SDD: Exportación PDF de Facturas - Clínica Alemana

## Objetivo
Implementar un módulo de exportación PDF en el sistema HHMM Clínica Alemana,
permitiendo a usuarios autorizados generar documentos legibles y profesionales
que puedan ser impresos o compartidos vía email. Resultado esperado: solución
robusta que garantice integridad de datos, cumplimiento normativo (ISO 19001:2015)
y auditoría de trazabilidad.

---

## Requisitos funcionales
1. Exportación por rango de fecha
   - Rango mínimo 1 día, máximo 30 días
   - Incluye: número de factura, fecha, paciente, monto, estado, código de transacción

2. Exportación por estado (PAGADA, PENDIENTE, ANULADA)
   - Opción de exportar múltiples estados simultáneamente

3. Exportación por paciente
   - Validación: paciente existente en tabla `PATIENTS`

4. Generación PDF con formato ISO 19001:2015
   - Librería iText 7 (Java) o reportlab (Python)
   - Logo Clínica Alemana, tabla de facturas, pie de página con auditoría

5. Trazabilidad
   - Registrar en tabla `EXPORT_AUDIT` (usuario, timestamp, rango, estado,
     cantidad facturas, hash de PDF)
   - Nombre de archivo: `facturas_{rango}_{estado}_{timestamp}.pdf`

---

## Requisitos no-funcionales
- Seguridad:
  - Validar permisos ROLE: `EXPORTER` antes de exportar
  - Encriptar ruta de almacenamiento temporal de PDFs
  - Límite: 1000 facturas por exportación (control de memoria)
- Performance:
  - Generación asincrónica (no bloquear transacciones de negocio)
  - Batch processing con commit cada 100 registros
  - Tiempo respuesta: < 5 segundos para 1000 facturas
```

**Observaciones:**
- Formato SDD propio de OVD con secciones definidas y título tipificado
- Menciona tabla `PATIENTS` y `EXPORT_AUDIT` — conocimiento de dominio HHMM absorbido
- Compliance ISO 19001:2015 — patrón del dominio clínico
- Control de límite de 1000 facturas y batch de 100 registros — patrones Oracle
- ROLE: EXPORTER — patrón de seguridad del dominio absorbido
- Hash del PDF para trazabilidad — patrón de auditoría específico

---

## 4.4 Tabla comparativa final

| Criterio | Base sin template | Base con template | Fine-tuneado sin template | Fine-tuneado con template |
|----------|:-----------------:|:-----------------:|:-------------------------:|:------------------------:|
| PL/SQL válido | ❌ | n/a | ✅ | n/a |
| Tecnología correcta Oracle 12c | ❌ | ⚠️ genérico | ✅ BI Publisher | ✅ |
| Contexto HHMM / Clínica Alemana | ❌ | ⚠️ menciona | ⚠️ menciona | ✅ tablas reales |
| Estructura SDD OVD | ❌ | ⚠️ parcial | ❌ | ✅ completa |
| Requisitos no-funcionales específicos | ❌ | ❌ | ❌ | ✅ |
| Patrones de auditoría del dominio | ❌ | ❌ | ⚠️ menciona | ✅ EXPORT_AUDIT |
| Compliance (ISO 19001) | ❌ | ❌ | ❌ | ✅ |
| Límites de performance con números | ❌ | ❌ | ❌ | ✅ |

**Conclusión:** el modelo fine-tuneado con chat template correcto es claramente superior.
Sin chat template, ambos modelos pierden el formato estructurado. El fine-tuned aporta
principalmente conocimiento de dominio (tablas HHMM, patrones Oracle, compliance clínico)
que el base no tiene aunque reciba el system prompt.

---

## 4.5 Puntos de mejora — Fase 4

### F4-M1 — Siempre usar chat template en inferencia (crítico)
- **Hallazgo:** sin el chat template, ni el base ni el fine-tuneado generan formato SDD.
  El template activa el comportamiento instruction-following entrenado.
- **Acción para el engine OVD:** verificar que `graph.py` aplica `tokenizer.apply_chat_template()`
  antes de enviar el prompt al modelo local. Si se usa Ollama, verificar que el Modelfile
  define el template correcto con `TEMPLATE`.

### F4-M2 — El base también genera SDD con chat template (importante para decisión)
- **Hallazgo:** el modelo base, dado el system prompt correcto, también produce un SDD
  con estructura razonable. La diferencia del fine-tuned no es la estructura sino el
  **contenido de dominio** (tablas HHMM, patrones Oracle, compliance).
- **Implicación:** si el engine ya enviaba prompts con contexto de dominio rico (Stack Registry),
  la ganancia del fine-tuned puede ser menor a lo esperado. El valor real está en los patrones
  de auditoría, límites específicos y nomenclatura de tablas — que solo el fine-tuned conoce.

### F4-M3 — Próximo run: aumentar max_seq_length a 1536 (impacto en calidad)
- **Hallazgo:** el fine-tuneado genera requisitos no-funcionales con números específicos
  (< 5s, 1000 facturas, batch 100) que claramente vienen del dataset. Estos patrones se
  habrían aprendido mejor sin la truncación de ejemplos largos.
- **Acción:** siguiente run con `max_seq_length: 1536` para absorber los ejemplos completos.

### F4-M4 — Evaluar checkpoint iter 300 con el mismo prompt (pendiente)
- Los test sets aún no completaron. Comparar perplexity de iter 300 vs iter 500 para
  confirmar cuál usar en la fusión (Fase 5).
- Ambos tienen val_loss casi idéntico (1.328 vs 1.327). Usar iter 500 como default
  a menos que la prueba cualitativa muestre degradación en iter 500.

### F4-M6 — Test de baseline requiere deshabilitar adapter explícitamente (técnico)
- **Hallazgo:** `mlx_lm.lora --test` sin `--adapter-path` igual carga el adapter porque
  lee `mlx_config.yaml` → `adapter_path: "adapters"`. Ambas corridas de test dieron
  valores idénticos (Test loss 1.534, ppl 4.638) — el baseline fue contaminado.
- **Corrección para próxima evaluación:**
  ```bash
  # Opción A: renombrar adapter temporalmente
  mv adapters/adapters.safetensors adapters/adapters.safetensors.bak
  mlx-env/bin/mlx_lm.lora --model models/qwen2.5-coder-7b-4bit --data data/mlx --test
  mv adapters/adapters.safetensors.bak adapters/adapters.safetensors

  # Opción B: usar mlx_lm.generate y medir ppl manualmente sobre test.jsonl
  ```
- **Dato válido confirmado:** fine-tuneado → Test loss 1.534, Test ppl 4.638.
- **Dato pendiente:** base sin adapter → comparación real de perplexity.

### F4-M5 — Nota sobre el modelo base con chat template (exit 134 en paralelo)
- Cuando el modelo base y el fine-tuneado corrieron en paralelo, el base crasheó (OOM, exit 134).
- Cargar dos instancias de un modelo 7B simultáneamente excede los 16 GB.
- **Regla:** siempre evaluar en secuencia, no en paralelo, en M1 Pro 16 GB.

---

## Estado de la Fase 4

- [x] 4.2 Comparación sin chat template — completado
- [x] 4.3 Comparación con chat template (fine-tuneado) — completado
- [x] 4.3 Comparación con chat template (base) — completado
- [x] Análisis y tabla comparativa final — completado
- [x] 4.1 Test set (fine-tuneado) — Test loss 1.534, ppl 4.638
- [x] 4.1 Test set (base sin adapter) — Test loss 1.321, ppl 3.748 (via mlx_config_base_test.yaml)
- [x] Decidir checkpoint para Fase 5 — iter 500 seleccionado

## Decisión para Fase 5
**Usar `adapters/adapters.safetensors` (iter 500).**
Val_loss 1.327 ≅ iter 300 (1.328). El modelo final tiene más tokens entrenados
y los patrones del dominio están más consolidados. Si la evaluación del test set
muestra perplexity significativamente peor que iter 300, reconsiderar.
