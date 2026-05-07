"""
ssh_client/commands.py
~~~~~~~~~~~~~~~~~~~~~~
Execute shell commands on the remote server.

Example
-------
    from ssh_client.connection import SSHConnection
    from ssh_client.commands import run_command

    with SSHConnection() as conn:
        stdout, stderr, exit_code = run_command(conn, "pwd")
        print(stdout)
"""

from dataclasses import dataclass
from typing import Optional

from .connection import SSHConnection


@dataclass
class CommandResult:
    """Holds the output of a single remote command."""
    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def __str__(self) -> str:
        parts = [f"exit_code={self.exit_code}"]
        if self.stdout:
            parts.append(f"stdout:\n{self.stdout.rstrip()}")
        if self.stderr:
            parts.append(f"stderr:\n{self.stderr.rstrip()}")
        return "\n".join(parts)


def run_command(
    conn: SSHConnection,
    command: str,
    timeout: int = 30,
    stdin_input: "Optional[str]" = None,
    source_env: "Optional[str]" = None,
) -> CommandResult:
    """
    Run a shell command on the remote host.

    Parameters
    ----------
    conn        : Active SSHConnection instance.
    command     : Shell command string, e.g. "mkdir -p /tmp/test".
    timeout     : Seconds to wait for the command to finish (default 30).
    stdin_input : Text to send to the command's stdin before reading output.
                  Use this to respond to prompts, e.g. stdin_input="y\n"
                  to confirm a yes/no question, or "y\ny\n" for multiple.
    source_env  : Path to a shell environment file to source before running
                  the command, e.g. "/p/pde/tvpv/cwf/sourceme.rc".
                  When set, the commands are fed to `bash -s` via stdin so
                  there are no quoting or variable-expansion issues — it
                  behaves exactly like typing in a terminal:
                      source /p/pde/tvpv/cwf/sourceme.rc
                      <your command>
                  This is required when your tools are only available after
                  loading a custom environment.

    Returns
    -------
    CommandResult with .stdout, .stderr, .exit_code, and .success.

    Raises
    ------
    RuntimeError  if the connection is not open.
    TimeoutError  if the command exceeds `timeout` seconds.
    """
    if not conn.is_connected:
        raise RuntimeError("SSHConnection is not open. Call connect() first.")

    if source_env:
        # Feed the commands to the server's shell via stdin.
        # This avoids ALL quoting/escaping issues and behaves exactly like
        # typing the commands in a terminal session.
        # Works for both tcsh and bash — both support reading from stdin.
        shell = conn.shell  # e.g. "tcsh" or "bash", from config.ini
        shell_script = f"source {source_env}\n{command}\n"
        actual_command = f"{shell} -s"
        # stdin_input is intentionally NOT appended here.
        # Interactive responses for the script must be embedded in the
        # command string itself (e.g. `yes | script` or `printf '...' | script`)
        # because the shell is already consuming stdin for its own commands.
        actual_stdin = shell_script
    else:
        actual_command = command
        actual_stdin = stdin_input

    print(f"[ssh_client] exec: {actual_command}")
    if source_env:
        print(f"[ssh_client] script fed to {conn.shell}:\n  source {source_env}\n  {command}")

    stdin_channel, stdout_channel, stderr_channel = conn.client.exec_command(
        actual_command, timeout=timeout
    )

    if actual_stdin is not None:
        stdin_channel.write(actual_stdin)
        stdin_channel.flush()
        stdin_channel.channel.shutdown_write()  # signal EOF so the script stops waiting

    exit_code = stdout_channel.channel.recv_exit_status()
    stdout = stdout_channel.read().decode("utf-8", errors="replace")
    stderr = stderr_channel.read().decode("utf-8", errors="replace")

    return CommandResult(stdout=stdout, stderr=stderr, exit_code=exit_code)
