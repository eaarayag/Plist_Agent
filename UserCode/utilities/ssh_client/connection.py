"""
ssh_client/connection.py
~~~~~~~~~~~~~~~~~~~~~~~~
Core SSH connection class.  All other modules receive an SSHConnection
instance — they never open sockets themselves.

Usage (context manager, recommended):

    from utilities.ssh_client import SSHConnection

    with SSHConnection() as conn:                    # uses [SSH] section
        ...

    with SSHConnection(profile="SC15") as conn:      # uses [SC15] section
        ...

Usage (manual):

    conn = SSHConnection(profile="CR")
    conn.connect()
    ...
    conn.disconnect()
"""

import configparser
import os
import warnings
from pathlib import Path

import paramiko


# Default config location: UserCode/config/ssh_config.ini
# Resolved relative to this file's location:
#   utilities/ssh_client/connection.py → utilities/ssh_client/ → utilities/ → UserCode/
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ssh_config.ini"


def _load_config(profile: str = "SSH") -> configparser.SectionProxy:
    """
    Parse ssh_config.ini and return the requested section.

    Parameters
    ----------
    profile : str
        Name of the [section] in ssh_config.ini to load (default "SSH").
        Examples: "SC11", "SC15", "CR".
    """
    cfg = configparser.ConfigParser()
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {_CONFIG_PATH}")
    cfg.read(_CONFIG_PATH, encoding="utf-8")
    if profile not in cfg:
        available = [s for s in cfg.sections()]
        raise KeyError(
            f"Profile '[{profile}]' not found in ssh_config.ini. "
            f"Available profiles: {available}"
        )
    return cfg[profile]


class SSHConnection:
    """
    Manages a single SSH session.

    Parameters
    ----------
    profile : str
        Section name in ssh_config.ini to use (default "SSH").
        Use named profiles to switch between servers:
            SSHConnection("SC11"), SSHConnection("SC15"), SSHConnection("CR")
    config_path : str | Path | None
        Override the default ssh_config.ini file location.
    """

    def __init__(
        self,
        profile: str = "SSH",
        config_path: "str | Path | None" = None,
    ):
        if config_path is not None:
            global _CONFIG_PATH
            _CONFIG_PATH = Path(config_path)

        self._profile = profile
        self._cfg = _load_config(profile)
        self.client: paramiko.SSHClient = paramiko.SSHClient()
        self._sftp: "paramiko.SFTPClient | None" = None
        self._connected = False
        self._known_hosts_path: "str | None" = None
        self._save_host_keys_after_connect: bool = False

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def connect(self) -> None:
        """Open the SSH connection using parameters from ssh_config.ini."""
        if self._connected:
            return

        self._configure_host_keys()

        hostname = self._cfg.get("hostname")
        port = self._cfg.getint("port", fallback=22)
        username = self._cfg.get("username")
        auth_method = self._cfg.get("auth_method", fallback="key").strip().lower()

        connect_kwargs: dict = dict(hostname=hostname, port=port, username=username)

        if auth_method == "password":
            password = self._cfg.get("password", fallback="")
            if not password:
                raise ValueError(
                    "auth_method is 'password' but no password is set in ssh_config.ini."
                )
            connect_kwargs["password"] = password

        elif auth_method == "key":
            key_path = self._cfg.get("key_path", fallback="").strip()
            if not key_path:
                raise ValueError(
                    "auth_method is 'key' but key_path is not set in ssh_config.ini."
                )
            key_path = os.path.expanduser(key_path)
            passphrase = self._cfg.get("key_passphrase", fallback="") or None
            connect_kwargs["key_filename"] = key_path
            if passphrase:
                connect_kwargs["passphrase"] = passphrase

        else:
            raise ValueError(
                f"Unknown auth_method '{auth_method}'. Use 'password' or 'key'."
            )

        self.client.connect(**connect_kwargs)

        # Persist new host keys discovered during this connection (TOFU).
        if self._save_host_keys_after_connect and self._known_hosts_path:
            self.client.save_host_keys(self._known_hosts_path)
            self._save_host_keys_after_connect = False

        self._connected = True

    def disconnect(self) -> None:
        """Close the SFTP channel (if open) and the SSH connection."""
        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        if self._connected:
            try:
                self.client.close()
            except Exception:
                pass
            self._connected = False

    @property
    def sftp(self) -> paramiko.SFTPClient:
        """Return the SFTP client, opening it on first access."""
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        if self._sftp is None:
            self._sftp = self.client.open_sftp()
        return self._sftp

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def shell(self) -> str:
        """Shell executable used on this server (from ssh_config.ini, default 'tcsh')."""
        return self._cfg.get("shell", fallback="tcsh").strip()

    # ------------------------------------------------------------------ #
    #  Context manager support                                             #
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "SSHConnection":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _configure_host_keys(self) -> None:
        """
        Configure host-key verification using Trust-On-First-Use (TOFU),
        the same behaviour as the standard `ssh` command:

        - known_hosts_path is set → create the file if missing, load any
          existing entries, then use AutoAddPolicy.
          * For servers already in known_hosts: paramiko verifies the key
            matches what was saved — mismatch raises an error.
          * For servers NOT yet in known_hosts: the key is accepted and
            saved automatically so the next connection verifies it.

        - known_hosts_path is blank → AutoAddPolicy with no persistence and
          a warning. Convenient for quick tests, insecure for production.
        """
        known_hosts = self._cfg.get("known_hosts_path", fallback="").strip()

        if not known_hosts:
            warnings.warn(
                "known_hosts_path is not set. Host-key verification is disabled. "
                "This is insecure — set known_hosts_path in ssh_config.ini for production use.",
                stacklevel=3,
            )
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            return

        known_hosts_file = Path(os.path.expanduser(known_hosts))
        self._known_hosts_path = str(known_hosts_file)

        # Create the file (and ~/.ssh dir) if they don't exist yet.
        if not known_hosts_file.exists():
            known_hosts_file.parent.mkdir(parents=True, exist_ok=True)
            known_hosts_file.touch()

        # Load whatever keys are already stored (may be empty on first run).
        self.client.load_host_keys(str(known_hosts_file))

        # AutoAddPolicy: new servers are accepted and added (TOFU).
        # Servers already in known_hosts are still verified by paramiko
        # against the loaded keys before this policy is ever consulted.
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Always save after connect so new keys are persisted immediately.
        self._save_host_keys_after_connect = True
