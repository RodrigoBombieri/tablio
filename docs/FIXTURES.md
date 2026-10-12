# Archivos de prueba del PoC

Generados y verificados el 2026-09-04. Por pedido del usuario, los casos vigentes son un minimercado y un corralón de materiales. Reemplazan los datasets iniciales Clientes/Productos como archivos de referencia del primer recorrido.

Todos los productos, cantidades, precios y pesos son datos sintéticos para pruebas. No representan cotizaciones de mercado ni especificaciones técnicas verificadas. Las fechas corresponden a agosto de 2026. No contienen datos de clientes reales.

## Archivos

| Archivo | Hoja | Registros | Columnas |
|---|---|---|---|
| [minimercado.xlsx](../outputs/01a06e97-c8d6-7c20-aebd-4c816513d8af/minimercado.xlsx) | Productos minimercado | 30 | 9 |
| [corralon_materiales.xlsx](../outputs/01a06e97-c8d6-7c20-aebd-4c816513d8af/corralon_materiales.xlsx) | Materiales corralón | 30 | 10 |

Cada libro tiene una sola tabla, encabezados en fila 1, filtros y encabezado inmovilizado. No hay fórmulas, celdas combinadas, filas de totales ni hojas auxiliares. Los importes están expresados en ARS por unidad de venta. Stock es una cantidad informada, no calculada desde movimientos.

## Interpretación confirmable: minimercado

| Columna | Tipo esperado | Obligatoria | Regla |
|---|---|---|---|
| Codigo | text | Sí | Conservar ceros iniciales; 00001 a 00030 |
| Producto | text | Sí | Campo principal |
| Categoria | enum | Sí | Almacén, Lácteos, Bebidas, Panadería, Verdulería, Limpieza, Higiene |
| Unidad | enum | Sí | unidad, kg, docena |
| Stock | decimal | Sí | Escala 3; incluye venta por peso y valores cero |
| PrecioVenta | currency | Sí | ARS, escala 2, por Unidad |
| Activo | boolean | Sí | Celdas booleanas reales, no texto |
| UltimaReposicion | date | No | Fecha de Excel o null |
| Observaciones | text | No | Texto libre o null |

Casos puntuales: A2 contiene el texto 00001; E12 contiene 4.750 kg de queso; el producto 00028 está inactivo, con stock cero y sin fecha de reposición. Hay tres productos con stock cero. Estos casos son válidos y no deben confundirse con datos faltantes.

## Interpretación confirmable: corralón

| Columna | Tipo esperado | Obligatoria | Regla |
|---|---|---|---|
| SKU | text | Sí | CM-0001 a CM-0030 |
| Material | text | Sí | Campo principal |
| Rubro | enum | Sí | Cementos y cales, Revestimientos, Áridos, Mampostería, Hierros, Techos, Sanitarios, Pinturas, Construcción seca |
| UnidadVenta | enum | Sí | bolsa, m3, unidad, barra, panel, kg, rollo, balde, bidón, caja, placa |
| StockDisponible | decimal | Sí | Escala 3; cantidad en UnidadVenta |
| PrecioUnitario | currency | Sí | ARS, escala 2, por UnidadVenta |
| PesoKgUnidad | decimal | Sí | Escala 3; kg por unidad de venta, dato ficticio |
| Estado | enum | Sí | Disponible, Sin stock, Discontinuado |
| UltimoIngreso | date | No | Fecha de Excel o null |
| Ubicacion | text | No | Texto libre o null |

Casos puntuales: E6 contiene 18.500 m3 de arena; G14 contiene 2.664 kg por barra; CM-0030 está discontinuado y sin fecha ni ubicación. Hay tres materiales con stock cero. No se debe imponer stock entero a todo el inventario.

UnidadVenta tiene 11 valores distintos: supera el umbral de sugerencia automática de enum (10), pero puede configurarse manualmente como enum dentro del límite de 100 opciones. El motor no debe imponer el umbral de inferencia como límite del contrato.

## Recorrido de prueba previsto

1. Subir cada archivo y seleccionar su única hoja.
2. Revisar tipos, moneda, obligatoriedad y opciones con las tablas anteriores.
3. Importar 30 registros por entidad sin lógica específica para sus encabezados.
4. Comprobar dos páginas con tamaño 25, búsqueda textual, filtros por categoría/estado, stock y fecha.
5. Editar un precio y una cantidad fraccionada; crear y eliminar un registro de prueba.
6. Exportar y comparar valores, ceros iniciales, booleanos, fechas y null.

El recorrido HTTP y la importación desde la interfaz local se verificaron con ambos archivos. La medición sintética de capacidad se registró en VALIDATION.md; queda pendiente una evaluación visual amplia en escritorio.

## Verificación realizada sobre los XLSX

- Inspección de valores y ausencia de errores de fórmula mediante la herramienta de planillas.
- Revisión visual de las dos hojas: encabezados legibles y columnas dimensionadas.
- Reapertura de ambos XLSX con un lector independiente: una hoja, 30 registros, 9/10 columnas, sin fórmulas ni combinaciones, tabla con filtros y primera fila inmovilizada.
- Comprobación de tipos de texto, número, booleano y fecha; preservación del código 00001, cantidades fraccionadas y vacíos opcionales.

La previsualización de la herramienta muestra algunos códigos numéricos textuales sin ceros; la reapertura del XLSX confirmó que A2 conserva exactamente 00001 como texto. No se alteraron los datos para compensar esa limitación del render.

Se verificaron en pruebas unitarias errores de fechas, importes, enteros y campos obligatorios. Las variantes XLSX deliberadamente inválidas adicionales y las pruebas de volumen siguen pendientes. Los teléfonos del ejemplo previo no están cubiertos por estos dos libros.
