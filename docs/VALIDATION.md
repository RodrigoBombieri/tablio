# Validación de V0

Fecha: 2026-10-12. Entorno local Windows, Python 3.14. Las pruebas usaron datos sintéticos. No son una prueba de uso con organizaciones reales.

## Pruebas funcionales

Comando: `python -m unittest discover -s tests -v`.

Resultado: 5 pruebas aprobadas. La batería cubre:

- Importación de minimercado y corralón, 30 registros cada uno, desde sus XLSX.
- Revisión de 25 + 5 registros, filtros, CRUD y exportación.
- Reintento de la misma importación sin duplicar datos.
- Rechazo completo de una importación con importe inválido.
- Errores de fecha, entero y campo obligatorio con coordenadas de origen.
- Conservación de identificadores textuales con ceros iniciales.
- Fórmulas simples, corrección de fórmulas inválidas y reapertura de datos persistidos en SQLite.

También se ejecutaron `node --check web/app.js` y `python -m compileall -q app tests` sin errores.

## Revisión en navegador

Se abrió la aplicación local, se cargaron `minimercado.xlsx` y `corralon_materiales.xlsx`, se revisaron tipos y se confirmó cada importación desde la interfaz. La pantalla inicial muestra ambos módulos con 30 registros cada uno. El listado mostró códigos como `00001` y `CM-0001`, importes en ARS, fechas y valores vacíos. Se inspeccionó el formulario dinámico de edición y una vista angosta con desplazamiento horizontal de la tabla.

No se hizo una revisión detallada de todos los tamaños de escritorio, lectores de pantalla ni navegadores.

## Medición del límite propuesto

Comando: `python -m tests.benchmark_v0`.

Se generó un XLSX sintético con 5.000 filas de datos y 30 columnas de texto, tamaño comprimido de 0,50 MiB. Resultado de una ejecución en este equipo:

| Operación | Tiempo |
|---|---:|
| Lectura XLSX y propuesta de estructura | 1,78 s |
| Conversión de registros | 0,05 s |
| Importación SQLite | 0,10 s |
| Lectura de los 5.000 registros | 0,05 s |

No equivale a medir una planilla de 5 MiB con formatos complejos ni concurrencia de varios usuarios. Los límites siguen siendo de V0 y deben reevaluarse con planillas reales.

## Límites conocidos

- V0 admite tablas rectangulares y fórmulas aritméticas de la misma fila. No procesa funciones de Excel, referencias entre filas u hojas, combinaciones, macros ni relaciones entre hojas.

El libro real `Libro1 (1).xlsx` (528 filas, 18 columnas) se analizó sin modificarlo: contiene fórmulas A1 y de tabla, y una referencia rota `#REF!` en Q2. Tras corregir esa fórmula en memoria a `=N2/L2`, los 527 registros de datos se convierten sin errores. Las pruebas automatizadas cubren ambas sintaxis, la lista de errores, la corrección previa a la importación, el recálculo de registros y la exportación con fórmulas.
- Funciona localmente, sin autenticación, organizaciones independientes ni copias de seguridad automáticas.
- El parser/exportador XLSX cubre el subconjunto usado en el PoC; archivos reales heterogéneos requieren ampliar compatibilidad.
- La búsqueda y filtros se ejecutan sobre registros del módulo en memoria. Para más volumen o concurrencia deben trasladarse a consultas indexadas.
- Las fechas, importes y textos exportados se preservan como valores tipados admitidos; no se recupera la apariencia original del libro.
- Se probó la reapertura de conexiones SQLite, pero no se automatizó el reinicio completo del proceso del servidor.
- Las variantes inválidas se generan dentro de las pruebas. No se añadieron libros inválidos adicionales a `outputs/`.
