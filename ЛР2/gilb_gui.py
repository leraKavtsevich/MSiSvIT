# -*- coding: utf-8 -*-
"""
gilb_gui.py
Графическое приложение (Tkinter) для расчёта метрики Джилба
по исходному коду на JavaScript.

Запуск:
    python3 gilb_gui.py
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from gilb_core import analyze, ParseError

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "example.js")


class GilbApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Метрика Джилба — анализатор JavaScript")
        self.geometry("1280x780")
        self.minsize(1000, 600)
        self.result = None
        self.base_one = tk.BooleanVar(value=False)
        self._build()
        self._load_initial()

    # ------------------------------------------------------------------
    # Интерфейс
    # ------------------------------------------------------------------
    def _build(self):
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # --- слева: исходный код ---
        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        ttk.Label(left, text="Исходный код JavaScript:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))

        editor = ttk.Frame(left)
        editor.pack(fill=tk.BOTH, expand=True)
        self.lines = tk.Text(editor, width=4, padx=4, takefocus=0, border=0,
                             background="#f0f0f0", foreground="#888",
                             font=("Consolas", 10), state="disabled")
        self.code = tk.Text(editor, wrap="none", font=("Consolas", 10), undo=True)
        ys = ttk.Scrollbar(editor, orient="vertical", command=self._scroll_both)
        xs = ttk.Scrollbar(editor, orient="horizontal", command=self.code.xview)
        self.code.configure(yscrollcommand=lambda a, b: (ys.set(a, b), self.lines.yview_moveto(a)),
                            xscrollcommand=xs.set)
        self.lines.grid(row=0, column=0, sticky="ns")
        self.code.grid(row=0, column=1, sticky="nsew")
        ys.grid(row=0, column=2, sticky="ns")
        xs.grid(row=1, column=1, sticky="ew")
        editor.rowconfigure(0, weight=1)
        editor.columnconfigure(1, weight=1)
        self.code.tag_configure("branch", background="#fff2b3")
        self.code.tag_configure("selected", background="#ffc870")
        self.code.bind("<<Modified>>", self._on_modified)

        bar = ttk.Frame(left)
        bar.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(bar, text="Открыть файл...", command=self.open_file).pack(side=tk.LEFT)
        ttk.Button(bar, text="Очистить", command=self.clear).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Рассчитать метрики", command=self.calculate).pack(side=tk.RIGHT)
        self.file_label = ttk.Label(left, text="", foreground="#666")
        self.file_label.pack(anchor="w", pady=(6, 0))

        # --- справа: результаты ---
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        box = ttk.LabelFrame(right, text="Метрика Джилба")
        box.pack(fill=tk.X)
        self.v_CL = tk.StringVar(value="Абсолютная сложность  CL = —")
        self.v_cl = tk.StringVar(value="Относительная сложность  cl = —")
        self.v_CLI = tk.StringVar(value="Максимальный уровень вложенности  CLI = —")
        for v in (self.v_CL, self.v_cl, self.v_CLI):
            ttk.Label(box, textvariable=v, font=("Segoe UI", 12, "bold"),
                      padding=(10, 4)).pack(anchor="w")
        ttk.Checkbutton(box, text="Считать уровень вложенности с 1 (по умолчанию с 0)",
                        variable=self.base_one, command=self._refresh).pack(
            anchor="w", padx=10, pady=(2, 6))

        # таблица ветвлений
        bf = ttk.LabelFrame(right, text="Ветвления, учтённые в CL")
        bf.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.tree_b = self._table(bf, [("n", "№", 40), ("line", "Строка", 60),
                                       ("kind", "Вид", 120), ("lvl", "Уровень", 70),
                                       ("text", "Фрагмент кода", 320)])
        self.tree_b.bind("<<TreeviewSelect>>", lambda e: self._select(self.tree_b))

        # таблица операторов
        sf = ttk.LabelFrame(right, text="Операторы программы (знаменатель cl)")
        sf.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.tree_s = self._table(sf, [("n", "№", 40), ("line", "Строка", 60),
                                       ("kind", "Вид оператора", 160)])
        self.tree_s.bind("<<TreeviewSelect>>", lambda e: self._select(self.tree_s))

    def _table(self, parent, cols):
        tree = ttk.Treeview(parent, columns=[c[0] for c in cols], show="headings", height=8)
        for cid, title, width in cols:
            tree.heading(cid, text=title)
            tree.column(cid, width=width, anchor="w" if cid == "text" else "center",
                        stretch=(cid == "text"))
        sb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    # ------------------------------------------------------------------
    # Нумерация строк
    # ------------------------------------------------------------------
    def _scroll_both(self, *args):
        self.code.yview(*args)
        self.lines.yview(*args)

    def _on_modified(self, _event=None):
        if self.code.edit_modified():
            self._update_line_numbers()
            self.code.edit_modified(False)

    def _update_line_numbers(self):
        count = int(self.code.index("end-1c").split(".")[0])
        self.lines.configure(state="normal")
        self.lines.delete("1.0", tk.END)
        self.lines.insert("1.0", "\n".join(str(i) for i in range(1, count + 1)))
        self.lines.configure(state="disabled", width=max(3, len(str(count))) + 1)
        self.lines.yview_moveto(self.code.yview()[0])

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------
    def _load_initial(self):
        if os.path.exists(EXAMPLE):
            self._load(EXAMPLE)

    def _load(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror("Ошибка чтения файла", str(exc))
            return
        self.code.delete("1.0", tk.END)
        self.code.insert("1.0", content)
        self.file_label.config(text=f"Файл: {path}")

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Выберите файл JavaScript",
            filetypes=[("JavaScript", "*.js *.mjs *.cjs"), ("Все файлы", "*.*")])
        if path:
            self._load(path)

    def clear(self):
        self.code.delete("1.0", tk.END)
        self.file_label.config(text="")
        self.result = None
        self._refresh()

    def calculate(self):
        src = self.code.get("1.0", "end-1c")
        if not src.strip():
            messagebox.showwarning("Нет кода", "Введите или откройте код JavaScript.")
            return
        try:
            self.result = analyze(src)
        except ParseError as exc:
            messagebox.showerror("Ошибка разбора", str(exc))
            return
        except RecursionError:
            messagebox.showerror("Ошибка разбора", "Слишком глубокая вложенность конструкций.")
            return
        self._refresh()

    def _refresh(self):
        for tree in (self.tree_b, self.tree_s):
            tree.delete(*tree.get_children())
        self.code.tag_remove("branch", "1.0", tk.END)
        self.code.tag_remove("selected", "1.0", tk.END)
        r = self.result
        if r is None:
            self.v_CL.set("Абсолютная сложность  CL = —")
            self.v_cl.set("Относительная сложность  cl = —")
            self.v_CLI.set("Максимальный уровень вложенности  CLI = —")
            return

        base = 1 if self.base_one.get() else 0
        n = r.total_statements
        self.v_CL.set(f"Абсолютная сложность  CL = {r.CL}")
        cl = f"{r.cl:.3f}".replace(".", ",") if n else "—"
        self.v_cl.set(f"Относительная сложность  cl = CL / N = {r.CL} / {n} = {cl}")
        self.v_CLI.set(f"Максимальный уровень вложенности  CLI = {r.CLI(base)}")

        for i, b in enumerate(r.branches, 1):
            self.tree_b.insert("", tk.END, values=(i, b.line, b.kind, b.level + base, b.text))
            self.code.tag_add("branch", f"{b.line}.0", f"{b.line}.end")
        for i, s in enumerate(r.statements, 1):
            self.tree_s.insert("", tk.END, values=(i, s.line, s.kind))

    def _select(self, tree):
        sel = tree.selection()
        if not sel:
            return
        line = tree.item(sel[0])["values"][1]
        self.code.tag_remove("selected", "1.0", tk.END)
        self.code.tag_add("selected", f"{line}.0", f"{line}.end")
        self.code.see(f"{line}.0")


def main():
    GilbApp().mainloop()


if __name__ == "__main__":
    main()
