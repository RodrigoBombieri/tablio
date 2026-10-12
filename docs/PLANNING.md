# Planificación

## Estado

V0 tiene un flujo local ejecutable y pruebas automatizadas con las dos planillas sectoriales. Las fases 1 a 3 están implementadas para el formato controlado; la fase 4 tiene verificación de servidor y datos, con revisión visual de navegador y mediciones de capacidad aún pendientes. El stack local y sus diferencias frente a la propuesta inicial constan en DECISIONS.md, R-004.

## Roadmap del producto

| Etapa | Objetivo |
|---|---|
| V0 — PoC | Excel controlado → parser → schema → CRUD dinámico |
| V1 — MVP | Importación real, configuración, aplicación dinámica, usuarios y permisos |
| V2 — Relaciones | Detección y configuración de relaciones entre entidades |
| V3 — Inteligencia de negocio | Dashboards, indicadores y reportes |
| V4 — Automatizaciones | Alertas, vencimientos, notificaciones y workflows |
| V5 — AI Assistant | Interpretación semántica y configuración mediante lenguaje natural |
| V6 — Ecosistema | Templates sectoriales, módulos e integraciones |

## Fase 0: cerrar el diseño

- [x] Leer el brief y distinguir PoC de MVP.
- [x] Formular una propuesta de alcance, arquitectura y stack.
- [x] Crear la documentación inicial del repositorio.
- [x] Adoptar o ajustar las propuestas como base de trabajo y registrar el estado en DECISIONS.md.
- [x] Seleccionar el dataset ficticio de referencia: Minimercado, definido en FIXTURES.md (reemplaza Clientes por pedido del usuario).
- [x] Definir la interpretación esperada de cada columna.
- [x] Precisar conversiones, filtros admitidos y mensajes de error.
- [x] Definir una segunda planilla simple para verificar generalidad: Corralón de materiales, definida en FIXTURES.md.

Los datasets vigentes y sus XLSX se documentan en [FIXTURES.md](FIXTURES.md). Las reglas generales continúan en POC_SPEC.md. Ambos archivos ya pasaron por el flujo de Tablio en pruebas HTTP; el minimercado también se importó desde la interfaz.

## Fase 1: contrato y análisis

- [x] Definir el Application Schema versionado y sus validaciones en DATA_MODEL.md.
- [x] Generar minimercado.xlsx y corralon_materiales.xlsx con 30 registros ficticios cada uno.
- [x] Verificar estructura, tipos y presentación de ambos XLSX; evidencia en FIXTURES.md.
- [x] Generar variantes inválidas durante las pruebas y cubrir fecha, importe, entero y campo obligatorio; ampliar casos de archivos reales en V1.
- [x] Inicializar el servidor Python local, SQLite y `unittest` sin dependencias externas.
- [x] Implementar el contrato del schema y sus validadores para V0.
- [x] Leer hojas, encabezados, valores y formatos de XLSX controlados.
- [x] Detectar fórmulas, celdas combinadas y aplicar límites básicos de tamaño y forma.
- [x] Inferir tipos con reglas determinísticas.
- [x] Producir muestras y errores de validación por fila y columna; ampliar códigos específicos y advertencias semánticas en una iteración posterior.

Salida esperada: propuesta de estructura verificable, sin importar registros definitivos.

## Fase 2: revisión e importación

- [x] Crear el flujo de subida, selección de hoja y revisión.
- [x] Permitir corregir la estructura e ignorar columnas.
- [x] Validar todos los registros con el schema confirmado.
- [x] Importar de forma transaccional.
- [x] Evitar duplicación al reintentar la misma confirmación.
- [x] Gestionar archivos temporales con vencimiento de 24 horas.

Salida esperada: entidad y registros persistidos sin importaciones parciales.

## Fase 3: aplicación dinámica

- [x] Construir listados y formularios desde metadatos.
- [x] Implementar CRUD con validación en servidor.
- [x] Incorporar paginación, búsqueda y filtros simples según tipo.
- [x] Crear una interfaz responsive para consulta y edición; verificar su uso visual en teléfono más adelante.
- [x] Exportar los datos actuales a XLSX.
- [x] Admitir fórmulas aritméticas de la misma fila, recalcular campos derivados y exportarlas a XLSX.
- [x] Mostrar fórmulas inválidas por fila y columna y permitir corregirlas en la revisión previa.

## Fase 4: verificar el PoC

- [x] Completar el flujo HTTP con la planilla de referencia de minimercado.
- [x] Repetirlo con la planilla del corralón sin agregar lógica específica por campo.
- [x] Verificar errores de fecha, importe, entero, identificadores y campos vacíos con pruebas específicas.
- [x] Comprobar atomicidad y reintentos de importación.
- [x] Verificar CRUD, reapertura de SQLite y exportación; falta prueba explícita de reinicio del proceso.
- [x] Revisar visualmente la carga, el listado responsive y el formulario en navegador. Falta una pasada específica con viewport de escritorio amplio.
- [x] Medir análisis, importación y consulta con 5.000 filas y 30 columnas sintéticas; ver VALIDATION.md.
- [x] Documentar resultados, limitaciones y ajustes necesarios en VALIDATION.md.

## Criterios de aceptación de V0

1. El flujo completo funciona sin manipular manualmente la base de datos.
2. Los errores se localizan por fila y columna; no se descartan datos silenciosamente.
3. Una importación fallida no publica registros parciales.
4. Los formularios y listados se derivan del schema.
5. Se pueden consultar y modificar registros desde escritorio y teléfono.
6. Los datos persisten y la exportación preserva sus valores y tipos admitidos.
7. Una segunda planilla compatible funciona sin pantallas específicas.

`python -m unittest discover -s tests -v` verifica ambos XLSX, importación, reintentos, paginación, filtro, CRUD, exportación, errores de conversión, fórmulas simples y corrección de una fórmula inválida. La interfaz previa se revisó en el navegador local con el libro del minimercado; la nueva lista de corrección aún no tiene revisión visual específica.

## Preparación del MVP

Antes de ampliar el producto, estudiar aproximadamente 5 a 10 planillas reales, como propone el brief. Observar fórmulas, relaciones implícitas, colores con significado, celdas combinadas, identificadores y tareas cotidianas.

Antes de un piloto con datos reales: resolver autenticación, autorización, aislamiento entre organizaciones, almacenamiento privado, retención, backups y despliegue con HTTPS. No tratar el PoC local como un servicio multi-tenant validado.

## Registro de avances

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-04 | Documentación y estructura inicial para VS Code | docs, src, README y configuración del editor |
| 2026-09-04 | Base de diseño adoptada; datasets Clientes y Productos definidos | DECISIONS.md, entrada R-002; POC_SPEC.md |
| 2026-09-04 | Conversiones, inferencia, filtros, errores y temporales especificados | POC_SPEC.md |
| 2026-09-04 | Contrato documental del Application Schema v1 | DATA_MODEL.md |
| 2026-09-04 | Dos XLSX sectoriales generados y verificados, 30 registros cada uno | FIXTURES.md y archivos enlazados; DECISIONS.md, R-003 |
| 2026-10-12 | PoC local implementado: servidor, parser, schema, SQLite, interfaz, CRUD y exportación | `app/`, `web/`, README.md; DECISIONS.md, R-004 |
| 2026-10-12 | Pruebas HTTP y de datos aprobadas con ambas planillas | `tests/test_app.py`, 5 pruebas completadas |
| 2026-10-12 | Carga y confirmación de ambas planillas; listado y formulario revisados visualmente | Navegador local con dos módulos de 30 registros |
| 2026-10-12 | Medición sintética del límite 5.000 × 30 y registro de límites | `tests/benchmark_v0.py`, VALIDATION.md |
| 2026-10-12 | Fórmulas simples y corrección durante la revisión de importación | `app/formulas.py`, `app/core.py`, `web/app.js`, pruebas y libro real del usuario; DECISIONS.md, R-005 |

Actualizar las casillas y agregar evidencia en esta sección cada vez que se complete una tarea. Registrar cambios de alcance o arquitectura también en DECISIONS.md. No marcar implementación o pruebas como completadas por haberlas documentado.
