from __future__ import annotations

import os
import queue
import shutil
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import check_impressoras as checker


BASE_DIR = Path(__file__).resolve().parent
IPS_FILE = BASE_DIR / "ips.txt"
HTML_FILE = BASE_DIR / "relatorio_impressoras.html"
CSV_FILE = BASE_DIR / "relatorio_impressoras.csv"
XLSX_FILE = BASE_DIR / "relatorio_impressoras.xlsx"
HISTORY_FILE = BASE_DIR / "historico_impressoras.csv"
BACKUP_DIR = BASE_DIR / "backups"

GROUPS = ("Assistencial 24h", "Administrativo")


class CheckImpressorasApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Check Impressoras")
        self.geometry("1080x700")
        self.minsize(940, 620)
        self.result_queue: queue.Queue[tuple[str, str, list[checker.PrinterCheck] | None]] = queue.Queue()

        self.ip_var = tk.StringVar()
        self.sector_var = tk.StringVar()
        self.group_var = tk.StringVar(value=GROUPS[0])
        self.status_var = tk.StringVar(value="Pronto para iniciar.")
        self.assistencial_summary_var = tk.StringVar(value="Nenhuma pesquisa realizada.")
        self.administrativo_summary_var = tk.StringVar(value="Nenhuma pesquisa realizada.")

        self.configure(bg="#f4f7fb")
        self.create_styles()
        self.create_widgets()
        self.load_printers()
        self.after(200, self.poll_result_queue)

    def create_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f7fb")
        style.configure("Header.TLabel", background="#f4f7fb", foreground="#17212b", font=("Arial", 20, "bold"))
        style.configure("Muted.TLabel", background="#f4f7fb", foreground="#5f6f80", font=("Arial", 10))
        style.configure("TLabel", background="#f4f7fb", foreground="#17212b", font=("Arial", 10))
        style.configure("TButton", font=("Arial", 10, "bold"), padding=(12, 8))
        style.configure("Primary.TButton", background="#0b7fc3", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#096aa3")])
        style.configure("Treeview", rowheight=28, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"), background="#e8eef6")

    def create_widgets(self) -> None:
        container = ttk.Frame(self, padding=18)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container)
        header.pack(fill="x")
        ttk.Label(header, text="Check Impressoras", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Cadastre IP, setor e grupo. Depois clique em Iniciar pesquisa para atualizar os relatorios.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 12))

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)

        register_tab = ttk.Frame(self.notebook, padding=(0, 14, 0, 0))
        results_tab = ttk.Frame(self.notebook, padding=(0, 14, 0, 0))
        self.notebook.add(register_tab, text="Cadastro")
        self.notebook.add(results_tab, text="Resultado da pesquisa")

        form = ttk.Frame(register_tab)
        form.pack(fill="x", pady=(0, 14))

        ttk.Label(form, text="IP").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ip_var, width=20).grid(row=1, column=0, sticky="ew", padx=(0, 10))

        ttk.Label(form, text="Setor").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.sector_var, width=32).grid(row=1, column=1, sticky="ew", padx=(0, 10))

        ttk.Label(form, text="Grupo").grid(row=0, column=2, sticky="w")
        ttk.Combobox(form, textvariable=self.group_var, values=GROUPS, state="readonly", width=24).grid(
            row=1, column=2, sticky="ew", padx=(0, 10)
        )

        ttk.Button(form, text="Adicionar", command=self.add_printer, style="Primary.TButton").grid(
            row=1, column=3, sticky="ew"
        )
        form.columnconfigure(1, weight=1)

        table_frame = ttk.Frame(register_tab)
        table_frame.pack(fill="both", expand=True)

        columns = ("ip", "sector", "group")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("ip", text="IP")
        self.tree.heading("sector", text="Setor")
        self.tree.heading("group", text="Grupo")
        self.tree.column("ip", width=160, anchor="w")
        self.tree.column("sector", width=380, anchor="w")
        self.tree.column("group", width=190, anchor="w")
        self.tree.bind("<Double-1>", self.load_selected_into_form)
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        buttons = ttk.Frame(register_tab)
        buttons.pack(fill="x", pady=(14, 8))

        ttk.Button(buttons, text="Atualizar selecionado", command=self.update_selected).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Remover selecionado", command=self.remove_selected).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Salvar lista", command=self.save_printers).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Abrir pasta", command=self.open_project_folder).pack(side="left", padx=(0, 8))

        self.run_button = ttk.Button(buttons, text="Iniciar pesquisa", command=self.start_check, style="Primary.TButton")
        self.run_button.pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Abrir Excel", command=self.open_excel).pack(side="right")

        self.create_results_tab(results_tab)

        footer = ttk.Frame(container)
        footer.pack(fill="x")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=180)
        self.progress.pack(side="right")
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w")

    def create_results_tab(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 12))
        self.result_run_button = ttk.Button(
            toolbar,
            text="Iniciar nova pesquisa",
            command=self.start_check,
            style="Primary.TButton",
        )
        self.result_run_button.pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Abrir Excel", command=self.open_excel).pack(side="left")
        ttk.Button(toolbar, text="Abrir historico", command=self.open_history).pack(side="left", padx=(8, 0))

        self.assistencial_tree = self.create_result_section(
            parent,
            "Setores assistenciais 24h",
            self.assistencial_summary_var,
        )
        self.administrativo_tree = self.create_result_section(
            parent,
            "Setores administrativos",
            self.administrativo_summary_var,
        )

    def create_result_section(
        self,
        parent: ttk.Frame,
        title: str,
        summary_var: tk.StringVar,
    ) -> ttk.Treeview:
        section = ttk.Frame(parent)
        section.pack(fill="both", expand=True, pady=(0, 14))

        title_bar = ttk.Frame(section)
        title_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(title_bar, text=title, font=("Arial", 12, "bold")).pack(side="left")
        ttk.Label(title_bar, textvariable=summary_var, style="Muted.TLabel").pack(side="left", padx=(10, 0))

        table_frame = ttk.Frame(section)
        table_frame.pack(fill="both", expand=True)

        columns = ("ip", "sector", "toner", "image_unit", "result")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=7)
        tree.heading("ip", text="IP")
        tree.heading("sector", text="Setor")
        tree.heading("toner", text="Cartucho de toner")
        tree.heading("image_unit", text="Unidade de imagem")
        tree.heading("result", text="Resultado")
        tree.column("ip", width=130, anchor="w")
        tree.column("sector", width=260, anchor="w")
        tree.column("toner", width=150, anchor="center")
        tree.column("image_unit", width=160, anchor="center")
        tree.column("result", width=330, anchor="w")
        tree.tag_configure("good", background="#e9f7ef")
        tree.tag_configure("warn", background="#fff5d9")
        tree.tag_configure("bad", background="#fde8e8")
        tree.bind("<Double-1>", self.open_selected_result_printer)
        tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scroll.set)
        return tree

    def load_printers(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for ip, sector, group in checker.read_printers(IPS_FILE):
            self.tree.insert("", "end", values=(ip, sector, checker.normalize_group(group)))
        self.status_var.set(f"{len(self.tree.get_children())} impressora(s) cadastradas.")

    def add_printer(self) -> None:
        ip = self.ip_var.get().strip()
        sector = self.sector_var.get().strip()
        group = checker.normalize_group(self.group_var.get())
        valid, message = self.validate_form(ip, sector)
        if not valid:
            messagebox.showwarning("Cadastro invalido", message)
            return
        if self.ip_exists(ip):
            messagebox.showwarning("IP duplicado", "Este IP ja esta cadastrado.")
            return
        self.tree.insert("", "end", values=(ip, sector, group))
        self.clear_form()
        self.save_printers(show_message=False)
        self.status_var.set("Impressora adicionada.")

    def update_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Selecione uma linha", "Selecione uma impressora para atualizar.")
            return
        ip = self.ip_var.get().strip()
        sector = self.sector_var.get().strip()
        group = checker.normalize_group(self.group_var.get())
        valid, message = self.validate_form(ip, sector)
        if not valid:
            messagebox.showwarning("Cadastro invalido", message)
            return
        if self.ip_exists(ip, ignore_item=selected[0]):
            messagebox.showwarning("IP duplicado", "Este IP ja esta cadastrado em outra linha.")
            return
        self.tree.item(selected[0], values=(ip, sector, group))
        self.save_printers(show_message=False)
        self.status_var.set("Impressora atualizada.")

    def validate_form(self, ip: str, sector: str) -> tuple[bool, str]:
        if not ip or not sector:
            return False, "Informe o IP e o setor."
        valid_ip, ip_message = checker.validate_printer_ip(ip)
        if not valid_ip:
            return False, ip_message
        if ";" in sector or "\n" in sector:
            return False, "O setor nao pode conter ponto e virgula ou quebra de linha."
        return True, ""

    def ip_exists(self, ip: str, ignore_item: str | None = None) -> bool:
        for item in self.tree.get_children():
            if ignore_item and item == ignore_item:
                continue
            values = self.tree.item(item, "values")
            if values and values[0] == ip:
                return True
        return False

    def remove_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Selecione uma linha", "Selecione uma impressora para remover.")
            return
        values = self.tree.item(selected[0], "values")
        if messagebox.askyesno("Remover impressora", f"Remover {values[0]} - {values[1]}?"):
            self.tree.delete(selected[0])
            self.save_printers(show_message=False)
            self.status_var.set("Impressora removida.")

    def load_selected_into_form(self, _event: tk.Event | None = None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        ip, sector, group = self.tree.item(selected[0], "values")
        self.ip_var.set(ip)
        self.sector_var.set(sector)
        self.group_var.set(checker.normalize_group(group))

    def clear_form(self) -> None:
        self.ip_var.set("")
        self.sector_var.set("")
        self.group_var.set(GROUPS[0])

    def save_printers(self, show_message: bool = True) -> None:
        rows = [self.tree.item(item, "values") for item in self.tree.get_children()]
        self.backup_ips_file()
        lines = [
            "# Coloque uma impressora por linha no formato:",
            "# IP;Setor;Grupo",
            "#",
            "# Grupos aceitos:",
            "# - Assistencial 24h",
            "# - Administrativo",
            "#",
            "# Se deixar sem grupo, o sistema considera Assistencial 24h.",
            "",
        ]
        for ip, sector, group in rows:
            lines.append(f"{ip};{sector};{checker.normalize_group(group)}")
        IPS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if show_message:
            self.status_var.set("Lista salva.")

    def backup_ips_file(self) -> None:
        if not IPS_FILE.exists():
            return
        BACKUP_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(IPS_FILE, BACKUP_DIR / f"ips-{stamp}.txt")

    def start_check(self) -> None:
        self.save_printers(show_message=False)
        self.run_button.configure(state="disabled")
        self.result_run_button.configure(state="disabled")
        self.progress.start(12)
        self.clear_result_tables()
        self.notebook.select(1)
        self.status_var.set("Pesquisando impressoras... aguarde.")
        thread = threading.Thread(target=self.run_check_worker, daemon=True)
        thread.start()

    def run_check_worker(self) -> None:
        try:
            printers = checker.read_printers(IPS_FILE)
            results = checker.check_all(printers, timeout=8.0, workers=12)
            checker.write_csv(results, CSV_FILE)
            checker.write_xlsx(results, XLSX_FILE)
            checker.write_html(results, HTML_FILE, CSV_FILE.name)
            checker.append_history(results, HISTORY_FILE)
            ok_count = sum(1 for result in results if result.ok)
            message = f"Pesquisa concluida: {ok_count}/{len(results)} impressora(s) OK."
            self.result_queue.put(("ok", message, results))
        except Exception as exc:
            self.result_queue.put(("error", str(exc), None))

    def poll_result_queue(self) -> None:
        try:
            kind, message, results = self.result_queue.get_nowait()
        except queue.Empty:
            self.after(200, self.poll_result_queue)
            return

        self.run_button.configure(state="normal")
        self.result_run_button.configure(state="normal")
        self.progress.stop()
        if kind == "ok":
            self.show_results(results or [])
            self.status_var.set(message)
            messagebox.showinfo("Pesquisa concluida", message)
        else:
            self.status_var.set("Erro ao pesquisar.")
            messagebox.showerror("Erro", message)
        self.after(200, self.poll_result_queue)

    def clear_result_tables(self) -> None:
        for tree in (self.assistencial_tree, self.administrativo_tree):
            tree.delete(*tree.get_children())
        self.assistencial_summary_var.set("Pesquisando...")
        self.administrativo_summary_var.set("Pesquisando...")

    def show_results(self, results: list[checker.PrinterCheck]) -> None:
        assistencial = [result for result in results if result.group == "Assistencial 24h"]
        administrativo = [result for result in results if result.group == "Administrativo"]
        self.populate_result_tree(self.assistencial_tree, assistencial)
        self.populate_result_tree(self.administrativo_tree, administrativo)
        self.assistencial_summary_var.set(self.summary_text(assistencial))
        self.administrativo_summary_var.set(self.summary_text(administrativo))

    def populate_result_tree(self, tree: ttk.Treeview, results: list[checker.PrinterCheck]) -> None:
        tree.delete(*tree.get_children())
        for result in results:
            tag = checker.health_class(result)
            tree.insert(
                "",
                "end",
                values=(
                    result.ip,
                    result.sector,
                    result.toner_percent or "-",
                    result.image_unit_percent or "-",
                    "" if result.ok else result.error,
                ),
                tags=(tag,),
            )

    def summary_text(self, results: list[checker.PrinterCheck]) -> str:
        if not results:
            return "Nenhuma impressora neste grupo."
        ok_count = sum(1 for result in results if result.ok)
        red_count = sum(1 for result in results if checker.health_class(result) == "bad")
        yellow_count = sum(1 for result in results if checker.health_class(result) == "warn")
        return f"{ok_count}/{len(results)} OK | {yellow_count} amarelo(s) | {red_count} vermelho(s)"

    def open_report(self) -> None:
        if HTML_FILE.exists():
            os.startfile(HTML_FILE)
        else:
            messagebox.showinfo("Relatorio nao encontrado", "Clique em Iniciar pesquisa para gerar o relatorio.")

    def open_excel(self) -> None:
        if XLSX_FILE.exists():
            os.startfile(XLSX_FILE)
        else:
            messagebox.showinfo("Excel nao encontrado", "Clique em Iniciar pesquisa para gerar o Excel.")

    def open_history(self) -> None:
        if HISTORY_FILE.exists():
            os.startfile(HISTORY_FILE)
        else:
            messagebox.showinfo("Historico nao encontrado", "Clique em Iniciar pesquisa para gerar o historico.")

    def open_project_folder(self) -> None:
        os.startfile(BASE_DIR)

    def open_selected_result_printer(self, event: tk.Event) -> None:
        tree = event.widget
        if not isinstance(tree, ttk.Treeview):
            return
        selected = tree.selection()
        if not selected:
            return
        values = tree.item(selected[0], "values")
        if values:
            os.startfile(f"http://{values[0]}/sws/index.html")


if __name__ == "__main__":
    app = CheckImpressorasApp()
    app.mainloop()
