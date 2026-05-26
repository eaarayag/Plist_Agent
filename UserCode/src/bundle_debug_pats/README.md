# bundle_debug_pats

End-to-end Python tool that automates the full debug pattern bundle workflow
for CWF silicon validation. A single command replaces the manual sequence of
extracting a plist, creating a server directory, uploading files, running the
bundle script, and cleaning up.

---

## Workflow

```
  Local                         CR server              SC11 / ZN11
  ──────                        ─────────              ───────────
  STEP 1  plist_extractor  →   .plist (data/)
  STEP 2                   →   mkdir -p + chmod 777
  STEP 3                                          →    upload .plist to /tmp/
  STEP 4                                          →    source sourceme.rc
                                                       bundle_debug_pats.py
                                                       rsync → CR destpath
  STEP 5                                          →    rm /tmp/<plist>
```

---

## Usage

Run from the **repo root** (`Plist_Agent/`):

```bash
python UserCode/src/bundle_debug_pats/main.py [options]
```

### Minimal example

```bash
python UserCode/src/bundle_debug_pats/main.py \
  --plist "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdcc_debug.plist" \
  --partition ddrmc \
  --skip ddrmcnor \
  --skip repair \
  --bundle-dir ddrmc_debug
```

### With approach and content-type filters

```bash
python UserCode/src/bundle_debug_pats/main.py \
  --plist "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdccap.plist" \
  --partition cgu \
  --content-type atpg \
  --approach sSs \
  --bundle-dir cgu_atpg_sSs \
  --output-name cgu_atpg_sSs.plist
```

---

## CLI Reference

### plist_extractor options

| Argument | Default | Description |
|---|---|---|
| `--plist PATH` | required | Source `.plist` file |
| `--partition PART [...]` | required | Partition(s) to extract. Prefix-matched: `ddrmc` also matches `ddrmcs0c0`. |
| `--content-type TYPE [...]` | — | Content type filter (`atpg`, `tatpg`, `chain`, `ca1tf`, `ca2tf`, …). Repeatable. |
| `--approach APPR` | — | Approach filter (`sSs`, `sEs`, …). See [Domain Terminology](#domain-terminology). |
| `--phase PHASE` | — | Phase filter (`ph1`, `ph2`, …) |
| `--full-content` | false | Auto-expand: `atpg` → adds `ca1tf` + `atpgtop*`; `tatpg` → adds `ca2tf` + `tatpgtop*`; `chain` → adds `chaintop*` |
| `--skip PATTERN` | — | Exclude plists whose name contains this substring. Repeatable. |
| `--output-name NAME` | `debug_plist.plist` | File name saved under `data/` |

### bundle_debug_pats.py options

| Argument | Default | Description |
|---|---|---|
| `--bundle-dir DIR` | required | Subdirectory under `/intel/hdmxpats/cwf/dev/{username}/` |
| `--username USER` | `jdcubero` | Username in the CR destpath |
| `--product PROD` | `cwf` | `-p` argument to `bundle_debug_pats.py` |
| `--module MOD` | `MscnCdXCC` | `-module` argument |
| `--tester TST` | `hdmt2` | `-tester` argument |
| `--site SITE` | `CR` | `-site` argument |
| `--timeout SECS` | `120` | Max seconds to wait for the bundle script |

---

## Domain Terminology

| User says | Meaning | CLI flag |
|---|---|---|
| "IO", "IO content", "IO mode" | sSs approach | `--approach sSs` |
| "IE", "IE content", "HVM", "AP" | sEs approach | `--approach sEs` |

### Source plist selection

| Approach | Recommended source plist |
|---|---|
| sSs (IO) | `scan_uncore_class_xdcc_debug.plist` — try this first; fall back to HVM plist if zero matches |
| sEs (IE/HVM) | `scan_uncore_class_xdccap.plist` |

Both files are under:
```
I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p<N>\plb\
```
where `p<N>` is the latest patch (currently `p29`).

---

## Project Structure

```
UserCode/src/bundle_debug_pats/
├── main.py          ← Entry point; sets up sys.path and runs AppRunner
├── libs/
│   ├── __init__.py
│   └── app_runner.py  ← CLI arg parsing + 5-step orchestration
├── config/          ← Reserved for future configuration files
└── data/            ← Generated .plist files saved here temporarily
```

### Key dependencies

| Dependency | Location | Purpose |
|---|---|---|
| `plist_extractor` | `UserCode/src/plist_extractor/` | Step 1 — called as a subprocess |
| `ssh_client` | `UserCode/utilities/ssh_client/` | Steps 2–5 — SSH, SFTP, remote script execution |
| `ssh_config.ini` | `UserCode/config/ssh_config.ini` | SSH profiles `[CR]` and `[SC11]` |

---

## Prerequisites

### 1. Python 3.10+

```bash
python --version
```

### 2. paramiko

```bash
pip install paramiko
# On Intel corporate network (proxy required):
pip install --proxy http://proxy-dmz.intel.com:912 paramiko
```

### 3. SSH configuration

Create `UserCode/config/ssh_config.ini` (not committed to git):

```ini
[CR]
hostname         = crsvnc111.cr.intel.com
port             = 22
username         = <your_username>
auth_method      = key
key_path         = ~/.ssh/id_ed25519
key_passphrase   =
known_hosts_path = ~/.ssh/known_hosts
shell            = bash

[SC11]
hostname         = sccf03121306.zsc11.intel.com
port             = 22
username         = <your_username>
auth_method      = key
key_path         = ~/.ssh/id_ed25519
key_passphrase   =
known_hosts_path = ~/.ssh/known_hosts
shell            = tcsh
```

> **Key notes:**
> - `key_path` must point to your **private key** (`~/.ssh/id_ed25519`).
>   `~/.ssh/authorized_keys` is a server-side file — do not use it here.
> - SC11/ZN11 servers use **`tcsh`**. Setting `shell = bash` will cause
>   `sourceme.rc` to fail and the bundle script won't be found.
> - See `UserCode/utilities/ssh_client/README.md` for the full setup guide.

### 4. Intel VPN

Must be connected before running — internal hostnames require VPN for DNS
resolution.

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All steps succeeded |
| `1` | Step failed — check stdout/stderr output for the failing step |

> **Known non-fatal:** The SC11 tcsh session exits with code `141` due to a
> non-fatal `sourceme.rc` sub-source warning. The bundle itself reports
> `Status: Success` in stdout. This is expected behaviour.

---

## Common Recipes

### ddrmc IO (sSs) — standard debug command

```bash
python UserCode/src/bundle_debug_pats/main.py \
  --plist "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdcc_debug.plist" \
  --partition ddrmc \
  --skip ddrmcnor \
  --skip repair \
  --bundle-dir ddrmc_debug \
  --output-name ddrmc_debug.plist
```

### cgu atpg IO (sSs) — from HVM plist (cgu not in debug plist)

```bash
python UserCode/src/bundle_debug_pats/main.py \
  --plist "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdccap.plist" \
  --partition cgu \
  --content-type atpg \
  --approach sSs \
  --bundle-dir cgu_atpg_sSs \
  --output-name cgu_atpg_sSs.plist
```

### vinfrar5 atpg IO (sSs) — from debug plist

```bash
python UserCode/src/bundle_debug_pats/main.py \
  --plist "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdcc_debug.plist" \
  --partition vinfrar5 \
  --content-type atpg \
  --approach sSs \
  --bundle-dir vinfrar5_atpg_sSs \
  --output-name vinfrar5_atpg_sSs.plist
```

### vinfrar6 atpg IO (sSs) — from both debug and HVM plists

> **Note:** vinfrar partitions have atpg sSs content spread across both the debug
> plist and the HVM plist. Pass `--plist` twice to combine results.

```bash
python UserCode/src/bundle_debug_pats/main.py \
  --plist "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdcc_debug.plist" \
  --plist "I:\hdmxpats\cwf\MscnCdXCC\RevTCB0.0\p29\plb\scan_uncore_class_xdccap.plist" \
  --partition vinfrar6 \
  --content-type atpg \
  --approach sSs \
  --bundle-dir vinfrar6_atpg_sSs \
  --output-name vinfrar6_atpg_sSs.plist
```
