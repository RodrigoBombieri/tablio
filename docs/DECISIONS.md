# Registro de decisiones

Fecha de registro inicial: 2026-09-04.

## Estados

- **Establecida:** proviene explícitamente del Project Brief.
- **Adoptada como base de trabajo:** elección operativa de diseño para avanzar, revisable; no implica validación técnica ejecutada ni aprobación individual explícita del usuario.
- **Propuesta:** recomendación de diseño pendiente de confirmación.
- **Pendiente:** todavía no hay una elección concreta.
- **Reemplazada:** decisión conservada como historial, con referencia a su sustituta.

La solicitud de crear documentación no se interpreta como aprobación automática de las propuestas técnicas.

## Definiciones establecidas por el brief

| ID | Decisión | Justificación / fuente |
|---|---|---|
| D-001 | Separar PoC de MVP | V0 comprueba el núcleo con un Excel controlado; sección 19 |
| D-002 | Explorar preferentemente un motor basado en metadatos | Evitar desarrollar y desplegar un proyecto por planilla; sección 7 |
| D-003 | Confirmación humana de la interpretación | La inferencia no es infalible; secciones 8 y 9 |
| D-004 | IA opcional y ejecución determinística | La IA no es requisito para validar el concepto; sección 18 |
| D-005 | Mantener importación y exportación como capacidades del producto | Los datos pertenecen al cliente; sección 12 |
| D-006 | Priorizar simplicidad y experiencia móvil | Reducir la barrera de adopción; secciones 11 y 17 |
| D-007 | Definir el diseño antes de implementar | Próximo objetivo del brief; sección 26 |

## Propuestas para V0

Actualización 2026-09-04: P-001 a P-009 se adoptan como base de trabajo mediante R-002. El texto original se conserva como historial de la propuesta; los ajustes detallados vigentes están en POC_SPEC.md y DATA_MODEL.md.

### P-001 — Monolito modular con TypeScript

**Estado:** propuesta.

Next.js + React en Node.js, PostgreSQL, ExcelJS y Zod. Mantener análisis y validación separados de la interfaz.

**Motivo:** un único lenguaje y despliegue para verificar el flujo vertical con pocas piezas.

**Alternativa:** backend Python si los casos reales demandan un procesamiento tabular mucho más complejo. No hay evidencia suficiente para introducir esa separación en V0.

### P-002 — Metadatos relacionales y registros JSONB

**Estado:** propuesta.

**Motivo:** representar columnas variables sin crear tablas y migraciones por cada entidad importada.

**Alternativas:** tablas SQL por entidad, con mayor carga de DDL dinámico; modelo atributo–valor, con consultas más complejas.

**Consecuencia:** validación de campos dinámicos en servidor y consultas conscientes de los tipos. Revisar al diseñar relaciones y reportes.

### P-003 — Entrada deliberadamente controlada

**Estado:** propuesta.

Una hoja seleccionada por importación, tabla rectangular y encabezados en primera fila. Límites tentativos: 5 MB, 5.000 registros y 30 columnas. Bloquear fórmulas y celdas combinadas dentro de la tabla seleccionada.

**Motivo:** comprobar el núcleo antes de resolver la heterogeneidad de archivos reales. Los límites requieren medición y no garantizan capacidad ya comprobada.

### P-004 — Exportación incluida en el PoC

**Estado:** propuesta.

**Motivo:** verificar temprano la recuperación de los datos. Extiende el flujo mínimo de V0 del brief, sin incorporar reconstrucción de formato ni fórmulas.

### P-005 — PoC local de un operador

**Estado:** propuesta.

Una organización preconfigurada, sin login, acceso local y datos ficticios o anonimizados. Modelo con propiedad organizacional explícita.

**Motivo:** concentrar V0 en la transformación Excel → aplicación. Autenticación, autorización y aislamiento probado son requisitos previos a un piloto con clientes.

### P-006 — Estructura congelada tras importar

**Estado:** propuesta.

**Motivo:** evitar diseñar migraciones de datos dinámicos antes de probar el primer flujo. Los identificadores de campos y la versión del schema quedan explícitos desde el principio.

### P-007 — Importación atómica e idempotente

**Estado:** propuesta.

Validar todos los registros antes de publicar. Reintentar la misma confirmación no duplica datos.

**Motivo:** evitar importaciones parciales y duplicaciones accidentales. No incluye reconciliación entre diferentes archivos.

### P-008 — Segunda planilla como prueba de generalidad

**Estado:** propuesta.

**Motivo:** demostrar que formularios y listados dependen del schema, sin lógica específica para las columnas de la primera planilla.

### P-009 — Archivos temporales

**Estado:** propuesta.

Almacenamiento fuera de rutas públicas y eliminación al terminar o vencer la importación.

**Motivo:** el funcionamiento posterior debe depender del schema y los registros, sin requerir conservar el XLSX original. Plazo de vencimiento pendiente.

## Pendientes antes de implementar

- Generar variantes inválidas y casos unitarios de tipos no cubiertos; los dos XLSX válidos sectoriales ya existen (R-003).
- Versiones de dependencias, cliente SQL, migraciones y herramientas de pruebas.

El alcance, stack base, datasets, conversiones, contrato de schema, filtros y política de temporales tienen definición de trabajo en R-002, POC_SPEC.md y DATA_MODEL.md. Su comportamiento aún debe implementarse y verificarse.

## Pendientes antes del MVP o piloto

- Autenticación, roles, membresías y aislamiento multi-tenant.
- Hosting, almacenamiento privado, retención y backups.
- Manejo de casos reales fuera del formato controlado.
- Estrategia de evolución del schema y datos existentes.
- Modelo comercial y acompañamiento de implementación.

## Decisiones de organización del repositorio

### R-001 — Estructura inicial para Visual Studio Code

**Fecha:** 2026-09-04. **Estado:** establecida por solicitud del usuario.

Usar Visual Studio Code como editor. Crear una estructura mínima con documentación en docs, espacio de código en src, README raíz y convenciones básicas de edición. Agregar carpetas y archivos cuando el avance del proyecto los requiera.

Esta estructura no confirma el stack propuesto ni inicia la implementación. No se instalaron dependencias ni se configuraron comandos de ejecución. Para un único proyecto basta con abrir su carpeta; no se necesita un archivo de workspace adicional.

## Mantenimiento del registro

### R-002 — Avanzar con la base de diseño y registrar cada avance

**Fecha:** 2026-09-04. **Estado:** base de trabajo adoptada por el asistente para ejecutar la solicitud de avanzar según la planificación.

Se toman P-001 a P-009 como punto de partida, sin atribuir al usuario una ratificación individual de cada tecnología. Se seleccionan datasets ficticios de Clientes y Productos para no depender de archivos de terceros en V0. POC_SPEC.md fija interpretación, conversiones, filtros, errores y casos; DATA_MODEL.md fija el contrato v1.

Ajustes: límites expresados como 5 MiB comprimidos y 50 MiB descomprimidos; importaciones temporales vencen a las 24 horas. Precisión decimal limitada a 15 dígitos significativos y escala de 0 a 6, con importes ARS de escala 2. Estos límites requieren verificación, no se presentan como capacidad demostrada.

La fase 0 se completa a nivel documental. Generar XLSX, implementar validadores y ejecutar pruebas quedan como tareas explícitas abiertas. El pedido del usuario de mantener la planificación actualizada se aplica mediante casillas y un registro de avances con evidencia en PLANNING.md.

## Cómo actualizar este registro

### R-003 — Fixtures sectoriales de minimercado y corralón

**Fecha:** 2026-09-04. **Estado:** establecida por solicitud explícita del usuario en cuanto a los dos sectores.

Reemplazar los ejemplos iniciales Clientes/Productos por inventarios ficticios de un minimercado y un corralón de materiales. Se crearon minimercado.xlsx (30 registros, 9 columnas) y corralon_materiales.xlsx (30 registros, 10 columnas), una tabla por libro. FIXTURES.md registra ubicación, tipos esperados y verificación.

Se mantiene el alcance V0 sin relaciones, fórmulas ni movimientos de stock. Las estructuras diferentes, cantidades fraccionadas, códigos textuales, fechas y vacíos permiten probar generalidad. La moneda es ARS y todos los valores son sintéticos. Las variantes inválidas y las pruebas del motor permanecen pendientes.

## Procedimiento de actualización

### R-004 — Stack local ejecutable para V0

**Fecha:** 2026-10-12. **Estado:** decisión de implementación para el PoC.

El usuario pidió desarrollar la aplicación. Al iniciar, el registro de npm no respondió y Docker no permitió conectar con su motor. Para entregar y verificar el flujo V0 en este entorno se implementó un servidor Python estándar, SQLite y una interfaz HTML/CSS/JavaScript. La lectura y exportación XLSX usan ZIP/XML sin paquetes externos. La aplicación está limitada a `127.0.0.1` y un operador.

Esto sustituye P-001 (Next.js/TypeScript) y P-002 (PostgreSQL/JSONB) **solo para V0**. Se conserva el contrato basado en metadatos, validación humana y separación del analyzer. El stack del MVP debe volver a evaluarse con planillas y requisitos reales antes de un piloto. No se afirma equivalencia con un servicio multi-tenant ni compatibilidad con todos los XLSX.

También se simplifica el modelo de V0 a módulos, registros e importaciones; los IDs de campo son estables dentro de cada módulo (`f1`, `f2`, etc.). Las tablas de organización, aplicación y membresías siguen pendientes para V1. Las pruebas HTTP verifican dos libros sectoriales, CRUD, paginación, filtros, exportación, atomicidad e idempotencia.

### R-005 — Fórmulas aritméticas en V0

**Fecha:** 2026-10-12. **Estado:** establecida por solicitud explícita del usuario. Sustituye la exclusión de fórmulas en P-003, P-004 y R-003 solo para este subconjunto.

Se admiten constantes numéricas, paréntesis, `+`, `-`, `*`, `/` y referencias a columnas de la misma fila en formato A1 (`I2`), de tabla (`[@COSTO]`, `[@[% DE GTOS]]`) y explícito (`Tabla1[[#This Row],[COSTO]]`). Las expresiones se convierten a identificadores de campo y se evalúan con decimal exacto. El campo calculado es de solo lectura en el formulario y se recalcula al crear o editar un registro. La exportación escribe fórmulas A1 con el valor calculado.

El análisis lista referencias rotas, expresiones incompatibles o diferentes de la fórmula de su columna. La persona puede corregir cada fórmula en la revisión; el servidor valida nuevamente todo antes de importar. Las fórmulas entre filas, funciones, referencias entre hojas y ciclos quedan fuera de este alcance. El libro aportado contiene un `#REF!` en Q2, que se muestra para corrección.

## Cómo registrar cambios futuros

Agregar una entrada con fecha, estado, contexto, decisión, alternativas y consecuencias. Si reemplaza otra, referenciar su ID y actualizar PROJECT.md, PLANNING.md, ARCHITECTURE.md o DATA_MODEL.md según corresponda. No cambiar silenciosamente una definición del brief.
