"""Schema inference and deterministic record conversion."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .formulas import parse_formula, dependencies, evaluate

TYPES = {"text", "integer", "decimal", "currency", "date", "boolean", "enum"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FormulaEvaluationError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


def error(code, message, row=None, column=None, field=None):
    return {"code": code, "message": message, "row": row, "column": column, "field": field}


def _normalize(value):
    if isinstance(value, dict) and "formula" in value:
        value = value.get("cached")
    return None if value is None or isinstance(value, str) and not value.strip() else value


def infer_sheet(sheet):
    rows = sheet["rows"]
    if not rows or rows[0]["number"] != 1:
        raise ValueError("La primera fila debe contener encabezados.")
    header = rows[0]["cells"]
    if not header:
        raise ValueError("No hay encabezados.")
    last_col = max((max(row["cells"]) for row in rows), default=-1)
    if last_col >= 64:
        raise ValueError("La tabla supera 64 columnas.")
    labels = []
    unnamed = []
    repeated = []
    for col in range(last_col + 1):
        label = str(header.get(col) or "").strip()
        if not label:
            label = f"Sin título ({col + 1})"
            unnamed.append(col)
        if label.casefold() in [item.casefold() for item in labels]:
            repeated.append(col)
            label = f"{label} (columna {col + 1})"
        labels.append(label)
    named_cols = set(range(last_col + 1)) - set(unnamed)
    data_rows = [row for row in rows[1:] if any(_normalize(row["cells"].get(col)) is not None for col in named_cols)]
    if len(data_rows) > 5000:
        raise ValueError("La tabla supera 5.000 registros.")
    fields = []
    for col, label in enumerate(labels):
        values = [_normalize(row["cells"].get(col)) for row in data_rows]
        nonempty = [v for v in values if v is not None]
        name = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode().lower()
        if nonempty and all(isinstance(v, bool) for v in nonempty):
            field_type = "boolean"
        elif nonempty and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nonempty):
            field_type = "integer" if all(float(v).is_integer() for v in nonempty) else "decimal"
        elif nonempty and all(isinstance(v, str) and DATE_RE.fullmatch(v) for v in nonempty):
            field_type = "date"
        else:
            field_type = "text"
        if field_type in ("integer", "decimal") and any(word in name for word in ("precio", "saldo", "importe", "costo")):
            field_type = "currency"
        distinct = list(dict.fromkeys(str(v) for v in nonempty))
        enum_suggestion = field_type == "text" and 2 <= len(distinct) <= 10 and len(distinct) < len(nonempty)
        formulas = [row["cells"].get(col) for row in data_rows if isinstance(row["cells"].get(col), dict)]
        canonical = None
        if formulas:
            for row in data_rows:
                cell = row["cells"].get(col)
                if isinstance(cell, dict):
                    try:
                        canonical, _ = parse_formula(cell["formula"], row["number"], labels)
                        break
                    except ValueError: pass
            if canonical: field_type = "decimal"
        fields.append({"id": f"f{col + 1}", "label": label, "sourceColumn": col, "type": field_type,
                       "required": False, "ignored": col in unnamed, "scale": 2 if field_type == "currency" else 6 if canonical else 3 if field_type == "decimal" else None,
                       "currency": "ARS" if field_type == "currency" else None,
                       "options": distinct if enum_suggestion else [],
                       "enumSuggested": enum_suggestion, "emptyCount": len(values)-len(nonempty),
                       "examples": [str(v) for v in nonempty[:5]], "formula": canonical,
                       "formulaCount": len(formulas) if canonical else 0})
    issues = []
    for row in data_rows:
        for col, cell in row["cells"].items():
            if not isinstance(cell, dict) or "formula" not in cell: continue
            try:
                expression, _ = parse_formula(cell["formula"], row["number"], labels)
                expected = fields[col].get("formula")
                if expected and expression != expected: raise ValueError("La fórmula difiere de la fórmula de esta columna.")
                if isinstance(cell.get("cached"), str) and cell["cached"].startswith(("#REF!", "#DIV/0!", "#VALUE!", "#NUM!", "#NAME?", "#N/A")):
                    raise ValueError(f"Excel informa {cell['cached']} en esta fórmula.")
            except ValueError as exc:
                cached = _normalize(cell)
                excel_error = isinstance(cached, str) and cached.startswith(("#REF!", "#DIV/0!", "#VALUE!", "#NUM!", "#NAME?", "#N/A"))
                if not fields[col].get("formula") and cached is not None and not excel_error:
                    continue
                issues.append({"row": row["number"], "column": col+1, "field": labels[col],
                               "formula": cell["formula"], "message": str(exc)})
    warnings = []
    if unnamed: warnings.append(f"{len(unnamed)} columnas sin título quedaron desmarcadas. Revisalas antes de importar.")
    if repeated: warnings.append(f"{len(repeated)} encabezados repetidos recibieron un nombre distinto.")
    fallback = sum(1 for row in data_rows for col, cell in row["cells"].items()
                   if isinstance(cell, dict) and col < len(fields) and not fields[col].get("formula") and _normalize(cell) is not None)
    if fallback: warnings.append(f"{fallback} fórmulas no compatibles se importarán con su último valor guardado en Excel; no se recalcularán en Tablio.")
    if sheet.get("mergedRanges"): warnings.append(f"La hoja contiene {len(sheet['mergedRanges'])} área(s) combinada(s); revisá esos datos.")
    if not data_rows: warnings.append("La hoja no contiene registros.")
    return {"sheet": sheet["name"], "rowCount": len(data_rows), "fields": fields,
            "formulaIssues": issues, "warnings": warnings, "schemaVersion": 1}


def validate_schema(candidate, source):
    if candidate.get("schemaVersion") != 1:
        raise ValueError("Versión de esquema no admitida.")
    name = str(candidate.get("name", "")).strip()
    if not 1 <= len(name) <= 80:
        raise ValueError("El módulo necesita un nombre de 1 a 80 caracteres.")
    template = candidate.get("template", "general")
    if template not in {"general", "habilitaciones", "minimercado", "corralon"}:
        raise ValueError("Elegí una plantilla válida.")
    fields = candidate.get("fields", [])
    if not isinstance(fields, list) or not 1 <= len(fields) <= 30:
        raise ValueError("El módulo necesita entre 1 y 30 campos.")
    source_cols = {f["sourceColumn"] for f in source["fields"]}
    ids, labels, cols = set(), set(), set()
    clean = []
    for field in fields:
        fid, label, kind = field.get("id"), str(field.get("label", "")).strip(), field.get("type")
        col = field.get("sourceColumn")
        if not isinstance(fid, str) or not re.fullmatch(r"f\d+", fid) or fid in ids or not 1 <= len(label) <= 80 or label.casefold() in labels:
            raise ValueError("Los campos necesitan IDs y etiquetas únicos.")
        if kind not in TYPES or type(field.get("required")) is not bool or type(col) is not int or col not in source_cols or col in cols:
            raise ValueError(f"Configuración inválida en {label}.")
        ids.add(fid); labels.add(label.casefold()); cols.add(col)
        item = {"id": fid, "label": label, "type": kind, "required": field["required"], "sourceColumn": col}
        original = next((f for f in source["fields"] if f["sourceColumn"] == col), None)
        if original and original.get("formulaCount"):
            if kind not in ("integer", "decimal", "currency"):
                raise ValueError(f"La columna calculada {label} debe ser numérica.")
            if original.get("formula"):
                item["formula"] = original["formula"]
        if kind in ("decimal", "currency"):
            scale = field.get("scale")
            if type(scale) is not int or not 0 <= scale <= 6:
                raise ValueError(f"Escala inválida en {label}.")
            item["scale"] = scale
            if kind == "currency": item["currency"] = "ARS"
        if kind == "enum":
            options = field.get("options", [])
            if not isinstance(options, list) or not 1 <= len(options) <= 100 or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 100 for v in options) or len({v.casefold() for v in options}) != len(options):
                raise ValueError(f"Opciones inválidas en {label}.")
            item["options"] = options
        clean.append(item)
    primary = candidate.get("primaryFieldId")
    if primary not in ids:
        raise ValueError("Elegí un campo principal válido.")
    for field in clean:
        if field.get("formula") and not dependencies(field["formula"]).issubset(ids):
            raise ValueError(f"Incluí las columnas referenciadas por {field['label']}.")
    _formula_order(clean)
    return {"schemaVersion": 1, "revision": 1, "name": name, "template": template,
            "primaryFieldId": primary, "fields": clean}


def _formula_order(fields):
    calculated = {f["id"]: f for f in fields if f.get("formula")}
    ordered, visiting = [], set()
    def visit(fid):
        if fid in visiting: raise ValueError("Las fórmulas contienen referencias circulares.")
        if fid in ordered: return
        visiting.add(fid)
        for dep in dependencies(calculated[fid]["formula"]):
            if dep in calculated: visit(dep)
        visiting.remove(fid); ordered.append(fid)
    for fid in calculated: visit(fid)
    return [calculated[fid] for fid in ordered]


def calculate_record(record, schema):
    for field in _formula_order(schema["fields"]):
        try:
            raw = evaluate(field["formula"], record)
            if raw is not None and field["type"] in ("decimal", "currency"):
                raw = str(Decimal(raw).quantize(Decimal(1).scaleb(-field["scale"]), rounding=ROUND_HALF_UP))
            record[field["id"]] = convert(raw, field)
        except (ValueError, InvalidOperation) as exc:
            raise FormulaEvaluationError(field, str(exc)) from exc
    return record


def convert(value, field):
    value = _normalize(value)
    if value is None:
        if field["required"]:
            raise ValueError("Completá este campo obligatorio.")
        return None
    kind = field["type"]
    if kind == "text":
        return str(value)
    if kind == "enum":
        if str(value) not in field["options"]:
            raise ValueError("Elegí una de las opciones permitidas.")
        return str(value)
    if kind == "boolean":
        if isinstance(value, bool): return value
        if isinstance(value, str):
            token = value.strip().casefold()
            if token in ("sí", "si", "true"): return True
            if token in ("no", "false"): return False
        if value in (0, 1): return bool(value)
        raise ValueError("Ingresá Sí o No.")
    if kind == "date":
        if isinstance(value, str):
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d" if DATE_RE.fullmatch(value) else "%d/%m/%Y").date()
                return parsed.isoformat()
            except ValueError: pass
        raise ValueError("Ingresá una fecha válida.")
    if kind in ("integer", "decimal", "currency"):
        if isinstance(value, bool): raise ValueError("Ingresá un número válido.")
        raw = str(value).strip()
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw):
            raise ValueError("Ingresá un número válido con punto decimal.")
        try: num = Decimal(raw)
        except InvalidOperation: raise ValueError("Ingresá un número válido.")
        if kind == "integer":
            if num != num.to_integral_value() or abs(num) > 9007199254740991:
                raise ValueError("Ingresá un número entero dentro del rango admitido.")
            return int(num)
        scale = field["scale"]
        if -num.as_tuple().exponent > scale or len(num.as_tuple().digits) > 15:
            raise ValueError(f"Se admiten hasta {scale} decimales y 15 dígitos.")
        return format(num.quantize(Decimal(1).scaleb(-scale)), f".{scale}f")
    raise ValueError("Tipo no admitido.")


def convert_rows(source_sheet, schema):
    records, errors = [], []
    selected_cols = [f["sourceColumn"] for f in schema["fields"]]
    for row in source_sheet["rows"][1:]:
        if not any(_normalize(row["cells"].get(col)) is not None for col in selected_cols):
            continue
        record = {}
        for field in schema["fields"]:
            if field.get("formula"): continue
            raw = row["cells"].get(field["sourceColumn"])
            if isinstance(raw, dict) and "formula" in raw:
                cached = _normalize(raw)
                if cached is None or (isinstance(cached, str) and cached.startswith(("#REF!", "#DIV/0!", "#VALUE!", "#NUM!", "#NAME?", "#N/A"))):
                    errors.append(error("INVALID_FORMULA", "La fórmula no tiene un valor válido guardado en Excel. Escribí un valor fijo o excluí la columna.",
                                        row["number"], field["sourceColumn"] + 1, field["label"]))
                    continue
            try:
                record[field["id"]] = convert(raw, field)
            except ValueError as exc:
                code = ("REQUIRED_VALUE" if _normalize(raw) is None and field["required"] else
                        "PRECISION_EXCEEDED" if str(exc).startswith("Se admiten") else
                        {"date": "INVALID_DATE", "enum": "INVALID_OPTION",
                         "integer": "INVALID_NUMBER", "decimal": "INVALID_NUMBER", "currency": "INVALID_NUMBER"}.get(field["type"], "INVALID_VALUE"))
                errors.append(error(code, str(exc), row["number"], field["sourceColumn"] + 1, field["label"]))
        for field in schema["fields"]:
            if not field.get("formula"): continue
            raw = row["cells"].get(field["sourceColumn"])
            if isinstance(raw, dict):
                try:
                    header = source_sheet["rows"][0]["cells"]
                    actual, _ = parse_formula(raw["formula"], row["number"], [header[i] for i in range(max(header)+1)])
                    if actual != field["formula"]: raise ValueError("La fórmula difiere de la fórmula de la columna.")
                except ValueError as exc:
                    errors.append(error("INVALID_FORMULA", str(exc), row["number"], field["sourceColumn"]+1, field["label"]))
        if not any(e["row"] == row["number"] for e in errors):
            try: calculate_record(record, schema)
            except FormulaEvaluationError as exc:
                errors.append(error("INVALID_FORMULA", str(exc), row["number"], exc.field["sourceColumn"]+1, exc.field["label"]))
        records.append(record)
    return records, errors


def validate_record(values, schema):
    if not isinstance(values, dict) or not {f["id"] for f in schema["fields"] if not f.get("formula")}.issubset(values) or set(values) - {f["id"] for f in schema["fields"]}:
        raise ValueError("Los campos del registro no coinciden con el módulo.")
    record = {f["id"]: convert(values[f["id"]], f) for f in schema["fields"] if not f.get("formula")}
    return calculate_record(record, schema)
