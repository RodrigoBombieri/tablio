# Código de la aplicación

Esta carpeta quedó como reserva de la estructura inicial. La implementación local V0 reside en `app/` (servidor) y `web/` (interfaz); ver el [README principal](../README.md).

El cambio de estructura y stack está documentado en [DECISIONS.md](../docs/DECISIONS.md), R-004.

Mantener el análisis de Excel, la conversión y la validación independientes de la interfaz. Crear módulos cuando exista una responsabilidad concreta que implementar; evitar una jerarquía vacía anticipada.

Los archivos Excel de organizaciones y sus datos no deben guardarse en esta carpeta. Las futuras muestras versionadas deberán ser ficticias o anonimizadas.
