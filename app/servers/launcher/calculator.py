"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索框计算器：安全 AST 求值，不使用 eval。
"""
import ast
import math
import re

from .models import SearchItem


_MAX_LENGTH = 240
_MAX_NODES = 120
_MAX_POWER = 10000
_MAX_INT_BITS = 4096
_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "ln": math.log,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": math.factorial,
    "radians": math.radians,
    "degrees": math.degrees,
    "pow": pow,
}
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


class CalculatorError(ValueError):
    pass


def _normalize(text):
    value = (text or "").strip()
    value = value.replace("×", "*").replace("÷", "/")
    value = value.replace("−", "-").replace("π", "pi")
    value = value.replace("^", "**")
    value = re.sub(r"(?<=\d),(?=\d)", "", value)
    return value


def _looks_like_math(value):
    if not value:
        return False
    if re.search(r"[+\-*/%^]", value):
        return True
    if re.search(r"(?i)\b(?:sqrt|sin|cos|tan|asin|acos|atan|log|ln|exp|abs|round|floor|ceil|factorial|radians|degrees|pow)\s*\(", value):
        return True
    return False


def _evaluate_node(node):
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise CalculatorError("unsupported constant")
        if not isinstance(node.value, (int, float)):
            raise CalculatorError("unsupported constant")
        return node.value
    if isinstance(node, ast.Name):
        key = node.id.lower()
        if key not in _CONSTANTS:
            raise CalculatorError("unknown name")
        return _CONSTANTS[key]
    if isinstance(node, ast.UnaryOp):
        value = _evaluate_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.USub):
            return -value
        raise CalculatorError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        elif isinstance(node.op, ast.Div):
            result = left / right
        elif isinstance(node.op, ast.FloorDiv):
            result = left // right
        elif isinstance(node.op, ast.Mod):
            result = left % right
        elif isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_POWER:
                raise CalculatorError("power too large")
            result = left ** right
        else:
            raise CalculatorError("unsupported binary operator")
        return result
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise CalculatorError("unsupported function")
        name = node.func.id.lower()
        if node.keywords:
            raise CalculatorError("keyword arguments are not supported")
        args = [_evaluate_node(arg) for arg in node.args]
        if name == "log":
            if len(args) == 1:
                return math.log10(args[0])
            if len(args) == 2:
                return math.log(args[0], args[1])
            raise CalculatorError("log expects 1 or 2 arguments")
        func = _FUNCTIONS.get(name)
        if func is None:
            raise CalculatorError("unsupported function")
        if name == "factorial" and (
                len(args) != 1 or not isinstance(args[0], int)
                or args[0] < 0 or args[0] > 1000):
            raise CalculatorError("factorial out of range")
        return func(*args)
    raise CalculatorError("unsupported expression")


def evaluate(text):
    raw = (text or "").strip()
    if not raw or len(raw) > _MAX_LENGTH:
        return None
    forced = raw.startswith("=")
    value = _normalize(raw[1:] if forced else raw)
    if not forced and not _looks_like_math(value):
        return None
    try:
        tree = ast.parse(value, mode="eval")
    except SyntaxError:
        return None
    if sum(1 for _ in ast.walk(tree)) > _MAX_NODES:
        return None
    try:
        result = _evaluate_node(tree)
    except (ArithmeticError, CalculatorError, TypeError, ValueError, OverflowError):
        return None
    if isinstance(result, complex):
        return None
    if isinstance(result, int):
        if result.bit_length() > _MAX_INT_BITS:
            return None
        return str(result)
    if not math.isfinite(result):
        return None
    if result == 0:
        return "0"
    if result.is_integer() and abs(result) < 1e16:
        return str(int(result))
    return format(result, ".12g")


def find(query):
    value = evaluate(query)
    if value is None:
        return None
    raw = (query or "").strip()
    expression = raw[1:].strip() if raw.startswith("=") else raw
    return SearchItem(
        id="calculator:%s" % expression,
        kind="calculator",
        title=value,
        subtitle=expression,
        provider="calculator",
        payload={"value": value, "expression": expression},
        icon_name="calculator",
        tooltip="%s\nEnter 复制结果" % expression,
    )
