import re


def analyze_c_code_light(code: str) -> list[dict]:
    issues: list[dict] = []
    lines = code.splitlines() or [code]
    full_code = "\n".join(lines)
    declared_uninitialized: dict[str, int] = {}
    initialized: set[str] = set()

    for index, line in enumerate(lines, start=1):
        compact = line.strip()
        scanf_match = re.search(r"scanf\s*\(([^;]+)\)", compact)
        if scanf_match:
            args = [part.strip() for part in scanf_match.group(1).split(",")][1:]
            format_count = _count_scanf_format_specifiers(scanf_match.group(1))
            if format_count != len(args):
                issues.append(
                    {
                        "line": index,
                        "type": "scanf_argument_count_mismatch",
                        "severity": "high",
                        "message": f"scanf 格式符数量是 {format_count}，但实际参数数量是 {len(args)}。",
                    }
                )
            missing_address = [arg for arg in args if re.fullmatch(r"[A-Za-z_]\w*", arg)]
            for arg in args:
                initialized.add(arg.lstrip("&"))
            if missing_address:
                issues.append(
                    {
                        "line": index,
                        "type": "scanf_missing_address",
                        "severity": "high",
                        "message": f"scanf 读取普通变量 {', '.join(missing_address)} 时疑似缺少 &。",
                    }
                )
        if re.search(r"if\s*\([^=()]+=[^=]", compact):
            issues.append(
                {
                    "line": index,
                    "type": "assignment_in_condition",
                    "severity": "medium",
                    "message": "条件判断中疑似使用赋值符号 =，可能应为 ==。",
                }
            )
        if re.search(r"for\s*\([^;]+;[^;]*<=\s*[A-Za-z_]\w*", compact) and re.search(r"\w+\s*\[\s*\w+\s*\]", compact):
            issues.append(
                {
                    "line": index,
                    "type": "array_boundary_risk",
                    "severity": "medium",
                    "message": "循环条件使用 <= 且访问数组下标，可能会访问到越界位置。",
                }
            )
        for_match = re.search(r"for\s*\(([^)]*)\)", compact)
        if for_match:
            parts = for_match.group(1).split(";")
            if len(parts) == 3 and not parts[2].strip():
                issues.append(
                    {
                        "line": index,
                        "type": "loop_update_missing",
                        "severity": "medium",
                        "message": "for 循环缺少更新表达式，循环变量可能不会变化。",
                    }
                )
        if (re.search(r"while\s*\(\s*(1|true)\s*\)", compact) or re.search(r"for\s*\(\s*;\s*;\s*\)", compact)) and "break" not in compact:
            issues.append(
                {
                    "line": index,
                    "type": "infinite_loop_risk",
                    "severity": "medium",
                    "message": "循环条件看起来恒为真，且当前行没有明显 break，可能导致死循环。",
                }
            )
        if "left = mid" in compact or "l = mid" in compact:
            issues.append(
                {
                    "line": index,
                    "type": "binary_search_boundary_risk",
                    "severity": "medium",
                    "message": "二分查找中 left = mid 可能导致区间不缩小。",
                }
            )
        for declaration in re.finditer(r"\bint\s+([A-Za-z_]\w*)\s*(?=[,;])", compact):
            name = declaration.group(1)
            declared_uninitialized.setdefault(name, index)
        for declaration in re.finditer(r"\bint\s+([A-Za-z_]\w*)\s*=", compact):
            initialized.add(declaration.group(1))
        for name in declared_uninitialized:
            if name in initialized:
                continue
            if re.search(rf"\b(printf|return)\b[^;]*\b{name}\b", compact):
                issues.append(
                    {
                        "line": index,
                        "type": "uninitialized_variable_risk",
                        "severity": "medium",
                        "message": f"变量 {name} 声明后可能未初始化就被使用。",
                    }
                )
                initialized.add(name)
    issues.extend(_detect_recursive_base_case_missing(full_code))
    issues.extend(_detect_string_missing_terminator_risk(full_code))
    return issues


def _count_scanf_format_specifiers(scanf_content: str) -> int:
    format_match = re.search(r'"([^"]*)"', scanf_content)
    if not format_match:
        return 0
    format_string = format_match.group(1)
    return len(re.findall(r"%(?!%)(?:\*?)(?:\d+)?(?:hh|h|ll|l|L)?[diuoxXfFeEgGaAcspn]", format_string))


def _detect_recursive_base_case_missing(code: str) -> list[dict]:
    issues = []
    function_defs = list(re.finditer(r"\b(?:int|void|long|double|float|char)\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", code))
    for match in function_defs:
        name = match.group(1)
        body = code[match.end():]
        if re.search(rf"\b{name}\s*\(", body) and not re.search(r"\bif\s*\(", body):
            issues.append(
                {
                    "line": code[:match.start()].count("\n") + 1,
                    "type": "recursive_base_case_missing",
                    "severity": "medium",
                    "message": f"函数 {name} 疑似递归调用自己，但没有明显的 if 终止条件。",
                }
            )
    return issues


def _detect_string_missing_terminator_risk(code: str) -> list[dict]:
    issues = []
    for declaration in re.finditer(r"\bchar\s+([A-Za-z_]\w*)\s*\[\s*\d+\s*\]\s*(?:;|,)", code):
        name = declaration.group(1)
        uses_as_string = re.search(rf"printf\s*\(\s*\"%s\"\s*,\s*{name}\s*\)", code)
        has_terminator = "\\0" in code or re.search(rf"{name}\s*\[[^\]]+\]\s*=\s*'\\0'", code)
        if uses_as_string and not has_terminator:
            issues.append(
                {
                    "line": code[:declaration.start()].count("\n") + 1,
                    "type": "string_missing_terminator_risk",
                    "severity": "medium",
                    "message": f"字符数组 {name} 按字符串输出，但没有看到字符串结束符 \\0。",
                }
            )
    return issues
