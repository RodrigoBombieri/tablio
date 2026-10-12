"""Small, dependency-free XLSX reader/writer for the deliberately narrow V0 format."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DATE_FORMATS = {14, 15, 16, 17, 22, 45, 46, 47}


class SpreadsheetError(ValueError):
    pass


def _column_index(ref: str) -> int:
    result = 0
    for char in re.match(r"[A-Z]+", ref).group(0):
        result = result * 26 + ord(char) - 64
    return result - 1


def _excel_date(value: float, date1904: bool) -> str:
    base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    date = base + timedelta(days=value)
    if date.time().hour or date.time().minute or date.time().second:
        raise SpreadsheetError("La tabla contiene una fecha con hora; usá fechas sin hora.")
    return date.date().isoformat()


def read_workbook(blob: bytes) -> list[dict]:
    if len(blob) > 5 * 1024 * 1024:
        raise SpreadsheetError("El archivo supera 5 MiB.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise SpreadsheetError("El archivo no es un XLSX válido.") from exc
    with archive:
        infos = archive.infolist()
        if sum(item.file_size for item in infos) > 50 * 1024 * 1024:
            raise SpreadsheetError("El archivo descomprimido supera 50 MiB.")
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names:
            raise SpreadsheetError("Falta la estructura principal del XLSX.")
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        props = workbook.find(f"{S}workbookPr")
        date1904 = props is not None and props.get("date1904") in ("1", "true")
        relationships = {}
        rel_path = "xl/_rels/workbook.xml.rels"
        if rel_path in names:
            for rel in ET.fromstring(archive.read(rel_path)):
                target = rel.get("Target", "").lstrip("/")
                relationships[rel.get("Id")] = target if target.startswith("xl/") else "xl/" + target
        strings = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iter(f"{S}t")) for si in root]
        date_styles = set()
        if "xl/styles.xml" in names:
            root = ET.fromstring(archive.read("xl/styles.xml"))
            custom = {}
            for fmt in root.findall(f"{S}numFmts/{S}numFmt"):
                custom[int(fmt.get("numFmtId"))] = fmt.get("formatCode", "")
            cell_xfs = root.find(f"{S}cellXfs")
            if cell_xfs is not None:
                for index, xf in enumerate(cell_xfs):
                    num_id = int(xf.get("numFmtId", "0"))
                    fmt = re.sub(r'"[^\"]*"|\\.', '', custom.get(num_id, "")).lower()
                    if num_id in DATE_FORMATS or (fmt and any(ch in fmt for ch in "dmy") and not any(ch in fmt for ch in "0#")):
                        date_styles.add(index)
        sheets = []
        for sheet in workbook.findall(f"{S}sheets/{S}sheet"):
            path = relationships.get(sheet.get(f"{R}id"))
            if not path or path not in names:
                continue
            root = ET.fromstring(archive.read(path))
            merges = root.find(f"{S}mergeCells")
            if merges is not None and len(merges):
                raise SpreadsheetError(f"La hoja {sheet.get('name')} contiene celdas combinadas.")
            rows = []
            for row in root.findall(f"{S}sheetData/{S}row"):
                number = int(row.get("r", "0"))
                cells = {}
                for cell in row.findall(f"{S}c"):
                    ref = cell.get("r", "")
                    if not re.match(r"^[A-Z]+\d+$", ref):
                        continue
                    col = _column_index(ref)
                    if col >= 30 or number > 5001:
                        raise SpreadsheetError("La tabla supera 30 columnas o 5.000 registros.")
                    formula_node = cell.find(f"{S}f")
                    if formula_node is not None and len(formula_node.text or "") > 500:
                        raise SpreadsheetError(f"Fórmula demasiado larga en {sheet.get('name')}!{ref}.")
                    kind = cell.get("t", "n")
                    value_node = cell.find(f"{S}v")
                    if kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(f"{S}t"))
                    elif value_node is None or value_node.text is None:
                        value = None
                    elif kind == "s":
                        value = strings[int(value_node.text)]
                    elif kind == "b":
                        value = value_node.text == "1"
                    elif kind in ("str", "e"):
                        value = value_node.text
                    else:
                        raw = value_node.text
                        if int(cell.get("s", "0")) in date_styles:
                            value = _excel_date(float(raw), date1904)
                        else:
                            value = float(raw) if any(c in raw.lower() for c in (".", "e")) else int(raw)
                    cells[col] = {"formula": "=" + (formula_node.text or ""), "cached": value} if formula_node is not None else value
                if cells:
                    rows.append({"number": number, "cells": cells})
            sheets.append({"name": sheet.get("name"), "rows": rows})
        if not sheets:
            raise SpreadsheetError("El libro no contiene hojas con datos.")
        return sheets


def _col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def write_workbook(sheet_name: str, headers: list[str], rows: list[list], types: list[str] | None = None, formulas: dict[int, str] | None = None, field_columns: dict[str, int] | None = None) -> bytes:
    """Export typed values and supported computed columns."""
    from .formulas import excel_formula
    formulas = formulas or {}
    def cell_xml(value, address, kind="text", formula=None):
        if formula and value is not None:
            return f'<c r="{address}"><f>{escape(formula)}</f><v>{escape(str(value))}</v></c>'
        if value is None:
            return ""
        if isinstance(value, bool):
            return f'<c r="{address}" t="b"><v>{1 if value else 0}</v></c>'
        if kind == "date":
            serial = (date.fromisoformat(str(value)) - date(1899, 12, 30)).days
            return f'<c r="{address}" s="1"><v>{serial}</v></c>'
        if kind in ("integer", "decimal", "currency"):
            return f'<c r="{address}"><v>{value}</v></c>'
        if isinstance(value, (int, float)):
            return f'<c r="{address}"><v>{value}</v></c>'
        # Inline strings keep identifiers, decimal precision and user text intact.
        return f'<c r="{address}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'

    xml_rows = []
    for row_num, values in enumerate([headers] + rows, 1):
        columns = field_columns or {f"f{i+1}": i for i in range(len(headers))}
        xml_rows.append(f'<row r="{row_num}">' + "".join(cell_xml(value, f"{_col_name(i)}{row_num}", types[i-1] if types and row_num > 1 else "text", excel_formula(formulas[i-1], row_num, columns) if row_num > 1 and i-1 in formulas else None) for i, value in enumerate(values, 1)) + '</row>')
    sheet_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + f'<worksheet xmlns="{S[1:-1]}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    workbook_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + f'<workbook xmlns="{S[1:-1]}" xmlns:r="{R[1:-1]}"><sheets><sheet name={quoteattr(sheet_name[:31])} sheetId="1" r:id="rId1"/></sheets></workbook>'
    styles_xml = '<?xml version="1.0" encoding="UTF-8"?>' + f'<styleSheet xmlns="{S[1:-1]}"><fonts count="1"><font/></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>'
    types_xml = '<?xml version="1.0" encoding="UTF-8"?>' + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8"?>' + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    wb_rels = '<?xml version="1.0" encoding="UTF-8"?>' + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in {'[Content_Types].xml': types_xml, '_rels/.rels': rels, 'xl/workbook.xml': workbook_xml, 'xl/_rels/workbook.xml.rels': wb_rels, 'xl/worksheets/sheet1.xml': sheet_xml, 'xl/styles.xml': styles_xml}.items():
            archive.writestr(name, content)
    return output.getvalue()
