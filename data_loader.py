import json
import os
import re
from datetime import datetime
from typing import Any

from openpyxl import load_workbook

class DataLoader:
    def __init__(self):
        self.workbook = None
        self.cell_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self.active_cache_path = ""
        self.current_character_name = "unknown_character"
        self.source_file_path = ""
        self.load_cache_from_json()

    def load_file(self, file_path):
        lower_path = str(file_path).lower()
        if lower_path.endswith(".ods"):
            print("[LOAD] ODS not supported:", file_path)
            raise ValueError("ODS wird aktuell nicht unterstützt. Bitte als XLSX exportieren.")
        if not (lower_path.endswith(".xlsx") or lower_path.endswith(".xlsm")):
            raise ValueError("Dateityp nicht unterstützt. Bitte .xlsx oder .xlsm verwenden.")
        self.workbook = load_workbook(file_path, data_only=False)
        self.source_file_path = file_path
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

    def save_cache_to_json(self, path=None):
        if path is None:
            character_name = self._get_character_name_from_cache()
            slug = self.make_character_slug(character_name)
            path = os.path.join("data", "cache", f"{slug}.json")
        else:
            character_name = self._get_character_name_from_cache()

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._to_serializable(self.cell_cache), f, ensure_ascii=False, indent=2)
        self.active_cache_path = path
        self.current_character_name = character_name
        self._write_current_character_metadata(path, character_name)
        print("[CACHE] character:", character_name)
        print("[CACHE] saved character cache:", path)
        print("[CACHE] active:", path)

    def load_cache_from_json(self, path=None):
        if path is None:
            metadata_path = os.path.join("data", "current_character.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    active_cache = metadata.get("active_cache")
                    if isinstance(active_cache, str) and active_cache:
                        path = active_cache
                        self.current_character_name = str(
                            metadata.get("character_name", "unknown_character")
                        )
                        self.source_file_path = str(metadata.get("source_file", ""))
                except Exception:
                    path = None

        if path is None:
            self.cell_cache = {}
            print("[CACHE] no active character cache found")
            return False
        if not os.path.exists(path):
            self.cell_cache = {}
            print("[CACHE] no active character cache found")
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.cell_cache = loaded if isinstance(loaded, dict) else {}
            self.active_cache_path = path
            if not self.current_character_name or self.current_character_name == "unknown_character":
                self.current_character_name = self._get_character_name_from_cache()
            print("[CACHE] active:", path)
            return True
        except Exception:
            self.cell_cache = {}
            print("[CACHE] no active character cache found")
            return False

    def make_character_slug(self, name: str) -> str:
        if not isinstance(name, str):
            return "unknown_character"
        slug = name.strip().lower()
        slug = (
            slug.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        slug = re.sub(r"\s+", "_", slug)
        slug = re.sub(r"[^a-z0-9_]", "", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug if slug else "unknown_character"

    def list_character_caches(self) -> list[dict[str, str]]:
        cache_dir = os.path.join("data", "cache")
        if not os.path.isdir(cache_dir):
            return []

        results: list[dict[str, str]] = []
        for file_name in sorted(os.listdir(cache_dir)):
            if not file_name.lower().endswith(".json"):
                continue
            cache_path = os.path.join(cache_dir, file_name)
            character_name = os.path.splitext(file_name)[0]
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    sheet = payload.get("Charakterbogen", {})
                    if isinstance(sheet, dict):
                        cell_g1 = sheet.get("G1", {})
                        if isinstance(cell_g1, dict):
                            value = cell_g1.get("value")
                            if isinstance(value, str) and value.strip():
                                character_name = value.strip()
            except Exception:
                pass
            results.append(
                {
                    "name": character_name,
                    "path": cache_path,
                    "file": file_name,
                }
            )
        return results

    def load_character_cache(self, cache_path: str) -> bool:
        if not cache_path or not os.path.exists(cache_path):
            return False
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                return False
            self.cell_cache = loaded
            self.active_cache_path = cache_path
            self.current_character_name = self._get_character_name_from_cache()
            self._write_current_character_metadata(cache_path, self.current_character_name)
            print("[CACHE] active:", cache_path)
            return True
        except Exception:
            return False

    def _build_cache(self):
        if self.workbook is None:
            self.cell_cache = {}
            return
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

    def _get_character_name_from_cache(self) -> str:
        candidates = [("Charakterbogen", "G1"), ("CharacterSheet", "G1"), ("Sheet1", "G1")]
        for sheet_name, cell_ref in candidates:
            value = self.get_cell(sheet_name, cell_ref)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for sheet_name, sheet_cache in self.cell_cache.items():
            if not isinstance(sheet_cache, dict):
                continue
            g1 = sheet_cache.get("G1")
            if isinstance(g1, dict):
                value = g1.get("value")
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return "unknown_character"

    def _write_current_character_metadata(self, active_cache_path: str, character_name: str) -> None:
        metadata_path = os.path.join("data", "current_character.json")
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        payload = {
            "active_cache": active_cache_path,
            "character_name": character_name,
            "source_file": self.source_file_path,
            "last_loaded": datetime.now().isoformat(),
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
