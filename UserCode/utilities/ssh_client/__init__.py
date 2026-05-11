"""
ssh_client
~~~~~~~~~~
Shared utility: SSH connection, command execution, file transfer, and
remote script execution over paramiko.

Quick start:

    from utilities.ssh_client import SSHConnection, run_command, upload_file, download_file, run_remote_script

    with SSHConnection() as conn:
        result = run_command(conn, "pwd")
        print(result.stdout)

Connection profiles are defined in UserCode/config/ssh_config.ini.
"""

from .connection import SSHConnection
from .commands import CommandResult, run_command
from .file_transfer import download_file, upload_file
from .script_runner import run_remote_script

__all__ = [
    "SSHConnection",
    "CommandResult",
    "run_command",
    "upload_file",
    "download_file",
    "run_remote_script",
]
