"""
ssh_client/file_transfer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Upload and download plain files over SFTP.

Example
-------
    from ssh_client.connection import SSHConnection
    from ssh_client.file_transfer import upload_file, download_file

    with SSHConnection() as conn:
        upload_file(conn, local_path="report.csv", remote_path="/home/user/report.csv")
        download_file(conn, remote_path="/home/user/output.log", local_path="output.log")
"""

import os
from pathlib import Path

from .connection import SSHConnection


def upload_file(
    conn: SSHConnection,
    local_path: "str | Path",
    remote_path: str,
) -> None:
    """
    Upload a local file to the remote server via SFTP.

    Parameters
    ----------
    conn        : Active SSHConnection instance.
    local_path  : Path to the file on this machine.
    remote_path : Absolute (or relative to home) path on the server.

    Raises
    ------
    FileNotFoundError  if `local_path` does not exist.
    RuntimeError       if the connection is not open.
    """
    if not conn.is_connected:
        raise RuntimeError("SSHConnection is not open. Call connect() first.")

    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")
    if not local_path.is_file():
        raise ValueError(f"local_path must point to a file, not a directory: {local_path}")

    conn.sftp.put(str(local_path), remote_path)


def download_file(
    conn: SSHConnection,
    remote_path: str,
    local_path: "str | Path",
) -> None:
    """
    Download a file from the remote server to this machine via SFTP.

    Parameters
    ----------
    conn        : Active SSHConnection instance.
    remote_path : Absolute (or relative to home) path on the server.
    local_path  : Destination path on this machine.
                  Parent directories are created automatically.

    Raises
    ------
    RuntimeError  if the connection is not open.
    IOError       if the remote file cannot be read.
    """
    if not conn.is_connected:
        raise RuntimeError("SSHConnection is not open. Call connect() first.")

    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    conn.sftp.get(remote_path, str(local_path))
