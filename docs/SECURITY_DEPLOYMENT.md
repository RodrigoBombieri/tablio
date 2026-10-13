# Acceso, datos privados, backups y despliegue

Esta guía describe la implementación actual y las operaciones necesarias para una instalación. La configuración HTTPS está preparada, pero no se ha publicado un servicio: todavía no hay dominio ni servidor.

## Primer propietario y migración de V0

La aplicación no ofrece registro público. Antes de abrirla por primera vez, creá el propietario desde una terminal con acceso a la base:

```powershell
python -m app.admin --email vos@ejemplo.com --name "Tu nombre" --organization "Mi organización"
python -m app.server
```

La contraseña se pide dos veces sin mostrarla. Debe tener al menos 12 caracteres. `app.server` crea o actualiza las tablas SQLite. Si ya existían módulos de V0, quedan en una organización llamada temporalmente `Legado V0`; al crear el primer propietario se le asignan y se cambia el nombre de esa organización. Hacé una copia de `data/tablio.sqlite3` antes de actualizar una instalación existente. El comando inicial solo funciona si todavía no existe ningún usuario.

Para una instalación Docker, ejecutá el bootstrap una vez, después de levantar `app`:

```sh
docker compose up -d app
docker compose exec app python -m app.admin --email vos@ejemplo.com --name "Tu nombre" --organization "Mi organización"
```

Luego abrí el sitio y cambiá la contraseña inicial desde la interfaz si fue generada por otra persona.

## Permisos y aislamiento

| Rol | Consultar y exportar | Importar y editar | Administrar usuarios |
|---|---:|---:|---:|
| Propietario | Sí | Sí | Sí |
| Administrador | Sí | Sí | No |
| Editor | Sí | Sí | No |
| Lector | Sí | No | No |

Cada usuario puede pertenecer a varias organizaciones. La interfaz permite elegir la activa; el servidor comprueba la membresía en cada solicitud. Los módulos, registros e importaciones se consultan con `organization_id`. Una URL o identificador de otra organización no concede acceso. Solo el propietario puede crear usuarios, agregarlos a su organización, cambiar roles o quitar membresías. Un cambio de rol o retiro invalida las sesiones del usuario. No se puede retirar al propietario desde la interfaz.

Las sesiones duran 12 horas y usan una cookie `HttpOnly`, `SameSite=Strict`; en HTTPS llevan también `Secure`. Cada escritura autenticada exige un token CSRF. Las contraseñas se guardan con PBKDF2-SHA256, sal aleatoria y 600.000 iteraciones. El servidor limita los intentos de login por dirección y email. El cambio de contraseña invalida todas las sesiones del usuario.

El propietario puede crear una invitación para una persona nueva o una cuenta ya existente. El enlace se muestra una sola vez, vence a los siete días y debe compartirse por un canal privado elegido por el propietario; Tablio todavía no envía correos. Para una cuenta existente se pide la contraseña actual antes de agregar la organización. El propietario también puede generar un enlace de recuperación para cualquier integrante, incluso para sí mismo si conserva una sesión abierta. Ese enlace vence en una hora, se usa una vez y revoca las sesiones al cambiar la contraseña. Si el único propietario pierde toda sesión y su contraseña, un operador con acceso al servidor puede ejecutar `python -m app.recover --email vos@ejemplo.com --base-url https://tu-dominio` para emitir un enlace de emergencia. No hay autoservicio por email. Los enlaces llevan el token en el fragmento `#` de la URL para evitar enviarlo al servidor al cargar la página. No compartas ni registres estos enlaces públicamente.

La vista **Actividad** está disponible para propietarios y administradores y muestra cambios de registros, importaciones, configuración, membresías y accesos. Es una bitácora básica; aún faltan políticas de retención, exportación, monitoreo de anomalías y revisión de seguridad antes de operar como servicio público completo. No hay segundo factor.

Los XLSX pendientes se guardan fuera de `web/`, con token aleatorio, usuario y organización asociados. Se eliminan al importar o al vencer 24 horas después. En Linux, las carpetas privadas y la base usan permisos de propietario; en Docker están en un volumen privado no publicado. No incluyas `data/`, `uploads/`, `backups/` ni `.env` en Git.

## Copias y recuperación

La copia usa la API de backup online de SQLite y se comprueba con `PRAGMA integrity_check`:

```powershell
python -m app.backup create
python -m app.backup verify "backups/tablio-AAAAMMDDTHHMMSSZ-XXXXXXXX.sqlite3"
python -m app.backup status --max-age-hours 36
```

En Docker, el servicio `backup` crea una copia al iniciar y luego cada 24 horas. Conserva 30 días en un volumen separado de la base. El comando `status` y el healthcheck del servicio comprueban que la última copia tenga menos de 36 horas y pase `integrity_check`. Esto protege contra fallos de la base y errores operativos locales, pero **no contra la pérdida del servidor**. Todavía falta elegir un destino externo, cifrar las copias antes de enviarlas, automatizar el traslado y probar una restauración desde ese destino. Las copias contienen usuarios y datos de todas las organizaciones; solo operadores autorizados deben acceder a ellas.

Para restaurar en local, detené Tablio y ejecutá:

```powershell
python -m app.backup restore "backups/NOMBRE.sqlite3" --force
```

El comando verifica la copia, crea una copia previa de la base vigente y reemplaza el archivo de forma atómica. Volvé a iniciar el servidor y comprobá el acceso y los módulos. En Docker, detené `app` y `backup`, luego ejecutá:

```sh
docker compose stop app backup
docker compose --profile maintenance run --rm restore /backups/NOMBRE.sqlite3 --force
docker compose up -d app backup
```

## HTTPS cuando haya dominio y servidor

Requisitos: servidor con Docker Compose, DNS A/AAAA del dominio apuntando al servidor, y puertos 80 y 443 accesibles. Copiá `.env.example` a `.env` y definí `TABLIO_DOMAIN` con el dominio real. No uses el dominio de ejemplo. Luego:

```sh
docker compose up -d --build
docker compose ps
```

Caddy publica únicamente 80/443, obtiene y renueva el certificado TLS para el dominio configurado y envía las solicitudes a la app por la red interna de Compose. La app usa cookies `Secure` y rechaza orígenes distintos de `https://<dominio>`. SQLite, XLSX temporales y backups viven en volúmenes sin puertos públicos. La app se niega a escuchar fuera de `127.0.0.1` si faltan las variables de HTTPS. Verificá en el dominio real que HTTP redirija a HTTPS, que el certificado sea válido y que el login funcione antes de cargar datos reales.

La imagen se construyó localmente, Caddy aceptó el Caddyfile y los servicios `app` y `backup` funcionaron en un proyecto Docker aislado. No se ha probado aún la obtención de certificados en un servidor real. Después del primer despliegue se requieren pruebas de restauración, monitoreo de backups, registro de errores y revisión de seguridad de la infraestructura.
