"""Deterministic calculation: a small numeric grammar, never Python eval."""

import ast
import math
import operator

_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
}
_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "c": 299792458,
    "G": 6.67430e-11,
    "h": 6.62607015e-34,
    "k_B": 1.380649e-23,
}
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def calculate(expression: str) -> int | float:
    if not expression.strip() or len(expression) > 512:
        raise ValueError("Calculation requires 1–512 characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Invalid numeric expression") from exc
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("Expression is too complex")

    def visit(node):
        match node:
            case ast.Constant(value=value) if type(value) in (int, float):
                result = value
            case ast.Name(id=name) if name in _CONSTANTS:
                result = _CONSTANTS[name]
            case ast.UnaryOp(op=ast.USub(), operand=operand):
                result = -visit(operand)
            case ast.UnaryOp(op=ast.UAdd(), operand=operand):
                result = visit(operand)
            case ast.BinOp(left=left, op=op, right=right) if type(op) in _OPERATORS:
                a, b = visit(left), visit(right)
                if isinstance(op, ast.Pow) and abs(b) > 100:
                    raise ValueError("Exponent magnitude must not exceed 100")
                result = _OPERATORS[type(op)](a, b)
            case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if (
                name in _FUNCTIONS
            ):
                if not 1 <= len(args) <= 10:
                    raise ValueError("Function requires 1–10 numeric arguments")
                result = _FUNCTIONS[name](*(visit(arg) for arg in args))
            case _:
                raise ValueError(
                    "Use only numbers, arithmetic, named constants and math functions"
                )
        if (
            type(result) not in (int, float)
            or not math.isfinite(result)
            or abs(result) > 1e100
        ):
            raise ValueError("Calculation exceeds the finite numeric limit")
        return result

    try:
        return visit(tree.body)
    except (ArithmeticError, TypeError, OverflowError) as exc:
        raise ValueError(
            "Calculation is undefined or outside supported bounds"
        ) from exc
