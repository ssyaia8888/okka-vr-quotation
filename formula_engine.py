#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""formula_engine.py — 產品計價公式引擎（ECST ProductOther/formula 仿製）

安全 eval（ast 白名單，唔用 Python eval）。支援中文變數名、× ÷ ＋ － 、括號。
對應 ERP product.template.x_formula（公式）+ x_formula_unit（單位）。

用法：
  python3 formula_engine.py "長*闊*單價+五金" 長=3 闊=2 單價=500 五金=200
  from formula_engine import compute; compute("長*闊*500", {"長":3,"闊":2})
"""
import ast, sys

BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
       ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
       ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}
UN = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}
FUNCS = {"min": min, "max": max, "round": lambda x, n=0: round(x, int(n)),
         "abs": abs, "int": lambda x: float(int(x))}

_NORM = str.maketrans({"×": "*", "÷": "/", "＋": "+", "－": "-", "(": "(", "）": ")",
                       "（": "(", "，": ",", "　": " ", "．": ".", "。": "."})


def normalize(expr: str) -> str:
    return expr.translate(_NORM).strip()


def _ev(node, names):
    if isinstance(node, ast.Expression):
        return _ev(node.body, names)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("只准數字常數")
    if isinstance(node, ast.Name):
        if node.id in names:
            return float(names[node.id])
        raise KeyError("缺少變數: %s" % node.id)
    if isinstance(node, ast.BinOp) and type(node.op) in BIN:
        return BIN[type(node.op)](_ev(node.left, names), _ev(node.right, names))
    if isinstance(node, ast.UnaryOp) and type(node.op) in UN:
        return UN[type(node.op)](_ev(node.operand, names))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in FUNCS and not node.keywords):
        return float(FUNCS[node.func.id](*[_ev(a, names) for a in node.args]))
    raise ValueError("運算式含不允許嘅節點: %s" % type(node).__name__)


def required_vars(expr: str):
    """抽出公式需要嘅變數名（排除函數名 min/max/round/abs/int）。"""
    tree = ast.parse(normalize(expr), mode="eval")
    return sorted({n.id for n in ast.walk(tree)
                   if isinstance(n, ast.Name) and n.id not in FUNCS})


def compute(expr: str, variables: dict) -> float:
    tree = ast.parse(normalize(expr), mode="eval")
    return _ev(tree, variables)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    expr = sys.argv[1]
    vars_ = {}
    for a in sys.argv[2:]:
        k, _, v = a.partition("=")
        vars_[k] = float(v)
    print("公式:", expr, "| 需要變數:", required_vars(expr))
    print("結果:", compute(expr, vars_))
