# remote_connection_demo

End-to-end demonstration of the shared `ssh_client` utility. The demo mirrors
the real production workflow:

1. Create a destination directory on server **CR** (Costa Rica).
2. Upload a PList file to server **SC11** (Santa Clara Zone 11) via SFTP.
3. Execute `bundle_debug_pats.py` on **SC11** with environment sourcing,
   named arguments, and automatic interactive approval.

---

## Project structure

```
UserCode/
├── config/
│   └── ssh_config.ini          ← connection parameters (NOT committed to git)
├── src/
│   └── remote_connection_demo/
│       ├── data/
│       │   └── debug_plist.plist   ← input file uploaded to SC11
│       ├── libs/
│       │   └── app_runner.py       ← bundle execution workflow
│       └── main.py                 ← entry point
└── utilities/
    └── ssh_client/                 ← shared SSH utility (used by this demo)
```

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Python | 3.9+ |
| OpenSSH client | bundled with Windows 10/11, macOS, all Linux distros |

---

## Step 1 — Clone the repository

```bash
git clone <repo-url>
cd <repo-root>
```

---

## Step 2 — Set up `ssh_client`

Follow the Installation and Configuration steps in
[`utilities/ssh_client/README.md`](../../../utilities/ssh_client/README.md)
to install `paramiko`, generate your SSH key, authorize it on each server,
and create `UserCode/config/ssh_config.ini`.

---

## Step 3 — Run the demo

```bash
cd UserCode/src/remote_connection_demo
python main.py
```

On the **first** connection to a new server, the host key is automatically
saved to `~/.ssh/known_hosts`. All subsequent connections verify against it.

Expected output:

```
Setting up...

────────────────────────────────────────────────────────────
  BUNDLE EXECUTION
────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────
  BUNDLE EXECUTION: Create CR directory
────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────
  1. mkdir — create a remote directory for the bundle content
────────────────────────────────────────────────────────────
...
[exit_code]  0
[stdout]
...

Done.
```

---

## Troubleshooting

For SSH authentication and configuration issues, see the
[`ssh_client` Troubleshooting](../../../utilities/ssh_client/README.md#troubleshooting) section.

| Error | Cause | Fix |
|---|---|---|
| `FileNotFoundError: Local file not found` | `debug_plist.plist` missing from `data/` | Ensure the file exists at `src/remote_connection_demo/data/debug_plist.plist` |
| `Permission denied` on remote dir | NFS UID mismatch between servers | Use `chmod 777` on the destination directory (done automatically in this demo) |
