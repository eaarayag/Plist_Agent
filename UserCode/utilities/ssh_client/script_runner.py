"""
ssh_client/script_runner.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Execute scripts that already reside on the remote server.

Example
-------
    from ssh_client.connection import SSHConnection
    from ssh_client.script_runner import run_remote_script

    with SSHConnection() as conn:

        # Positional / flag arguments (flat list)
        result = run_remote_script(conn, "/home/user/process.sh",
                                   args=["--verbose"])

        # Named -flag value arguments (dict)
        result = run_remote_script(
            conn,
            "/path/to/bundle_debug_pats.py",
            interpreter="python3",
            named_args={
                "p":        "cwf",
                "module":   "MscnCdXCC",
                "tester":   "hdmt2",
                "site":     "CR",
                "destpath": "/intel/hdmxpats/cwf/dev/jdcubero/...",
            },
            args=["a0TTR_ddimb_trans.plist"],   # positional at the end
        )
        print(result)
"""

import shlex
from typing import Dict, List, Optional

from .commands import CommandResult, run_command
from .connection import SSHConnection


def run_remote_script(
    conn: SSHConnection,
    remote_script_path: str,
    args: "Optional[List[str]]" = None,
    named_args: "Optional[Dict[str, str]]" = None,
    interpreter: "Optional[str]" = None,
    source_env: "Optional[str]" = None,
    stdin_input: "Optional[str]" = None,
    auto_approve: bool = False,
    timeout: int = 60,
) -> CommandResult:
    """
    Execute a script that already exists on the remote server.

    Parameters
    ----------
    conn               : Active SSHConnection instance.
    remote_script_path : Absolute path to the script on the server.
    args               : Optional list of positional / flag arguments appended
                         after named_args, e.g. ["--verbose", "file.plist"].
                         Each token is shell-escaped automatically.
    named_args         : Optional dict of  -key value  pairs, e.g.
                             {"p": "cwf", "module": "MscnCdXCC"}
                         produces:  -p cwf -module MscnCdXCC
                         Keys with more than one character keep a single dash
                         prefix to match tools that use that convention
                         (e.g. -module, -tester).  You can also pass the dash
                         yourself: {"-p": "cwf"} works too.
                         Values are shell-escaped automatically.
    interpreter        : Interpreter to invoke, e.g. "python3", "bash", "perl",
                         or a full path like "/p/pde/tvpv/tools/anaconda3.7/bin/python".
                         When None (default), the script is executed directly
                         (relies on the shebang line or the PATH).
    source_env         : Path to an environment file to source before running
                         the script, e.g. "/p/pde/tvpv/cwf/sourceme.rc".
                         Required when the script is only findable/runnable
                         after loading a custom environment.
    stdin_input        : Text sent to the script's stdin, e.g. "y\n" to confirm
                         a single prompt, or "y\ny\n" for two prompts.
                         Use this when you know exactly what the script asks.
    auto_approve       : Shortcut — if True, sends "y\n" automatically for every
                         prompt the script may issue (equivalent to piping `yes`).
                         Ignored when stdin_input is also provided.
    timeout            : Seconds to wait for the script to finish (default 60).

    Returns
    -------
    CommandResult with .stdout, .stderr, .exit_code, and .success.

    Raises
    ------
    RuntimeError  if the connection is not open.
    ValueError    if remote_script_path is empty.

    Examples
    --------
    # bash script with flags
    run_remote_script(conn, "/home/user/deploy.sh", args=["--env", "prod"])

    # python script with -name value style arguments
    run_remote_script(
        conn,
        "/path/to/bundle_debug_pats.py",
        interpreter="python3",
        named_args={
            "p":        "cwf",
            "module":   "MscnCdXCC",
            "tester":   "hdmt2",
            "site":     "CR",
            "destpath": "/intel/hdmxpats/cwf/dev/jdcubero/ddimb_IE/tatpg_ddimb_a0TTR",
        },
        args=["a0TTR_ddimb_trans.plist"],
    )
    """
    if not remote_script_path.strip():
        raise ValueError("remote_script_path must not be empty.")

    # Build -key value tokens from named_args dict.
    named_tokens: List[str] = []
    for key, value in (named_args or {}).items():
        # Normalise: strip any leading dashes the caller may have included,
        # then always use a single dash prefix.
        clean_key = key.lstrip("-")
        named_tokens.append(f"-{clean_key}")
        named_tokens.append(shlex.quote(str(value)))

    # Positional args go after named args.
    positional_tokens = [shlex.quote(a) for a in (args or [])]

    if interpreter:
        command_parts = [interpreter, shlex.quote(remote_script_path)]
    else:
        command_parts = [shlex.quote(remote_script_path)]

    command_parts += named_tokens + positional_tokens
    command = " ".join(command_parts)

    # Embed interactive input at the shell level using pipes.
    #
    # WHY: when source_env is used, the shell (tcsh/bash) reads ALL of its
    # stdin as shell commands — so any "y\n" responses sent via paramiko
    # stdin are consumed by the shell itself, leaving the script with no
    # stdin → EOFError.
    #
    # Piping at the command level (yes | script or printf | script) gives
    # the script its own stdin regardless of how the outer shell is invoked.
    # This also works correctly when source_env is NOT set.
    if auto_approve:
        command = f"yes | {command}"
    elif stdin_input is not None:
        # printf preserves \n and avoids heredoc quoting issues.
        safe = stdin_input.replace("'", "'\\''")
        command = f"printf '{safe}' | {command}"

    return run_command(conn, command, timeout=timeout, source_env=source_env)
