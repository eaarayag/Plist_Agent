#!/usr/bin/env python3
"""
PLB Debug CLI App — Headless adapter and interactive CLI helpers.

Contains:
  - resolve_plist_path()  : multi-format .plist path resolver
  - _MockText / _MockEntry / _MockVar : lightweight tkinter widget stubs
  - CLIApp                : drives Extractor, Finder, Generator from the CLI
  - run(argv)             : interactive CLI workflow (Step 1..5)
"""

import os
import re
import sys
import time
import getpass
from itertools import permutations as _permutations

from libs.Extractor  import Extractor
from libs.Finder     import Finder
from libs.Generator  import Gen_PLB
from libs.UsageLog   import append_usage_log


# ─── Path resolver ────────────────────────────────────────────────────────────

def resolve_plist_path(raw: str) -> str | None:
    """
    Resolve a .plist file path that may be:
      - A local or relative Windows path    e.g.  scan_foo.plist  /  .\subdir\foo.plist
      - An absolute Windows path            e.g.  I:\hdmxpats\cwf\...\foo.plist
      - A Unix-style network path           e.g.  /intel/hdmxpats/cwf/.../foo.plist
                                                  /nfs/cr/disks/.../foo.plist

    For Unix paths on Windows the function tries every drive letter A:-Z: with
    progressively shorter path tails (dropping one leading component at a time)
    until the file is found or all options are exhausted.

    Returns the resolved absolute path string, or None if not found.
    """
    # 1. Strip surrounding quotes (user may paste from Explorer with quotes)
    path = raw.strip().strip('"').strip("'").strip()

    if not path:
        return None

    # 2. Convert forward slashes to backslashes for consistency
    normalized = path.replace("/", "\\")

    # 3. Direct check (handles relative paths, UNC, and already-correct drive paths)
    if os.path.isfile(normalized):
        return os.path.abspath(normalized)

    # 4. If looks like a Windows absolute path (X:\...) just fail fast — drive missing
    if len(normalized) >= 3 and normalized[1] == ":" and normalized[2] == "\\":
        return None  # drive letter present but file not found

    # 5. Unix-style path: strip the leading backslash and try every drive + tail combo
    #    e.g.  \intel\hdmxpats\cwf\foo.plist  →  tries  A:\intel\..., B:\intel\..., etc.
    #          then  A:\hdmxpats\..., B:\hdmxpats\...  etc.
    parts = [p for p in normalized.split("\\") if p]  # drop empty segments

    # Drive letters to probe (prefer I: first, common network drive)
    letters = ["I"] + [chr(c) for c in range(ord("A"), ord("Z") + 1) if chr(c) != "I"]

    for start_idx in range(len(parts) - 1):           # drop 0, 1, 2 … leading parts
        tail = "\\".join(parts[start_idx:])
        for letter in letters:
            candidate = f"{letter}:\\{tail}"
            if os.path.isfile(candidate):
                print(f"  [Path resolved] {raw!r} → {candidate}")
                return candidate

    return None


# ─── Minimal widget mocks ─────────────────────────────────────────────────────

class _MockText:
    """
    Lightweight stand-in for tkinter.Text.

    Supports the tkinter line.col index format used by Finder/Extractor:
        "1.0"          → beginning of buffer
        "5.0"          → start of line 5
        "5.end"        → end of line 5
        "end" / tk.END → end of buffer
        "end-1c"       → end of buffer minus trailing newline
    """
    def __init__(self):
        self._buf = ""

    # ── Public interface ──────────────────────────────────────────────────────

    def get(self, start="1.0", end=None):
        end_s = str(end) if end is not None else None

        # Full-buffer shorthands
        if end_s in (None, "end", "tk.END") and (start == "1.0"):
            return self._buf
        if end_s == "end-1c" and start == "1.0":
            return self._buf.rstrip("\n")

        lines = self._buf.splitlines()

        try:
            s_parts = str(start).split(".", 1)
            s_line  = int(s_parts[0])
            s_col   = 0 if (len(s_parts) < 2 or s_parts[1] == "0") else int(s_parts[1])
        except (ValueError, IndexError):
            return self._buf

        # No end — return from start to EOF
        if end_s in (None, "end", "tk.END"):
            return "\n".join(lines[s_line - 1:])

        try:
            e_parts = str(end_s).split(".", 1)
            e_line  = int(e_parts[0])
            e_col   = e_parts[1] if len(e_parts) > 1 else "end"
        except (ValueError, IndexError):
            return self._buf

        if s_line == e_line and s_line <= len(lines):
            line = lines[s_line - 1]
            if e_col == "end":
                return line[s_col:]
            try:
                return line[s_col:int(e_col)]
            except ValueError:
                return line[s_col:]

        return self._buf

    def insert(self, index, text):
        self._buf += text

    def delete(self, start, end=None):
        # Clears the full buffer (sufficient for our use-cases)
        self._buf = ""

    # tkinter event stubs — no-ops in CLI
    def tag_remove(self, *a, **kw): pass
    def tag_add(self,    *a, **kw): pass
    def tag_config(self, *a, **kw): pass
    def see(self,        *a, **kw): pass
    def config(self,     **kw):     pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def lines(self):
        """Return buffer as a list of lines (no trailing newlines)."""
        return self._buf.splitlines()


class _MockEntry:
    """Lightweight stand-in for tkinter.Entry."""
    def __init__(self, value=""):
        self._v = value
    def get(self):       return self._v
    def set(self, v):    self._v = v


class _MockVar:
    """Lightweight stand-in for tkinter.BooleanVar / StringVar."""
    def __init__(self, value=None):
        self._v = value
    def get(self):       return self._v
    def set(self, v):    self._v = v


# ─── CLI Application adapter ──────────────────────────────────────────────────

class CLIApp(Finder):
    """
    Headless adapter that drives Extractor, Finder, and Generator from the CLI.

    Inherits from Finder (same as PlistTool in Main_GUI) and replaces tkinter
    widgets with lightweight mocks so the existing business logic runs unchanged.
    """

    def __init__(self):
        # ── State variables (same names as Main_GUI.__init__) ─────────────
        self.content                   = ""
        self.file_path                 = ""
        self.matches                   = []
        self.matches_tab1              = []
        self.matches_tab2              = []
        self.current_index             = 0
        self.processed_text            = ""
        self.IO_plb_output             = ""
        self.output_file_path          = ""
        self.appended_plist_content    = ""
        self.Extracted_PreBurstPList_list = []

        # ── Mock widgets ─────────────────────────────────────────────────
        self.Plist_file_viewer_text_area    = _MockText()
        self.Selected_PList_extract_text_area = _MockText()
        self.search_filter_user_input_text      = _MockEntry()
        self.search_filter_user_input_text_tab2 = _MockEntry()

        # ── Mock vars ────────────────────────────────────────────────────
        self.include_preburst   = _MockVar(True)
        self.use_debug_default  = _MockVar(True)
        self.custom_name_plb    = _MockVar("")
        self.night_mode         = _MockVar(False)

        # ── Business-logic modules ───────────────────────────────────────
        self.extractor = Extractor(self)
        self.generator = Gen_PLB(self)

    # ── Finder callbacks (overridden to be no-ops in CLI mode) ───────────────
    def Set_matches_count(self, count):                              pass
    def Set_extract_matches_button_state(self, enabled, match_count=None): pass
    def Highlight_matches_search_main_global_PList(self):            pass

    # ── File loading ──────────────────────────────────────────────────────────
    def load_file(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            self.content = f.read()
        self.file_path = path
        self.Plist_file_viewer_text_area.delete("1.0")
        self.Plist_file_viewer_text_area.insert("1.0", self.content)
        line_count = len(self.content.splitlines())
        print(f"  Loaded '{os.path.basename(path)}' — {line_count:,} lines.")

    # ── Generate (bypasses filedialog) ────────────────────────────────────────
    def generate(self):
        """Run the same pipeline as Main_GUI._on_generate_debug_plb."""
        # 1. Clean + deduplicate extract area → self.processed_text
        self.extractor.Extract_selected_PList()

        if not self.processed_text:
            print("\n[ERROR] No processed text. Make sure you extracted PList elements first.")
            return False

        # 2. If extract area contains GlobalPList block headers, strip them out
        #    automatically so only inner PList entries remain for processing.
        extract_content = self.Selected_PList_extract_text_area.get("1.0", "end-1c")
        if "GlobalPList" in extract_content:
            filtered_lines = [
                line for line in extract_content.splitlines()
                if not line.strip().startswith("GlobalPList") and line.strip() != "}"
            ]
            filtered = "\n".join(filtered_lines)
            self.Selected_PList_extract_text_area.delete("1.0")
            self.Selected_PList_extract_text_area.insert("1.0", filtered)
            # Re-run Extract_selected_PList with the cleaned content
            self.extractor.Extract_selected_PList()
            if not self.processed_text:
                print("\n[ERROR] No valid PList entries found after filtering GlobalPList headers.")
                return False

        # 3. Write blocks, regroup, rename
        self.generator.Give_me_this_block(
            self.processed_text.splitlines(), self.output_file_path
        )
        self.generator.Extract_plb_calls_grouping()
        if self.custom_name_plb.get() or self.use_debug_default.get():
            self.generator.Add_custom_plb_name()

        return True


# ─── CLI helpers ──────────────────────────────────────────────────────────────

def _header(text):
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def _ask(prompt, default=""):
    """Prompt with an optional default value shown in brackets."""
    display = f"{prompt} [{default}]: " if default else f"{prompt}: "
    raw = input(display).strip()
    return raw if raw else default


def _show_matches(app, limit=40):
    viewer_lines = app.Plist_file_viewer_text_area.lines()
    count = len(app.matches)

    if count == 0:
        print("  (no matches found)")
        return

    print(f"\n  {count} match(es) found:")
    for i, (start, _) in enumerate(app.matches[:limit]):
        ln = int(start.split(".")[0])
        text = viewer_lines[ln - 1].strip() if ln <= len(viewer_lines) else ""
        print(f"    [{i + 1:3d}] line {ln:6d}: {text}")
    if count > limit:
        print(f"    ... ({count - limit} more not shown)")


def _do_search(app):
    """
    Interactive search. Returns the mode string used ("1" or "2").
    Keeps asking until the user chooses a valid option.
    """
    while True:
        print()
        print("  Search mode:")
        print("    1 — Regex / wildcard   (example: inf*atpg*ph1)")
        print("    2 — IO equivalent IE   (example: scn_c_inf_x_begin_sEs_edt_IEvinfra1_atpg_list)")
        mode = input("  Select [1/2]: ").strip()

        if mode == "1":
            term = input("  Search term: ").strip()
            if not term:
                print("  Empty search term — skipping.")
                continue
            app.search_filter_user_input_text.set(term)
            app.Find_matches_search_main_global_PList()
            return "1"

        elif mode == "2":
            ie = input("  IO equivalent IE: ").strip()
            if not ie:
                print("  Empty input — skipping.")
                continue
            app.search_filter_user_input_text_tab2.set(ie)
            app.Get_IO_Plist()
            return "2"

        else:
            print("  Invalid option, please enter 1 or 2.")


def _do_extract(app, mode):
    """Extract matches into Selected_PList_extract_text_area and show a summary."""
    if not app.matches:
        print("  Nothing to extract (no matches).")
        return

    if mode == "1":
        app.Extract_selected_matches()
    else:
        app.Extract_selected_matches_IO()

    lines = app.Selected_PList_extract_text_area.lines()
    print(f"\n  Extracted {len(lines)} line(s):")
    for ln in lines[:25]:
        print(f"    {ln}")
    if len(lines) > 25:
        print(f"    ... ({len(lines) - 25} more not shown)")


# ─── Directory resolver ──────────────────────────────────────────────────────

def _resolve_dir(unix_path: str) -> str | None:
	"""
	Resolve a Unix-style directory path to a Windows path.
	Mirrors resolve_plist_path() logic but checks isdir instead of isfile.
	"""
	normalized = unix_path.strip().replace("/", "\\")
	if os.path.isdir(normalized):
		return normalized

	parts = [p for p in normalized.split("\\") if p]
	letters = ["I"] + [chr(c) for c in range(ord("A"), ord("Z") + 1) if chr(c) != "I"]

	for start_idx in range(len(parts)):
		tail = "\\".join(parts[start_idx:])
		for letter in letters:
			candidate = f"{letter}:\\{tail}"
			if os.path.isdir(candidate):
				return candidate
	return None


def _find_latest_patch(unix_base_path: str) -> str | None:
	"""
	Return the name of the highest-numbered 'pN' subdirectory under
	unix_base_path (e.g. returns 'p27' when p1..p27 exist).
	"""
	resolved = _resolve_dir(unix_base_path)
	if not resolved:
		return None
	try:
		entries = os.listdir(resolved)
	except OSError:
		return None
	patches = []
	for e in entries:
		m = re.match(r'^p(\d+)$', e, re.IGNORECASE)
		if m and os.path.isdir(os.path.join(resolved, e)):
			patches.append((int(m.group(1)), e))
	if not patches:
		return None
	return max(patches)[1]


def _find_plist_in_dir(unix_dir_path: str, use_debug: bool) -> str | None:
	"""
	Find the appropriate .plist file inside unix_dir_path.
	  use_debug=True  (sSs/io)  → file whose name matches regex 'cc_debug'
	  use_debug=False (sEs/ie)  → first .plist file whose name does NOT match 'cc_debug'
	"""
	resolved = _resolve_dir(unix_dir_path)
	if not resolved:
		return None
	try:
		entries = os.listdir(resolved)
	except OSError:
		return None
	plist_files = [e for e in entries if e.lower().endswith(".plist")]
	if use_debug:
		for f in plist_files:
			if re.search(r'cc_debug', f, re.IGNORECASE):
				return f
	else:
		for f in plist_files:
			if not re.search(r'cc_debug', f, re.IGNORECASE):
				return f
	return None


def _guided_plist_path() -> str | None:
	"""
	Guide the user through questions A / B / C to build the source .plist path.

	  [A] Core (MscnCoreXCC) or Uncore (MscnCdXCC)
	  [B] Latest patch or specific patch (e.g. p26)
	  [C] sSs/io (cc_debug file) or sEs/ie (non-cc_debug file)

	Returns the resolved Unix-style path string, or None on failure.
	"""
	# ── [A] Core / Uncore ───────────────────────────────────────────────────
	print()
	print("  ¿El contenido es de Core o Uncore?")
	print("    1 — Core")
	print("    2 — Uncore")
	while True:
		choice_a = input("  Selección [1/2]: ").strip()
		if choice_a == "1":
			folder_a = "MscnCoreXCC"
			break
		elif choice_a == "2":
			folder_a = "MscnCdXCC"
			break
		print("  Opción inválida, ingresa 1 o 2.")

	base_path = f"/intel/hdmxpats/cwf/{folder_a}/RevTCB0.0"

	# ── [B] Patch version ───────────────────────────────────────────────────
	print()
	print(f"  Path base: {base_path}/")
	print("  ¿Qué patch usar?")
	print("    Enter → Latest (el más reciente disponible)")
	print("    o escribe el patch específico (ej: p26)")
	patch_input = input("  Patch: ").strip()

	if not patch_input:
		print("  Buscando el latest patch...", end=" ", flush=True)
		folder_b = _find_latest_patch(base_path)
		if not folder_b:
			print(f"\n  [ERROR] No se pudo determinar el latest patch en: {base_path}")
			return None
		print(f"encontrado: {folder_b}")
	else:
		folder_b = patch_input

	plb_base = f"{base_path}/{folder_b}/plb"

	# ── [C] sSs / sEs ───────────────────────────────────────────────────────
	print()
	print("  ¿Tipo de contenido?")
	print("    1 — sSs / io  (Input/Output)")
	print("    2 — sEs / ie  (Input/Expect)")
	while True:
		choice_c = input("  Selección [1/2]: ").strip()
		if choice_c in ("1", "2"):
			break
		print("  Opción inválida, ingresa 1 o 2.")

	use_debug = (choice_c == "1")
	print(f"  Buscando archivo .plist en: {plb_base}/...", end=" ", flush=True)
	plist_file = _find_plist_in_dir(plb_base, use_debug=use_debug)
	if not plist_file:
		print(f"\n  [ERROR] No se encontró un archivo .plist adecuado en: {plb_base}")
		return None
	print(f"encontrado: {plist_file}")

	full_path = f"{plb_base}/{plist_file}"
	print(f"\n  → Fuente seleccionada: {full_path}")
	return full_path


def _smart_search(app, terms_groups: list[list[str]]) -> int:
	"""
	For each group of terms, try every permutation of the combined wildcard
	until matches are found.  Falls back to per-term individual searches if
	no permutation yields results.

	Returns the total number of lines extracted across all groups.
	"""
	all_extracted: list[str] = []

	for g_idx, terms in enumerate(terms_groups, 1):
		print(f"\n  Grupo {g_idx}/{len(terms_groups)}: {terms}")
		group_matched = False

		# ── Try every permutation of the combined wildcard ────────────────
		perms = list(_permutations(terms))
		for perm in perms:
			pattern = "*" + "*".join(perm) + "*"
			print(f"    Probando patrón: {pattern!r} ...", end=" ", flush=True)

			app.Plist_file_viewer_text_area.delete("1.0")
			app.Plist_file_viewer_text_area.insert("1.0", app.content)
			app.Selected_PList_extract_text_area.delete("1.0")
			app.matches = []
			app.current_index = 0

			app.search_filter_user_input_text.set(pattern)
			app.Find_matches_search_main_global_PList()

			if app.matches:
				print(f"{len(app.matches)} coincidencia(s)")
				app.Extract_selected_matches()
				new_lines = app.Selected_PList_extract_text_area.lines()
				all_extracted.extend(new_lines)
				group_matched = True
				break
			else:
				print("sin coincidencias")

		# ── Fallback: search each term individually ───────────────────────
		if not group_matched:
			print(f"    Ninguna permutación tuvo resultados. Buscando por término individual...")
			for term in terms:
				pattern = f"*{term}*"
				print(f"    Probando: {pattern!r} ...", end=" ", flush=True)

				app.Plist_file_viewer_text_area.delete("1.0")
				app.Plist_file_viewer_text_area.insert("1.0", app.content)
				app.Selected_PList_extract_text_area.delete("1.0")
				app.matches = []
				app.current_index = 0

				app.search_filter_user_input_text.set(pattern)
				app.Find_matches_search_main_global_PList()

				if app.matches:
					print(f"{len(app.matches)} coincidencia(s)")
					app.Extract_selected_matches()
					new_lines = app.Selected_PList_extract_text_area.lines()
					all_extracted.extend(new_lines)
				else:
					print("sin coincidencias")
					print(f"    ⚠️  Sin coincidencias para '{term}'. Verifica que el término exista en el plist.")

	# ── Consolidate all extracted lines back into the text area ──────────────
	app.Selected_PList_extract_text_area.delete("1.0")
	if all_extracted:
		app.Selected_PList_extract_text_area.insert("1.0", "\n".join(all_extracted))

	return len(all_extracted)


# ─── Interactive CLI flow ─────────────────────────────────────────────────────

def run(argv=None):
	print("=" * 60)
	print("   PLB DEBUG TOOL — CLI Mode")
	print("   (wraps Extractor · Finder · Generator)")
	print("=" * 60)

	start_time = time.time()
	app = CLIApp()

	# ── Step 1 · Open .plist file ─────────────────────────────────────────────
	_header("Step 1 · Archivo .plist de origen")

	plist_path = None

	# If a path was passed via argv, try it first
	if argv and argv[0]:
		resolved = resolve_plist_path(argv[0])
		if resolved:
			plist_path = resolved
			print(f"  Usando: {plist_path}")

	# If we still have no path, guide the user
	if not plist_path:
		print()
		print("  No se proporcionó un archivo .plist de origen.")
		print("  Puedes escribir la ruta directamente o dejar que el asistente la construya.")
		print()
		print("    1 — Escribir la ruta manualmente")
		print("    2 — Guiarme para construir la ruta")
		while True:
			choice = input("  Selección [1/2]: ").strip()
			if choice == "1":
				while True:
					raw_path = input("  Ruta del .plist: ").strip()
					resolved = resolve_plist_path(raw_path)
					if resolved:
						plist_path = resolved
						break
					print(f"\n  [ERROR] Archivo no encontrado: {raw_path!r}")
					print("  Formatos aceptados:")
					print("    scan_foo.plist                         (local / relativo)")
					print("    I:\\hdmxpats\\cwf\\...\\foo.plist          (Windows)")
					print("    /intel/hdmxpats/cwf/.../foo.plist      (Unix / red)")
					if input("\n  ¿Intentar de nuevo? [S/n]: ").strip().lower() == "n":
						sys.exit(1)
				break
			elif choice == "2":
				while True:
					guided = _guided_plist_path()
					if guided:
						resolved = resolve_plist_path(guided)
						if resolved:
							plist_path = resolved
							break
					print("  No se pudo resolver el path. Intentemos de nuevo.")
				break
			else:
				print("  Opción inválida, ingresa 1 o 2.")

	app.load_file(plist_path)

	# ── Step 2 · Contenido a buscar ───────────────────────────────────────────
	_header("Step 2 · Contenido a buscar")
	print("  Ingresa los términos de búsqueda.")
	print("  · Separa términos con espacios dentro de un grupo.")
	print("  · Separa grupos con coma (,) para múltiples búsquedas acumuladas.")
	print("  Ejemplo:  inf ddimbc4r0 atpg ph1, inf ddimbc4r0 atpg ph2, inf ddimbc4r0 atpg ph3")
	print()

	while True:
		raw_content = input("  Contenido: ").strip()
		if raw_content:
			break
		print("  Debes ingresar al menos un término.")

	# Parse comma-separated groups, each group is a list of whitespace-split terms
	groups_raw   = [g.strip() for g in raw_content.split(",") if g.strip()]
	terms_groups = [g.split() for g in groups_raw]

	print(f"\n  {len(terms_groups)} grupo(s) detectado(s):")
	for i, terms in enumerate(terms_groups, 1):
		print(f"    [{i}] {' · '.join(terms)}")

	total_extracted = _smart_search(app, terms_groups)

	if total_extracted == 0:
		print("\n  [ERROR] No se encontraron coincidencias. Verifica los términos e intenta de nuevo.")
		sys.exit(1)

	print(f"\n  Total de líneas extraídas: {total_extracted}")

	# ── Step 3 · Opciones ─────────────────────────────────────────────────────
	_header("Step 3 · Opciones")

	inc = _ask("¿Incluir PreBurstPList (hotreset)? [S/n]", "s")
	app.include_preburst.set(inc.lower() != "n")

	print()
	print("  Sufijo para el nombre del archivo de salida:")
	print("    Enter → usa 'debug' como sufijo  (por defecto)")
	print("    Escribe una palabra → sufijo personalizado")
	custom_suffix = input("  Sufijo: ").strip()

	if custom_suffix:
		app.use_debug_default.set(False)
		app.custom_name_plb.set(custom_suffix)
		effective_suffix = custom_suffix
	else:
		app.use_debug_default.set(True)
		app.custom_name_plb.set("")
		effective_suffix = "debug"

	# ── Step 4 · Ruta de salida ───────────────────────────────────────────────
	_header("Step 4 · Archivo de salida")

	stem         = os.path.splitext(os.path.basename(plist_path))[0]
	current_dir  = os.path.abspath(".")
	default_out  = os.path.join(current_dir, f"{stem}_{effective_suffix}.plist")

	print(f"  Directorio actual: {current_dir}")
	print(f"  Archivo por defecto: {default_out}")
	print()
	print("  ¿Dónde guardar el archivo?")
	print("    Enter → guardar en el directorio actual (por defecto)")
	print("    o escribe la ruta deseada (Windows o Unix)")
	raw_out = input("  Ruta de salida: ").strip()

	if raw_out:
		# Accept Unix-style paths too
		win_out = raw_out.replace("/", "\\")
		out_path = win_out
	else:
		out_path = default_out

	app.output_file_path = out_path

	# ── Step 5 · Generar ──────────────────────────────────────────────────────
	_header("Step 5 · Generando")

	ok = app.generate()

	if not ok:
		print("\n  La generación falló. Revisa los errores anteriores.")
		sys.exit(1)

	# ── Usage log ─────────────────────────────────────────────────────────────
	try:
		search_text = " | ".join(" ".join(g) for g in terms_groups)
		append_usage_log(
			username    = getpass.getuser(),
			plb_name    = os.path.basename(out_path),
			search_text = search_text,
			mtpl_file   = os.path.basename(plist_path),
		)
	except Exception:
		pass  # Never block user on logging

	elapsed = time.time() - start_time
	print(f"\n  ✓ Archivo guardado en:")
	print(f"  {os.path.abspath(out_path)}")
	print(f"\n  ⏱  Tiempo de ejecución: {elapsed:.2f}s")
	print()
