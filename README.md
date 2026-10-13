# Tablio

**De planilla a sistema.**

Tablio convierte una tabla de Excel en un módulo web para consultar y editar registros. Esta implementación cubre el Proof of Concept V0 definido en el [Project Brief](Tablio%20%E2%80%94%20Project%20Brief.md). Funciona en un equipo local, con datos ficticios o anonimizados.

## Ejecutar en Visual Studio Code

Requisito: Python 3.11 o superior. Abrí esta carpeta del repositorio en VS Code. La primera vez, creá el propietario; el comando pedirá una contraseña de al menos 12 caracteres:

```powershell
python -m app.admin --email vos@ejemplo.com --name "Tu nombre" --organization "Mi organización"
```

Después ejecutá:

```powershell
python -m app.server
```

Abrí `http://127.0.0.1:8000` en el navegador. No hay paquetes externos que instalar. La base SQLite se crea automáticamente en `data/tablio.sqlite3`. Las importaciones pendientes se guardan temporalmente en `uploads/` y vencen a las 24 horas. Ambas rutas quedan fuera del control de versiones.

Para verificar el flujo:

```powershell
python -m unittest discover -s tests -v
```

Si el puerto 8000 está ocupado, configurá `TABLIO_PORT` antes de iniciar el servidor.

## Primer recorrido

1. Seleccioná **Importar una planilla**.
2. Elegí [minimercado.xlsx](outputs/01a06e97-c8d6-7c20-aebd-4c816513d8af/minimercado.xlsx) o [corralon_materiales.xlsx](outputs/01a06e97-c8d6-7c20-aebd-4c816513d8af/corralon_materiales.xlsx).
3. Revisá los tipos de campo. Para categorías, rubros, unidad y estado, podés seleccionar **Opciones** y confirmar la lista separada por comas.
4. Elegí **Comprobar datos**. Si hay celdas o fórmulas con errores, corregilas por fila y campo desde la misma pantalla y repetí la comprobación. Se admiten operaciones `+`, `-`, `*`, `/`, paréntesis y referencias de la misma fila, incluidas referencias de tabla.
5. Guardá el módulo. Luego probá búsqueda, filtros, orden, columnas visibles, vistas guardadas, edición y exportación. Los campos calculados se actualizan al editar sus entradas y se exportan como fórmulas.
6. Desde el módulo, elegí **Actualizar desde Excel**, indicá la columna que identifica cada registro y revisá cuántos se agregarán o cambiarán. Las filas ausentes del archivo quedan intactas. **Historial** permite deshacer una actualización si esos registros no se editaron después.

**Configurar campos** permite cambiar nombres, marcar campos obligatorios y agregar otros opcionales. La sección **Usuarios** permite invitar personas con un enlace privado o generar un enlace para recuperar el acceso. Propietarios y administradores pueden consultar **Actividad**.

Los datos de prueba son sintéticos. La [guía de los dos XLSX](docs/FIXTURES.md) indica sus columnas y valores especiales.

## Estructura

```text
app/       Servidor local, análisis, validación y persistencia
web/       Interfaz responsive en HTML, CSS y JavaScript
tests/     Pruebas del recorrido con ambos XLSX
docs/      Planificación, arquitectura y decisiones
outputs/   Dos archivos Excel de prueba
data/      Base local creada al ejecutar (ignorada)
uploads/   Archivos temporales de importación (ignorados)
```

El [registro de decisiones](docs/DECISIONS.md) explica por qué la implementación local usa Python y SQLite en esta etapa. La [planificación](docs/PLANNING.md) distingue las funciones implementadas de las pendientes del MVP. [Acceso, backups y despliegue](docs/SECURITY_DEPLOYMENT.md) describe los roles, la migración de datos V0, las copias y la preparación de HTTPS.

## Límite de uso

La app local escucha en `127.0.0.1`. Ahora exige inicio de sesión y aplica permisos por organización. El despliegue con HTTPS está configurado mediante Docker Compose y Caddy, pero sigue pendiente de un servidor, dominio y verificación operativa. Antes de usar datos reales fuera de una prueba controlada, prepará copias externas, restauración, monitoreo y revisión de la infraestructura.
