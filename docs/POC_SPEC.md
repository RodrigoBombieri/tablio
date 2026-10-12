# Especificación verificable del PoC

Fecha: 2026-09-04. Base de trabajo adoptada para avanzar con la planificación. Los XLSX vigentes son Minimercado y Corralón, generados y documentados en [FIXTURES.md](FIXTURES.md) por pedido del usuario (R-003). Los dos ejemplos iniciales siguientes se conservan como referencia histórica y no son archivos generados. Las reglas generales desde Conversión de valores orientan el diseño; la implementación local V0 y las diferencias de alcance están registradas en ARCHITECTURE.md y DECISIONS.md, R-004.

## Ejemplo inicial reemplazado: clientes

Archivo previsto: clientes.xlsx. Hoja: Clientes. Todos los datos son ficticios. Encabezados en fila 1; celdas sin fórmulas, combinaciones ni filas de totales.

| Codigo | Nombre | Telefono | Saldo | UltimaCompra | Activo | Categoria |
|---|---|---|---|---|---|---|
| 0001 | Cliente Demo A | 01100000001 | 125000.50 | 2026-09-01 | true | Minorista |
| 0002 | Cliente Demo B | 01100000002 | 0.00 | 2026-09-02 | false | Mayorista |
| 0003 | Cliente Demo C | | -1500.25 | | true | Minorista |

Esta tabla describe valores canónicos. En el XLSX, Codigo y Telefono deben ser celdas de texto, Saldo numérico con dos decimales, UltimaCompra fecha de Excel y Activo booleano. Vacíos indicados por celdas vacías.

| Columna | Tipo confirmado | Obligatoria | Resultado esperado |
|---|---|---|---|
| Codigo | text | Sí | Conservar 0001; no usarlo como ID interno |
| Nombre | text | Sí | Campo principal del listado y detalle |
| Telefono | text | No | Conservar el cero inicial |
| Saldo | currency, ARS, escala 2 | Sí | Decimal exacto; saldo informado, sin cálculos contables |
| UltimaCompra | date | No | Fecha sin hora o null |
| Activo | boolean | Sí | true o false |
| Categoria | enum | Sí | Minorista o Mayorista, confirmados por la persona |

La obligatoriedad, moneda y enumeración son decisiones de revisión, no conclusiones automáticas garantizadas por el analyzer.

Recorrido esperado: importar tres clientes, buscar Demo B, filtrar saldos mayores que cero, editar el saldo del cliente A, crear y eliminar un cliente de prueba y exportar los registros actuales. La exportación debe conservar códigos y teléfonos como texto.

## Segundo ejemplo inicial reemplazado: productos

Archivo previsto: productos.xlsx. Hoja: Productos. Se importa como otra entidad independiente en la misma aplicación; no se relaciona con Clientes.

| SKU | Descripcion | Stock | PesoKg | Precio | Estado |
|---|---|---|---|---|---|
| P-001 | Producto Demo A | 12 | 0.750 | 1800.00 | Disponible |
| P-002 | Producto Demo B | 0 | 1.250 | 2450.50 | Agotado |
| P-003 | Producto Demo C | 5 | 2.000 | 3200.00 | Disponible |

| Columna | Tipo confirmado | Obligatoria | Configuración |
|---|---|---|---|
| SKU | text | Sí | Código textual |
| Descripcion | text | Sí | Campo principal |
| Stock | integer | Sí | Sin regla automática de stock no negativo |
| PesoKg | decimal | Sí | Escala 3 |
| Precio | currency | Sí | ARS, escala 2 |
| Estado | enum | Sí | Disponible, Agotado |

El motor debe mostrar ambas entidades sin código condicionado a nombres como Saldo, Stock o Clientes. No se implementan movimientos de inventario ni relaciones.

## Conversión de valores

Las reglas siguientes se aplican al importar y al validar formularios; el adaptador de entrada diferencia celdas tipadas de cadenas introducidas por una persona.

| Caso | Regla |
|---|---|
| Vacío | Celda vacía o cadena compuesta solo por espacios → null; se rechaza si el campo es obligatorio |
| Texto | Conservar contenido no vacío; nunca convertir códigos textuales a números |
| Entero | Admitir de -9007199254740991 a 9007199254740991; rechazar fracciones o valores fuera del rango |
| Decimal | Máximo 15 dígitos significativos para V0; escala confirmada de 0 a 6; cadena canónica con punto decimal y escala fija |
| Importe | Misma representación decimal, escala 2 y moneda ARS para estos datasets |
| Precisión | Rechazar exceso de escala o precisión; no redondear silenciosamente |
| Fecha de texto | Admitir YYYY-MM-DD; DD/MM/YYYY solo con configuración es-AR confirmada; validar calendario |
| Fecha de Excel | Interpretar el sistema de fechas del libro; rechazar fechas inválidas y componente horario distinto de cero |
| Booleano | Celdas booleanas; texto sí/si/no/true/false sin distinguir mayúsculas y con espacios extremos eliminados; números 1/0 solo al confirmar tipo booleano |
| Enum | Comparación exacta con opciones confirmadas; no corregir variantes silenciosamente |

Los números nativos de Excel se interpretan como números, sin volver a analizar el texto de presentación regional. Las cadenas numéricas requieren una convención confirmada por columna: es-AR (1.234,50) o decimal con punto sin miles (1234.50). Mostrar la conversión en la revisión; no adivinar entre ambas. No admitir notación científica ni símbolos monetarios dentro de cadenas en V0.

Una columna numérica original no permite recuperar ceros iniciales ya perdidos. El analyzer debe advertirlo si se cambia a texto; no inventarlos. Las columnas completamente vacías se proponen como texto opcional. Las filas completamente vacías se omiten, informando el conteo y conservando coordenadas originales de las restantes.

## Inferencia determinística

1. Revisar toda la tabla dentro de los límites; la UI solo muestra hasta cinco ejemplos por columna.
2. Priorizar celdas booleanas y fechas tipadas coherentes.
3. Para números, proponer entero si todos son enteros admitidos; en otro caso decimal.
4. Para cadenas, proponer texto salvo evidencia inequívoca de otro tipo; no convertir cadenas con ceros iniciales a números.
5. Una mezcla incompatible se propone como texto con advertencia y ejemplos; la persona puede confirmar otro tipo y corregir el archivo si falla la validación.
6. Los nombres y formatos pueden sugerir importe o identificador, pero no alteran los valores ni imponen obligatoriedad, moneda o unicidad.
7. Ofrecer enum como sugerencia si hay entre 2 y 10 valores distintos y al menos un valor repetido. La persona confirma las opciones.

La revisión muestra tipo propuesto, motivo, vacíos e incompatibilidades. Cambiar el tipo invalida la validación anterior y exige validar nuevamente todos los registros.

## Consultas de V0

| Tipo | Operadores |
|---|---|
| text | contiene, igual |
| integer, decimal, currency | igual, mayor que, menor que |
| date | igual, anterior a, posterior a |
| boolean, enum | igual |
| Todos | está vacío, no está vacío |

Búsqueda global por subcadena en campos text, sin distinguir mayúsculas, pero distinguiendo acentos. Filtros combinados con AND; sin agrupaciones ni OR. Null no coincide con comparaciones de valores. Orden por un campo, null al final y desempate por ID interno. Decimales se comparan numéricamente y fechas cronológicamente. Paginación inicial de 25 registros.

## Errores y casos de aceptación

Cada error de celda incluye código estable, hoja, fila y columna de Excel, etiqueta del campo y mensaje comprensible. No volcar filas completas en logs. Los errores de archivo no requieren coordenadas.

| Código | Ejemplo de mensaje / comportamiento |
|---|---|
| REQUIRED_VALUE | Clientes, fila 3, Nombre: completá este campo obligatorio |
| INVALID_DATE | Clientes, fila 2, UltimaCompra: 31/02/2026 no es una fecha válida |
| INVALID_NUMBER | Productos, fila 2, Stock: ingresá un número entero |
| PRECISION_EXCEEDED | Clientes, fila 2, Saldo: se admiten hasta 2 decimales |
| INVALID_OPTION | Productos, fila 3, Estado: elegí Disponible o Agotado |
| DUPLICATE_HEADER | Hay dos columnas con el mismo encabezado; cambialo en el Excel |
| EMPTY_HEADER | Una columna con datos no tiene encabezado |
| INVALID_FORMULA | La fórmula tiene una referencia inválida, usa sintaxis fuera del subconjunto admitido o difiere de la fórmula de su columna; corregila en la revisión |
| MERGED_CELLS | La tabla contiene celdas combinadas; separalas antes de importar |
| LIMIT_EXCEEDED | El archivo supera uno de los límites admitidos |

Crear variantes de prueba alterando una celda por caso, además de archivos con encabezados duplicados, fórmulas, celdas combinadas y límites excedidos. Son casos especificados, todavía no ejecutados.

## Archivos temporales

Vencimiento de una importación no completada: 24 horas desde la recepción. Eliminar el XLSX al completar o vencer; limpieza al iniciar la aplicación y antes de aceptar nuevas subidas. La importación vencida exige volver a subir el archivo. Validar antes de parsear un máximo de 5 MiB comprimidos y 50 MiB descomprimidos; 5.000 filas de datos y 30 columnas por tabla. Estos son límites de diseño sujetos a pruebas de recursos, no capacidad ya demostrada.
