"""
bundle_debug_pats/libs/app_runner.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Orchestrates the full bundle_debug_pats workflow in 4 steps:

  1. Generate a debug .plist locally using plist_extractor.
  2. Create the destination directory on the CR server (mkdir -p + chmod 777).
  3. Upload the .plist to SC11/ZN11, run bundle_debug_pats.py, capture result.
  4. Delete the tmp .plist from SC11/ZN11.

Lifecycle:  setup() → start() → shutdown()
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from utilities.ssh_client import (
    SSHConnection,
    run_command,
    run_remote_script,
    upload_file,
)

# ── Path resolution ───────────────────────────────────────────────────────────
# This file is at: UserCode/src/bundle_debug_pats/libs/app_runner.py
#   .parent              → libs/
#   .parent.parent       → bundle_debug_pats/      (_PROJECT_ROOT)
#   .parent.parent.parent → src/
#   .parent×4            → UserCode/               (_USERCODE_ROOT)
_PROJECT_ROOT          = Path(__file__).resolve().parent.parent
_USERCODE_ROOT         = _PROJECT_ROOT.parent.parent
_PLIST_EXTRACTOR_MAIN  = _USERCODE_ROOT / "src" / "plist_extractor" / "main.py"


class AppRunner:

    def __init__(self) -> None:
        self._args:      argparse.Namespace | None = None
        self._exit_code: int = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def setup(self) -> None:
        self._args = self._build_parser().parse_args()

    def start(self) -> None:
        assert self._args is not None
        args = self._args

        cr_dir      = f"/intel/hdmxpats/cwf/dev/{args.username}/{args.bundle_dir}"
        local_plist = _PROJECT_ROOT / "data" / args.output_name
        remote_tmp  = f"/tmp/{args.output_name}"

        # ── Step 1: Generate plist locally ────────────────────────────────────
        self._section("STEP 1 — Generate plist via plist_extractor")
        if not self._generate_plist(args, local_plist, args.plist):
            self._exit_code = 1
            return

        # ── Step 2: Create CR directory ───────────────────────────────────────
        self._section("STEP 2 — Create destination directory on CR")
        with SSHConnection(profile="CR") as conn:
            self._show(run_command(conn, f"mkdir -p {cr_dir}"))
            # chmod 777 required: bundle script runs on SC11 and writes here
            # via NFS — the UID may differ between SC11 and CR, so the process
            # appears as "other" on the CR filesystem and needs write access.
            run_command(conn, f"chmod 777 {cr_dir}")
            print(f"  Ready: {cr_dir}")

        # ── Steps 3 + 4: Upload, run, and clean up on SC11/ZN11 ───────────────
        self._section("STEP 3 — Upload plist to SC11 / ZN11")
        with SSHConnection(profile="SC11") as conn:
            upload_file(conn, local_path=local_plist, remote_path=remote_tmp)
            print(f"  Uploaded: {local_plist.name}  →  {remote_tmp}")

            self._section("STEP 4 — Execute bundle_debug_pats.py on SC11 / ZN11")
            result = run_remote_script(
                conn,
                remote_script_path="bundle_debug_pats.py",
                source_env="/p/pde/tvpv/cwf/sourceme.rc",
                named_args={
                    "p":        args.product,
                    "module":   args.module,
                    "tester":   args.tester,
                    "site":     args.site,
                    "destpath": cr_dir,
                },
                args=[remote_tmp],
                auto_approve=True,
                timeout=args.timeout,
            )
            print(f"[exit_code]  {result.exit_code}")
            print(f"[stdout]\n{result.stdout}")
            if result.stderr:
                print(f"[stderr]\n{result.stderr}")

            if not result.success:
                self._exit_code = result.exit_code

            self._section("STEP 5 — Delete tmp plist from SC11 / ZN11")
            self._show(run_command(conn, f"rm -f {remote_tmp}"))
            print(f"  Deleted: {remote_tmp}")

    def shutdown(self) -> None:
        print("\nDone.")
        sys.exit(self._exit_code)

    def run(self) -> None:
        self.setup()
        self.start()
        self.shutdown()

    # ── Plist generation ──────────────────────────────────────────────────────

    @staticmethod
    def _generate_plist(
        args: argparse.Namespace,
        output_path: Path,
        plist_paths: list[str],
    ) -> bool:
        """
        Invoke plist_extractor/main.py for each plist in *plist_paths* and
        write the combined output to *output_path*.
        When multiple plists are given, results are appended (the 'Version 5.0;'
        header is kept only from the first run).
        Returns True only if all invocations succeed.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _build_cmd(plist: str, out: Path) -> list[str]:
            cmd: list[str] = [
                sys.executable,
                str(_PLIST_EXTRACTOR_MAIN),
                "--plist",     plist,
                "--partition", *args.partition,
                "--output",    str(out),
            ]
            if args.content_type:
                for ct_group in args.content_type:
                    cmd += ["--content-type"] + ct_group
            if args.approach:
                cmd += ["--approach", args.approach]
            if args.phase:
                cmd += ["--phase", args.phase]
            if args.full_content:
                cmd.append("--full-content")
            for pattern in (args.skip or []):
                cmd += ["--skip", pattern]
            return cmd

        for i, plist in enumerate(plist_paths):
            if i == 0:
                out = output_path
            else:
                out = output_path.with_suffix(f".tmp{i}.plist")

            cmd = _build_cmd(plist, out)
            print(f"  [plist {i+1}/{len(plist_paths)}] Command: {' '.join(cmd)}")
            result = subprocess.run(cmd, text=True)

            if result.returncode != 0:
                if i == 0:
                    # First plist failed — nothing to combine, abort.
                    return False
                else:
                    # Subsequent plist had no matches — warn and continue.
                    print(
                        f"  WARNING: No matches in plist {i+1} ({Path(plist).name}). "
                        "Skipping — combined output will use results from other plist(s)."
                    )
                    out.unlink(missing_ok=True)
                    continue

            # Append subsequent plist results to the first output (skip header)
            if i > 0 and out.exists():
                lines = out.read_text(encoding="utf-8").splitlines(keepends=True)
                # Strip leading 'Version 5.0;' line and any blank lines before first block
                body = "".join(
                    l for l in lines if not l.strip().startswith("Version")
                )
                with output_path.open("a", encoding="utf-8") as f:
                    f.write(body)
                out.unlink(missing_ok=True)

        return True

    # ── Argparse ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            prog="bundle_debug_pats",
            description=(
                "Full-stack bundle debug pats runner:\n"
                "  1. Generate a .plist via plist_extractor\n"
                "  2. Create the CR destination directory (mkdir -p + chmod 777)\n"
                "  3. Upload .plist to SC11/ZN11 and run bundle_debug_pats.py\n"
                "  4. Delete the tmp .plist from SC11/ZN11\n\n"
                "Example:\n"
                "  python main.py \\\n"
                "    --plist scan_uncore_class_xdcc_debug.plist \\\n"
                "    --partition ddrmc --skip ddrmcnor --skip repair \\\n"
                "    --bundle-dir my_bundle_dir"
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        # ── plist_extractor options ───────────────────────────────────────────
        plist_grp = p.add_argument_group("plist_extractor options")
        plist_grp.add_argument(
            "--plist", metavar="PATH", action="append", dest="plist",
            required=True,
            help=(
                "Source .plist file path. Repeatable: --plist debug.plist --plist hvm.plist. "
                "Results from all plists are combined into a single output."
            ),
        )
        plist_grp.add_argument(
            "--partition", metavar="PART", nargs="+", required=True,
            help="Partition name(s) to extract.",
        )
        plist_grp.add_argument(
            "--content-type", metavar="TYPE", nargs="+", action="append",
            help=(
                "Content type(s) to match (atpg, tatpg, chain, ca1tf, …). "
                "Repeatable: --content-type atpg --content-type ca1tf."
            ),
        )
        plist_grp.add_argument(
            "--approach", metavar="APPR",
            help="Approach filter (e.g. sSs, sEs).",
        )
        plist_grp.add_argument(
            "--phase", metavar="PHASE",
            help="Phase filter (e.g. ph1, ph2).",
        )
        plist_grp.add_argument(
            "--full-content", action="store_true",
            help=(
                "Auto-expand base content type: "
                "atpg → adds ca1tf + atpgtop*; "
                "tatpg → adds ca2tf + tatpgtop*; "
                "chain → adds chaintop*."
            ),
        )
        plist_grp.add_argument(
            "--skip", metavar="PATTERN", action="append", default=[],
            help="Exclude matched plists containing this substring. Repeatable.",
        )
        plist_grp.add_argument(
            "--output-name", metavar="NAME", default="debug_plist.plist",
            dest="output_name",
            help=(
                "File name for the generated .plist saved to data/ "
                "(default: debug_plist.plist)."
            ),
        )

        # ── bundle_debug_pats.py options ──────────────────────────────────────
        bundle_grp = p.add_argument_group("bundle_debug_pats.py options")
        bundle_grp.add_argument(
            "--username", metavar="USER", default="jdcubero",
            help="Username for the CR destpath (default: jdcubero).",
        )
        bundle_grp.add_argument(
            "--bundle-dir", metavar="DIR", required=True,
            dest="bundle_dir",
            help="Subdirectory under /intel/hdmxpats/cwf/dev/{username}/.",
        )
        bundle_grp.add_argument(
            "--product", metavar="PROD", default="cwf",
            help="Value for -p argument to bundle_debug_pats.py (default: cwf).",
        )
        bundle_grp.add_argument(
            "--module", metavar="MOD", default="MscnCdXCC",
            help="Value for -module argument (default: MscnCdXCC).",
        )
        bundle_grp.add_argument(
            "--tester", metavar="TST", default="hdmt2",
            help="Value for -tester argument (default: hdmt2).",
        )
        bundle_grp.add_argument(
            "--site", metavar="SITE", default="CR",
            help="Value for -site argument (default: CR).",
        )
        bundle_grp.add_argument(
            "--timeout", metavar="SECS", type=int, default=120,
            help="Seconds to wait for bundle_debug_pats.py (default: 120).",
        )

        return p

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _section(title: str) -> None:
        print(f"\n{'─' * 60}")
        print(f"  {title}")
        print("─" * 60)

    @staticmethod
    def _show(result) -> None:
        print(result)
