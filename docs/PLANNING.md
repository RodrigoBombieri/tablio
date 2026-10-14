# Planificación

## Estado

V0 tiene un flujo local ejecutable y pruebas automatizadas con las dos planillas sectoriales. Las fases 1 a 4 están verificadas en el alcance documentado. La base de acceso, organizaciones, backups y configuración HTTPS también está implementada; faltan dominio y servidor para publicar y validar la operación real. El stack local y sus diferencias frente a la propuesta inicial constan en DECISIONS.md, R-004 y R-006.

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

`python -m unittest discover -s tests -v` verifica ambos XLSX, importación, reintentos, paginación, filtro, CRUD, exportación, errores de conversión, fórmulas, correcciones, reimportación, configuración y accesos. La revisión visual anterior corresponde al flujo V0; las pantallas nuevas todavía necesitan una evaluación de uso completa.

## Preparación del MVP

### Base de acceso y operación

- [x] Inicio de sesión, sesiones, cambio de contraseña y protección CSRF.
- [x] Usuarios, roles y permisos comprobados en el servidor.
- [x] Aislamiento de módulos, registros e importaciones por organización; migración de datos V0.
- [x] Almacenamiento privado de la base y los XLSX temporales.
- [x] Copias SQLite automáticas, verificación de integridad y comando de restauración.
- [x] Configuración de Docker Compose y Caddy para HTTPS con dominio real.
- [x] Invitaciones privadas de un solo uso, restablecimiento por enlace, actividad de cambios y monitoreo básico de la última copia.
- [ ] Publicar en un servidor con dominio y comprobar certificado y redirección HTTPS.
- [ ] Configurar copia cifrada fuera del servidor, monitoreo y prueba periódica de restauración.
- [ ] Revisar la seguridad operativa y la interfaz completa antes de un piloto con datos reales.

Antes de ampliar el producto, estudiar aproximadamente 5 a 10 planillas reales, como propone el brief. Observar fórmulas, relaciones implícitas, colores con significado, celdas combinadas, identificadores y tareas cotidianas.

La base técnica de acceso y separación entre organizaciones está implementada y tiene pruebas de API. La operación real todavía depende de un servidor y dominio, copias externas y una revisión de seguridad; ver SECURITY_DEPLOYMENT.md. No tratar las pruebas locales como validación de un servicio público.

## Mejora de importación y trabajo diario

- [x] Probar la primera pestaña de una planilla real de habilitaciones sin copiar sus datos personales al repositorio.
- [x] Mostrar columnas sin título desmarcadas, diferenciar encabezados repetidos y avisar cuando una fórmula se conserva como último valor guardado en Excel.
- [x] Agrupar fórmulas pendientes por fila y permitir excluir cada fila afectada, con opción de volver a incluirla antes de guardar.
- [x] Permitir deshacer una importación inicial mientras el módulo no tenga cambios posteriores.
- [x] Ofrecer plantillas de habilitaciones, minimercado y corralón; permitir agregar campos sugeridos para inventario.
- [x] Mostrar un resumen de excepciones y sugerencias de reposición explicadas cuando existan los campos necesarios.
- [x] Registrar ventas y entradas de mercadería en módulos con stock numérico, actualizar existencias y usar ventas de los últimos 30 días en la reposición.
- [ ] Validar estos flujos visualmente con usuarios de distintas edades y con planillas de cada rubro.

El archivo real de habilitaciones no contiene stock ni ventas. Las sugerencias de compra se activan solo en módulos con «Stock actual» y «Stock mínimo»; las ventas registradas durante los últimos 30 días y «Días de entrega» mejoran el cálculo. También puede usarse un campo manual «Ventas 30 días» mientras no haya movimientos registrados. Son propuestas para revisión humana, no pedidos automáticos. Las fórmulas de Excel no compatibles con valor guardado se importan como valor fijo y se advierte que no se recalcularán.

### Próximas microfuncionalidades propuestas (aún no implementadas)

1. En la revisión del Excel, contraer inicialmente las columnas sin título y mostrar siempre cuántas columnas y filas quedarán fuera.
2. Antes de guardar, mostrar un resumen final fácil de leer: registros a crear, filas excluidas, columnas usadas y fórmula que quedará como valor fijo.
3. En cada error de validación, ofrecer «Ir a la fila» y mantener visible la acción de excluirla sin perder las correcciones escritas.
4. Recordar la selección de columnas y tipos para una futura importación del mismo formato, con revisión visible antes de aplicar esa preferencia.
5. En el módulo, conservar la búsqueda y filtros al volver de editar un registro; facilitar deshacer la última edición accidental.

Revisar estas prioridades con usuarios adultos antes de implementarlas; no son funcionalidades completadas.

## Registro de avances

### Mejoras posteriores al PoC

- [x] Reimportar un XLSX sobre un módulo existente mediante una a tres columnas identificadoras, con vista previa de altas, cambios, filas sin cambios y conflictos por clave duplicada. Proponer una combinación única cuando la elegida se repite. No se borran filas ausentes.
- [x] Aplicar la reimportación en una transacción, detectar cambios entre vista previa y confirmación, admitir reintentos sin duplicar y deshacer una actualización si sus registros no se editaron después.
- [x] Comprobar todas las filas antes de la importación inicial y corregir valores y fórmulas por fila y campo desde la revisión.
- [x] Configurar nombres, obligatoriedad y opciones de campos existentes; agregar campos opcionales sin perder datos; guardar vistas personales con filtros, orden y columnas visibles.
- [x] Ejecutar búsqueda, filtro, orden y paginación en SQLite, evitando cargar todos los registros para cada página.
- [x] Registrar actividad de cambios, crear invitaciones de un solo uso y permitir restablecer contraseñas mediante enlaces de una hora; comprobar antigüedad e integridad del último backup.
- [ ] Validar la experiencia completa con personas usuarias de distintas edades y planillas reales; ajustar textos, tamaño y navegación según observaciones.
- [ ] Configurar copia cifrada fuera del servidor y ensayar la recuperación desde ella.
- [ ] Publicar con dominio real, verificar HTTPS y realizar revisión de seguridad operativa.

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
| 2026-10-12 | Traslado del trabajo al repositorio Git indicado por el usuario | `C:\Users\Rodrigo\Escritorio\Repositorio Git\tablio`, rama `main`, remoto `origin` |
| 2026-10-12 | Acceso, roles, organizaciones, datos privados, backups y configuración HTTPS | `app/security.py`, `app/store.py`, `app/backup.py`, `compose.yaml`, `Caddyfile`, SECURITY_DEPLOYMENT.md; 12 pruebas, imagen y servicios Docker verificados; DECISIONS.md, R-006 |
| 2026-10-12 | Copia verificada y migración de la base existente del nuevo repositorio | Backup privado en `backups/`, dos módulos preservados en `Legado V0`; el propietario se creó y comprobó después |
| 2026-10-13 | Reimportación incremental con comparación, clave única, historial y deshacer condicionado | `app/reimport.py`, `app/store.py`, `app/server.py`, `web/app.js`, prueba HTTP |
| 2026-10-13 | Revisión de filas, corrección de datos y fórmulas antes de guardar | `app/server.py`, `web/app.js`, prueba de corrección |
| 2026-10-13 | Configuración de campos, vistas personales, búsqueda y paginación SQL | `app/store.py`, `web/index.html`, `web/app.js`, prueba HTTP |
| 2026-10-13 | Actividad, invitaciones, recuperación y estado de backups; controles de lectura ampliados | `app/store.py`, `app/backup.py`, `compose.yaml`, pruebas de permisos y recuperación |
| 2026-10-13 | Primera hoja real de habilitaciones, exclusión por columna, plantillas, avisos, movimientos de stock y reposición explicada | `app/xlsx_io.py`, `app/core.py`, `app/insights.py`, `app/store.py`, `web/`, validación sin incluir datos privados |
| 2026-10-14 | Exclusión individual y reversible de filas con fórmulas conflictivas; comprobación de importación con celdas combinadas y ruta de guardado | `app/server.py`, `web/app.js`, `tests/test_app.py`; prueba HTTP con filas excluidas y libro real: 1.922 registros guardados en base temporal; inicio verificable desde VS Code |
| 2026-10-14 | Diagnóstico en la app activa: dos servidores Windows compartían el puerto 8000 y respondían con versiones distintas; se detuvo el antiguo y se impidió un segundo enlace al mismo puerto | `app/server.py`, `tests/test_app.py`; importación y validación del libro real comprobadas en la interfaz local, sin confirmar un módulo nuevo |
| 2026-10-14 | Actualización desde Excel con identificación compuesta genérica y sugerencia de la menor combinación única | `app/reimport.py`, `app/server.py`, `web/app.js`, pruebas HTTP y de tres campos; el libro real se revisó sin modificar el módulo |

Actualizar las casillas y agregar evidencia en esta sección cada vez que se complete una tarea. Registrar cambios de alcance o arquitectura también en DECISIONS.md. No marcar implementación o pruebas como completadas por haberlas documentado.
