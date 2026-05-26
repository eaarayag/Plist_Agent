# ssh_client — Shared SSH Utility

A modular Python utility that wraps [paramiko](https://www.paramiko.org/) for
connecting to Intel Unix servers. Provides three capabilities:

1. Execute built-in shell commands (`mkdir`, `grep`, etc.)
2. Upload and download files via SFTP
3. Execute scripts already on the remote server (with environment sourcing,
   named arguments, and interactive approval)

---

## Installation

```bash
pip install paramiko
```

### Intel corporate network (proxy required)

If `pip` times out, pass your proxy explicitly:

```bash
pip install --proxy http://proxy-dmz.intel.com:912 paramiko
```

To make the proxy permanent so you never need `--proxy` again:

```bash
pip config set global.proxy http://proxy-dmz.intel.com:912
```

> **Finding the Intel proxy address:** On Windows PowerShell, read it from the
> WPAD auto-config file:
> ```powershell
> $b = Invoke-WebRequest -Uri "http://wpad.intel.com/wpad.dat" -UseBasicParsing
> [System.Text.Encoding]::UTF8.GetString($b.Content) | Select-String "PROXY\s+\S+"
> ```

---

## Public API

```python
from utilities.ssh_client import (
    SSHConnection,
    CommandResult,
    run_command,
    upload_file,
    download_file,
    run_remote_script,
)
```

### `SSHConnection(profile="SSH")`

Context manager that opens an SSH connection using the named profile from
`UserCode/config/ssh_config.ini`.

```python
with SSHConnection(profile="SC11") as conn:
    result = run_command(conn, "pwd")
```

---

### `run_command(conn, command, timeout=30, stdin_input=None, source_env=None)`

Executes a shell command on the remote server.

| Parameter | Type | Description |
|---|---|---|
| `conn` | `SSHConnection` | Open connection |
| `command` | `str` | Shell command to run |
| `timeout` | `int` | Seconds to wait (default: 30) |
| `stdin_input` | `str \| None` | Text sent to stdin |
| `source_env` | `str \| None` | Path to an env file to `source` before running (uses `tcsh -s`) |

Returns a `CommandResult`.

---

### `CommandResult` fields

| Field | Type | Description |
|---|---|---|
| `.stdout` | `str` | Standard output |
| `.stderr` | `str` | Standard error |
| `.exit_code` | `int` | Exit code (`0` = success) |
| `.success` | `bool` | `True` if `exit_code == 0` |

---

### `upload_file(conn, local_path, remote_path)`

Uploads a file from the local machine to the remote server via SFTP.

```python
upload_file(conn, local_path=Path("report.csv"), remote_path="/home/user/report.csv")
```

---

### `download_file(conn, remote_path, local_path)`

Downloads a file from the remote server to the local machine via SFTP.
Parent directories on the local path are created automatically.

```python
download_file(conn, remote_path="/home/user/output.log", local_path=Path("output.log"))
```

---

### `run_remote_script(conn, remote_script_path, args=None, named_args=None, interpreter=None, source_env=None, stdin_input=None, auto_approve=False, timeout=30)`

Executes a script that already exists on the remote server.

| Parameter | Type | Description |
|---|---|---|
| `remote_script_path` | `str` | Absolute or relative path to the script on the server |
| `args` | `list[str] \| None` | Positional arguments appended after the script path |
| `named_args` | `dict \| None` | `-key value` pairs (single-dash, shell-quoted) |
| `interpreter` | `str \| None` | Interpreter prefix (e.g. `"python3"`). If `None`, the script is called directly |
| `source_env` | `str \| None` | Path to an env file to `source` before running |
| `stdin_input` | `str \| None` | Text piped into the script's stdin |
| `auto_approve` | `bool` | Prepends `yes \|` to auto-answer interactive prompts |
| `timeout` | `int` | Seconds to wait (default: 30) |

```python
result = run_remote_script(
    conn,
    remote_script_path="bundle_debug_pats.py",
    source_env="/p/pde/tvpv/cwf/sourceme.rc",
    named_args={"p": "cwf", "module": "MscnCdXCC", "tester": "hdmt2"},
    args=["/nfs/site/disks/.../input.plist"],
    auto_approve=True,
    timeout=120,
)
print(result.stdout)
```

---

## Configuration

Connection profiles are read from `UserCode/config/ssh_config.ini`
(not committed to git — must be created manually on each machine).

### Step 1 — Generate an SSH key pair

Skip this step if `~/.ssh/id_ed25519` already exists.

```bash
# Linux / macOS / Windows PowerShell
ssh-keygen -t ed25519 -C "your_comment" -f ~/.ssh/id_ed25519
```

Press **Enter** twice for no passphrase, or enter one for extra security.

| File | Purpose |
|---|---|
| `~/.ssh/id_ed25519` | **Private key** — never share this |
| `~/.ssh/id_ed25519.pub` | **Public key** — copied to each server |

---

### Step 2 — Authorize the key on each server

This is a **one-time step per server**. Repeat for every server profile you
intend to use (SC11, SC15, CR).

#### Option A — Automated (recommended, Linux / macOS)

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub jdcubero@sccf03121306.zsc11.intel.com
ssh-copy-id -i ~/.ssh/id_ed25519.pub jdcubero@sccc16170110.zsc15.intel.com
ssh-copy-id -i ~/.ssh/id_ed25519.pub jdcubero@crsvnc111.cr.intel.com
```

#### Option B — Windows PowerShell

```powershell
# Replace <user> and <host> for each server
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh <user>@<host> `
  "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

#### Option C — Manual

1. Print your public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
2. Log into the server with your password and append that line:
   ```bash
   mkdir -p ~/.ssh && chmod 700 ~/.ssh
   echo "ssh-ed25519 AAAA...your-key... comment" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

---

### Step 3 — Create `UserCode/config/ssh_config.ini`

This file is **not committed to git**. Create it manually on each machine.

Copy the template below and fill in your values:

```ini
# ─────────────────────────────────────────────────────────────
# SSH Connection Configuration
# ─────────────────────────────────────────────────────────────

# ── Default profile (backwards compatibility) ─────────────────
[SSH]
hostname         = sccf03121306.zsc11.intel.com
port             = 22
username         = <your_username>
auth_method      = key
password         =
key_path         = ~/.ssh/id_ed25519
key_passphrase   =
known_hosts_path = ~/.ssh/known_hosts
shell            = tcsh

# ── Santa Clara Zone 11 ───────────────────────────────────────
[SC11]
hostname         = sccf03121306.zsc11.intel.com
port             = 22
username         = <your_username>
auth_method      = key
password         =
key_path         = ~/.ssh/id_ed25519
key_passphrase   =
known_hosts_path = ~/.ssh/known_hosts
shell            = tcsh

# ── Santa Clara Zone 15 ───────────────────────────────────────
[SC15]
hostname         = sccc16170110.zsc15.intel.com
port             = 22
username         = <your_username>
auth_method      = key
password         =
key_path         = ~/.ssh/id_ed25519
key_passphrase   =
known_hosts_path = ~/.ssh/known_hosts
shell            = tcsh

# ── Costa Rica ────────────────────────────────────────────────
[CR]
hostname         = crsvnc111.cr.intel.com
port             = 22
username         = <your_username>
auth_method      = key
password         =
key_path         = ~/.ssh/id_ed25519
key_passphrase   =
known_hosts_path = ~/.ssh/known_hosts
shell            = tcsh
```

> **How to find each value on the Linux server:**
>
> | Key | Command |
> |---|---|
> | `hostname` | `hostname -I` or `cat /etc/hostname` |
> | `port` | `grep Port /etc/ssh/sshd_config` (default: `22`) |
> | `username` | `whoami` |

---

## Notes

- **tcsh**: All Intel Unix servers use `/bin/tcsh`. When `source_env` is set,
  the utility invokes `tcsh -s` and feeds the source + command via stdin — this
  avoids quoting and re-expansion issues that occur with `bash -c "source ..."`.
- **TOFU host verification**: On first connect to a new server the host key is
  automatically accepted and saved to `~/.ssh/known_hosts`. Subsequent
  connections verify against it.
- **NFS UID mismatch**: If a script running on SC11 writes to a CR NFS mount,
  use `chmod 777` on the destination directory beforehand — the UID seen by
  the SC11 process may not match the directory owner on CR.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Connection timed out` on `pip install` | Corporate proxy not configured | See **Installation** |
| `FileNotFoundError: ~/.ssh/id_ed25519` | Key not generated yet | See **Configuration → Step 1** |
| `FileNotFoundError: ~/.ssh/authorized_keys` | Wrong `key_path` — `authorized_keys` is a **server-side** file listing authorized public keys; it is not the private key. Set `key_path = ~/.ssh/id_ed25519` (the private key). | See **Configuration → Step 1** |
| `AuthenticationException` | Key not authorized on server | See **Configuration → Step 2** |
| `FileNotFoundError: ssh_config.ini` | Config file not created | See **Configuration → Step 3** |
| `NoValidConnectionsError` | Wrong hostname or port | Verify `hostname` / `port` in `ssh_config.ini` |
| `source: Command not found` | Shell is `bash` but server uses `tcsh` | Ensure `shell = tcsh` in `ssh_config.ini` |
