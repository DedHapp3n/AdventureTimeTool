import json
import os
import re

from openpyxl import load_workbook

class DataLoader:
    def __init__(self):
        self.workbook = None
        self.cell_cache = {}
        self.load_cache_from_json()

    def load_file(self, file_path):
        self.workbook = load_workbook(file_path, data_only=False)
        self._build_cache()
        self.save_cache_to_json()
        print("[CACHE] built:", len(self.cell_cache))

    def get_sheets(self):
        if self.cell_cache:
            return list(self.cell_cache.keys())
        if self.workbook is not None:
            return self.workbook.sheetnames
        return []

    def get_sheet_data(self, sheet_name):
        sheet_cache = self.cell_cache.get(sheet_name, {})
        if not sheet_cache:
            return []

        max_row = 0
        max_col = 0
        for cell_ref in sheet_cache.keys():
            row, col = self._cell_ref_to_row_col(cell_ref)
            if row > max_row:
                max_row = row
            if col > max_col:
                max_col = col

        data = []
        for row_index in range(1, max_row + 1):
            row_data = []
            for col_index in range(1, max_col + 1):
                cell_ref = self._col_to_letters(col_index) + str(row_index)
                cell_data = sheet_cache.get(cell_ref)
                row_data.append(cell_data.get("value") if cell_data else None)
            data.append(row_data)

        return data

    def get_sheet_object(self, sheet_name):
        if self.workbook is None:
            return None
        return self.workbook[sheet_name]

    def get_cell(self, sheet, cell):
        sheet_cache = self.cell_cache.get(sheet, {})
        cell_data = sheet_cache.get(cell)
        if not cell_data:
            return None
        return cell_data.get("value")

    def save_cache_to_json(self, path="data/character_cache.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._to_serializable(self.cell_cache), f, ensure_ascii=False, indent=2)

    def load_cache_from_json(self, path="data/character_cache.json"):
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.cell_cache = loaded if isinstance(loaded, dict) else {}
            return True
        except Exception:
            self.cell_cache = {}
            return False

    def _build_cache(self):
        self.cell_cache = {}
        for sheet_name in self.workbook.sheetnames:
            sheet = self.workbook[sheet_name]
            self.cell_cache[sheet_name] = {}
            for row in sheet.iter_rows():
                for cell in row:
                    raw_value = cell.value
                    formula = raw_value if isinstance(raw_value, str) and raw_value.startswith("=") else None
                    references = self._extract_references(formula) if formula else []
                    if raw_value is None and formula is None and not references:
                        continue
                    self.cell_cache[sheet_name][cell.coordinate] = {
                        "value": raw_value,
                        "formula": formula,
                        "references": references,
                    }

    def _extract_references(self, formula):
        refs = re.findall(r"[A-Za-z]+[0-9]+", formula or "")
        unique = []
        seen = set()
        for ref in refs:
            ref_up = ref.upper()
            if ref_up not in seen:
                seen.add(ref_up)
                unique.append(ref_up)
        return unique

    def _cell_ref_to_row_col(self, cell_ref):
        match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", cell_ref)
        if not match:
            return (0, 0)
        letters = match.group(1).upper()
        row = int(match.group(2))
        col = 0
        for letter in letters:
            col = col * 26 + (ord(letter) - ord("A") + 1)
        return (row, col)

    def _col_to_letters(self, col):
        letters = ""
        number = col
        while number > 0:
            number, remainder = divmod(number - 1, 26)
            letters = chr(ord("A") + remainder) + letters
        return letters

    def _to_serializable(self, value):
        if isinstance(value, dict):
            return {k: self._to_serializable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._to_serializable(v) for v in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)
