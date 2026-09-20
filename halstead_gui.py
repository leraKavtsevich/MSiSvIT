import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from halstead_core import analyze, tokenize



SAMPLE_CODE = """function isPrime(num) {
    if (num <= 1) {
        return false;
    }
    for (let i = 2; i <= Math.sqrt(num); i++) {
        if (num % i === 0) {
            return false;
        }
    }
    return true;
}

let count = 0;
let limit = 50;
for (let n = 2; n < limit; n = n + 1) {
    if (isPrime(n)) {
        count = count + 1;
        console.log(n);
    }
}
let ratio = (count / limit) * 100;
"""



RULES_TEXT = """ПРАВИЛА ПОДСЧЁТА (соответствуют halstead_core.py)

ОПЕРАТОРЫ:
  • знаки операций: + - * / % < > <= >= == != === !== && || ! ++ --
    += -= *= /= %= ?:  и т.п.
  • присваивание =
  • разделители: . (доступ к свойству) и ; (конец оператора)
  • пара ( ) — ОДИН оператор, если это группировка подвыражения,
    например: (2 + 3) * (4 - 1).
    В вызовах foo(...), в if(...), while(...), for(...), switch(...),
    catch(...), function(...) скобки оператором НЕ считаются.
    Также НЕ считаются: foo()()  и  arr[i]()  (вызов результата).
  • составной оператор { } — ОДИН оператор на пару.
  • индекс/массив [ ] — ОДИН оператор на пару.
  • имена процедур и функций (например, foo в foo(x)) — ОПЕРАТОРЫ.
  • управляющие конструкции СКЛЕИВАЮТСЯ в один оператор:
        if ... else                → if-else
        switch/case/default        → switch-case-default
        try/catch/finally          → try-catch-finally
        do ... while               → do-while
        for ( ... )                → for
        for (... in ...) / (... of ...) → for (in/of — часть того же)
        while ( ... )              → while
        a ? b : c                  → ? :
  • одиночные ключевые слова-операторы:
        return, break, continue, throw,
        new, delete, typeof, instanceof, void,
        yield, await.

НЕ СЧИТАЮТСЯ (ни операторами, ни операндами):
  • объявления: let, var, const, function, class,
    import, export, from, as, extends, super,
    static, get, set, async, debugger;
  • запятая ',';
  • метки (label:);
  • закрывающие скобки ) } ] и открывающая ( для вызова/конструкции.

ОПЕРАНДЫ:
  • переменные (идентификаторы, не являющиеся функциями
    и не входящие в списки ключевых слов/объявлений);
  • числа (десятичные, hex, bin, oct, с плавающей точкой);
  • строки в "..." и '...', шаблонные строки `...`;
  • regex-литералы /.../flags;
  • константы: true, false, null, undefined, NaN, Infinity, this.

ПРОИЗВОДНЫЕ МЕТРИКИ:
  η = η1 + η2          — словарь программы
  N = N1 + N2          — длина программы
  V = N · log₂(η)      — объём программы
"""


class HalsteadApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Метрики Холстеда — анализатор JavaScript")
        self.geometry("1180x760")
        self.minsize(900, 600)

        self._build_menu()
        self._build_layout()

        # при старте — пример, помечаем как пример
        self.file_label.config(text="Файл не загружен (пример)")
        self._last_result = None

    
    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Открыть файл .js...",
            command=self.open_file,
            accelerator="Ctrl+O",
        )
        file_menu.add_command(label="Загрузить пример", command=self.load_sample)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)
        menubar.add_cascade(label="Файл", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О правилах подсчёта", command=self.show_rules)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.config(menu=menubar)
        self.bind("<Control-o>", self._on_ctrl_o)

    def _on_ctrl_o(self, event):
        self.open_file()
        return "break"

    
    def _build_layout(self):
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---------------- Левая панель: ввод кода ----------------
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text="Исходный код JavaScript:",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        text_frame = ttk.Frame(left_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.code_text = tk.Text(
            text_frame, wrap="none", font=("Consolas", 10), undo=True
        )
        y_scroll = ttk.Scrollbar(text_frame, orient="vertical",
                                 command=self.code_text.yview)
        x_scroll = ttk.Scrollbar(text_frame, orient="horizontal",
                                 command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=y_scroll.set,
                                 xscrollcommand=x_scroll.set)

        self.code_text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self.code_text.insert("1.0", SAMPLE_CODE)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(btn_frame, text="Открыть файл...",
                   command=self.open_file).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Очистить",
                   command=self.clear_code).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Показать токены",
                   command=self.show_tokens).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Рассчитать метрики",
                   command=self.calculate).pack(side=tk.RIGHT)

        self.file_label = ttk.Label(
            left_frame,
            text="Файл не загружен (пример)",
            foreground="#666",
        )
        self.file_label.pack(anchor="w", pady=(6, 0))

        # ---------------- Правая панель: результаты ----------------
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        ttk.Label(
            right_frame,
            text="Базовые метрики Холстеда (таблица, аналог примера 1):",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        tables_frame = ttk.Frame(right_frame)
        tables_frame.pack(fill=tk.BOTH, expand=True)

        # --- Таблица операторов ---
        op_frame = ttk.LabelFrame(tables_frame, text="Операторы")
        op_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        self.op_tree = ttk.Treeview(
            op_frame, columns=("j", "operator", "f1j"),
            show="headings", height=16,
        )
        self.op_tree.heading("j", text="j")
        self.op_tree.heading("operator", text="Оператор")
        self.op_tree.heading("f1j", text="f1j")
        self.op_tree.column("j", width=40, anchor="center")
        self.op_tree.column("operator", width=160, anchor="center")
        self.op_tree.column("f1j", width=60, anchor="center")
        op_scroll = ttk.Scrollbar(op_frame, orient="vertical",
                                  command=self.op_tree.yview)
        self.op_tree.configure(yscrollcommand=op_scroll.set)
        self.op_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        op_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Таблица операндов ---
        opd_frame = ttk.LabelFrame(tables_frame, text="Операнды")
        opd_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))

        self.opd_tree = ttk.Treeview(
            opd_frame, columns=("i", "operand", "f2i"),
            show="headings", height=16,
        )
        self.opd_tree.heading("i", text="i")
        self.opd_tree.heading("operand", text="Операнд")
        self.opd_tree.heading("f2i", text="f2i")
        self.opd_tree.column("i", width=40, anchor="center")
        self.opd_tree.column("operand", width=160, anchor="center")
        self.opd_tree.column("f2i", width=60, anchor="center")
        opd_scroll = ttk.Scrollbar(opd_frame, orient="vertical",
                                   command=self.opd_tree.yview)
        self.opd_tree.configure(yscrollcommand=opd_scroll.set)
        self.opd_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        opd_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Итоговая строка базовых метрик ---
        basic_summary = ttk.Frame(right_frame)
        basic_summary.pack(fill=tk.X, pady=(6, 10))

        self.basic_vars = {
            "n1": tk.StringVar(value="η1 = —"),
            "N1": tk.StringVar(value="N1 = —"),
            "n2": tk.StringVar(value="η2 = —"),
            "N2": tk.StringVar(value="N2 = —"),
        }
        for key in ("n1", "N1", "n2", "N2"):
            ttk.Label(
                basic_summary,
                textvariable=self.basic_vars[key],
                font=("Consolas", 11, "bold"),
                relief="groove",
                padding=6,
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        # --- Производные метрики ---
        ext_frame = ttk.LabelFrame(right_frame,
                                   text="Расширенные (производные) метрики")
        ext_frame.pack(fill=tk.X, pady=(4, 0))

        self.ext_vars = {
            "eta": tk.StringVar(value="Словарь программы  η = η1 + η2 = —"),
            "N":   tk.StringVar(value="Длина программы  N = N1 + N2 = —"),
            "V":   tk.StringVar(value="Объём программы  V = N·log₂(η) = —"),
        }
        for key in ("eta", "N", "V"):
            ttk.Label(
                ext_frame,
                textvariable=self.ext_vars[key],
                font=("Segoe UI", 11),
                padding=(10, 6),
            ).pack(anchor="w")

    
    def open_file(self):
        path = filedialog.askopenfilename(
            title="Выберите файл JavaScript",
            filetypes=[("JavaScript files", "*.js"),
                       ("Текстовые файлы", "*.txt"),
                       ("Все файлы", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            messagebox.showerror("Ошибка чтения файла", str(exc))
            return
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", content)
        self.file_label.config(text=f"Файл: {path}")

    def load_sample(self):
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", SAMPLE_CODE)
        self.file_label.config(text="Файл не загружен (пример)")

    def clear_code(self):
        self.code_text.delete("1.0", tk.END)
        self.file_label.config(text="Файл не загружен (введён вручную)")

    def show_rules(self):
        # отдельное окно с прокруткой — текст длинный
        win = tk.Toplevel(self)
        win.title("Правила подсчёта операторов/операндов")
        win.geometry("760x620")
        win.transient(self)

        txt = tk.Text(win, wrap="word", font=("Consolas", 10))
        scroll = ttk.Scrollbar(win, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        txt.insert("1.0", RULES_TEXT)
        txt.configure(state="disabled")

        ttk.Button(win, text="Закрыть", command=win.destroy).pack(
            side=tk.BOTTOM, pady=6
        )

    
    def show_tokens(self):
        code = self.code_text.get("1.0", tk.END)
        if not code.strip():
            messagebox.showwarning("Нет кода",
                                   "Введите или загрузите код JavaScript.")
            return
        try:
            toks = tokenize(code)
        except Exception as exc:
            messagebox.showerror("Ошибка токенизации", str(exc))
            return

        win = tk.Toplevel(self)
        win.title("Токены (для отладки)")
        win.geometry("560x620")
        win.transient(self)

        tree = ttk.Treeview(win, columns=("n", "kind", "text"),
                            show="headings")
        tree.heading("n", text="#")
        tree.heading("kind", text="Тип")
        tree.heading("text", text="Текст")
        tree.column("n", width=50, anchor="center")
        tree.column("kind", width=120, anchor="center")
        tree.column("text", width=360, anchor="w")

        scroll = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for i, tok in enumerate(toks, start=1):
            tree.insert("", tk.END,
                        values=(i, tok.kind, tok.text))

        ttk.Button(win, text="Закрыть", command=win.destroy).pack(
            side=tk.BOTTOM, pady=6
        )

    
    def calculate(self):
        code = self.code_text.get("1.0", tk.END)
        if not code.strip():
            messagebox.showwarning("Нет кода",
                                   "Введите или загрузите код JavaScript "
                                   "для анализа.")
            return

        try:
            result = analyze(code)
        except Exception as exc:
            messagebox.showerror("Ошибка анализа",
                                 f"Не удалось разобрать код:\n{exc}")
            return

        self._last_result = result
        self._fill_tables(result)
        self._fill_summary(result)

    def _fill_tables(self, result):
        for row in self.op_tree.get_children():
            self.op_tree.delete(row)
        for row in self.opd_tree.get_children():
            self.opd_tree.delete(row)

        for j, (name, count) in enumerate(result.operators.items(), start=1):
            self.op_tree.insert("", tk.END, values=(j, name, count))

        for i, (name, count) in enumerate(result.operands.items(), start=1):
            self.opd_tree.insert("", tk.END, values=(i, name, count))

    def _fill_summary(self, result):
        self.basic_vars["n1"].set(f"η1 = {result.n1}")
        self.basic_vars["N1"].set(f"N1 = {result.N1}")
        self.basic_vars["n2"].set(f"η2 = {result.n2}")
        self.basic_vars["N2"].set(f"N2 = {result.N2}")

        eta = result.vocabulary
        N = result.length
        V = result.volume

        self.ext_vars["eta"].set(
            f"Словарь программы   η = η1 + η2 = "
            f"{result.n1} + {result.n2} = {eta}"
        )
        self.ext_vars["N"].set(
            f"Длина программы    N = N1 + N2 = "
            f"{result.N1} + {result.N2} = {N}"
        )
        self.ext_vars["V"].set(
            f"Объём программы    V = N·log₂(η) = "
            f"{N}·log₂({eta}) ≈ {V:.2f}"
        )


def main():
    app = HalsteadApp()
    app.mainloop()


if __name__ == "__main__":
    main()