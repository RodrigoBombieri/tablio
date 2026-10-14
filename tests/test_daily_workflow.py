import unittest
import tempfile
from pathlib import Path

from app.core import convert_rows, infer_sheet, validate_schema
from app.insights import analyze
from app import store


class DailyWorkflowTests(unittest.TestCase):
    def test_duplicate_and_untitled_columns_can_be_excluded_independently(self):
        sheet = {"name": "Prueba", "mergedRanges": [], "rows": [
            {"number": 1, "cells": {0: "Producto", 1: "Cálculo", 2: "Cálculo"}},
            {"number": 2, "cells": {0: "Arroz", 1: {"formula": "=A3", "cached": None},
                                    2: {"formula": "=A3", "cached": None}, 3: "nota"}},
        ]}
        preview = infer_sheet(sheet)
        self.assertEqual(len(preview["formulaIssues"]), 2)
        self.assertEqual({issue["column"] for issue in preview["formulaIssues"]}, {2, 3})
        self.assertTrue(preview["fields"][3]["ignored"])
        self.assertNotEqual(preview["fields"][1]["label"], preview["fields"][2]["label"])
        schema = validate_schema({"schemaVersion": 1, "name": "Productos", "template": "minimercado",
                                  "primaryFieldId": "f1", "fields": [{"id": "f1", "label": "Producto",
                                  "type": "text", "required": False, "sourceColumn": 0}]}, preview)
        records, errors = convert_rows(sheet, schema)
        self.assertEqual(len(records), 1)
        self.assertEqual(errors, [])

    def test_replenishment_is_explained_and_requires_stock_fields(self):
        schema = {"template": "corralon", "primaryFieldId": "f1", "fields": [
            {"id": "f1", "label": "Material"}, {"id": "f2", "label": "Stock mínimo"},
            {"id": "f3", "label": "Stock actual"}, {"id": "f4", "label": "Ventas 30 días"},
            {"id": "f5", "label": "Días de entrega"}]}
        report = analyze(schema, [{"values": {"f1": "Cemento", "f2": 5, "f3": 3,
                                               "f4": 60, "f5": 7}}])
        self.assertEqual(report["orderCount"], 1)
        self.assertEqual(report["orders"][0]["suggestedQuantity"], 15)
        self.assertIn("60 ventas", report["orders"][0]["reason"])
        self.assertFalse(analyze({"template": "habilitaciones", "primaryFieldId": "f1",
                                  "fields": [{"id": "f1", "label": "Razón social"}]}, [])
                         ["canSuggestOrders"])

    def test_excel_cached_error_must_be_fixed_or_excluded(self):
        sheet = {"name": "Vencimientos", "rows": [
            {"number": 1, "cells": {0: "Comercio", 1: "Vencimiento"}},
            {"number": 2, "cells": {0: "Ejemplo", 1: {"formula": "=DATE(YEAR(A2)+5,1,1)", "cached": "#VALUE!"}}},
        ]}
        preview = infer_sheet(sheet)
        self.assertEqual(len(preview["formulaIssues"]), 1)
        schema = validate_schema({"schemaVersion": 1, "name": "Vencimientos", "primaryFieldId": "f1",
                                  "fields": [{"id": "f1", "label": "Comercio", "type": "text", "required": False, "sourceColumn": 0},
                                             {"id": "f2", "label": "Vencimiento", "type": "text", "required": False, "sourceColumn": 1}]}, preview)
        _, errors = convert_rows(sheet, schema)
        self.assertEqual([e["code"] for e in errors], ["INVALID_FORMULA"])
        sheet["rows"][1]["cells"][1] = "15/10/2029"
        _, errors = convert_rows(sheet, schema)
        self.assertEqual(errors, [])

    def test_initial_import_can_be_undone_only_before_edits(self):
        prior = store.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as folder:
                store.DB_PATH = Path(folder) / "test.sqlite3"
                store.initialize()
                actor, org = store.bootstrap_owner("owner@example.test", "Dueño", "contraseña-larga-123", "Comercio")
                schema = {"schemaVersion": 1, "revision": 1, "name": "Productos", "template": "minimercado",
                          "primaryFieldId": "f1", "fields": [{"id": "f1", "label": "Producto", "type": "text",
                          "required": False, "sourceColumn": 0}]}
                first = store.import_records(org, "first", schema, [{"f1": "Arroz"}], actor)
                self.assertTrue(store.get_module(org, first)["canUndoImport"])
                store.undo_import(org, first, actor)
                self.assertIsNone(store.get_module(org, first))
                second = store.import_records(org, "second", schema, [{"f1": "Arroz"}], actor)
                store.create_record(org, second, {"f1": "Fideos"}, actor)
                self.assertFalse(store.get_module(org, second)["canUndoImport"])
                with self.assertRaises(ValueError):
                    store.undo_import(org, second, actor)
        finally:
            store.DB_PATH = prior

    def test_sale_and_receipt_update_stock_and_sales_history(self):
        prior = store.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as folder:
                store.DB_PATH = Path(folder) / "test.sqlite3"
                store.initialize()
                actor, org = store.bootstrap_owner("owner@example.test", "Dueño", "contraseña-larga-123", "Comercio")
                schema = {"schemaVersion": 1, "revision": 1, "name": "Productos", "template": "minimercado",
                          "primaryFieldId": "f1", "fields": [
                              {"id": "f1", "label": "Producto", "type": "text", "required": False, "sourceColumn": 0},
                              {"id": "f2", "label": "Stock actual", "type": "decimal", "scale": 2, "required": False, "sourceColumn": 1},
                              {"id": "f3", "label": "Stock mínimo", "type": "decimal", "scale": 2, "required": False, "sourceColumn": 2},
                              {"id": "f4", "label": "Días de entrega", "type": "integer", "required": False, "sourceColumn": 3}]}
                mid = store.import_records(org, "products", schema, [{"f1": "Arroz", "f2": "5.00",
                                                               "f3": "3.00", "f4": 7}], actor)
                rid = store.record_list(org, mid)[0]["id"]
                self.assertEqual(store.record_stock_movement(org, mid, rid, "sale", "2", actor)["stock"], "3.00")
                self.assertFalse(store.get_module(org, mid)["canUndoImport"])
                self.assertEqual(store.recent_sales(org, mid)[rid], 2)
                self.assertEqual(analyze(schema, store.record_list(org, mid), recent_sales=store.recent_sales(org, mid))["orderCount"], 1)
                self.assertEqual(store.record_stock_movement(org, mid, rid, "receipt", "1", actor)["stock"], "4.00")
                with self.assertRaises(ValueError): store.record_stock_movement(org, mid, rid, "sale", "10", actor)
        finally:
            store.DB_PATH = prior


if __name__ == "__main__":
    unittest.main()
