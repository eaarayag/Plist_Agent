from __future__ import annotations

import getpass
from datetime import datetime
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sanitize_field(value: str) -> str:
    # Keep the log single-line and resilient to the chosen '|' separator.
    sanitized = (value or "").replace("\r", " ").replace("\n", " ").strip()
    return sanitized.replace("|", "\\|")


def append_usage_log(
    username: Optional[str],
    plb_name: str,
    search_text: str = "",
    mtpl_file: str = "",
    saved_at: Optional[datetime] = None,
) -> Path:
    """Append a usage entry to Usage_Log.txt stored at project root.

    Entry format (single line):
        <Date>|<Hour>|<os_user>|<search_text>|<plb_name>\n

    Where Date is formatted as "wwXpY", where X is ISO week number and Y is ISO weekday number.
    """

    safe_username = getpass.getuser()
    dt = saved_at or datetime.now()

    iso = dt.isocalendar()
    date_str = f"ww{iso.week}p{iso.weekday}"
    hour_str = dt.strftime("%H:%M:%S")

    log_path = _project_root() / "data" / "Usage_Log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    plb_name_s = _sanitize_field(plb_name)
    search_text_s = _sanitize_field(search_text)
    mtpl_file_s = _sanitize_field(mtpl_file)

    existed = log_path.exists()

    with log_path.open("a", encoding="utf-8", newline="\n") as f:
        if not existed:
            f.write("Date   | Hour  | User  | Regex/IE PLB  | Generate IO PLB   | Debug MTPL file used\n")
        f.write(f"{date_str}|{hour_str}|{safe_username}|{search_text_s}|{plb_name_s}|{mtpl_file_s}\n")

    return log_path
