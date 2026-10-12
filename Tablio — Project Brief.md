# TABLIO
### De planilla a sistema

## 1. Propósito de este documento

Este documento constituye el contexto maestro inicial de **Tablio**.

Debe utilizarse como fuente de verdad para las decisiones de producto, diseño y arquitectura durante las primeras etapas del proyecto.

Las decisiones aquí establecidas pueden evolucionar, pero no deben modificarse arbitrariamente. Cuando una decisión importante cambie, deberá documentarse junto con su justificación.

---

# 2. Visión

**Tablio transforma las planillas que una organización ya utiliza en sistemas web de gestión simples, intuitivos y seguros.**

El objetivo no es crear otro ERP genérico ni obligar al usuario a abandonar inmediatamente Excel.

El objetivo es reducir al mínimo la distancia entre:

**“Así administro mi negocio actualmente”**

y

**“Tengo un sistema de gestión.”**

La planilla existente constituye el punto de partida.

```text
Excel
  ↓
Análisis
  ↓
Interpretación de estructura
  ↓
Validación humana
  ↓
Importación
  ↓
Aplicación web
```

Concepto central:

> **No abandones tu planilla. Evolucionala.**

---

# 3. Origen del problema

Tablio nace a partir de observar el funcionamiento de pequeñas organizaciones, inicialmente en una ciudad argentina de aproximadamente 12.000 habitantes.

Existe una gran cantidad de:

- PyMEs.
- Comercios.
- Emprendimientos.
- Profesionales.
- Clubes.
- Instituciones.
- Pequeñas industrias.

Muchas de estas organizaciones poseen cierto grado de digitalización, pero su gestión continúa dependiendo fundamentalmente de archivos Excel.

Ejemplos:

```text
clientes.xlsx
stock.xlsx
ventas.xlsx
socios.xlsx
cuotas.xlsx
proveedores.xlsx
mantenimiento.xlsx
pedidos.xlsx
```

Estas planillas pueden haber evolucionado durante años y contener una parte importante del conocimiento operativo de la organización.

El problema no es necesariamente que Excel sea una mala herramienta.

El problema aparece cuando una planilla comienza a funcionar como si fuera una base de datos o un sistema de gestión.

Surgen entonces problemas relacionados con:

- duplicación de archivos;
- modificaciones accidentales;
- fórmulas rotas;
- falta de permisos;
- ausencia de trazabilidad;
- dificultad para trabajar simultáneamente;
- dificultad de utilización desde dispositivos móviles;
- información duplicada;
- búsquedas manuales;
- dependencia de una persona que conoce la planilla;
- ausencia de validaciones;
- backups deficientes;
- dificultad para obtener indicadores.

---

# 4. Contexto humano

Este aspecto es fundamental para el diseño de Tablio.

En ciudades pequeñas y organizaciones tradicionales existe una relación muy directa entre proveedor y cliente.

La adopción de un nuevo software puede generar resistencia.

Un comerciante que utilizó durante años una determinada planilla puede no querer:

- aprender un ERP;
- migrar manualmente sus datos;
- modificar completamente su metodología;
- depender de un sistema que no comprende;
- quedar encerrado en una plataforma.

Por esta razón, Tablio no debe presentarse como:

> “Abandoná Excel y aprendé este sistema.”

Debe presentarse como:

> **“Mostrame cómo trabajás actualmente y transformemos eso en algo mejor.”**

La **baja barrera de adopción** es una característica central del producto.

---

# 5. Propuesta de valor

El usuario entrega o importa la planilla que ya utiliza.

Tablio analiza su estructura y propone una aplicación basada en ella.

Por ejemplo:

```text
clientes.xlsx

ID
Nombre
DNI
Teléfono
Dirección
Saldo
Última compra
```

podría convertirse en un módulo:

```text
CLIENTES

Buscar...

Juan Pérez
Teléfono: ...
Saldo: $125.000
Última compra: 02/09/2026

[Ver] [Editar]
```

La información permanece conceptualmente familiar para el usuario, pero ahora dispone de las ventajas propias de una aplicación.

Una posible forma de expresar la propuesta de valor es:

> **“Tu negocio ya tiene los datos. Tablio los convierte en un sistema.”**

---

# 6. Tablio NO es

Es importante establecer explícitamente qué no se pretende construir inicialmente.

Tablio no es:

- un clon web de Excel;
- un visualizador de archivos XLSX;
- un ERP tradicional;
- un constructor genérico de sitios web;
- un reemplazo completo de Excel;
- una herramienta no-code de propósito universal;
- un generador arbitrario de código mediante IA.

Tablio utiliza la estructura y los datos existentes para generar una **experiencia de gestión adaptada al usuario**.

---

# 7. Concepto técnico fundamental

La aplicación no debería generar necesariamente un proyecto web independiente por cada Excel.

La arquitectura debe explorar preferentemente un modelo de **aplicación dinámica basada en metadatos**.

Conceptualmente:

```text
              PLANILLA
                 │
                 ▼
          Excel Analyzer
                 │
                 ▼
       Application Schema
                 │
                 ▼
        Schema Validator
                 │
                 ▼
       Confirmación humana
                 │
                 ▼
           Data Importer
                 │
                 ▼
        Dynamic App Engine
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
    Clientes   Ventas    Stock
       │         │         │
       └─────────┼─────────┘
                 ▼
            Base de datos
```

Esto permitiría que una única plataforma Tablio pueda representar múltiples sistemas diferentes sin tener que desarrollar y desplegar una aplicación independiente para cada organización.

---

# 8. Application Schema

Uno de los componentes más importantes de Tablio será una representación intermedia de la aplicación.

Por ejemplo:

```json
{
  "entity": "Cliente",
  "fields": [
    {
      "name": "Nombre",
      "type": "text",
      "required": true
    },
    {
      "name": "Telefono",
      "type": "phone"
    },
    {
      "name": "Saldo",
      "type": "currency"
    },
    {
      "name": "UltimaCompra",
      "type": "date"
    }
  ]
}
```

El Excel Analyzer deberá inferir progresivamente:

- entidades;
- columnas;
- tipos de datos;
- campos obligatorios;
- identificadores;
- posibles relaciones;
- valores enumerados;
- fechas;
- importes;
- teléfonos;
- estados;
- observaciones.

La inferencia nunca debe considerarse infalible.

---

# 9. Principio Human-in-the-loop

Una decisión fundamental del proyecto es **no intentar automatizar completamente la interpretación de cualquier Excel en la primera versión**.

Tablio propone.

El usuario o implementador confirma.

Ejemplo:

```text
Detectamos 4 hojas:

✓ Clientes        → Entidad
✓ Productos       → Entidad
✓ Ventas          → Entidad
? Resumen 2026    → ¿Dashboard / ignorar?

Posibles relaciones:

Ventas.Cliente
       ↓
Clientes.Nombre

Ventas.Producto
       ↓
Productos.Codigo
```

El usuario podrá aceptar, rechazar o modificar estas interpretaciones antes de realizar la importación definitiva.

---

# 10. Conversión de tipos

Tablio deberá transformar conceptos propios de una planilla en componentes apropiados de una aplicación.

Ejemplos:

```text
Excel                    Aplicación

Fecha             →      Date picker
Sí / No           →      Checkbox / switch
Estado            →      Select
Precio            →      Currency
Teléfono          →      Phone
Observaciones     →      Textarea
Cliente           →      Posible relación
Producto          →      Posible relación
Email             →      Email
Porcentaje        →      Percentage
```

El objetivo no es simplemente mostrar celdas en HTML.

El objetivo es **interpretar semánticamente la información**.

---

# 11. Experiencia móvil

Tablio deberá diseñarse considerando seriamente dispositivos móviles.

Un usuario puede no valorar conceptos técnicos como integridad referencial, RBAC o normalización de datos.

Sí puede valorar inmediatamente:

> **“Puedo consultar desde el teléfono cuánto me debe un cliente.”**

Ejemplo:

```text
MI NEGOCIO

Ventas de hoy
$845.300

Pendiente de cobro
$1.240.000

Stock bajo
8 productos

Últimos movimientos
────────────────────
Juan Pérez       $45.000
Empresa X        $82.500
María López      $21.000
```

Por lo tanto, la experiencia deberá ser responsive y especialmente cómoda para operaciones frecuentes desde teléfonos.

---

# 12. Importación y exportación

Tablio no debe intentar encerrar los datos del usuario.

Principio:

> **Los datos pertenecen al cliente.**

Debe existir:

```text
Excel
   ↓
Importar
   ↓
Tablio
   ↓
Trabajar
   ↓
Exportar
   ↓
Excel
```

Esto tiene beneficios técnicos y comerciales.

Reduce el miedo a adoptar la plataforma porque el usuario sabe que puede recuperar su información.

---

# 13. MVP

La primera versión debe mantenerse deliberadamente pequeña.

Objetivo:

> **Demostrar que una planilla real puede convertirse rápidamente en una aplicación web útil.**

Flujo inicial:

```text
1. Crear organización

2. Crear aplicación

3. Subir Excel

4. Analizar hojas

5. Detectar columnas

6. Inferir tipos

7. Mostrar interpretación

8. Permitir correcciones

9. Confirmar estructura

10. Importar información

11. Generar módulos dinámicos

12. CRUD

13. Búsqueda

14. Filtros

15. Usuarios

16. Permisos básicos

17. Exportación a Excel
```

---

# 14. Lo que NO debe incluir el MVP

Evitar inicialmente:

- IA generativa compleja;
- automatizaciones avanzadas;
- integraciones contables;
- facturación electrónica;
- WhatsApp;
- dashboards generados por IA;
- generación automática de relaciones complejas;
- workflows empresariales;
- marketplace;
- plugins;
- aplicaciones móviles nativas;
- personalización visual extrema;
- soporte para todos los formatos posibles.

Primero debe funcionar extraordinariamente bien:

> **Excel → estructura → datos → aplicación usable.**

---

# 15. Usuarios objetivo iniciales

Los primeros casos de uso deben estudiarse en organizaciones pequeñas.

### Comercio

```text
Productos
Clientes
Ventas
Proveedores
```

### Taller

```text
Clientes
Vehículos
Reparaciones
Repuestos
```

### Club

```text
Socios
Cuotas
Actividades
Pagos
```

### Profesional

```text
Clientes
Turnos
Servicios
Pagos
```

### Distribuidora

```text
Clientes
Productos
Pedidos
Entregas
```

### Pequeña industria

```text
Productos
Producción
Stock
Mantenimiento
Proveedores
```

Tablio no debería necesitar conocer previamente cada sector.

Debe interpretar su estructura.

---

# 16. Estrategia de validación

Antes de desarrollar excesivamente el producto deberán conseguirse ejemplos reales de planillas utilizadas por organizaciones.

No preguntar principalmente:

> “¿Usarías una aplicación que convierte Excel en software?”

Preguntar:

> **“¿Me podés mostrar cómo administrás actualmente el negocio?”**

Analizar entre aproximadamente 5 y 10 casos reales puede revelar patrones importantes.

Aspectos a observar:

- cantidad de hojas;
- cantidad de registros;
- fórmulas;
- relaciones implícitas;
- columnas repetidas;
- colores utilizados como información;
- comentarios;
- celdas combinadas;
- hojas de resumen;
- campos utilizados como identificadores;
- errores frecuentes;
- tareas realizadas manualmente;
- información consultada diariamente.

La arquitectura deberá evolucionar basándose en problemas reales y no solamente en ejemplos artificiales.

---

# 17. Filosofía de desarrollo

Tablio debe priorizar:

1. Simplicidad.
2. Seguridad.
3. Mantenibilidad.
4. Experiencia de usuario.
5. Baja barrera de adopción.
6. Propiedad de los datos.
7. Automatización progresiva.
8. Arquitectura preparada para crecer sin sobreingeniería inicial.

Evitar construir infraestructura que todavía no sea necesaria.

---

# 18. IA

La inteligencia artificial puede formar parte importante de Tablio en versiones posteriores, pero no debe ser requisito para demostrar el concepto.

Una arquitectura futura podría ser:

```text
Excel
   ↓
Análisis determinístico
   ↓
Schema preliminar
   ↓
IA
   ↓
Interpretación semántica
   ↓
Schema propuesto
   ↓
Validación humana
   ↓
Dynamic App Engine
```

La IA podría eventualmente detectar que:

```text
Cli.
Cliente
Nombre Cliente
Razón Social
```

representan conceptos relacionados.

También podría interpretar instrucciones como:

> “Esta hoja contiene los clientes y esta otra las compras que realizó cada uno.”

Pero las decisiones estructurales importantes deben ser verificables.

Principio:

> **La IA puede interpretar y proponer. El motor de Tablio debe ejecutar de manera determinística.**

---

# 19. Evolución potencial

## V0 — Proof of Concept

Un Excel controlado.

```text
Excel
↓
Parser
↓
Schema
↓
CRUD dinámico
```

El objetivo es comprobar la viabilidad técnica del núcleo de Tablio.

## V1 — MVP

Importación real + configuración + aplicación dinámica.

## V2 — Relaciones

Detección y configuración de relaciones entre entidades.

## V3 — Inteligencia de negocio

Dashboards, indicadores y reportes.

## V4 — Automatizaciones

Alertas, vencimientos, notificaciones y workflows.

## V5 — AI Assistant

Interpretación semántica avanzada y configuración mediante lenguaje natural.

## V6 — Ecosistema

Templates sectoriales, módulos reutilizables e integraciones.

---

# 20. Modelo comercial — pendiente de validar

No asumir todavía un modelo definitivo.

Posibilidades futuras:

```text
SaaS mensual
```

o:

```text
Implementación inicial
+
abono mensual
```

Para mercados pequeños y tradicionales puede ser particularmente interesante un modelo híbrido:

```text
Digitalización / configuración inicial
            +
      suscripción mensual
```

El servicio humano puede constituir inicialmente una ventaja y no una limitación.

Tablio podría comenzar como un producto acompañado de un servicio de digitalización y progresivamente transformarse en una plataforma cada vez más autoservicio.

---

# 21. Diferenciador

Tablio no debería competir diciendo:

> “Tenemos más funcionalidades que Excel.”

El diferencial es:

> **Partimos de cómo ya trabaja la organización.**

La competencia conceptual no es solamente Excel.

También es:

```text
"No quiero cambiar."

"No tengo tiempo para aprender otro sistema."

"Mi Excel ya funciona."

"Siempre lo hicimos así."
```

Tablio debe hacer que migrar resulte más fácil que continuar acumulando complejidad en la planilla.

---

# 22. Principio fundamental

Toda decisión de producto debe contrastarse con esta pregunta:

> **¿Esto hace más sencilla la transición desde una planilla hacia un sistema de gestión?**

Si una funcionalidad agrega complejidad sin mejorar significativamente esa transición, probablemente no corresponda al MVP.

---

# 23. Documentación del repositorio

A medida que avance el desarrollo mantener:

```text
README.md

PROJECT.md
Visión, problema y alcance.

PLANNING.md
Roadmap, fases y tareas.

ARCHITECTURE.md
Arquitectura técnica.

DATA_MODEL.md
Modelo dinámico y representación de entidades.

DECISIONS.md
Decisiones arquitectónicas/producto importantes.
```

No permitir que conversaciones aisladas con IA reemplacen la documentación persistente del proyecto.

---

# 24. Reglas para asistentes de IA

Al trabajar sobre Tablio:

- No comenzar a generar grandes cantidades de código sin definir previamente la etapa.
- Explicar decisiones arquitectónicas relevantes.
- Priorizar implementaciones simples antes que soluciones excesivamente abstractas.
- Diferenciar claramente MVP de funcionalidades futuras.
- Mantener coherencia con este documento.
- Señalar cuando una decisión contradiga principios previamente establecidos.
- No asumir requisitos empresariales que todavía no hayan sido validados.
- Proponer alternativas cuando existan decisiones técnicas importantes.
- Favorecer desarrollo incremental y verificable.
- Evitar introducir tecnologías solamente porque sean novedosas.
- Evaluar cada abstracción en función de una necesidad concreta.
- Mantener separado el análisis determinístico de Excel de futuras capacidades de IA.
- Diseñar pensando en organizaciones reales con bajo nivel de informatización.

El desarrollador debe comprender las piezas centrales del sistema y conservar control arquitectónico del proyecto.

---

# 25. Identidad inicial

**Nombre:** Tablio

**Concepto:** transformación progresiva de planillas en aplicaciones de gestión.

**Tagline principal:**

> **De planilla a sistema.**

Propuesta de valor resumida:

> **Tu negocio ya tiene los datos. Tablio los convierte en un sistema.**

Otros conceptos que pueden explorarse posteriormente para comunicación comercial:

> **Tu planilla. Tu información. Ahora, tu sistema.**

> **No cambies cómo trabajás. Evolucionalo.**

La identidad visual, logotipo, colores, dominio y branding definitivo deberán definirse posteriormente y no condicionan el Proof of Concept.

---

# 26. Próximo objetivo

Todavía no comenzar la implementación completa.

El próximo paso del proyecto es definir:

1. alcance exacto del Proof of Concept;
2. stack tecnológico;
3. arquitectura;
4. representación del Application Schema;
5. funcionamiento del Excel Analyzer;
6. estrategia para datos dinámicos;
7. estrategia multi-tenant;
8. autenticación y autorización;
9. almacenamiento de archivos;
10. despliegue.

Una vez tomadas esas decisiones se deberá diseñar el primer flujo vertical:

> **Subir un Excel simple → interpretarlo → confirmar su estructura → importar los registros → visualizar y editar esos datos mediante una interfaz web.**

Ese será el primer gran hito técnico de **Tablio**.