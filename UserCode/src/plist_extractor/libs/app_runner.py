"""
app_runner.py — AppRunner orchestrates the plist_extractor application lifecycle.

Lifecycle
---------
    AppRunner.run()
        └── setup()    ← argparse / interactive prompts
        └── start()    ← Parser → Matcher → Extractor → Generator
        └── shutdown() ← sys.exit(exit_code)

Modes
-----
    Batch mode     : python main.py --plist <path> --partition <name> --output <path> [options]
    Interactive    : python main.py --interactive
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from libs.Parser    import PlistParser
from libs.Matcher   import PlistMatcher
from libs.Extractor import PlistExtractor
from libs.Generator import PlistGenerator


class AppRunner:
    def __init__(self) -> None:
        self._args:      argparse.Namespace | None = None
        self._exit_code: int = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def setup(self) -> None:
        self._args = self._build_parser().parse_args()

    def start(self) -> None:
        assert self._args is not None
        if self._args.interactive:
            params = self._run_interactive()
        else:
            params = self._args_to_params(self._args)

        if params is None:
            self._exit_code = 1
            return

        self._run_batch(**params)

    def shutdown(self) -> None:
        sys.exit(self._exit_code)

    def run(self) -> None:
        self.setup()
        self.start()
        self.shutdown()

    # ── Argparse ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            prog="plist_extractor",
            description=(
                "Extract matching GlobalPList blocks from a .plist file.\n"
                "The output file always starts with 'Version 5.0;'."
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        mode = p.add_mutually_exclusive_group()
        mode.add_argument(
            "--interactive",
            action="store_true",
            help="Launch the interactive step-by-step guided flow.",
        )

        # Required in batch mode
        p.add_argument("--plist",     metavar="PATH",       help="Input .plist file.")
        p.add_argument("--partition", metavar="PART", nargs="+", help="Partition name(s) to extract.")
        p.add_argument("--output",    metavar="PATH",       help="Output .plist file.")

        # Content filters
        p.add_argument("--content-type",  metavar="TYPE",   nargs="+", action="append",
                       help="Content type(s) to match (atpg, tatpg, chain, ca1tf, …). "
                            "Repeatable: --content-type atpg --content-type ca1tf.")
        p.add_argument("--approach",      metavar="APPR",
                       help="Approach filter (e.g. sSs, sEs).")
        p.add_argument("--phase",         metavar="PHASE",
                       help="Phase filter (e.g. ph1, ph2).")
        p.add_argument("--power-domain",  metavar="DOM",
                       help="Power-domain filter (e.g. cfc, inf, ddr).")
        p.add_argument("--frequency",     metavar="FREQ",
                       help="Frequency filter (e.g. f1, f2).")
        p.add_argument("--flow",          metavar="FLOW",
                       help="Flow filter (e.g. chk, srh, vmax).")
        p.add_argument("--full-content",  action="store_true",
                       help=(
                           "Auto-expand base content type: "
                           "atpg → adds ca1tf + atpgtop*; "
                           "tatpg → adds ca2tf + tatpgtop*; "
                           "chain → adds chaintop*."
                       ))
        p.add_argument("--skip", metavar="PATTERN", action="append", default=[],
                       help="Exclude matched plists containing this substring. Repeatable.")

        return p

    # ── Batch runner ──────────────────────────────────────────────────────────

    def _run_batch(
        self,
        plist_path:    str,
        partitions:    list[str],
        output_path:   str,
        content_types: list[str] | None = None,
        approach:      str | None       = None,
        phase:         str | None       = None,
        power_domain:  str | None       = None,
        frequency:     str | None       = None,
        flow:          str | None       = None,
        full_content:  bool             = False,
        skip_patterns: list[str]        | None = None,
    ) -> None:
        t0 = time.perf_counter()

        print(f"\n[1/4] Cargando archivo: {plist_path}")
        try:
            plist_file = PlistParser.parse(plist_path)
        except FileNotFoundError as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            self._exit_code = 1
            return
        print(f"  Bloques encontrados: {len(plist_file.blocks)}")

        print(f"\n[2/4] Configurando criterios de búsqueda...")
        print(f"  Partición(es) : {', '.join(partitions)}")
        if content_types:
            print(f"  Tipo(s) de contenido : {', '.join(content_types)}"
                  + (" [full-content activado]" if full_content else ""))
        if approach:     print(f"  Approach     : {approach}")
        if phase:        print(f"  Phase        : {phase}")
        if power_domain: print(f"  Power-domain : {power_domain}")
        if frequency:    print(f"  Frequency    : {frequency}")
        if flow:         print(f"  Flow         : {flow}")
        if skip_patterns:print(f"  Skip         : {', '.join(skip_patterns)}")

        matcher = PlistMatcher(
            partitions    = partitions,
            content_types = content_types,
            approach      = approach,
            phase         = phase,
            power_domain  = power_domain,
            frequency     = frequency,
            flow          = flow,
            full_content  = full_content,
            skip_patterns = skip_patterns,
        )

        print(f"\n[3/4] Extrayendo árbol de plists...")
        extractor = PlistExtractor(plist_file, matcher)
        blocks = extractor.extract()

        if not blocks:
            print(
                "  ADVERTENCIA: No se encontraron plists que coincidan con los criterios.",
                file=sys.stderr,
            )
            self._exit_code = 1
            return

        content_count  = sum(1 for b in blocks if not _is_plb_or_hotreset(b))
        plb_count      = sum(1 for b in blocks if _is_plb_heuristic(b))
        hotreset_count = len(blocks) - content_count - plb_count
        print(f"  Hotreset : {hotreset_count}")
        print(f"  Contenido: {content_count}")
        print(f"  PLB(s)   : {plb_count}")
        print(f"  Total    : {len(blocks)}")

        print(f"\n[4/4] Generando archivo de salida: {output_path}")
        generator = PlistGenerator()
        try:
            generator.write(blocks, output_path)
        except OSError:
            self._exit_code = 1
            return

        elapsed = time.perf_counter() - t0
        print(f"\n  Tiempo de ejecución: {elapsed:.2f}s")

    # ── Interactive mode ──────────────────────────────────────────────────────

    def _run_interactive(self) -> dict | None:
        """
        Eight-step guided flow.  Returns a dict of keyword arguments for
        ``_run_batch``, or None if the user aborts.
        """
        print("\n" + "=" * 60)
        print("  plist_extractor — Modo interactivo")
        print("=" * 60 + "\n")

        # Step 1 — plist file path
        plist_path = self._prompt_plist_path()
        if plist_path is None:
            return None

        # Step 2 — partitions
        partitions = self._prompt_partitions()
        if not partitions:
            return None

        # Step 3 — content types
        content_types = self._prompt_content_types()

        # Step 4 — full-content
        full_content = False
        if content_types:
            resp = input("  [Paso 4] ¿Incluir contenido completo (cell-aware y topoff)? [S/N]: ").strip().upper()
            full_content = resp == "S"

        # Step 5 — approach
        approach = input("  [Paso 5] Approach (ej. sSs, sEs) — Enter para omitir: ").strip() or None

        # Step 6 — phase
        phase = input("  [Paso 6] Phase (ej. ph1, ph2) — Enter para omitir: ").strip() or None

        # Step 7 — skip patterns
        skip_patterns = self._prompt_skip_patterns()

        # Step 8 — output path
        output_path = self._prompt_output_path()
        if output_path is None:
            return None

        # Summary + confirmation
        print("\n" + "-" * 60)
        print("  Resumen de extracción:")
        print(f"    Archivo de entrada : {plist_path}")
        print(f"    Partición(es)      : {', '.join(partitions)}")
        if content_types:
            print(f"    Tipo(s) contenido  : {', '.join(content_types)}"
                  + (" [full-content]" if full_content else ""))
        if approach:     print(f"    Approach           : {approach}")
        if phase:        print(f"    Phase              : {phase}")
        if skip_patterns:print(f"    Skip               : {', '.join(skip_patterns)}")
        print(f"    Archivo de salida  : {output_path}")
        print("-" * 60)

        confirm = input("  ¿Continuar? [S/N]: ").strip().upper()
        if confirm != "S":
            print("  Operación cancelada.")
            return None

        return {
            "plist_path":    plist_path,
            "partitions":    partitions,
            "output_path":   output_path,
            "content_types": content_types if content_types else None,
            "full_content":  full_content,
            "approach":      approach,
            "phase":         phase,
            "skip_patterns": skip_patterns if skip_patterns else None,
        }

    # ── Interactive helpers ───────────────────────────────────────────────────

    @staticmethod
    def _prompt_plist_path() -> str | None:
        while True:
            raw = input("  [Paso 1] Ruta del archivo .plist: ").strip().strip('"').strip("'")
            if not raw:
                print("  ERROR: La ruta no puede estar vacía.")
                continue
            p = Path(raw)
            if not p.is_file():
                print(f"  ERROR: Archivo no encontrado: {raw}")
                retry = input("  ¿Intentar de nuevo? [S/N]: ").strip().upper()
                if retry != "S":
                    return None
                continue
            return str(p)

    @staticmethod
    def _prompt_partitions() -> list[str]:
        while True:
            raw = input("  [Paso 2] Partición(es) a extraer (separadas por espacio): ").strip()
            parts = raw.split()
            if parts:
                return parts
            print("  ERROR: Debes ingresar al menos una partición.")

    @staticmethod
    def _prompt_content_types() -> list[str]:
        raw = input(
            "  [Paso 3] Tipo(s) de contenido (ej. atpg tatpg chain) — Enter para todos: "
        ).strip()
        return raw.split() if raw else []

    @staticmethod
    def _prompt_skip_patterns() -> list[str]:
        raw = input(
            "  [Paso 7] Patrones a excluir, separados por espacio — Enter para omitir: "
        ).strip()
        return raw.split() if raw else []

    @staticmethod
    def _prompt_output_path() -> str | None:
        while True:
            raw = input("  [Paso 8] Ruta del archivo de salida (.plist): ").strip().strip('"').strip("'")
            if not raw:
                print("  ERROR: La ruta no puede estar vacía.")
                continue
            p = Path(raw)
            if p.exists() and not p.is_file():
                print(f"  ERROR: La ruta existe pero no es un archivo: {raw}")
                continue
            return str(p)

    # ── Params helper ─────────────────────────────────────────────────────────

    @staticmethod
    def _args_to_params(args: argparse.Namespace) -> dict | None:
        """Validate batch-mode args and convert to _run_batch kwargs."""
        missing = []
        if not args.plist:      missing.append("--plist")
        if not args.partition:  missing.append("--partition")
        if not args.output:     missing.append("--output")
        if missing:
            print(
                f"ERROR: Los siguientes argumentos son requeridos en modo batch: "
                f"{', '.join(missing)}",
                file=sys.stderr,
            )
            return None

        # Flatten list-of-lists produced by nargs="+" + action="append":
        # --content-type atpg ca1tf       → [["atpg", "ca1tf"]]     → ["atpg", "ca1tf"]
        # --content-type atpg --content-type ca1tf → [["atpg"],["ca1tf"]] → ["atpg", "ca1tf"]
        content_types: list[str] | None = None
        if args.content_type:
            content_types = [ct for group in args.content_type for ct in group]

        return {
            "plist_path":    args.plist,
            "partitions":    args.partition,
            "output_path":   args.output,
            "content_types": content_types,
            "approach":      args.approach,
            "phase":         args.phase,
            "power_domain":  args.power_domain,
            "frequency":     args.frequency,
            "flow":          args.flow,
            "full_content":  args.full_content,
            "skip_patterns": args.skip if args.skip else None,
        }


# ─── Classification helpers (used in progress reporting) ─────────────────────

def _is_plb_heuristic(block) -> bool:
    from libs.Generator import _is_plb
    return _is_plb(block)


def _is_plb_or_hotreset(block) -> bool:
    from libs.Generator import _is_plb, _is_hotreset
    return _is_plb(block) or _is_hotreset(block)
