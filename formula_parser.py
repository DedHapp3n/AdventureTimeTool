import re
from typing import Any, Callable

from app_logger import log_debug, log_warning


class FormulaEvaluationError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


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

    def recalculate_cache(self, cell_cache):
        self.set_cell_cache(cell_cache)
        if not isinstance(cell_cache, dict):
            return cell_cache

        unsupported_count = 0
        for sheet_name, sheet_cache in cell_cache.items():
            if not isinstance(sheet_cache, dict):
                continue
            for cell_ref, cell_info in sheet_cache.items():
                if not isinstance(cell_info, dict):
                    continue
                formula = cell_info.get("formula")
                if not isinstance(formula, str) or not formula.startswith("="):
                    cell_info["error"] = None
                    continue
                try:
                    result = self._evaluate_cache_cell(sheet_name, cell_ref, set())
                    cell_info["value"] = result
                    cell_info["error"] = None
                    log_debug("parser", f"{sheet_name} {cell_ref} {formula} -> {result}")
                except FormulaEvaluationError as exc:
                    cell_info["error"] = exc.code
                    if exc.code == "cycle":
                        cell_info["value"] = None
                    if exc.code == "unsupported":
                        unsupported_count += 1
                        log_debug("parser", f"{sheet_name} {cell_ref} {formula} {exc.code}")
                    else:
                        log_warning("parser", f"{sheet_name} {cell_ref} {formula} {exc.code}")
                except Exception as exc:
                    cell_info["error"] = "unsupported"
                    unsupported_count += 1
                    log_debug("parser", f"{sheet_name} {cell_ref} {formula} {exc}")

        if unsupported_count:
            log_debug("parser", f"{unsupported_count} unsupported formulas during recalculation")

        return cell_cache

    def extract_references(self, formula):
        if not isinstance(formula, str):
            return []
        refs = re.findall(r"\$?([A-Za-z]+\$?[0-9]+)", formula)
        unique = []
        seen = set()
        for ref in refs:
            ref_upper = ref.replace("$", "").upper()
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

        expression = self.normalize_excel_de_syntax(formula)
        expression = expression[1:] if expression.startswith("=") else expression
        expression = self.convert_sum_to_python(expression)
        expression = self.convert_if_to_python(expression)
        return expression

    def normalize_excel_de_syntax(self, formula):
        if not isinstance(formula, str):
            return formula

        normalized = formula.strip()
        uses_semicolon_args = ";" in normalized
        if uses_semicolon_args:
            normalized = re.sub(r"(?<=\d),(?=\d)", ".", normalized)
        normalized = normalized.replace("$", "")
        normalized = re.sub(r"\bSUMME\s*\(", "SUM(", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bWENN\s*\(", "IF(", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bVERGLEICH\s*\(", "MATCH(", normalized, flags=re.IGNORECASE)
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
        condition = condition.replace("<>", "!=")
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
        except FormulaEvaluationError:
            raise
        except Exception:
            return None

        cross_pattern = r"(?:'([^']+)'|([A-Za-z0-9_ äöüÄÖÜß.-]+))!([A-Za-z]+[0-9]+)"

        def replace_cross_ref(match):
            ref_sheet = match.group(1) or match.group(2)
            ref_cell = match.group(3)
            resolved = self._resolve_cell_value(ref_sheet, ref_cell, value_getter, visited)
            if resolved is None:
                raise ValueError("Unsupported cell value")
            return resolved

        expression_with_cross = expression
        try:
            expression_with_cross = re.sub(cross_pattern, replace_cross_ref, expression_with_cross)
        except FormulaEvaluationError:
            raise
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
        except FormulaEvaluationError:
            raise
        except Exception:
            return None

    def _resolve_cell_value(self, sheet_name, cell_ref, value_getter: Callable[[str, str], Any], visited):
        resolved_sheet = self._resolve_sheet_name(sheet_name)
        if resolved_sheet is None:
            return "0"

        normalized_cell = cell_ref.replace("$", "").upper()
        visit_key = (resolved_sheet, normalized_cell)
        if visit_key in visited:
            raise FormulaEvaluationError("cycle")

        value = value_getter(resolved_sheet, normalized_cell)
        if value is None or value == "":
            return "0"

        if isinstance(value, str) and value.startswith("="):
            visited.add(visit_key)
            nested_expression = self.preprocess_formula_for_eval(value)
            resolved_nested = self.resolve_references(
                resolved_sheet, nested_expression, value_getter, visited
            )
            visited.remove(visit_key)
            if resolved_nested is None:
                return None
            return f"({resolved_nested})"

        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)

        text_value = str(value).strip()
        text_value = re.sub(r"(?<=\d),(?=\d)", ".", text_value)
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

                range_sheet, range_start, range_end = self._parse_range_arg(clean_arg)
                range_match = range_start is not None and range_end is not None
                if range_match:
                    target_sheet = range_sheet or sheet_name
                    cells = self._expand_range(range_start, range_end)
                    for cell in cells:
                        resolved_value = self._resolve_cell_value(target_sheet, cell, value_getter, visited)
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

    def _parse_range_arg(self, arg):
        sheet_name = None
        range_text = arg.strip()
        sheet_match = re.fullmatch(
            r"(?:'([^']+)'|([A-Za-z0-9_ äöüÄÖÜß.-]+))!([A-Z]+[0-9]+):(?:[A-Za-z0-9_ äöüÄÖÜß.-]+!)?([A-Z]+[0-9]+)",
            range_text,
            flags=re.IGNORECASE,
        )
        if sheet_match:
            sheet_name = sheet_match.group(1) or sheet_match.group(2)
            return sheet_name, sheet_match.group(3).upper(), sheet_match.group(4).upper()

        range_match = re.fullmatch(
            r"([A-Z]+[0-9]+):([A-Z]+[0-9]+)",
            range_text,
            flags=re.IGNORECASE,
        )
        if range_match:
            return None, range_match.group(1).upper(), range_match.group(2).upper()

        return None, None, None

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

        expression = self.preprocess_formula_for_eval(formula)
        if not isinstance(expression, str):
            return "Nicht unterstützt"

        try:
            resolved = self.resolve_references(sheet_name, expression, value_getter, set())
            if resolved is None:
                return "Nicht unterstützt"
        except FormulaEvaluationError:
            return "Nicht unterstützt"

        if not re.fullmatch(r"[0-9+\-*/().\s<>=!a-zA-Z_]+", resolved):
            return "Nicht unterstützt"

        try:
            result = eval(resolved, {"__builtins__": {}}, {})
            if cell_ref and sheet_name in self.cell_cache and cell_ref in self.cell_cache[sheet_name]:
                self.cell_cache[sheet_name][cell_ref]["value"] = result
                self.cell_cache[sheet_name][cell_ref]["formula"] = formula
                self.cell_cache[sheet_name][cell_ref]["references"] = self.extract_references(formula)
            return result
        except Exception:
            return "Nicht unterstützt"

    def _evaluate_cache_cell(self, sheet_name, cell_ref, stack):
        resolved_sheet = self._resolve_sheet_name(sheet_name)
        if resolved_sheet is None:
            raise FormulaEvaluationError("unsupported")

        normalized_cell = cell_ref.replace("$", "").upper()
        sheet_cache = self.cell_cache.get(resolved_sheet, {})
        cell_info = sheet_cache.get(normalized_cell)
        if not isinstance(cell_info, dict):
            return 0

        formula = cell_info.get("formula")
        value = cell_info.get("value")
        if not isinstance(formula, str) or not formula.startswith("="):
            return self._coerce_numeric_value(value)

        visit_key = (resolved_sheet, normalized_cell)
        if visit_key in stack:
            cell_info["error"] = "cycle"
            raise FormulaEvaluationError("cycle")

        stack.add(visit_key)

        def value_getter(ref_sheet, ref_cell):
            return self._evaluate_cache_cell(ref_sheet, ref_cell, stack)

        try:
            result = self.evaluate_formula(resolved_sheet, formula, value_getter, cell_ref=normalized_cell)
        finally:
            stack.remove(visit_key)

        if result == "Nicht unterstützt":
            raise FormulaEvaluationError("unsupported")
        return result

    def _coerce_numeric_value(self, value):
        if value is None or value == "":
            return 0
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, (int, float)):
            return value
        text_value = str(value).strip()
        text_value = re.sub(r"(?<=\d),(?=\d)", ".", text_value)
        if not text_value:
            return 0
        if re.fullmatch(r"-?\d+(\.\d+)?", text_value):
            number = float(text_value)
            return int(number) if number.is_integer() else number
        return value

    def _resolve_sheet_name(self, sheet_name):
        if sheet_name in self.cell_cache:
            return sheet_name
        wanted = str(sheet_name).strip()
        for existing in self.cell_cache.keys():
            if str(existing).strip().lower() == wanted.lower():
                return existing
        return None

    def trace_formula(self, sheet_name, cell_ref, cache=None):
        target_cache = cache if isinstance(cache, dict) else self.cell_cache
        if not isinstance(target_cache, dict):
            return {
                "formula": None,
                "normalized": None,
                "sources": [],
                "steps": [],
                "value": None,
                "error": "missing_cache",
            }

        previous_cache = self.cell_cache
        self.cell_cache = target_cache
        try:
            resolved_sheet = self._resolve_sheet_name(sheet_name)
            if resolved_sheet is None:
                return {
                    "formula": None,
                    "normalized": None,
                    "sources": [],
                    "steps": [],
                    "value": None,
                    "error": "missing_sheet",
                }

            normalized_cell = str(cell_ref or "").replace("$", "").upper()
            cell_info = target_cache.get(resolved_sheet, {}).get(normalized_cell)
            if not isinstance(cell_info, dict):
                return {
                    "formula": None,
                    "normalized": None,
                    "sources": [],
                    "steps": [],
                    "value": None,
                    "error": "missing_cell",
                }

            formula = cell_info.get("formula")
            if not isinstance(formula, str) or not formula.startswith("="):
                return {
                    "formula": formula,
                    "normalized": None,
                    "sources": [],
                    "steps": ["Keine Formel vorhanden / manuell"],
                    "value": cell_info.get("value"),
                    "error": None,
                }

            normalized = self.normalize_excel_de_syntax(formula)
            parsed_sources = []
            for source in self.extract_references(formula):
                parsed_sources.append(
                    {"sheet": resolved_sheet, "cell": source, "ref": f"{resolved_sheet}!{source}"}
                )

            cross_matches = re.findall(
                r"(?:'([^']+)'|([A-Za-z0-9_ äöüÄÖÜß.-]+))!([A-Za-z]+[0-9]+)",
                formula,
                flags=re.IGNORECASE,
            )
            for match in cross_matches:
                source_sheet = (match[0] or match[1] or "").strip()
                source_cell = (match[2] or "").replace("$", "").upper()
                ref_text = f"{source_sheet}!{source_cell}"
                if not any(s.get("ref") == ref_text for s in parsed_sources):
                    parsed_sources.append(
                        {"sheet": source_sheet, "cell": source_cell, "ref": ref_text}
                    )

            steps = [f"Original: {formula}", f"Normalisiert: {normalized}"]
            expression = self.preprocess_formula_for_eval(formula)
            steps.append(f"Ausdruck: {expression}")

            def value_getter(ref_sheet, ref_cell):
                local_sheet = self._resolve_sheet_name(ref_sheet)
                if local_sheet is None:
                    return None
                local_cell = str(ref_cell).replace("$", "").upper()
                source_info = target_cache.get(local_sheet, {}).get(local_cell)
                if not isinstance(source_info, dict):
                    return None
                return source_info.get("value")

            resolved_expression = self.resolve_references(
                resolved_sheet, expression, value_getter, set()
            )
            if resolved_expression is None:
                return {
                    "formula": formula,
                    "normalized": normalized,
                    "sources": parsed_sources,
                    "steps": steps + ["Referenzauflösung nicht verfügbar"],
                    "value": cell_info.get("value"),
                    "error": "unsupported",
                }

            steps.append(f"Aufgelöst: {resolved_expression}")
            if not re.fullmatch(r"[0-9+\-*/().\s<>=!a-zA-Z_]+", resolved_expression):
                return {
                    "formula": formula,
                    "normalized": normalized,
                    "sources": parsed_sources,
                    "steps": steps + ["Ausdruck enthält nicht unterstützte Zeichen"],
                    "value": cell_info.get("value"),
                    "error": "unsupported",
                }

            try:
                evaluated = eval(resolved_expression, {"__builtins__": {}}, {})
                steps.append(f"Ergebnis: {evaluated}")
                return {
                    "formula": formula,
                    "normalized": normalized,
                    "sources": parsed_sources,
                    "steps": steps,
                    "value": evaluated,
                    "error": None,
                }
            except FormulaEvaluationError as exc:
                return {
                    "formula": formula,
                    "normalized": normalized,
                    "sources": parsed_sources,
                    "steps": steps + [f"Fehler: {exc.code}"],
                    "value": cell_info.get("value"),
                    "error": exc.code,
                }
            except Exception:
                return {
                    "formula": formula,
                    "normalized": normalized,
                    "sources": parsed_sources,
                    "steps": steps + ["Fehler: unsupported"],
                    "value": cell_info.get("value"),
                    "error": "unsupported",
                }
        finally:
            self.cell_cache = previous_cache
