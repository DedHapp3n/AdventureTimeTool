import json
import os


class SheetTab:
    def __init__(self, sheet_name, sheet, parser, sheet_tabs_provider):
        self.sheet_name = sheet_name
        self.sheet = sheet
        self.parser = parser
        self.sheet_tabs_provider = sheet_tabs_provider
        self.cell_cache = {self.sheet_name: {}}
        self._build_cell_cache()

    def _build_cell_cache(self):
        for row in self.sheet.iter_rows():
            for cell in row:
                raw_value = cell.value
                formula = raw_value if isinstance(raw_value, str) and raw_value.startswith("=") else None
                references = self.parser.extract_references(formula) if formula else []
                if raw_value is None and formula is None and not references:
                    continue
                self.cell_cache[self.sheet_name][cell.coordinate] = {
                    "value": raw_value,
                    "formula": formula,
                    "references": references,
                }

    def evaluate_formulas(self):
        for cell_ref, cell_data in self.cell_cache[self.sheet_name].items():
            formula = cell_data.get("formula")
            if formula:
                result = self.parser.evaluate_formula(
                    self.sheet_name,
                    formula,
                    self.get_cell_value_for_parser,
                    cell_ref=cell_ref,
                )
                if result != "Nicht unterstützt":
                    cell_data["value"] = result

    def get_cell_value_for_parser(self, sheet_name, cell_ref):
        sheet_tabs = self.sheet_tabs_provider()
        target_tab = sheet_tabs.get(sheet_name)
        if target_tab is None:
            return None

        cell_data = target_tab.cell_cache.get(sheet_name, {}).get(cell_ref)
        if not cell_data:
            return None
        if cell_data.get("formula"):
            return cell_data["formula"]
        return cell_data.get("value")

    def get_data(self):
        data = []
        for row in self.sheet.iter_rows():
            row_data = []
            for cell in row:
                cached = self.cell_cache[self.sheet_name].get(cell.coordinate, {})
                row_data.append(cached.get("value"))
            data.append(row_data)
        return data

    def get_formulas(self):
        formulas = {}
        for cell_ref, cell_data in self.cell_cache[self.sheet_name].items():
            if cell_data.get("formula"):
                formulas[cell_ref] = cell_data["formula"]
        return formulas

    def get_cell_cache(self):
        return self.cell_cache

    def update_formula(self, cell, formula):
        if cell not in self.cell_cache[self.sheet_name]:
            self.cell_cache[self.sheet_name][cell] = {"value": None, "formula": None, "references": []}
        self.cell_cache[self.sheet_name][cell]["formula"] = formula
        self.cell_cache[self.sheet_name][cell]["references"] = self.parser.extract_references(formula)

    def export_to_json(self, filepath):
        all_tabs = self.sheet_tabs_provider()
        export_data = {}

        for tab in all_tabs.values():
            for sheet_name, sheet_cache in tab.get_cell_cache().items():
                export_data[sheet_name] = {}
                for cell_ref, cell_data in sheet_cache.items():
                    export_data[sheet_name][cell_ref] = {
                        "value": self._to_serializable(cell_data.get("value")),
                        "formula": self._to_serializable(cell_data.get("formula")),
                        "references": [
                            self._to_serializable(ref) for ref in cell_data.get("references", [])
                        ],
                    }

        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

    def _to_serializable(self, value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)
