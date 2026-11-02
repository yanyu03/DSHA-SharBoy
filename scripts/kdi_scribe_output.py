"""Isolated KDI-01 Scribe managed-output experiment; NOT wired to DSHA.

The caller must supply an administrator-trusted absolute root. This module
cannot authenticate that configuration or constrain standalone Scribe.
"""

import os
import stat
from pathlib import Path


class ManagedOutputError(ValueError):
    """A managed output request cannot be safely honored."""


def validate_relative_output(name):
    """Return portable path components, rejecting ambiguous/escaping syntax."""
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ManagedOutputError("nonempty text path required")
    # Deliberately disallow backslash and colon on every host: this also
    # excludes Windows rooted, drive-relative, UNC and device namespaces.
    if "\\" in name or ":" in name or name.startswith("/"):
        raise ManagedOutputError("absolute or platform-dependent path")
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ManagedOutputError("empty, dot or parent component")
    return tuple(parts)


def open_managed_output(trusted_root, relative_name):
    """Exclusively create beneath an existing trusted root, POSIX only.

    Each directory component is opened relative to the previous directory fd
    with O_NOFOLLOW; the final file is O_EXCL|O_NOFOLLOW. No parents are made.
    On Windows or platforms without these primitives, refuse rather than
    falsely promise TOCTOU-resistant containment.
    """
    parts = validate_relative_output(relative_name)
    if not isinstance(trusted_root, (str, os.PathLike)):
        raise ManagedOutputError("trusted absolute root required")
    root = Path(trusted_root)
    if not root.is_absolute() or ".." in root.parts:
        raise ManagedOutputError("trusted absolute root required")
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_EXCL")
    if os.name != "posix" or any(not hasattr(os, flag) for flag in required):
        raise ManagedOutputError("race-resistant managed output unavailable")

    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    dir_fd = None
    try:
        # Walk from / to reject symlink ancestors of the trusted root too.
        dir_fd = os.open("/", dir_flags)
        for component in (*root.parts[1:], *parts[:-1]):
            next_fd = os.open(component, dir_flags, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        file_fd = os.open(
            parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600, dir_fd=dir_fd,
        )
        try:
            return os.fdopen(file_fd, "w", encoding="utf-8")
        except BaseException:
            os.close(file_fd)
            raise
    except (OSError, ValueError) as exc:
        raise ManagedOutputError("managed output refused") from exc
    finally:
        if dir_fd is not None:
            os.close(dir_fd)


def inspect_posix_root_mode_preconditions(trusted_root, *, approved_owner_uids):
    """Collect POSIX ancestor mode evidence; NEVER authorize managed writes.

    Reject obviously mutable or unapproved-owner ancestors. This necessary
    preflight does not audit ACLs, groups, capabilities, mount topology or
    concurrent renames. A separate trusted-host registration and effective-
    rights audit are required before any managed-output authorization.
    """
    required = ('O_DIRECTORY', 'O_NOFOLLOW')
    if os.name != 'posix' or any(not hasattr(os, flag) for flag in required):
        raise ManagedOutputError('POSIX registration preflight unavailable')
    if not isinstance(trusted_root, (str, os.PathLike)):
        raise ManagedOutputError('trusted absolute root required')
    root = Path(trusted_root)
    if not root.is_absolute() or '..' in root.parts:
        raise ManagedOutputError('trusted absolute root required')
    if not isinstance(approved_owner_uids, (tuple, list, set, frozenset)) or not approved_owner_uids:
        raise ManagedOutputError('explicit approved owner IDs required')
    if any(type(uid) is not int or uid < 0 for uid in approved_owner_uids):
        raise ManagedOutputError('invalid approved owner ID')

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = None
    evidence = []
    try:
        fd = os.open('/', flags)
        for component in (None, *root.parts[1:]):
            if component is not None:
                next_fd = os.open(component, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            info = os.fstat(fd)
            if (not stat.S_ISDIR(info.st_mode)
                    or info.st_uid not in approved_owner_uids
                    or info.st_mode & 0o022):
                raise ManagedOutputError('untrusted ancestor mode or owner')
            evidence.append((info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode)))
        return tuple(evidence)
    except OSError as exc:
        raise ManagedOutputError('registration mode preflight refused') from exc
    finally:
        if fd is not None:
            os.close(fd)

def bind_host_registration_identity(host_token):
    """Bind an opaque identity check at trusted bootstrap time (isolated only).

    The trusted host must retain the returned checker and must never allow a
    model-controlled request to select its host_token or replace the checker.
    Matching identity is NOT a permission grant: effective-rights auditing,
    root-handle identity, and parent/mount stability remain unimplemented.
    Arbitrary Python executing in this interpreter is outside this boundary.
    """
    if type(host_token) is not object:
        raise ManagedOutputError('opaque host token required')

    def inspect(candidate):
        if candidate is not host_token:
            raise ManagedOutputError('caller registration is not host-bound')
        # Deliberately return no authority, path, fd, or write capability.
        return None

    return inspect
