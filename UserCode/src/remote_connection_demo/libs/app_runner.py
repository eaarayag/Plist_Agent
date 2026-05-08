"""
remote_connection_demo/libs/app_runner.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Same example as remote_connection/main.py, structured as an AppRunner.

Lifecycle:  setup() → start() → shutdown()
"""

from pathlib import Path

from utilities.ssh_client import (
    SSHConnection,
    run_command,
    run_remote_script,
    upload_file,
)


class AppRunner:

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def setup(self) -> None:
        print("Setting up...")

    def start(self) -> None:
        self._section("BUNDLE EXECUTION")

        # ── Step 1: Create destination directory on CR ────────────────────
        self._section("BUNDLE EXECUTION: Create CR directory")
        username = "jdcubero"
        bundle_dir = "ssh_client_test"
        cr_directory = f"/intel/hdmxpats/cwf/dev/{username}/{bundle_dir}"

        with SSHConnection(profile="CR") as conn:
            self._section("1. mkdir — create a remote directory for the bundle content")
            self._show(run_command(conn, f"mkdir -p {cr_directory}"))
            # 777 is required because the script runs on SC11 and writes here
            # via NFS. The UID for jdcubero may differ between SC11 and CR,
            # so the process appears as "other" on the CR filesystem —
            # which needs write permission to create subdirectories.
            run_command(conn, f"chmod 777 {cr_directory}")

        # ── Step 2 & 3: Upload plist and run bundle script on SC11 ────────
        with SSHConnection(profile="SC11") as conn:

            self._section("BUNDLE EXECUTION: Send debug PList to SC11")
            file_sample = "debug_plist.plist"
            self._section("2. Upload a local file to the server")
            local_sample = Path(__file__).resolve().parent.parent / "data" / file_sample
            remote_target = (
                f"/tmp/{file_sample}"
            )
            upload_file(conn, local_path=local_sample, remote_path=remote_target)

            self._section("BUNDLE EXECUTION: Execute bundle_debug_pats.py")
            self._section("3. Run a script located on the server")

            result = run_remote_script(
                conn,
                remote_script_path="bundle_debug_pats.py",
                source_env="/p/pde/tvpv/cwf/sourceme.rc",
                named_args={
                    "p":        "cwf",
                    "module":   "MscnCdXCC",
                    "tester":   "hdmt2",
                    "site":     "CR",
                    "destpath": cr_directory,
                },
                args=[remote_target],
                auto_approve=True,
                timeout=120,
            )

            print(f"[exit_code]  {result.exit_code}")
            print(f"[stdout]\n{result.stdout}")
            if result.stderr:
                print(f"[stderr]\n{result.stderr}")

    def shutdown(self) -> None:
        print("\nDone.")

    def run(self) -> None:
        self.setup()
        self.start()
        self.shutdown()

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _section(title: str) -> None:
        print(f"\n{'─' * 60}")
        print(f"  {title}")
        print("─" * 60)

    @staticmethod
    def _show(result) -> None:
        print(result)
