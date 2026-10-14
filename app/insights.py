"""Small, explainable checks for imported modules. No automatic external actions."""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date


def _key(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()


def _field(fields, *needles):
    return next((f for term in needles for f in fields if term in _key(f["label"])), None)


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def stock_field(fields):
    field = _field(fields, "stock actual", "existencia", "cantidad disponible")
    if field: return field
    return next((f for f in fields if "stock" in _key(f["label"]) and "minim" not in _key(f["label"])), None)


def analyze(schema, records, today=None, recent_sales=None):
    today = today or date.today()
    fields = schema["fields"]
    template = schema.get("template", "general")
    primary = schema["primaryFieldId"]
    values = [r["values"] for r in records]
    groups = []

    def add(code, title, explanation, matched):
        if matched:
            groups.append({"code": code, "title": title, "count": len(matched),
                           "explanation": explanation,
                           "examples": [str(item.get(primary) or "Sin nombre") for item in matched[:5]]})

    expiry = _field(fields, "vencimiento", "vence")
    if expiry:
        expired = []
        for item in values:
            raw = item.get(expiry["id"])
            if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                try:
                    if date.fromisoformat(raw) < today: expired.append(item)
                except ValueError:
                    pass
        add("expired", "Fechas de vencimiento pasadas",
            "Se compararon fechas válidas con el día de hoy. Revisá cada caso antes de actuar.", expired)

    if template == "habilitaciones":
        identifier = _field(fields, "cuit")
        if identifier:
            add("missing_id", "Registros sin CUIT",
                "Falta el CUIT en la planilla de origen; completalo si corresponde.",
                [item for item in values if not str(item.get(identifier["id"]) or "").strip()])

    stock = stock_field(fields)
    minimum = _field(fields, "stock minimo", "minimo de stock", "punto de pedido")
    sales = _field(fields, "ventas 30 dias", "vendidas 30 dias")
    lead = _field(fields, "dias de entrega", "plazo de entrega")
    orders = []
    low_items = []
    if stock and minimum and stock["id"] != minimum["id"]:
        for record in records:
            item=record["values"]
            current, low = _number(item.get(stock["id"])), _number(item.get(minimum["id"]))
            if current is None or low is None or low < 0 or current > low:
                continue
            thirty = (recent_sales or {}).get(record.get("id"))
            if thirty is None: thirty = _number(item.get(sales["id"])) if sales else None
            days = _number(item.get(lead["id"])) if lead else None
            target = max(low * 2, low + 1)
            reason = f"Hay {current:g}; el mínimo indicado es {low:g}."
            if thirty is not None and days is not None and thirty >= 0 and days >= 0:
                target = max(target, math.ceil(thirty / 30 * days * 1.25))
                reason += f" Se consideraron {thirty:g} ventas en 30 días y {days:g} días de entrega."
            quantity = max(1, math.ceil(target - current))
            low_items.append(item)
            orders.append({"recordId": record.get("id"), "name": str(item.get(primary) or "Sin nombre"),
                           "current": current, "minimum": low, "suggestedQuantity": quantity,
                           "reason": reason + " Revisá la cantidad antes de pedir."})
        add("low_stock", "Productos para reponer", "El stock actual llegó al mínimo configurado.", low_items)

    guidance = {
        "habilitaciones": "Revisá vencimientos y datos faltantes. Los estados escritos como texto no se interpretan como fechas.",
        "minimercado": "Para sugerir compras, agregá campos numéricos «Stock actual» y «Stock mínimo». Opcionalmente, «Ventas 30 días» y «Días de entrega».",
        "corralon": "Para sugerir compras por material, agregá «Stock actual» y «Stock mínimo». Podés sumar «Ventas 30 días» y «Días de entrega».",
        "general": "Elegí una plantilla del rubro para recibir indicaciones adaptadas a tus datos.",
    }[template]
    return {"template": template, "groups": groups, "orders": orders[:100],
            "orderCount": len(orders), "guidance": guidance,
            "canSuggestOrders": bool(stock and minimum),
            "stockFieldId": stock["id"] if stock and stock.get("type") in {"integer","decimal","currency"} and not stock.get("formula") else None}
