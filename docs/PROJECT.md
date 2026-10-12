# Proyecto Tablio

## Fuente y estado

Fuente de verdad: [Project Brief](../Tablio%20%E2%80%94%20Project%20Brief.md). Estado: PoC local V0 implementado. El alcance se adoptó como base de trabajo mediante R-002 y el stack local se decidió en R-004 de DECISIONS.md. Datasets vigentes: [FIXTURES.md](FIXTURES.md).

## Visión

Transformar las planillas que una organización ya utiliza en sistemas web de gestión simples, intuitivos y seguros.

**No abandones tu planilla. Evolucionala.**

La planilla conserva conocimiento operativo del negocio. Tablio parte de esa estructura para reducir el esfuerzo de adopción y ofrecer búsqueda, validaciones, edición y acceso móvil.

## Problema y usuarios

Pequeñas organizaciones dependen de Excel para administrar clientes, stock, socios, cuotas, pedidos o mantenimiento. Al funcionar como sistemas, estas planillas presentan duplicación, modificaciones accidentales, fórmulas rotas, poca trazabilidad y dificultades de colaboración y consulta móvil.

Usuarios iniciales: comercios, talleres, clubes, profesionales, distribuidoras y pequeñas industrias. La familiaridad con sus datos y el acompañamiento humano son parte de la propuesta de valor.

## Principios establecidos

- Baja barrera de adopción y experiencia familiar.
- Simplicidad, seguridad, mantenibilidad y uso móvil.
- Los datos pertenecen al cliente; importación y exportación forman parte del producto.
- Interpretación verificable y confirmación humana.
- Preferencia por una aplicación dinámica basada en metadatos.
- Análisis determinístico separado de una posible capa futura de IA.
- Desarrollo incremental basado en planillas reales.

Tablio no es un clon de Excel, un ERP genérico, un constructor universal no-code ni un generador arbitrario de código.

## Hipótesis del PoC

Una planilla simple puede convertirse en una aplicación útil sin desarrollar pantallas específicas para sus columnas.

Flujo propuesto: subir Excel → interpretar → corregir y confirmar → importar → consultar y editar → exportar.

## Alcance propuesto de V0

| Área | Alcance |
|---|---|
| Entrada | XLSX con una hoja seleccionada y una tabla rectangular |
| Encabezados | Primera fila, sin encabezados vacíos ni duplicados en columnas utilizadas |
| Límites iniciales | 5 MiB comprimidos, 50 MiB descomprimidos, 5.000 registros y 30 columnas; a verificar con mediciones |
| Tipos | Texto, entero, decimal, importe, fecha, booleano y enumeración |
| Revisión | Cambiar etiquetas, tipos, obligatoriedad, opciones y columnas ignoradas |
| Operación | Listado paginado, búsqueda, filtros simples, detalle y CRUD |
| Interfaz | Responsive, con formularios cómodos desde teléfonos |
| Salida | XLSX con datos actuales, sin reconstruir el formato original |
| Entorno | Local, un operador y una organización preconfigurada |

Casos vigentes por solicitud del usuario: inventarios ficticios de un minimercado y un corralón de materiales. El stock es un dato informado; no se calcula a partir de movimientos. Ver [FIXTURES.md](FIXTURES.md). El ejemplo inicial de clientes con saldo queda como referencia histórica.

Se propone incluir exportación en V0 para verificar la recuperación de datos, aunque excede el recorrido mínimo del PoC del brief.

## Fuera de V0

Relaciones entre entidades, fórmulas avanzadas o entre hojas, dashboards, IA, sincronización con Excel, importaciones incrementales, cambios de estructura posteriores a la importación, personalización visual avanzada, usuarios y roles operativos de producción. V0 admite el subconjunto aritmético de la misma fila definido en DECISIONS.md, R-005.

## Diferencia con el MVP

El MVP incorporará importación de planillas reales, configuración más amplia, organizaciones, aplicaciones, usuarios y permisos básicos. El PoC demuestra el núcleo técnico y no acredita preparación para operar con clientes reales.

El modelo comercial y la identidad visual definitiva siguen pendientes de validación.
