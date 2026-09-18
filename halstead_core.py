# -*- coding: utf-8 -*-
"""
halstead_core.py
Токенизатор JavaScript и расчёт метрик Холстеда.

Логика классификации операторов/операндов адаптирована из таблицы
"Операторы языка Паскаль в интерпретации Холстеда" под синтаксис JavaScript.

Ключевое правило (по требованию задания):
    Круглые скобки "( )" считаются ОДНИМ оператором (пара = 1 оператор),
    ТОЛЬКО если они используются для группировки выражений (математика,
    логика, приоритет операций).
    Если скобки являются частью управляющих конструкций
    (if, while, for, switch, catch, with) или списка параметров function(...),
    либо являются скобками вызова функции identifier(...), то они
    самостоятельным оператором НЕ считаются (не учитываются в подсчёте).
"""

import re
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Словари токенов
# ---------------------------------------------------------------------------

KEYWORD_OPERATORS = {
    "var", "let", "const", "function", "return", "if", "else", "for", "while",
    "do", "switch", "case", "default", "break", "continue", "try", "catch",
    "finally", "throw", "new", "delete", "typeof", "instanceof", "in", "of",
    "class", "extends", "super", "import", "export", "from", "async", "await",
    "yield", "void", "with", "debugger", "static", "get", "set",
}

# Управляющие ключевые слова, после которых "(" не считается оператором
CONTROL_KEYWORDS = {"if", "while", "for", "switch", "catch", "with"}

LITERAL_KEYWORDS = {"true", "false", "null", "undefined", "NaN", "Infinity", "this"}

# многосимвольные операторы, отсортированы от самых длинных к коротким
MULTI_CHAR_OPERATORS = [
    ">>>=", "===", "!==", "**=", "<<=", ">>=", "&&=", "||=", "??=",
    ">>>", "...", "=>",
    "++", "--", "**", "==", "!=", "<=", ">=", "&&", "||", "??",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<", ">>",
]

SINGLE_CHAR_OPERATORS = set("+-*/%=<>!&|^~?:,;.")

OPEN_PAREN, CLOSE_PAREN = "(", ")"
OPEN_BRACE, CLOSE_BRACE = "{", "}"
OPEN_BRACKET, CLOSE_BRACKET = "[", "]"

# ---------------------------------------------------------------------------
# Токенизация
# ---------------------------------------------------------------------------

TOKEN_SPEC = [
    ("COMMENT_BLOCK", r"/\*.*?\*/"),
    ("COMMENT_LINE", r"//[^\n]*"),
    ("TEMPLATE", r"`(?:\\.|[^`\\])*`"),
    ("STRING_D", r'"(?:\\.|[^"\\])*"'),
    ("STRING_S", r"'(?:\\.|[^'\\])*'"),
    ("NUMBER", r"\b0[xX][0-9a-fA-F]+\b|\b0[bB][01]+\b|\b0[oO][0-7]+\b|"
               r"\b\d+\.\d+([eE][+-]?\d+)?\b|\b\.\d+([eE][+-]?\d+)?\b|"
               r"\b\d+([eE][+-]?\d+)?\b"),
    ("IDENT", r"[A-Za-z_$][A-Za-z0-9_$]*"),
    ("MULTIOP", "|".join(re.escape(op) for op in MULTI_CHAR_OPERATORS)),
    ("PUNCT", r"[{}()\[\]" + re.escape("".join(SINGLE_CHAR_OPERATORS)) + r"]"),
    ("NEWLINE", r"\n"),
    ("SKIP", r"[ \t\r]+"),
    ("MISMATCH", r"."),
]

TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC), re.DOTALL)


class Token:
    __slots__ = ("kind", "text")

    def __init__(self, kind, text):
        self.kind = kind
        self.text = text

    def __repr__(self):
        return f"Token({self.kind!r}, {self.text!r})"


def tokenize(code: str):
    """Возвращает список токенов (без пробелов и комментариев),
    но с базовым распознаванием regex-литералов JS."""
    tokens = []
    pos = 0
    n = len(code)
    prev_significant = None  # предыдущий "значимый" токен для эвристики regex

    while pos < n:
        # Попытка распознать regex-литерал: '/' в позиции, где ожидается
        # операнд (после оператора, скобки, запятой, начала кода, keyword)
        if code[pos] == "/" and _looks_like_regex_start(prev_significant):
            m = _match_regex_literal(code, pos)
            if m:
                tokens.append(Token("REGEX", m))
                pos += len(m)
                prev_significant = tokens[-1]
                continue

        match = TOKEN_RE.match(code, pos)
        if not match:
            pos += 1
            continue

        kind = match.lastgroup
        text = match.group()
        pos = match.end()

        if kind in ("SKIP", "NEWLINE", "COMMENT_BLOCK", "COMMENT_LINE"):
            continue
        if kind == "MISMATCH":
            continue

        tok = Token(kind, text)
        tokens.append(tok)
        prev_significant = tok

    return tokens


def _looks_like_regex_start(prev_tok):
    if prev_tok is None:
        return True
    if prev_tok.kind in ("MULTIOP", "PUNCT"):
        # после закрывающих скобок/идентификатора/числа/строки regex начаться не может
        return prev_tok.text not in (")", "]", "}")
    if prev_tok.kind == "IDENT":
        return prev_tok.text in KEYWORD_OPERATORS  # после keyword типа return, typeof и т.п.
    return False


def _match_regex_literal(code, pos):
    """Очень простой сканер regex-литерала /.../flags начиная с pos (code[pos]=='/')."""
    i = pos + 1
    n = len(code)
    in_class = False
    while i < n:
        c = code[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            i += 1
            # флаги
            while i < n and code[i].isalpha():
                i += 1
            return code[pos:i]
        elif c == "\n":
            return None
        i += 1
    return None


# ---------------------------------------------------------------------------
# Классификация и подсчёт метрик
# ---------------------------------------------------------------------------

class HalsteadResult:
    def __init__(self):
        self.operators = OrderedDict()  # name -> count (f1j)
        self.operands = OrderedDict()   # name -> count (f2i)

    @property
    def n1(self):
        return len(self.operators)

    @property
    def n2(self):
        return len(self.operands)

    @property
    def N1(self):
        return sum(self.operators.values())

    @property
    def N2(self):
        return sum(self.operands.values())

    @property
    def vocabulary(self):
        """eta = n1 + n2 (словарь программы)"""
        return self.n1 + self.n2

    @property
    def length(self):
        """N = N1 + N2 (длина программы)"""
        return self.N1 + self.N2

    @property
    def volume(self):
        """V = N * log2(eta) (объём программы)"""
        import math
        eta = self.vocabulary
        if eta <= 0:
            return 0.0
        return self.length * math.log2(eta)

    def add_operator(self, name):
        self.operators[name] = self.operators.get(name, 0) + 1

    def add_operand(self, name):
        self.operands[name] = self.operands.get(name, 0) + 1


def analyze(code: str) -> HalsteadResult:
    tokens = tokenize(code)
    result = HalsteadResult()

    n = len(tokens)
    for idx, tok in enumerate(tokens):
        kind, text = tok.kind, tok.text

        if kind in ("STRING_D", "STRING_S", "TEMPLATE"):
            result.add_operand(text)
            continue

        if kind == "REGEX":
            result.add_operand(text)
            continue

        if kind == "NUMBER":
            result.add_operand(text)
            continue

        if kind == "IDENT":
            if text in LITERAL_KEYWORDS:
                result.add_operand(text)
            elif text in KEYWORD_OPERATORS:
                result.add_operator(text)
            else:
                result.add_operand(text)
            continue

        if kind == "MULTIOP":
            result.add_operator(text)
            continue

        if kind == "PUNCT":
            if text == OPEN_PAREN:
                if _is_math_grouping_paren(tokens, idx):
                    result.add_operator("()")
                # иначе (управляющая конструкция / вызов функции / параметры function) -
                # скобка самостоятельным оператором не считается
                continue
            if text == CLOSE_PAREN:
                continue  # закрывающая скобка учтена вместе с открывающей как пара
            if text == OPEN_BRACE:
                result.add_operator("{}")
                continue
            if text == CLOSE_BRACE:
                continue
            if text == OPEN_BRACKET:
                result.add_operator("[]")
                continue
            if text == CLOSE_BRACKET:
                continue
            # обычная пунктуация-оператор: + - * / = < > ! & | ^ ~ ? : , ; .
            result.add_operator(text)
            continue

    return result


def _prev_significant_index(tokens, idx):
    j = idx - 1
    while j >= 0:
        return j
    return -1


def _is_math_grouping_paren(tokens, idx):
    """Определяет, является ли открывающая скобка tokens[idx] группирующей
    (математической/логической), а не частью if/while/for/switch/catch/with,
    вызова функции или списка параметров function(...)."""
    j = idx - 1
    if j < 0:
        return True  # скобка в самом начале файла - считаем группирующей

    prev = tokens[j]

    # после identifier -> вызов функции foo(...)  => не считается
    if prev.kind == "IDENT" and prev.text not in KEYWORD_OPERATORS and prev.text not in LITERAL_KEYWORDS:
        return False

    # после ключевого слова управляющей конструкции -> if(...) while(...) и т.д. => не считается
    if prev.kind == "IDENT" and prev.text in CONTROL_KEYWORDS:
        return False

    # после ключевого слова function -> список параметров => не считается
    if prev.kind == "IDENT" and prev.text == "function":
        return False

    # после закрывающей ")" сразу открывающая "(" на списке параметров стрелочной функции и т.п. -
    # редкий случай, считаем группирующей по умолчанию
    return True
