# Modelo de datos

## Estado

Contrato de diseño adoptado para V0 el 2026-09-04. Desde 2026-10-12 hay un validador y tablas SQLite locales en `app/core.py` y `app/store.py`. La implementación usa IDs `f1`, `f2`, etc. dentro de cada entidad y un schema JSON versionado. Es una simplificación de V0 frente a los IDs opacos y PostgreSQL/JSONB propuestos antes. Ver DECISIONS.md, R-004.

## Application Schema

Contrato que describe los datos admitidos y la presentación básica de una entidad. No contiene código ejecutable ni permite definir comportamientos arbitrarios.

| Nivel | Metadatos mínimos |
|---|---|
| Aplicación | Identificador y nombre |
| Entidad | Identificador estable, nombre y versión del schema |
| Campo | Identificador estable, etiqueta, tipo, obligatoriedad y opciones |
| Presentación | Orden, campos visibles y campo principal del registro |

Separar los metadatos de importación: hoja, coordenadas, correspondencia de columnas, muestras, advertencias y configuración regional. El motor de aplicación debe poder operar sin conservar el archivo original.

## Tipos propuestos

| Tipo | Representación y reglas |
|---|---|
| Texto | Cadena; conserva ceros iniciales de DNI, códigos y teléfonos |
| Entero | Número entero entre -9007199254740991 y 9007199254740991 |
| Decimal | Cadena canónica, máximo 15 dígitos significativos y escala fija entre 0 y 6 |
| Importe | Decimal exacto y moneda explícita en los metadatos del campo |
| Fecha | Fecha sin hora en formato YYYY-MM-DD |
| Booleano | true/false; conversiones desde Excel explícitamente admitidas |
| Enumeración | Valor perteneciente a opciones confirmadas |

Usar null para ausencia de valor: celda vacía o cadena compuesta solo por espacios. Conservar el contenido de textos no vacíos. Un campo obligatorio rechaza null.

## Contrato del schema v1

Separar schemaVersion (versión del formato del contrato, inicialmente 1) de revision (versión de la definición de una entidad, inicialmente 1). V0 no permite modificar la estructura importada.

Ejemplo documental mínimo; no es código implementado:

```json
{
  "schemaVersion": 1,
  "entityId": "ent_clientes",
  "revision": 1,
  "name": "Clientes",
  "fields": [
    { "id": "fld_nombre", "label": "Nombre", "type": "text", "required": true },
    { "id": "fld_saldo", "label": "Saldo", "type": "currency", "required": true, "scale": 2, "currency": "ARS" }
  ],
  "view": {
    "primaryFieldId": "fld_nombre",
    "visibleFieldIds": ["fld_nombre", "fld_saldo"]
  }
}
```

Los IDs legibles del ejemplo son ilustrativos; en ejecución se generan identificadores opacos. El orden del arreglo fields define el orden del formulario; visibleFieldIds define el del listado. Un registro guarda sus valores por ID de campo, por ejemplo fld_saldo: "125000.50". Aplicación y organización se obtienen de los vínculos relacionales, no de valores del schema enviados libremente por el cliente.

Validaciones del contrato:

- schemaVersion debe ser 1 y revision un entero positivo; rechazar versiones no soportadas y propiedades desconocidas.
- Nombre de entidad y etiquetas: entre 1 y 80 caracteres después de quitar espacios extremos.
- Entre 1 y 30 campos, con IDs únicos; etiquetas únicas ignorando mayúsculas y espacios extremos.
- Tipos admitidos: text, integer, decimal, currency, date, boolean y enum. required es siempre booleano explícito.
- scale es obligatorio solo para decimal y currency; currency exige código de moneda (ARS en V0).
- enum exige options: entre 1 y 100 cadenas no vacías, únicas, de hasta 100 caracteres; no se admite options en otros tipos.
- primaryFieldId y visibleFieldIds deben referir a campos existentes; el listado debe tener al menos un campo y no repetir IDs.
- Los registros completos tienen exactamente los IDs del schema; campos opcionales vacíos se materializan como null. Las escrituras parciales se combinan con el registro actual y se valida el resultado completo.
- Solo se admiten expresiones aritméticas de campos calculados derivadas del XLSX y validadas por el servidor; no se admiten funciones, relaciones ni validadores arbitrarios.

El mapeo de importación registra por separado sourceSheet, headerRow (1), columnas de origen con su fieldId, columnas ignoradas y convenciones de conversión. Cada campo tiene una sola columna de origen y una columna no puede alimentar dos campos. La confirmación referencia una revisión validada; una corrección invalida el resultado anterior.

Los decimales almacenados como cadenas requieren conversiones numéricas controladas para ordenar o filtrar; no deben compararse lexicográficamente. Las operaciones monetarias no usarán aritmética binaria de punto flotante.

Teléfono, email y porcentaje podrán evolucionar hacia formatos semánticos específicos. V0 no necesita implementar todos los tipos potenciales enumerados en el brief.

## Identidad y versiones

- Tablio genera identificadores internos para entidades, campos y registros.
- Una columna ID de Excel se conserva como dato; no se convierte automáticamente en clave primaria.
- Los datos de cada registro se asocian a identificadores estables de campo.
- Las etiquetas visibles no determinan la identidad de los campos.
- La estructura se congela al importar en V0.
- Los cambios posteriores de tipos o campos requerirán una estrategia de migración en otra etapa.

## Persistencia híbrida originalmente propuesta

| Tabla conceptual | Contenido |
|---|---|
| Organización | Identificador y nombre; una preconfigurada en V0 |
| Aplicación | Identificador, organización propietaria y nombre |
| Entidad | Identificador, organización, aplicación, nombre, schema y versión |
| Registro | Identificador, organización, entidad, datos JSONB y fechas de creación/modificación |
| Importación | Identificador, organización, aplicación, estado, schema confirmado, mapeo, conteos y errores |

La implementación actual contiene `organizations`, `users`, `memberships`, `sessions`, `modules`, `records`, `imports` y `pending_uploads` en SQLite; `schema_json` y `values_json` almacenan JSON en columnas de texto. `modules` e `imports` tienen `organization_id`; los registros se consultan a través del módulo de la organización activa. No hay una tabla separada de aplicaciones. Los datos dinámicos se validan en el servidor antes de persistir. Los módulos heredados de V0 se migran a la organización inicial.

Las fechas de creación y modificación no constituyen un historial de auditoría completo. La auditoría detallada queda fuera de V0.

## Validación y consultas

El schema se valida antes de persistirse. Los registros se validan en servidor tanto al importar como en altas y ediciones. Se rechazan campos desconocidos y valores incompatibles.

La búsqueda y los filtros se construyen a partir de campos y operadores permitidos por tipo. Los índices iniciales cubrirán los vínculos relacionales; agregar índices JSONB o por campo solo si las mediciones lo justifican.

La unicidad de un ID de negocio no se infiere ni se garantiza automáticamente en V0. Las relaciones entre entidades corresponden a V2.

## Ciclo de importación propuesto

Estados conceptuales: recibido → analizado → listo para importar → completado. Una operación puede fallar o vencer antes de completarse.

La confirmación vincula el archivo temporal con el schema revisado. La importación definitiva es atómica e idempotente respecto de esa confirmación. Guardar los conteos y errores necesarios para explicar el resultado sin conservar indefinidamente muestras de datos ni archivos originales.

## Exportación

Exportar etiquetas legibles y valores actuales respetando los tipos admitidos, incluidos identificadores textuales y fechas sin hora. Los campos calculados guardan una expresión canónica por ID de campo (por ejemplo `f9 * f10 + f11`) y exportan una fórmula A1 por fila junto al resultado calculado. Los textos se escriben como valores. No se reproducen estilos, macros ni la disposición original del libro.

La expresión es metadato controlado: se deriva de fórmulas de la hoja y admite solo aritmética decimal y referencias de la misma fila. Sus dependencias deben estar incluidas y no formar ciclos. Los resultados se recalculan en el servidor durante importación, alta y edición; un valor enviado para un campo calculado se ignora. Los errores se ubican por fila y columna y pueden corregirse antes de confirmar.
