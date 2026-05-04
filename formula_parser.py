import re
from typing import Any, Callable


class FormulaParser:
    def __init__(self):
        self.formulas: dict[str, dict[str, str]] = {}
        self.cell_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def extract_formulas(self, sheet_name, sheet):
        if sheet_name not in self.formulas:
            self.formulas[sheet_name] = {}

        for row in sheet.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str) and cell.value.startswith("="):
                    self.formulas[sheet_name][cell.coordinate] = cell.value

        return self.formulas[sheet_name]

    def update_formula(self, sheet_name, cell, formula):
        if sheet_name not in self.formulas:
            self.formulas[sheet_name] = {}

        self.formulas[sheet_name][cell] = formula

    def get_formulas(self, sheet_name):
        return self.formulas.get(sheet_name, {})

    def set_cell_cache(self, cell_cache):
        self.cell_cache = cell_cache

    def extract_references(self, formula):
        if not isinstance(formula, str):
            return []
        refs = re.findall(r"[A-Za-z]+[0-9]+", formula)
        unique = []
        seen = set()
        for ref in refs:
            ref_upper = ref.upper()
            if ref_upper not in seen:
                seen.add(ref_upper)
                unique.append(ref_upper)
        return unique

    def convert_if_to_python(self, formula):
        if not isinstance(formula, str):
            return formula

        result = formula.replace("WENN(", "IF(")
        return self._convert_if_isolated(result)

    def _convert_if_isolated(self, text):
        match = re.search(r"IF\(", text, flags=re.IGNORECASE)
        if not match:
            return text
        start = match.start()

        open_paren = start + 2
        end = self._find_matching_paren(text, open_paren)
        if end == -1:
            return text

        if_part = text[start:end + 1]
        rest = text[end + 1:]

        converted_if = self._convert_nested_if(if_part)
        converted_rest = self._convert_if_isolated(rest)
        return text[:start] + converted_if + converted_rest

    def preprocess_formula_for_eval(self, formula):
        if not isinstance(formula, str):
            return formula

        # 1) Normalize Excel-DE syntax first
        expression = self.normalize_excel_de_syntax(formula)
        # 2) Remove leading '='
        expression = expression[1:] if expression.startswith("=") else expression
        # 3) Convert Excel syntax to Python syntax
        expression = self.convert_sum_to_python(expression)
        expression = self.convert_if_to_python(expression)
        return expression

    def normalize_excel_de_syntax(self, formula):
        if not isinstance(formula, str):
            return formula

        normalized = formula.strip()
        normalized = normalized.replace("WENN(", "IF(")
        normalized = normalized.replace(";", ",")
        return normalized

    def _convert_nested_if(self, text):
        match = re.search(r"IF\(", text, flags=re.IGNORECASE)
        if not match:
            return text
        start = match.start()

        open_paren = start + 2
        end = self._find_matching_paren(text, open_paren)
        if end == -1:
            return text

        inner = text[open_paren + 1:end]
        parts = self._split_if_arguments(inner)
        if len(parts) != 3:
            return text

        condition = self._convert_condition(self._convert_nested_if(parts[0].strip()))
        true_part = self._convert_nested_if(parts[1].strip())
        false_part = self._convert_nested_if(parts[2].strip())
        python_if = f"(({true_part}) if ({condition}) else ({false_part}))"

        rebuilt = text[:start] + python_if + text[end + 1:]
        return self._convert_nested_if(rebuilt)

    def _split_if_arguments(self, content):
        args = []
        depth = 0
        current = []
        for char in content:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1

            if (char == ";" or char == ",") and depth == 0:
                args.append("".join(current))
                current = []
            else:
                current.append(char)

        args.append("".join(current))
        return args

    def _find_matching_paren(self, text, open_paren_index):
        depth = 0
        for i in range(open_paren_index, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def _convert_condition(self, condition):
        converted = re.sub(r"(?<![<>=!])=(?![=])", "==", condition)
        return converted

    def convert_sum_to_python(self, formula):
        return formula

    def resolve_references(self, sheet_name, expression, value_getter: Callable[[str, str], Any], visited=None):
        if not isinstance(expression, str):
            return None
        if visited is None:
            visited = set()

        try:
            expression = self._replace_sum_functions(sheet_name, expression, value_getter, visited)
        except Exception:
            return None

        # Resolve cross-sheet refs first: SheetName!A1
        cross_pattern = r"([A-Za-z0-9_]+)!([A-Za-z]+[0-9]+)"

        def replace_cross_ref(match):
            ref_sheet = match.group(1)
            ref_cell = match.group(2)
            resolved = self._resolve_cell_value(ref_sheet, ref_cell, value_getter, visited)
            if resolved is None:
                raise ValueError("Unsupported cell value")
            return resolved

        expression_with_cross = expression
        try:
            expression_with_cross = re.sub(cross_pattern, replace_cross_ref, expression_with_cross)
        except Exception:
            return None

        def replace_ref(match):
            cell_ref = match.group(0)
            resolved = self._resolve_cell_value(sheet_name, cell_ref, value_getter, visited)
            if resolved is None:
                raise ValueError("Unsupported cell value")
            return resolved

        try:
            return re.sub(r"[A-Za-z]+[0-9]+", replace_ref, expression_with_cross)
        except Exception:
            return None

    def _resolve_cell_value(self, sheet_name, cell_ref, value_getter: Callable[[str, str], Any], visited):
        visit_key = (sheet_name, cell_ref)
        if visit_key in visited:
            return None

        value = value_getter(sheet_name, cell_ref)
        if value is None or value == "":
            return "0"

        if isinstance(value, str) and value.startswith("="):
            visited.add(visit_key)
            nested_expression = self.preprocess_formula_for_eval(value)
            resolved_nested = self.resolve_references(
                sheet_name, nested_expression, value_getter, visited
            )
            visited.remove(visit_key)
            if resolved_nested is None:
                return None
            return f"({resolved_nested})"

        text_value = str(value).strip().replace(",", ".")
        if text_value == "":
            return "0"
        if not re.fullmatch(r"-?\d+(\.\d+)?", text_value):
            return None
        return text_value

    def _replace_sum_functions(self, sheet_name, expression, value_getter: Callable[[str, str], Any], visited):
        result = expression
        while True:
            match = re.search(r"SUM\(", result, flags=re.IGNORECASE)
            if not match:
                break

            start = match.start()
            open_paren = start + 3
            end = self._find_matching_paren(result, open_paren)
            if end == -1:
                raise ValueError("Invalid SUM")

            inner = result[open_paren + 1:end]
            args = self._split_if_arguments(inner)
            collected_parts = []

            for arg in args:
                clean_arg = arg.strip()
                if clean_arg == "":
                    continue

                range_match = re.fullmatch(r"([A-Z]+[0-9]+):([A-Z]+[0-9]+)", clean_arg, flags=re.IGNORECASE)
                if range_match:
                    cells = self._expand_range(range_match.group(1), range_match.group(2))
                    for cell in cells:
                        resolved_value = self._resolve_cell_value(sheet_name, cell, value_getter, visited)
                        if resolved_value is None:
                            raise ValueError("Unsupported range value")
                        collected_parts.append(resolved_value)
                    continue

                resolved_arg = self.resolve_references(sheet_name, clean_arg, value_getter, visited)
                if resolved_arg is None:
                    raise ValueError("Unsupported SUM argument")
                collected_parts.append(f"({resolved_arg})")

            replacement = "(0)" if not collected_parts else "(" + " + ".join(collected_parts) + ")"
            result = result[:start] + replacement + result[end + 1:]

        return result

    def _expand_range(self, start_cell, end_cell):
        start_col_letters, start_row = self._split_cell_ref(start_cell)
        end_col_letters, end_row = self._split_cell_ref(end_cell)
        start_col = self._col_letters_to_index(start_col_letters)
        end_col = self._col_letters_to_index(end_col_letters)

        col_from = min(start_col, end_col)
        col_to = max(start_col, end_col)
        row_from = min(start_row, end_row)
        row_to = max(start_row, end_row)

        cells = []
        for col in range(col_from, col_to + 1):
            col_letters = self._index_to_col_letters(col)
            for row in range(row_from, row_to + 1):
                cells.append(f"{col_letters}{row}")
        return cells

    def _split_cell_ref(self, cell_ref):
        match = re.fullmatch(r"([A-Z]+)([0-9]+)", cell_ref, flags=re.IGNORECASE)
        if not match:
            raise ValueError("Invalid cell")
        return match.group(1).upper(), int(match.group(2))

    def _col_letters_to_index(self, letters):
        index = 0
        for letter in letters:
            index = index * 26 + (ord(letter) - ord("A") + 1)
        return index

    def _index_to_col_letters(self, index):
        result = ""
        number = index
        while number > 0:
            number, remainder = divmod(number - 1, 26)
            result = chr(ord("A") + remainder) + result
        return result

    def evaluate_formula(self, sheet_name, formula, value_getter: Callable[[str, str], Any], cell_ref=None):
        if not formula:
            return ""

        if not isinstance(formula, str):
            return str(formula)

        if not formula.startswith("="):
            return formula

        # 1) preprocess_formula_for_eval()
        expression = self.preprocess_formula_for_eval(formula)
        if not isinstance(expression, str):
            return "Nicht unterstützt"

        # 2) resolve_references()
        resolved = self.resolve_references(sheet_name, expression, value_getter, set())
        if resolved is None:
            return "Nicht unterstützt"

        if not re.fullmatch(r"[0-9+\-*/().\s<>=!a-zA-Z:]+", resolved):
            return "Nicht unterstützt"

        # 3) eval()
        try:
            result = str(eval(resolved, {"__builtins__": {}}, {}))
            if cell_ref and sheet_name in self.cell_cache and cell_ref in self.cell_cache[sheet_name]:
                self.cell_cache[sheet_name][cell_ref]["value"] = result
                self.cell_cache[sheet_name][cell_ref]["formula"] = formula
                self.cell_cache[sheet_name][cell_ref]["references"] = self.extract_references(formula)
            return result
        except Exception:
            return "Nicht unterstützt"
