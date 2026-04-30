from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Check Impressoras"


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def default_install_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_NAME


def data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME


def run_powershell(script: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as file:
        file.write(script)
        script_path = file.name

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao executar PowerShell.")
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


def create_shortcuts(
    install_dir: Path,
    exe_path: Path,
    icon_path: Path,
    create_desktop: bool,
    create_start_menu: bool,
) -> None:
    escaped_install = str(install_dir).replace("'", "''")
    escaped_exe = str(exe_path).replace("'", "''")
    escaped_icon = str(icon_path).replace("'", "''")
    desktop_flag = "$true" if create_desktop else "$false"
    start_flag = "$true" if create_start_menu else "$false"

    script = f"""
$appName = '{APP_NAME}'
$installDir = '{escaped_install}'
$exePath = '{escaped_exe}'
$iconPath = '{escaped_icon}'
$createDesktop = {desktop_flag}
$createStartMenu = {start_flag}
$shell = New-Object -ComObject WScript.Shell
if ($createDesktop) {{
    $desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) "$appName.lnk"
    $desktop = $shell.CreateShortcut($desktopShortcut)
    $desktop.TargetPath = $exePath
    $desktop.WorkingDirectory = $installDir
    $desktop.IconLocation = "$iconPath,0"
    $desktop.Description = $appName
    $desktop.Save()
}}
if ($createStartMenu) {{
    $startMenuDir = Join-Path ([Environment]::GetFolderPath('Programs')) $appName
    $startMenuShortcut = Join-Path $startMenuDir "$appName.lnk"
    New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
    $startMenu = $shell.CreateShortcut($startMenuShortcut)
    $startMenu.TargetPath = $exePath
    $startMenu.WorkingDirectory = $installDir
    $startMenu.IconLocation = "$iconPath,0"
    $startMenu.Description = $appName
    $startMenu.Save()
}}
"""
    run_powershell(script)


def install(
    install_dir: Path,
    create_desktop: bool,
    create_start_menu: bool,
    run_after_install: bool,
) -> None:
    source = resource_dir()
    install_dir.mkdir(parents=True, exist_ok=True)
    data_dir().mkdir(parents=True, exist_ok=True)

    exe_path = install_dir / f"{APP_NAME}.exe"
    icon_path = install_dir / "app_icon.ico"

    shutil.copy2(source / "CheckImpressoras.exe", exe_path)
    shutil.copy2(source / "app_icon.ico", icon_path)
    create_shortcuts(install_dir, exe_path, icon_path, create_desktop, create_start_menu)

    if run_after_install:
        subprocess.Popen([str(exe_path)], cwd=str(install_dir))


class Installer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Instalar {APP_NAME}")
        self.geometry("620x390")
        self.resizable(False, False)
        self.configure(bg="#f4f7fb")

        icon_path = resource_dir() / "app_icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass

        self.install_dir_var = tk.StringVar(value=str(default_install_dir()))
        self.desktop_var = tk.BooleanVar(value=True)
        self.start_menu_var = tk.BooleanVar(value=True)
        self.run_after_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="")

        self.create_styles()
        self.create_widgets()

    def create_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f7fb")
        style.configure("TLabel", background="#f4f7fb", foreground="#17212b", font=("Arial", 10))
        style.configure("Title.TLabel", background="#f4f7fb", foreground="#17212b", font=("Arial", 18, "bold"))
        style.configure("Muted.TLabel", background="#f4f7fb", foreground="#617080", font=("Arial", 9))
        style.configure("TButton", font=("Arial", 10, "bold"), padding=(12, 8))
        style.configure("Primary.TButton", background="#0b7fc3", foreground="#ffffff")

    def create_widgets(self) -> None:
        main = ttk.Frame(self, padding=22)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Check Impressoras", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            main,
            text="Escolha onde instalar e quais atalhos criar.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 20))

        ttk.Label(main, text="Pasta de instalacao").pack(anchor="w")
        row = ttk.Frame(main)
        row.pack(fill="x", pady=(4, 16))
        ttk.Entry(row, textvariable=self.install_dir_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="Procurar", command=self.browse_install_dir).pack(side="right")

        ttk.Label(
            main,
            text=f"Dados, historico e logs serao salvos em: {data_dir()}",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 18))

        ttk.Checkbutton(main, text="Criar atalho na Area de Trabalho", variable=self.desktop_var).pack(anchor="w")
        ttk.Checkbutton(main, text="Criar atalho no Menu Iniciar", variable=self.start_menu_var).pack(anchor="w")
        ttk.Checkbutton(main, text="Abrir o app depois de instalar", variable=self.run_after_var).pack(anchor="w")

        ttk.Label(main, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w", pady=(18, 0))

        footer = ttk.Frame(main)
        footer.pack(side="bottom", fill="x", pady=(18, 0))
        ttk.Button(footer, text="Cancelar", command=self.destroy).pack(side="right")
        self.install_button = ttk.Button(
            footer,
            text="Instalar",
            command=self.install_clicked,
            style="Primary.TButton",
        )
        self.install_button.pack(side="right", padx=(0, 8))

    def browse_install_dir(self) -> None:
        selected = filedialog.askdirectory(
            title="Escolher pasta de instalacao",
            initialdir=str(Path(self.install_dir_var.get()).parent),
        )
        if selected:
            self.install_dir_var.set(str(Path(selected) / APP_NAME if Path(selected).name != APP_NAME else Path(selected)))

    def install_clicked(self) -> None:
        install_dir = Path(self.install_dir_var.get()).expanduser()
        if not str(install_dir).strip():
            messagebox.showwarning(APP_NAME, "Informe a pasta de instalacao.")
            return

        self.install_button.configure(state="disabled")
        self.status_var.set("Instalando...")
        self.update_idletasks()

        try:
            install(
                install_dir,
                self.desktop_var.get(),
                self.start_menu_var.get(),
                self.run_after_var.get(),
            )
        except Exception as exc:
            self.install_button.configure(state="normal")
            self.status_var.set("Falha na instalacao.")
            messagebox.showerror(APP_NAME, f"Nao foi possivel instalar o aplicativo.\n\n{exc}")
            return

        self.status_var.set("Instalacao concluida.")
        messagebox.showinfo(APP_NAME, "Check Impressoras instalado com sucesso.")
        self.destroy()


def main() -> int:
    app = Installer()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

