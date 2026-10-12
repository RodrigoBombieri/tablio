# Documentación de Tablio

**De planilla a sistema.**

Tablio transforma las planillas existentes de una organización en aplicaciones web de gestión simples, intuitivas y seguras.

## Estado del proyecto

Etapa actual: PoC local ejecutable. El flujo de servidor fue probado con los dos XLSX y la interfaz se revisó en navegador con el minimercado. La ejecución se explica en el [README principal](../README.md).

El [Project Brief](../Tablio%20%E2%80%94%20Project%20Brief.md) es la fuente de verdad inicial. El diseño del PoC se adoptó como base de trabajo para avanzar; ver R-002 en DECISIONS.md. Esto no constituye validación técnica ejecutada ni aprobación individual del usuario de cada detalle.

## Documentos

| Documento | Contenido |
|---|---|
| [PROJECT.md](PROJECT.md) | Visión, problema, principios y alcance |
| [PLANNING.md](PLANNING.md) | Etapas, tareas y criterios de aceptación |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Componentes, stack, límites y despliegue propuestos |
| [DATA_MODEL.md](DATA_MODEL.md) | Application Schema y persistencia dinámica |
| [DECISIONS.md](DECISIONS.md) | Decisiones del brief, propuestas y pendientes |
| [POC_SPEC.md](POC_SPEC.md) | Datasets ficticios, conversiones, filtros y casos de aceptación |
| [FIXTURES.md](FIXTURES.md) | XLSX vigentes de minimercado y corralón, tipos esperados y verificación |
| [VALIDATION.md](VALIDATION.md) | Pruebas, recorrido en navegador, medición y límites conocidos |

## Convenciones

- **Establecido por el brief:** definición vigente de producto o dirección arquitectónica.
- **Propuesto:** diseño sugerido para V0, pendiente de confirmación.
- **Pendiente:** cuestión todavía sin resolver.

Registrar los cambios importantes en DECISIONS.md con fecha, estado y justificación. Actualizar los documentos afectados para que describan el diseño vigente, conservando el historial de decisiones.

La ejecución y las pruebas se explican en el [README principal](../README.md).
