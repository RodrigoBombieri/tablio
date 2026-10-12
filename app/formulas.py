"""A deliberately small, safe same-row Excel arithmetic evaluator."""
import ast
import re
from decimal import Decimal, DivisionByZero, InvalidOperation

CELL = re.compile(r"\$?([A-Za-z]{1,3})\$?(\d+)")
TABLE = re.compile(r"[A-Za-z_][\w.]*\[\[#This Row\],\[([^\]]+)\]\]", re.I)
LOCAL = re.compile(r"\[@(?:\[([^\]]+)\]|([^\]]+))\]")
TOKEN = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[()+*/-]")


def _column_index(letters):
    index = 0
    for letter in letters.upper():
        index = index * 26 + ord(letter) - 64
    return index - 1


def _check(tree, ids):
    deps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expression): continue
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div): continue
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub): continue
        if isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.UAdd, ast.USub, ast.Load)): continue
        if isinstance(node, ast.Name) and node.id in ids:
            deps.add(node.id); continue
        if isinstance(node, ast.Constant) and type(node.value) in (int, float): continue
        raise ValueError("Solo se admiten números, referencias de la misma fila y +, -, *, /.")
    return deps


def parse_formula(formula, row_number, labels):
    """Return a canonical field-ID expression and its dependencies."""
    source = formula.lstrip("=").strip()
    by_label = {label.casefold(): f"f{i+1}" for i, label in enumerate(labels)}
    parts = []
    pos = 0
    while pos < len(source):
        if source[pos].isspace(): pos += 1; continue
        match = TABLE.match(source, pos) or LOCAL.match(source, pos)
        if match:
            label = next((x for x in match.groups() if x is not None), "")
            fid = by_label.get(label.casefold())
            if not fid: raise ValueError(f"Columna desconocida en fórmula: {label}.")
            parts.append(fid); pos = match.end(); continue
        match = CELL.match(source, pos)
        if match:
            if int(match.group(2)) != row_number:
                raise ValueError("La fórmula referencia otra fila.")
            index = _column_index(match.group(1))
            if index >= len(labels): raise ValueError("La fórmula referencia una columna inexistente.")
            parts.append(f"f{index+1}"); pos = match.end(); continue
        match = TOKEN.match(source, pos)
        if not match: raise ValueError("Fórmula no admitida o referencia inválida.")
        parts.append(match.group()); pos = match.end()
    try:
        tree = ast.parse(" ".join(parts), mode="eval")
        deps = _check(tree, {f"f{i+1}" for i in range(len(labels))})
    except (SyntaxError, ValueError) as exc:
        raise ValueError("Fórmula no admitida: " + str(exc)) from exc
    return ast.unparse(tree), deps


def dependencies(expression):
    tree = ast.parse(expression, mode="eval")
    return _check(tree, set(re.findall(r"\bf\d+\b", expression)))


def evaluate(expression, values):
    tree = ast.parse(expression, mode="eval")
    _check(tree, set(values))
    def calc(node):
        if isinstance(node, ast.Expression): return calc(node.body)
        if isinstance(node, ast.Name):
            value = values[node.id]
            if value is None: return None
            try: return Decimal(str(value))
            except InvalidOperation as exc: raise ValueError("La fórmula referencia un valor no numérico.") from exc
        if isinstance(node, ast.Constant): return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp):
            value = calc(node.operand)
            return None if value is None else value if isinstance(node.op, ast.UAdd) else -value
        left, right = calc(node.left), calc(node.right)
        if left is None or right is None: return None
        try:
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            return left / right
        except (DivisionByZero, InvalidOperation) as exc:
            raise ValueError("La fórmula produce división por cero o resultado inválido.") from exc
    result = calc(tree)
    return None if result is None else format(result, "f")


def excel_formula(expression, row_number, field_columns):
    def render(node):
        if isinstance(node, ast.Name): return f"{column_name(field_columns[node.id] + 1)}{row_number}"
        if isinstance(node, ast.Constant): return str(node.value)
        if isinstance(node, ast.UnaryOp): return ("+" if isinstance(node.op, ast.UAdd) else "-") + render(node.operand)
        op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}[type(node.op)]
        return f"({render(node.left)}{op}{render(node.right)})"
    return render(ast.parse(expression, mode="eval").body)


def column_name(index):
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result
