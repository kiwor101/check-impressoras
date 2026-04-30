from __future__ import annotations

import argparse
import csv
import html
import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import sys
import time
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit
from xml.sax.saxutils import escape


APP_NAME = "Check Impressoras"
IS_FROZEN = getattr(sys, "frozen", False)
BASE_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) if IS_FROZEN else BASE_DIR
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME if IS_FROZEN else BASE_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_IPS_FILE = DATA_DIR / "ips.txt"
DEFAULT_REPORT_FILE = DATA_DIR / "relatorio_impressoras.html"
DEFAULT_CSV_FILE = DATA_DIR / "relatorio_impressoras.csv"
DEFAULT_XLSX_FILE = DATA_DIR / "relatorio_impressoras.xlsx"
DEFAULT_HISTORY_FILE = DATA_DIR / "historico_impressoras.csv"
DEFAULT_LOG_FILE = DATA_DIR / "check_impressoras.log"
MAX_RESPONSE_BYTES = 2_000_000

PRINTER_PATHS = (
    "/sws/app/information/home/home.json",
    "/sws/app/information/supplies/supplies.json",
    "/sws/index.html",
    "/",
)


@dataclass
class PrinterCheck:
    ip: str
    sector: str = ""
    group: str = "Assistencial 24h"
    toner_percent: str = ""
    toner_status: str = ""
    image_unit_percent: str = ""
    image_unit_status: str = ""
    url: str = ""
    ok: bool = False
    error: str = ""
    checked_at: str = ""


def normalize_group(group: str) -> str:
    value = group.strip().lower()
    if value in {"adm", "admin", "administrativo", "administrativa"}:
        return "Administrativo"
    if value in {"24h", "assistencial", "assistencial 24h", "critico", "critico 24h", "crítico", "crítico 24h"}:
        return "Assistencial 24h"
    return group.strip() or "Assistencial 24h"


def validate_printer_ip(ip: str) -> tuple[bool, str]:
    try:
        address = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False, "IP invalido."

    if address.version != 4:
        return False, "Use um IPv4 da rede local."
    if not address.is_private:
        return False, "Por seguranca, use apenas IP de rede local."
    if address.is_loopback or address.is_multicast or address.is_unspecified or address.is_link_local:
        return False, "IP nao permitido para consulta."
    return True, ""


def read_printers(path: Path) -> list[tuple[str, str, str]]:
    if not path.exists():
        bundled_ips = RESOURCE_DIR / "ips.txt"
        if bundled_ips.exists() and bundled_ips.resolve() != path.resolve():
            shutil.copy2(bundled_ips, path)
        else:
            path.write_text("192.168.1.15;Financeiro;Assistencial 24h\n", encoding="utf-8")

    printers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            if ";" in value:
                parts = [part.strip() for part in value.split(";")]
            elif "," in value:
                parts = [part.strip() for part in value.split(",")]
            else:
                parts = [value]

            ip = parts[0] if len(parts) > 0 else ""
            sector = parts[1] if len(parts) > 1 else ""
            group = normalize_group(parts[2] if len(parts) > 2 else "")
            printers.append((ip, sector, group))
    return printers


def normalize_redirect_path(location: str, current_ip: str) -> str | None:
    if not location:
        return None
    if location.startswith("/"):
        return location

    parsed = urlsplit(location)
    if parsed.scheme == "http" and parsed.hostname == current_ip:
        path = parsed.path or "/"
        return f"{path}?{parsed.query}" if parsed.query else path
    return None


class LegacyHTTPSConnection(http.client.HTTPSConnection):
    def connect(self) -> None:
        super(http.client.HTTPSConnection, self).connect()
        self.sock = self._context.wrap_socket(self.sock)


def legacy_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            context.minimum_version = ssl.TLSVersion.TLSv1
    except AttributeError:
        pass
    try:
        context.set_ciphers("DEFAULT:@SECLEVEL=0")
    except ssl.SSLError:
        pass
    return context


def fetch_url(ip: str, path: str, timeout: float, scheme: str = "http") -> tuple[str, str, int, str, str]:
    url = f"{scheme}://{ip}{path}"
    if scheme == "https":
        connection = LegacyHTTPSConnection(ip, timeout=timeout, context=legacy_ssl_context())
    else:
        connection = http.client.HTTPConnection(ip, timeout=timeout)
    try:
        connection.request(
            "GET",
            path,
            headers={
                "User-Agent": "Check-Impressoras/1.0",
                "Accept": "text/html,application/json,*/*",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Resposta muito grande; consulta bloqueada por seguranca.")
        content_type = response.getheader("Content-Type") or ""
        location = response.getheader("Location") or ""
        charset_match = re.search(r"charset=([^;\s]+)", content_type, re.IGNORECASE)
        charset = charset_match.group(1) if charset_match else "utf-8"
        text = raw.decode(charset, errors="replace")
        return url, text, response.status, response.reason, location
    finally:
        connection.close()


def fetch_text(ip: str, timeout: float) -> tuple[str, str]:
    last_error = ""
    for initial_path in PRINTER_PATHS:
        path = initial_path
        scheme = "http"
        visited = set()
        for _ in range(5):
            visit_key = f"{scheme}://{path}"
            if visit_key in visited:
                last_error = f"Redirecionamento repetido em {visit_key}"
                break
            visited.add(visit_key)
            try:
                url, text, status, reason, location = fetch_url(ip, path, timeout, scheme)
                if 200 <= status < 300:
                    return url, text
                if 300 <= status < 400:
                    parsed_location = urlsplit(location)
                    if parsed_location.scheme == "https" and parsed_location.hostname == ip:
                        scheme = "https"
                        path = parsed_location.path or "/"
                        if parsed_location.query:
                            path = f"{path}?{parsed_location.query}"
                        continue
                    next_path = normalize_redirect_path(location, ip)
                    if next_path:
                        path = next_path
                        continue
                    last_error = f"A impressora redirecionou para {location or 'outro endereco'} ({status})."
                    break
                last_error = f"HTTP {status} {reason}"
                break
            except (OSError, TimeoutError, socket.timeout, UnicodeError) as exc:
                last_error = str(exc)
                break
    raise RuntimeError(last_error or "Nao foi possivel acessar a impressora")


def clean_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def find_percent_after(text: str, labels: Iterable[str]) -> str:
    lower_text = text.lower()
    for label in labels:
        start = lower_text.find(label.lower())
        if start == -1:
            continue
        window = text[start : start + 700]
        matches = re.findall(r"(\d{1,3})\s*%", window)
        for match in matches:
            value = int(match)
            if 0 <= value <= 100:
                return f"{value}%"
    return ""


def find_status_after(text: str, labels: Iterable[str]) -> str:
    lower_text = text.lower()
    known_statuses = ("Pronto", "Baixo", "Muito baixo", "Substituir", "Erro", "OK")
    for label in labels:
        start = lower_text.find(label.lower())
        if start == -1:
            continue
        window = text[start : start + 700]
        for status in known_statuses:
            if re.search(rf"\b{re.escape(status)}\b", window, re.IGNORECASE):
                return status
    return ""


def parse_json_payload(ip: str, sector: str, group: str, url: str, raw: str) -> PrinterCheck | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None

    if payload:
        flattened = json.dumps(payload, ensure_ascii=False)
        text = clean_text(flattened)
        result = parse_page(ip, sector, group, url, text, text)
        if result.toner_percent or result.image_unit_percent:
            return result

    result = PrinterCheck(ip=ip, sector=sector, group=group, url=url, ok=True)
    toner = extract_supply(raw, "toner_black")
    image_unit = extract_supply(raw, "drum_black")
    if toner:
        result.toner_percent = toner["remaining"]
        result.toner_status = toner["status"]
    if image_unit:
        result.image_unit_percent = image_unit["remaining"]
        result.image_unit_status = image_unit["status"]
    if result.toner_percent or result.image_unit_percent:
        return result

    return None


def extract_supply(raw: str, key: str) -> dict[str, str] | None:
    block_match = re.search(rf"{re.escape(key)}\s*:\s*\{{(?P<body>.*?)\n\s*\}}", raw, re.IGNORECASE | re.DOTALL)
    if not block_match:
        return None

    body = block_match.group("body")
    opt_match = re.search(r"\bopt\s*:\s*(\d+)", body)
    if opt_match and opt_match.group(1) == "0":
        return None

    remaining_match = re.search(r"\bremaining\s*:\s*(\d{1,3})", body)
    if not remaining_match:
        return None

    remaining_value = max(0, min(100, int(remaining_match.group(1))))
    error_match = re.search(r'\bnewError\s*:\s*"([^"]*)"', body)
    error = (error_match.group(1).strip() if error_match else "")
    return {
        "remaining": f"{remaining_value}%",
        "status": error or "Pronto",
    }


def parse_page(ip: str, sector: str, group: str, url: str, raw: str, visible_text: str | None = None) -> PrinterCheck:
    text = visible_text or clean_text(raw)
    result = PrinterCheck(ip=ip, sector=sector, group=group, url=url, ok=True)
    result.toner_percent = find_percent_after(text, ("Cartucho de toner",))
    result.image_unit_percent = find_percent_after(text, ("Unidade de imagem",))
    result.toner_status = find_status_after(text, ("Cartucho de toner",))
    result.image_unit_status = find_status_after(text, ("Unidade de imagem",))

    if not result.toner_percent and not result.image_unit_percent:
        percentages = re.findall(r"(\d{1,3})\s*%", text)
        valid = [f"{int(item)}%" for item in percentages if 0 <= int(item) <= 100]
        if valid:
            result.toner_percent = valid[0]
        if len(valid) > 1:
            result.image_unit_percent = valid[1]

    return result


def check_printer(ip: str, sector: str, group: str, timeout: float) -> PrinterCheck:
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    valid_ip, validation_error = validate_printer_ip(ip)
    if not valid_ip:
        return PrinterCheck(ip=ip, sector=sector, group=group, ok=False, error=validation_error, checked_at=checked_at)

    try:
        url, raw = fetch_text(ip, timeout)
        parsed = parse_json_payload(ip, sector, group, url, raw) or parse_page(ip, sector, group, url, raw)
        parsed.checked_at = checked_at
        if not parsed.toner_percent and not parsed.image_unit_percent:
            parsed.ok = False
            parsed.error = "A pagina abriu, mas nao encontrei os percentuais."
        return parsed
    except Exception as exc:
        return PrinterCheck(ip=ip, sector=sector, group=group, ok=False, error=str(exc), checked_at=checked_at)


def check_all(printers: list[tuple[str, str, str]], timeout: float, workers: int) -> list[PrinterCheck]:
    results: list[PrinterCheck] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(check_printer, ip, sector, group, timeout): ip for ip, sector, group in printers}
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=result_sort_key)


def group_order(group: str) -> int:
    return 0 if group == "Assistencial 24h" else 1


def percent_value(value: str) -> int | None:
    if value.endswith("%") and value[:-1].isdigit():
        return int(value[:-1])
    return None


def lowest_percent(result: PrinterCheck) -> int | None:
    values = [percent_value(result.toner_percent), percent_value(result.image_unit_percent)]
    values = [value for value in values if value is not None]
    return min(values) if values else None


def severity_rank(result: PrinterCheck) -> int:
    if not result.ok:
        return 0
    lowest = lowest_percent(result)
    if lowest is None or lowest <= 9:
        return 0
    if lowest <= 29:
        return 1
    return 2


def result_sort_key(result: PrinterCheck) -> tuple[int, int, int, str, str]:
    lowest = lowest_percent(result)
    return (
        group_order(result.group),
        severity_rank(result),
        lowest if lowest is not None else -1,
        result.sector.lower(),
        result.ip,
    )


def safe_sheet_text(value: object) -> str:
    text = str(value or "")
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def write_log(message: str, path: Path = DEFAULT_LOG_FILE) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def write_csv(results: list[PrinterCheck], path: Path) -> None:
    fieldnames = (
        "Grupo",
        "IP",
        "Setor",
        "Cartucho de toner",
        "Unidade de imagem",
        "Resultado",
    )
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "Grupo": result.group,
                    "IP": result.ip,
                    "Setor": safe_sheet_text(result.sector),
                    "Cartucho de toner": result.toner_percent,
                    "Unidade de imagem": result.image_unit_percent,
                    "Resultado": safe_sheet_text("" if result.ok else result.error),
                }
            )


def append_history(results: list[PrinterCheck], path: Path) -> None:
    fieldnames = (
        "Data hora",
        "Grupo",
        "IP",
        "Setor",
        "Cartucho de toner",
        "Unidade de imagem",
        "Resultado",
    )
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "Data hora": result.checked_at,
                    "Grupo": result.group,
                    "IP": result.ip,
                    "Setor": safe_sheet_text(result.sector),
                    "Cartucho de toner": result.toner_percent,
                    "Unidade de imagem": result.image_unit_percent,
                    "Resultado": safe_sheet_text("" if result.ok else result.error),
                }
            )


def health_class(result: PrinterCheck) -> str:
    severity = severity_rank(result)
    if severity == 0:
        return "bad"
    if severity == 1:
        return "warn"
    return "good"


def render_rows(results: list[PrinterCheck]) -> str:
    rows = []
    for result in results:
        status = health_class(result)
        rows.append(
            f"""
            <tr class="{status}">
              <td><a href="{html.escape(result.url or f'http://{result.ip}/sws/index.html')}" target="_blank">{html.escape(result.ip)}</a></td>
              <td>{html.escape(result.sector or "-")}</td>
              <td>{html.escape(result.toner_percent or "-")}</td>
              <td>{html.escape(result.image_unit_percent or "-")}</td>
              <td>{html.escape("" if result.ok else result.error)}</td>
            </tr>
            """
        )
    return "".join(rows)


def render_table(title: str, results: list[PrinterCheck]) -> str:
    if not results:
        return ""
    ok_count = sum(1 for result in results if result.ok)
    return f"""
    <section>
      <div class="section-title">
        <h2>{html.escape(title)}</h2>
        <p>{ok_count}/{len(results)} OK</p>
      </div>
      <table>
        <thead>
          <tr>
            <th>IP</th>
            <th>Setor</th>
            <th>Cartucho de toner</th>
            <th>Unidade de imagem</th>
            <th>Resultado</th>
          </tr>
        </thead>
        <tbody>
          {render_rows(results)}
        </tbody>
      </table>
    </section>
    """


def write_html(results: list[PrinterCheck], path: Path, csv_name: str) -> None:
    checked_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    assistencial = [result for result in results if result.group == "Assistencial 24h"]
    administrativo = [result for result in results if result.group == "Administrativo"]
    outros = [result for result in results if result.group not in {"Assistencial 24h", "Administrativo"}]
    sections = [
        render_table("Setores assistenciais 24h", assistencial),
        render_table("Setores administrativos", administrativo),
    ]
    for group in sorted({result.group for result in outros}):
        sections.append(render_table(group, [result for result in outros if result.group == group]))

    path.write_text(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Check Impressoras</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, Helvetica, sans-serif;
      --ink: #17212b;
      --muted: #617080;
      --line: #d8dee6;
      --good: #e9f7ef;
      --warn: #fff5d9;
      --bad: #fde8e8;
      --blue: #0b7fc3;
    }}
    body {{ margin: 0; background: #f6f8fa; color: var(--ink); }}
    header {{ background: #ffffff; border-bottom: 1px solid var(--line); padding: 22px 28px; }}
    h1 {{ margin: 0 0 6px; font-size: 28px; }}
    p {{ margin: 0; color: var(--muted); }}
    main {{ padding: 24px 28px; }}
    .actions {{ display: flex; gap: 12px; align-items: center; margin-bottom: 18px; flex-wrap: wrap; }}
    .button {{ background: var(--blue); color: #fff; text-decoration: none; border-radius: 6px; padding: 10px 14px; font-weight: 700; }}
    section {{ margin-top: 26px; }}
    .section-title {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }}
    h2 {{ margin: 0; font-size: 20px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid var(--line); }}
    th, td {{ padding: 12px; border-bottom: 1px solid var(--line); text-align: left; font-size: 14px; }}
    th {{ background: #eef3f8; color: #263544; }}
    tr.good {{ background: var(--good); }}
    tr.warn {{ background: var(--warn); }}
    tr.bad {{ background: var(--bad); }}
    td:last-child {{ color: #8a1f1f; }}
    a {{ color: #075f96; }}
    @media (max-width: 780px) {{
      main, header {{ padding-left: 14px; padding-right: 14px; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Check Impressoras</h1>
    <p>Ultima verificacao: {html.escape(checked_at)}</p>
  </header>
  <main>
    <div class="actions">
      <a class="button" href="{html.escape(csv_name)}">Abrir CSV</a>
      <a class="button" href="relatorio_impressoras.xlsx">Abrir Excel</a>
      <p>{len(results)} impressora(s) verificadas</p>
    </div>
    {''.join(sections)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def excel_col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def cell_xml(row: int, col: int, value: object, style: int = 0) -> str:
    ref = f"{excel_col_name(col)}{row}"
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, int):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    text = escape(safe_sheet_text(value))
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{text}</t></is></c>'


def row_xml(row_number: int, values: list[object], style: int = 0) -> str:
    cells = "".join(cell_xml(row_number, index + 1, value, style) for index, value in enumerate(values))
    return f'<row r="{row_number}">{cells}</row>'


def xlsx_rows_for_group(start_row: int, title: str, results: list[PrinterCheck]) -> tuple[list[str], int]:
    rows = []
    rows.append(row_xml(start_row, [title], 5))
    start_row += 1
    rows.append(row_xml(start_row, ["IP", "Setor", "Cartucho de toner", "Unidade de imagem", "Resultado"], 4))
    start_row += 1
    for result in results:
        style = {"bad": 3, "warn": 2, "good": 1}[health_class(result)]
        rows.append(
            row_xml(
                start_row,
                [
                    result.ip,
                    result.sector,
                    result.toner_percent,
                    result.image_unit_percent,
                    "" if result.ok else result.error,
                ],
                style,
            )
        )
        start_row += 1
    return rows, start_row + 1


def write_xlsx(results: list[PrinterCheck], path: Path) -> None:
    assistencial = [result for result in results if result.group == "Assistencial 24h"]
    administrativo = [result for result in results if result.group == "Administrativo"]
    outros = [result for result in results if result.group not in {"Assistencial 24h", "Administrativo"}]

    sheet_rows = [
        row_xml(1, ["Check Impressoras"], 5),
        row_xml(2, [f"Ultima verificacao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"], 0),
    ]
    next_row = 4
    for title, group_results in (
        ("Setores assistenciais 24h", assistencial),
        ("Setores administrativos", administrativo),
    ):
        if group_results:
            new_rows, next_row = xlsx_rows_for_group(next_row, title, group_results)
            sheet_rows.extend(new_rows)
    for group in sorted({result.group for result in outros}):
        new_rows, next_row = xlsx_rows_for_group(next_row, group, [result for result in outros if result.group == group])
        sheet_rows.extend(new_rows)

    worksheet = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cols>
    <col min="1" max="1" width="16" customWidth="1"/>
    <col min="2" max="2" width="24" customWidth="1"/>
    <col min="3" max="4" width="20" customWidth="1"/>
    <col min="5" max="5" width="52" customWidth="1"/>
  </cols>
  <sheetData>{''.join(sheet_rows)}</sheetData>
</worksheet>"""

    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><sz val="11"/><name val="Arial"/></font>
    <font><b/><sz val="11"/><name val="Arial"/></font>
    <font><b/><sz val="16"/><name val="Arial"/></font>
  </fonts>
  <fills count="6">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE9F7EF"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF5D9"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFDE8E8"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEEF3F8"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFD8DEE6"/></left><right style="thin"><color rgb="FFD8DEE6"/></right><top style="thin"><color rgb="FFD8DEE6"/></top><bottom style="thin"><color rgb="FFD8DEE6"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="6">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="0" fillId="2" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="1" fillId="5" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyFont="1"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""")
        xlsx.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        xlsx.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Relatorio" sheetId="1" r:id="rId1"/></sheets>
</workbook>""")
        xlsx.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""")
        xlsx.writestr("xl/worksheets/sheet1.xml", worksheet)
        xlsx.writestr("xl/styles.xml", styles)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica toner e unidade de imagem das HP Laser MFP 432.")
    parser.add_argument("--ips", default=str(DEFAULT_IPS_FILE), help="Arquivo com um IP por linha.")
    parser.add_argument("--html", default=str(DEFAULT_REPORT_FILE), help="Arquivo HTML de saida.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV_FILE), help="Arquivo CSV de saida.")
    parser.add_argument("--xlsx", default=str(DEFAULT_XLSX_FILE), help="Arquivo Excel formatado de saida.")
    parser.add_argument("--history", default=str(DEFAULT_HISTORY_FILE), help="Arquivo de historico acumulado.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Tempo maximo por tentativa, em segundos.")
    parser.add_argument("--workers", type=int, default=12, help="Quantidade de verificacoes simultaneas.")
    args = parser.parse_args()

    printers = read_printers(Path(args.ips))
    if not printers:
        print("Coloque pelo menos uma impressora no arquivo ips.txt.")
        return 1

    start = time.time()
    results = check_all(printers, timeout=args.timeout, workers=args.workers)
    csv_path = Path(args.csv)
    xlsx_path = Path(args.xlsx)
    history_path = Path(args.history)
    html_path = Path(args.html)
    write_csv(results, csv_path)
    write_xlsx(results, xlsx_path)
    write_html(results, html_path, csv_path.name)
    append_history(results, history_path)
    elapsed = time.time() - start

    ok_count = sum(1 for result in results if result.ok)
    write_log(f"Verificacao concluida: {ok_count}/{len(results)} impressora(s) OK em {elapsed:.1f}s.")
    print(f"Verificacao concluida: {ok_count}/{len(results)} impressora(s) OK em {elapsed:.1f}s.")
    print(f"Relatorio HTML: {html_path}")
    print(f"Relatorio CSV:  {csv_path}")
    print(f"Relatorio Excel: {xlsx_path}")
    print(f"Historico: {history_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
