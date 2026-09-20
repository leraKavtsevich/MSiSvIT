import re
from collections import OrderedDict
import math

# Управляющие ключевые слова — участвуют в склейке
CONTROL_KEYWORDS = {"if", "else", "for", "while", "do", "switch",
                    "case", "default", "try", "catch", "finally"}

# Ключевые слова-операторы (не склеиваемые, одиночные)
SIMPLE_KEYWORD_OPERATORS = {
    "return", "throw", "break", "continue",
    "new", "delete", "typeof", "instanceof", "void",
    "yield", "await",
}

# Объявления — НЕ считаются (анализируется только раздел операторов)
DECLARATIONS = {
    "var", "let", "const", "function", "class",
    "import", "export", "from", "as",
    "extends", "super", "static", "get", "set",
    "async", "debugger",
}

# Константы-литералы — ОПЕРАНДЫ
LITERAL_KEYWORDS = {
    "true", "false", "null", "undefined", "NaN", "Infinity", "this",
}

# Ключевые слова, после которых '(' — часть конструкции, а не группировка
PAREN_ATTACHED_KEYWORDS = {"if", "while", "for", "switch", "catch", "with",
                           "function", "func"}

# Многосимвольные операторы (от длинных к коротким)
MULTI_CHAR_OPERATORS = [
    ">>>=", "===", "!==", "**=", "<<=", ">>=", "&&=", "||=", "??=",
    ">>>", "...", "=>",
    "++", "--", "**", "==", "!=", "<=", ">=", "&&", "||", "??",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<", ">>",
]

# Односимвольные операторы. ',' ИСКЛЮЧЕНА. '.' и ';' ВКЛЮЧЕНЫ.
SINGLE_CHAR_OPERATORS = set("+-*/%=<>!&|^~?:;.")

OPEN_PAREN, CLOSE_PAREN     = "(", ")"
OPEN_BRACE, CLOSE_BRACE     = "{", "}"
OPEN_BRACKET, CLOSE_BRACKET = "[", "]"



TOKEN_SPEC = [
    ("COMMENT_BLOCK", r"/\*.*?\*/"),
    ("COMMENT_LINE",  r"//[^\n]*"),
    ("TEMPLATE",      r"`(?:\\.|[^`\\])*`"),
    ("STRING_D",      r'"(?:\\.|[^"\\])*"'),
    ("STRING_S",      r"'(?:\\.|[^'\\])*'"),
    ("NUMBER",        r"\b0[xX][0-9a-fA-F]+\b|\b0[bB][01]+\b|\b0[oO][0-7]+\b|"
                      r"\b\d+\.\d+([eE][+-]?\d+)?\b|\b\.\d+([eE][+-]?\d+)?\b|"
                      r"\b\d+([eE][+-]?\d+)?\b"),
    ("IDENT",         r"[A-Za-z_$][A-Za-z0-9_$]*"),
    ("MULTIOP",       "|".join(re.escape(op) for op in MULTI_CHAR_OPERATORS)),
    ("PUNCT",         r"[{}()\[\]" + re.escape("".join(SINGLE_CHAR_OPERATORS)) + r"]"),
    ("NEWLINE",       r"\n"),
    ("SKIP",          r"[ \t\r]+"),
    ("MISMATCH",      r"."),
]

TOKEN_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC),
    re.DOTALL,
)


class Token:
    __slots__ = ("kind", "text")
    def __init__(self, kind, text):
        self.kind = kind
        self.text = text
    def __repr__(self):
        return f"Token({self.kind!r}, {self.text!r})"


def tokenize(code: str):
    """Возвращает список токенов без пробелов/комментариев, с regex-литералами."""
    tokens = []
    pos, n = 0, len(code)
    prev_significant = None

    while pos < n:
        # regex-литерал: '/' там, где ожидается операнд
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

        kind, text = match.lastgroup, match.group()
        pos = match.end()

        if kind in ("SKIP", "NEWLINE", "COMMENT_BLOCK", "COMMENT_LINE", "MISMATCH"):
            continue

        tok = Token(kind, text)
        tokens.append(tok)
        prev_significant = tok

    return tokens


def _looks_like_regex_start(prev_tok):
    if prev_tok is None:
        return True
    if prev_tok.kind in ("MULTIOP", "PUNCT"):
        return prev_tok.text not in (")", "]", "}")
    if prev_tok.kind == "IDENT":
        return (prev_tok.text in SIMPLE_KEYWORD_OPERATORS
                or prev_tok.text in CONTROL_KEYWORDS
                or prev_tok.text in DECLARATIONS)
    return False


def _match_regex_literal(code, pos):
    """Простой сканер /.../flags. Возвращает подстроку или None."""
    i, n = pos + 1, len(code)
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
            while i < n and code[i].isalpha():
                i += 1
            return code[pos:i]
        elif c == "\n":
            return None
        i += 1
    return None


class HalsteadResult:
    def __init__(self):
        self.operators = OrderedDict()   # name -> count
        self.operands  = OrderedDict()   # name -> count

    # ---- базовые метрики ----
    @property
    def n1(self):  return len(self.operators)          # η1
    @property
    def n2(self):  return len(self.operands)           # η2
    @property
    def N1(self):  return sum(self.operators.values()) # N1
    @property
    def N2(self):  return sum(self.operands.values())  # N2

    # ---- производные метрики ----
    @property
    def vocabulary(self):  return self.n1 + self.n2     # η = η1 + η2
    @property
    def length(self):      return self.N1 + self.N2     # N = N1 + N2
    @property
    def volume(self):                                   # V = N * log2(η)
        eta = self.vocabulary
        if eta <= 0:
            return 0.0
        return self.length * math.log2(eta)

    # ---- добавление ----
    def add_operator(self, name):
        self.operators[name] = self.operators.get(name, 0) + 1

    def add_operand(self, name):
        self.operands[name] = self.operands.get(name, 0) + 1

    # ---- отчёт ----
    def report(self) -> str:
        lines = []
        lines.append(f"η1 (уникальных операторов) = {self.n1}")
        lines.append(f"η2 (уникальных операндов)  = {self.n2}")
        lines.append(f"N1 (всего операторов)      = {self.N1}")
        lines.append(f"N2 (всего операндов)       = {self.N2}")
        lines.append(f"η  (словарь программы)     = {self.vocabulary}")
        lines.append(f"N  (длина программы)       = {self.length}")
        lines.append(f"V  (объём программы)       = {self.volume:.2f}")
        return "\n".join(lines)


def _collect_function_names(tokens):
    """
    Имя функции — IDENT:
      * непосредственно перед '(' (вызов foo(...)),
      * или после 'function'.
    Такие идентификаторы по PDF — ОПЕРАТОРЫ.
    Управляющие ключевые слова, литералы и объявления исключаются.
    """
    names = set()
    for i, tok in enumerate(tokens):
        if tok.kind != "IDENT":
            continue
        nxt = tokens[i + 1].text if i + 1 < len(tokens) else None
        prv = tokens[i - 1].text if i > 0 else None

        if nxt == "(":
            if tok.text in PAREN_ATTACHED_KEYWORDS:   # if/while/for/switch/catch/function
                continue
            if tok.text in LITERAL_KEYWORDS:
                continue
            if tok.text in DECLARATIONS:
                continue
            names.add(tok.text)

        if prv == "function":
            names.add(tok.text)

    return names


def _is_math_grouping_paren(tokens, idx):
    """
    True  — '(' группирует подвыражение         => оператор '( )'.
    False — '(' часть вызова/конструкции/params => не считается.
    """
    j = idx - 1
    if j < 0:
        return True

    prev = tokens[j]

    # после идентификатора
    if prev.kind == "IDENT":
        # if(...) while(...) for(...) switch(...) catch(...) function(...)
        if prev.text in PAREN_ATTACHED_KEYWORDS:
            return False
        if prev.text in LITERAL_KEYWORDS:
            return False
        if prev.text in DECLARATIONS:
            return False
        # вызов функции foo(...)
        return False

    # после ')' — вызов результата: foo()()
    if prev.kind == "PUNCT" and prev.text == CLOSE_PAREN:
        return False

    # после ']' — вызов результата индекса: arr[i]()
    if prev.kind == "PUNCT" and prev.text == CLOSE_BRACKET:
        return False

    # после операторов/открывающих скобок/запятой/точки с запятой — группировка
    return True


def _is_ternary_colon(tokens, idx):
    """True, если ':' — часть тернарного '? :'."""
    depth = 0
    for k in range(idx - 1, -1, -1):
        t = tokens[k].text
        if t in (")", "]"):
            depth += 1
        elif t in ("(", "["):
            if depth == 0:
                break
            depth -= 1
        elif depth == 0:
            if t in (";", "{", "}"):
                break
            if t == "?":
                return True
    return False



def analyze(code: str) -> HalsteadResult:
    tokens = tokenize(code)
    result = HalsteadResult()
    function_names = _collect_function_names(tokens)

    # Стек незакрытых управляющих конструкций для склейки.
    # Элементы: {'kind': 'if'|'switch'|'try'|'do'|'for', 'parts': set}
    pending = []

    n = len(tokens)
    for idx, tok in enumerate(tokens):
        kind, text = tok.kind, tok.text

        # ---------- литералы / строки / числа / regex -> операнды ----------
        if kind in ("STRING_D", "STRING_S", "TEMPLATE", "REGEX", "NUMBER"):
            result.add_operand(text)
            continue

        # ---------- идентификаторы ----------
        if kind == "IDENT":
            # константы -> операнды
            if text in LITERAL_KEYWORDS:
                result.add_operand(text)
                continue

            # объявления -> пропуск
            if text in DECLARATIONS:
                continue

            # имена функций -> операторы
            if text in function_names:
                result.add_operator(text)
                continue

            # --- склейка управляющих конструкций ---

            # IF: сразу учитываем как один оператор 'if-else'.
            # ELSE: часть того же оператора, отдельно НЕ считается.
            if text == "if":
                result.add_operator("if-else")
                pending.append({'kind': 'if'})
                continue
            if text == "else":
                # закрываем соответствующий 'if' в стеке, если он есть
                if pending and pending[-1]['kind'] == 'if':
                    pending.pop()
                # 'else' без 'if' — некорректный код, просто игнорируем
                continue

            # SWITCH / CASE / DEFAULT — все дают один тип оператора,
            # каждое слово = отдельное вхождение.
            if text == "switch":
                result.add_operator("switch-case-default")
                pending.append({'kind': 'switch'})
                continue
            if text in ("case", "default"):
                result.add_operator("switch-case-default")
                continue

            # TRY / CATCH / FINALLY — один тип оператора.
            if text == "try":
                result.add_operator("try-catch-finally")
                pending.append({'kind': 'try'})
                continue
            if text == "catch":
                result.add_operator("try-catch-finally")
                continue
            if text == "finally":
                result.add_operator("try-catch-finally")
                if pending and pending[-1]['kind'] == 'try':
                    pending.pop()
                continue

            # DO / WHILE — склейка в 'do-while'
            if text == "do":
                result.add_operator("do-while")
                pending.append({'kind': 'do'})
                continue
            if text == "while":
                if pending and pending[-1]['kind'] == 'do':
                    # } while ( ... ) от do-while
                    result.add_operator("do-while")
                    pending.pop()
                else:
                    result.add_operator("while")
                continue

            # FOR / IN / OF — 'in'/'of' часть того же оператора
            if text == "for":
                result.add_operator("for")
                pending.append({'kind': 'for'})
                continue
            if text in ("in", "of"):
                if pending and pending[-1]['kind'] == 'for':
                    # часть того же оператора 'for' — не считаем отдельно
                    continue
                # вне for — редкий случай (например, 'in' в объекте)
                result.add_operator(text)
                continue

            # одиночные ключевые слова-операторы
            if text in SIMPLE_KEYWORD_OPERATORS:
                result.add_operator(text)
                continue

            # обычный идентификатор — переменная
            result.add_operand(text)
            continue

        # ---------- многосимвольные операторы ----------
        if kind == "MULTIOP":
            result.add_operator(text)
            continue

        # ---------- пунктуация ----------
        if kind == "PUNCT":
            # круглые скобки
            if text == OPEN_PAREN:
                if _is_math_grouping_paren(tokens, idx):
                    result.add_operator("( )")
                continue
            if text == CLOSE_PAREN:
                continue

            # фигурные скобки — всегда один оператор '{ }'
            if text == OPEN_BRACE:
                result.add_operator("{ }")
                continue
            if text == CLOSE_BRACE:
                continue

            # квадратные скобки — всегда один оператор '[ ]'
            if text == OPEN_BRACKET:
                result.add_operator("[ ]")
                continue
            if text == CLOSE_BRACKET:
                continue

            # запятая — не оператор (по PDF)
            if text == ",":
                continue

            # тернарный оператор '? :' — один оператор
            if text == "?":
                result.add_operator("? :")
                continue
            if text == ":":
                # ':' внутри '? :' — уже учтён; в 'case'/'default' — часть
                # склеенного оператора; в 'label:' — метка (не считается)
                continue

            # остальные односимвольные операторы (. ; + - * / = < > ! & | ^ ~)
            result.add_operator(text)
            continue

    

    return result

if __name__ == "__main__":
    sample = r'''
    // Пример на JS
    function sinTaylor(x, eps) {
        let y = x;
        let n = 2;
        let vs = x;
        do {
            vs = -vs * x * x / (2 * n - 1) / (2 * n - 2);
            n = n + 1;
            y = y + vs;
        } while (Math.abs(vs) >= eps);
        return y;
    }

    const r = sinTaylor(0.5, 0.0001);
    console.log(r);
    '''
    r = analyze(sample)
    print(r.report())
    print()
    print("Операторы:")
    for name, cnt in r.operators.items():
        print(f"  {name!r:20} x{cnt}")
    print("Операнды:")
    for name, cnt in r.operands.items():
        print(f"  {name!r:20} x{cnt}")