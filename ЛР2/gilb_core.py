# -*- coding: utf-8 -*-
"""
gilb_core.py
Расчёт метрики Джилба для исходного кода на JavaScript.

  CL  — абсолютная сложность: количество ветвлений
        (if / else if, for, for..in, for..of, for await..of, while,
        do..while, тернарный ?:, ветви switch);
  cl  — относительная сложность: CL / общее количество операторов;
  CLI — максимальный уровень вложенности ветвлений.

Правила для switch (по заданию):
  оператор множественного выбора заменяется вложенными друг в друга
  операторами условия. Каждая ветвь case -> один if, i-я ветвь вложена
  в else предыдущей. Селектор switch(x) и ветвь default условиями
  не являются. Несколько меток подряд с общим телом
  (case 1: case 2: ...) — одна ветвь (одно условие x==1 || x==2).
  break, завершающий ветвь case, в эквивалентной if-записи отсутствует,
  поэтому оператором не считается.

Уровень вложенности отсчитывается так же, как в методичке
(оператор выбора с n ветвями = n-1 if с глубиной вложенности n-2):
ветвление верхнего уровня имеет уровень 0.
"""

import re

# ---------------------------------------------------------------------------
# Токенизация
# ---------------------------------------------------------------------------

PUNCTUATORS = sorted([
    ">>>=", "...", "===", "!==", "**=", "<<=", ">>=", ">>>", "&&=", "||=", "??=",
    "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "**",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<", ">>",
    "{", "}", "(", ")", "[", "]", ";", ",", "<", ">", "+", "-", "*", "/", "%",
    "&", "|", "^", "!", "~", "?", ":", "=", ".", "@", "#",
], key=len, reverse=True)

KEYWORDS = {
    "var", "let", "const", "function", "return", "if", "else", "for", "while",
    "do", "switch", "case", "default", "break", "continue", "try", "catch",
    "finally", "throw", "new", "delete", "typeof", "instanceof", "in", "of",
    "class", "extends", "super", "import", "export", "void", "with",
    "debugger", "yield", "await", "this", "null", "true", "false",
}

# после этих ключевых слов "/" начинает регулярное выражение
REGEX_AFTER_KEYWORDS = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "throw", "case", "do", "else", "yield", "await",
}


class Token:
    __slots__ = ("kind", "text", "line", "nl")

    def __init__(self, kind, text, line, nl):
        self.kind = kind      # ident | num | str | tpl | regex | punct | eof
        self.text = text
        self.line = line      # номер строки (с 1)
        self.nl = nl          # перед токеном был перевод строки

    def __repr__(self):
        return f"{self.kind}:{self.text!r}@{self.line}"


class ParseError(Exception):
    pass


_NUM_RE = re.compile(
    r"0[xX][0-9a-fA-F_]+n?|0[bB][01_]+n?|0[oO][0-7_]+n?|"
    r"(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d+)?n?"
)
_IDENT_RE = re.compile(r"[A-Za-z_$\u0080-\uffff][A-Za-z0-9_$\u0080-\uffff]*")


def tokenize(code, first_line=1):
    tokens = []
    i, n, line, nl = 0, len(code), first_line, True

    def regex_allowed():
        if not tokens:
            return True
        p = tokens[-1]
        if p.kind in ("num", "str", "tpl", "regex"):
            return False
        if p.kind == "ident":
            return p.text in REGEX_AFTER_KEYWORDS
        return p.text not in (")", "]", "}")

    while i < n:
        c = code[i]
        if c == "\n":
            line += 1
            nl = True
            i += 1
            continue
        if c in " \t\r\f\v\ufeff\u00a0":
            i += 1
            continue
        # комментарии
        if code.startswith("//", i):
            j = code.find("\n", i)
            i = n if j < 0 else j
            continue
        if code.startswith("/*", i):
            j = code.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += code.count("\n", i, j)
            if "\n" in code[i:j]:
                nl = True
            i = j
            continue
        start_line = line
        # строки
        if c in "'\"":
            j = i + 1
            while j < n and code[j] != c:
                if code[j] == "\\":
                    j += 1
                elif code[j] == "\n":
                    break
                j += 1
            tokens.append(Token("str", code[i:j + 1], start_line, nl))
            i, nl = j + 1, False
            continue
        # шаблонные строки: сама строка — один токен, а выражения ${...}
        # разбираются отдельно (в них тоже могут быть ?: и функции)
        if c == "`":
            j, parts = i + 1, []
            while j < n and code[j] != "`":
                if code[j] == "\\":
                    j += 2
                    continue
                if code.startswith("${", j):
                    k, depth, s = j + 2, 1, j + 2
                    while k < n and depth:
                        if code[k] in "{":
                            depth += 1
                        elif code[k] == "}":
                            depth -= 1
                        elif code[k] in "'\"`":      # строка внутри ${...}
                            q = code[k]
                            k += 1
                            while k < n and code[k] != q:
                                k += 2 if code[k] == "\\" else 1
                        k += 1
                    parts.append((s, k - 1, line + code.count("\n", i, s)))
                    j = k
                    continue
                j += 1
            tokens.append(Token("tpl", code[i:j + 1], start_line, nl))
            for s, e, ln in parts:
                tokens.append(Token("punct", "(", ln, False))
                tokens.extend(tokenize(code[s:e], ln)[:-1])
                tokens.append(Token("punct", ")", ln, False))
            line += code.count("\n", i, j + 1)
            i, nl = j + 1, False
            continue
        # регулярные выражения
        if c == "/" and regex_allowed():
            j, in_cls = i + 1, False
            while j < n and code[j] != "\n":
                ch = code[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    in_cls = True
                elif ch == "]":
                    in_cls = False
                elif ch == "/" and not in_cls:
                    break
                j += 1
            if j < n and code[j] == "/":
                j += 1
                while j < n and (code[j].isalnum() or code[j] == "_"):
                    j += 1
                tokens.append(Token("regex", code[i:j], start_line, nl))
                i, nl = j, False
                continue
        # числа
        if c.isdigit() or (c == "." and i + 1 < n and code[i + 1].isdigit()):
            m = _NUM_RE.match(code, i)
            tokens.append(Token("num", m.group(), start_line, nl))
            i, nl = m.end(), False
            continue
        # идентификаторы / ключевые слова
        m = _IDENT_RE.match(code, i)
        if m:
            tokens.append(Token("ident", m.group(), start_line, nl))
            i, nl = m.end(), False
            continue
        # знаки пунктуации
        for p in PUNCTUATORS:
            if code.startswith(p, i):
                # "?." перед цифрой — это тернарный "?" и число ".5"
                if p == "?." and i + 2 < n and code[i + 2].isdigit():
                    continue
                tokens.append(Token("punct", p, start_line, nl))
                i, nl = i + len(p), False
                break
        else:
            raise ParseError(f"Неизвестный символ {c!r} в строке {line}")
    tokens.append(Token("eof", "", line, True))
    return tokens


# ---------------------------------------------------------------------------
# Результат
# ---------------------------------------------------------------------------

class Branch:
    """Одно ветвление (условие), учтённое в CL."""
    __slots__ = ("line", "kind", "level", "text")

    def __init__(self, line, kind, level, text):
        self.line, self.kind, self.level, self.text = line, kind, level, text


class Statement:
    """Один оператор программы, учтённый в знаменателе cl."""
    __slots__ = ("line", "kind")

    def __init__(self, line, kind):
        self.line, self.kind = line, kind


class GilbResult:
    def __init__(self):
        self.branches = []
        self.statements = []

    @property
    def CL(self):
        return len(self.branches)

    @property
    def total_statements(self):
        return len(self.statements)

    @property
    def cl(self):
        return self.CL / self.total_statements if self.statements else 0.0

    def CLI(self, base=0):
        """Максимальный уровень вложенности. base — уровень внешнего
        ветвления (0 — как в методичке, 1 — если считать с единицы)."""
        if not self.branches:
            return 0
        return max(b.level for b in self.branches) + base


# ---------------------------------------------------------------------------
# Разбор
# ---------------------------------------------------------------------------

# токены, которыми может заканчиваться выражение (для автоподстановки ";")
_EXPR_END_PUNCT = {")", "]", "}", "++", "--"}
_EXPR_END_KW = {"this", "null", "true", "false", "super"}
# ключевые слова, продолжающие выражение с новой строки
_CONTINUE_KW = {"in", "instanceof", "of"}
_OPEN = {"(": ")", "[": "]", "{": "}"}


class _Parser:
    def __init__(self, code):
        self.code_lines = code.splitlines()
        self.t = tokenize(code)
        self.p = 0
        self.r = GilbResult()
        # стек конструкций, к которым относится break: "loop" / "switch" / "func"
        self.breakable = []

    # --- служебное ---------------------------------------------------------
    @property
    def tok(self):
        return self.t[self.p]

    def peek(self, k=1):
        return self.t[min(self.p + k, len(self.t) - 1)]

    def at(self, text, kind=None):
        tk = self.tok
        return tk.text == text and tk.kind in ((kind,) if kind else ("punct", "ident"))

    def next(self):
        tk = self.tok
        if tk.kind != "eof":
            self.p += 1
        return tk

    def expect(self, text):
        if self.tok.text != text:
            raise ParseError(f"Строка {self.tok.line}: ожидалось «{text}», "
                             f"найдено «{self.tok.text or 'конец файла'}»")
        return self.next()

    def branch(self, tok, kind, level):
        src = self.code_lines[tok.line - 1].strip() if tok.line <= len(self.code_lines) else ""
        self.r.branches.append(Branch(tok.line, kind, level, src))

    def stmt(self, tok, kind):
        self.r.statements.append(Statement(tok.line, kind))

    def skip_semicolon(self):
        if self.at(";", "punct"):
            self.next()

    # --- программа и блоки -------------------------------------------------
    def parse_program(self):
        while self.tok.kind != "eof":
            self.statement(0)
        return self.r

    def block_body(self, depth):
        """{ операторы } — фигурная скобка уже текущая."""
        self.expect("{")
        while not self.at("}", "punct"):
            if self.tok.kind == "eof":
                raise ParseError("Не закрыта фигурная скобка «{»")
            self.statement(depth)
        self.next()

    def function_body(self, depth):
        self.breakable.append("func")
        self.block_body(depth)
        self.breakable.pop()

    # --- операторы ---------------------------------------------------------
    def statement(self, depth):
        tk = self.tok
        w = tk.text if tk.kind == "ident" else None

        if tk.kind == "punct":
            if tk.text == "{":
                self.block_body(depth)
                return
            if tk.text == ";":
                self.next()
                return

        # метка:  label: for (...)
        if tk.kind == "ident" and w not in KEYWORDS and self.peek().text == ":":
            self.next(); self.next()
            self.statement(depth)
            return

        if w == "if":
            self.parse_if(depth, "if")
        elif w == "for":
            self.parse_for(depth)
        elif w == "while":
            self.next()
            self.branch(tk, "while", depth)
            self.stmt(tk, "while")
            self.paren_expr(depth)
            self.loop_body(depth + 1)
        elif w == "do":
            self.next()
            self.branch(tk, "do..while", depth)
            self.stmt(tk, "do..while")
            self.loop_body(depth + 1)
            self.expect("while")
            self.paren_expr(depth)
            self.skip_semicolon()
        elif w == "switch":
            self.parse_switch(depth)
        elif w == "try":
            self.next()
            self.stmt(tk, "try")
            self.block_body(depth)
            if self.at("catch", "ident"):
                self.next()
                if self.at("(", "punct"):
                    self.paren_expr(depth)
                self.block_body(depth)
            if self.at("finally", "ident"):
                self.next()
                self.block_body(depth)
        elif w in ("function",) or (w == "async" and self.peek().text == "function"
                                     and not self.peek().nl):
            self.parse_function_decl(depth)
        elif w == "class":
            self.parse_class(depth)
        elif w in ("var", "const") or (w == "let" and self.peek().kind == "ident"
                                       or w == "let" and self.peek().text in ("[", "{")):
            self.next()
            self.stmt(tk, w)
            self.expression(depth)
            self.skip_semicolon()
        elif w in ("return", "throw"):
            self.next()
            self.stmt(tk, w)
            if not (self.tok.nl or self.at(";", "punct") or self.at("}", "punct")
                    or self.tok.kind == "eof"):
                self.expression(depth)
            self.skip_semicolon()
        elif w in ("break", "continue"):
            self.next()
            has_label = self.tok.kind == "ident" and not self.tok.nl and \
                self.tok.text not in KEYWORDS
            if has_label:
                self.next()
            self.skip_semicolon()
            # break, закрывающий ветвь case, в if-эквиваленте не существует
            nearest = self.breakable[-1] if self.breakable else None
            if not (w == "break" and not has_label and nearest == "switch"):
                self.stmt(tk, w)
        elif w == "import" and self.peek().text not in ("(", "."):
            # объявление импорта — не исполняемый оператор
            self.next()
            self.expression(depth)
            self.skip_semicolon()
        elif w == "export":
            self.next()
            if self.at("default", "ident"):
                self.next()
            if self.tok.text in ("{", "*"):
                self.expression(depth)
                self.skip_semicolon()
            else:
                self.statement(depth)
        elif w == "debugger":
            self.next()
            self.stmt(tk, "debugger")
            self.skip_semicolon()
        elif w in ("else", "case", "default", "catch", "finally"):
            raise ParseError(f"Строка {tk.line}: неожиданное «{w}»")
        else:
            # оператор-выражение (присваивание, вызов функции, ++ и т.д.)
            self.stmt(tk, "выражение")
            self.expression(depth)
            self.skip_semicolon()

    def loop_body(self, depth):
        self.breakable.append("loop")
        self.statement(depth)
        self.breakable.pop()

    def parse_if(self, depth, kind):
        tk = self.next()
        self.branch(tk, kind, depth)
        self.stmt(tk, kind)
        self.paren_expr(depth)
        self.statement(depth + 1)
        if self.at("else", "ident"):
            self.next()
            if self.at("if", "ident"):
                # else if — if, вложенный в ветвь else
                self.parse_if(depth + 1, "else if")
            else:
                self.statement(depth + 1)

    def parse_for(self, depth):
        tk = self.next()
        kind = "for"
        if self.at("await", "ident"):
            self.next()
            kind = "for await..of"
        # определяем вид цикла по заголовку: of/in на верхнем уровне скобок
        start = self.p
        self.expect("(")
        lvl = 0
        while True:
            t = self.tok
            if t.kind == "eof":
                raise ParseError(f"Строка {tk.line}: не закрыт заголовок for")
            if t.kind == "punct" and t.text in ("(", "[", "{"):
                lvl += 1
            elif t.kind == "punct" and t.text in (")", "]", "}"):
                if lvl == 0:
                    break
                lvl -= 1
            elif lvl == 0 and kind == "for" and t.kind == "ident" and t.text in ("of", "in"):
                kind = "for..of" if t.text == "of" else "for..in"
            elif lvl == 0 and t.text == ";":
                if kind != "for await..of":
                    kind = "for"
                break
            self.next()
        self.p = start
        self.branch(tk, kind, depth)
        self.stmt(tk, kind)
        self.paren_expr(depth)
        self.loop_body(depth + 1)

    def parse_switch(self, depth):
        tk = self.next()
        self.paren_expr(depth)          # селектор — не условие
        self.expect("{")
        self.breakable.append("switch")
        # Метки и тела разбираются по порядку; уровень тела зависит
        # от номера ветви, известного в момент метки.
        cond_index = 0                  # номер текущей ветви-условия (0..k-1)
        pending_labels = []             # метки без тела (case 1: case 2:)
        pending_default = False

        def flush_group():
            nonlocal cond_index, pending_labels, pending_default
            if pending_labels and not pending_default:
                lvl = depth + cond_index
                first = pending_labels[0]
                self.branch(first, "switch-case", lvl)
                self.stmt(first, "case → if")
                cond_index += 1
                body_level = lvl + 1
            else:
                # ветвь default — заключительный else цепочки if
                body_level = depth + cond_index
            pending_labels = []
            pending_default = False
            return body_level

        body_level = depth
        while not self.at("}", "punct"):
            if self.tok.kind == "eof":
                raise ParseError(f"Строка {tk.line}: не закрыт switch")
            if self.at("case", "ident"):
                ct = self.next()
                pending_labels.append(ct)
                self.expression(depth, stop_colon=True)
                self.expect(":")
                continue
            if self.at("default", "ident"):
                self.next()
                self.expect(":")
                pending_default = True
                pending_labels.append(self.t[self.p - 2])
                continue
            # тело ветви
            if pending_labels:
                body_level = flush_group()
            self.statement(body_level)
        if pending_labels:
            flush_group()
        self.next()
        self.breakable.pop()
        if cond_index == 0:
            # switch только с default — один оператор, ветвлений нет
            self.stmt(tk, "switch")

    def parse_function_decl(self, depth):
        if self.at("async", "ident"):
            self.next()
        self.expect("function")
        if self.at("*", "punct"):
            self.next()
        if self.tok.kind == "ident":
            self.next()
        self.paren_expr(depth)
        self.function_body(depth)

    def parse_class(self, depth):
        self.next()
        while not self.at("{", "punct"):
            if self.tok.kind == "eof":
                raise ParseError("Не найдено тело класса")
            if self.at("extends", "ident"):
                self.next()
                self.expression(depth, stop_brace=True)
                continue
            self.next()
        self.skip_balanced_with_functions(depth)

    # --- выражения ---------------------------------------------------------
    def paren_expr(self, depth):
        """( ... ) — пропуск содержимого с учётом тернарных операторов
        и тел функций внутри."""
        if not self.at("(", "punct"):
            raise ParseError(f"Строка {self.tok.line}: ожидалось «(»")
        self.skip_balanced_with_functions(depth)

    def skip_balanced_with_functions(self, depth):
        """Текущий токен — открывающая скобка. Пропускает до парной,
        разбирая вложенные функции и тернарные операторы."""
        self.expression(depth, balanced=True)

    def expression(self, depth, balanced=False, stop_colon=False, stop_brace=False):
        """Пропускает выражение. Внутри выражения:
          ? (тернарный)          -> ветвление;
          ) {  и  => {           -> тело функции (разбирается как операторы);
          function ... ( ) {     -> то же.
        balanced=True: текущий токен — открывающая скобка, читать до парной.
        Иначе — до ; / } / конца строки (автоподстановка ;) на верхнем уровне.
        """
        frames = [0]            # на каждом уровне скобок — число открытых ?
        q_open = 0              # незакрытые ? на верхнем уровне (для case ... :)
        closers = []
        if balanced:
            op = self.next()
            closers.append(_OPEN[op.text])
            frames.append(0)
        prev = self.t[self.p - 1] if self.p else None
        first = True

        while True:
            tk = self.tok
            if tk.kind == "eof":
                if closers:
                    raise ParseError("Не закрыта скобка в выражении")
                return
            top = not closers

            if top and not first:
                if tk.kind == "punct" and tk.text in (";", "}", ")", "]"):
                    return
                if stop_colon and tk.text == ":" and q_open == 0:
                    return
                if stop_brace and tk.text == "{":
                    return
                if tk.nl and self._asi_break(prev, tk):
                    return
            elif top and first:
                if tk.kind == "punct" and tk.text in (";", "}", ")", "]"):
                    return
            first = False

            lvl = depth + sum(frames)

            if tk.kind == "punct":
                t = tk.text
                if t == "?":
                    self.branch(tk, "?: (тернарный)", lvl)
                    frames[-1] += 1
                    if not closers:
                        q_open += 1
                elif t == ":" and closers == [] and stop_colon:
                    q_open -= 1          # ":" тернарного оператора в метке case
                elif t == ",":
                    frames[-1] = 0
                elif t == "{" and prev is not None and prev.kind == "punct" \
                        and prev.text in (")", "=>"):
                    # тело функции / метода
                    self.function_body(lvl)
                    prev = self.t[self.p - 1]
                    continue
                elif t in _OPEN:
                    closers.append(_OPEN[t])
                    frames.append(0)
                elif t in (")", "]", "}"):
                    if not closers or closers[-1] != t:
                        raise ParseError(f"Строка {tk.line}: непарная скобка «{t}»")
                    closers.pop()
                    frames.pop()
                    self.next()
                    if balanced and not closers:
                        return
                    prev = tk
                    continue
                elif t == "=>" and self.peek().text == "{":
                    self.next()
                    prev = tk
                    continue
            elif tk.kind == "ident" and tk.text == "class" and not (
                    prev is not None and prev.text in (".", "?.")):
                # выражение-класс: пропускаем до тела
                self.next()
                while not self.at("{", "punct"):
                    if self.tok.kind == "eof":
                        raise ParseError("Не найдено тело класса")
                    self.next()
                prev = self.t[self.p - 1]
                self.expression(lvl, balanced=True)
                prev = self.t[self.p - 1]
                continue
            prev = tk
            self.next()

    @staticmethod
    def _asi_break(prev, tk):
        """Автоматическая вставка ';' при переводе строки."""
        if prev is None:
            return False
        ends = (prev.kind in ("num", "str", "tpl", "regex")
                or (prev.kind == "ident" and (prev.text not in KEYWORDS
                                              or prev.text in _EXPR_END_KW))
                or (prev.kind == "punct" and prev.text in _EXPR_END_PUNCT))
        if not ends:
            return False
        if tk.kind in ("num", "str", "regex"):
            return True
        if tk.kind == "ident":
            return tk.text not in _CONTINUE_KW
        if tk.kind == "punct":
            return tk.text in ("++", "--", "{", "!", "~")
        return False


def analyze(code):
    """Возвращает GilbResult для исходного текста JavaScript."""
    return _Parser(code).parse_program()
