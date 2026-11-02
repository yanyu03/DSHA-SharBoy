"""Isolated KDI-01 managed-output tests; no production Scribe calls."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.kdi_scribe_output import ManagedOutputError, open_managed_output, validate_relative_output, inspect_posix_root_mode_preconditions


class ManagedOutputTests(unittest.TestCase):
    def test_portable_acceptance(self):
        self.assertEqual(validate_relative_output('reports/incident.md'), ('reports', 'incident.md'))
        self.assertEqual(validate_relative_output('日本語.md'), ('日本語.md',))

    def test_portable_rejections(self):
        cases = ('', '.', '..', 'a/../b', 'a//b', 'a/./b', 'a/', '/tmp/out.md',
                 r'C:\temp\out.md', 'C:out.md', r'\\server\share\out.md',
                 r'\\?\C:\out.md', r'\rooted.md', 'a\\b', 'a\x00b')
        for name in cases:
            with self.subTest(name=name), self.assertRaises(ManagedOutputError):
                validate_relative_output(name)

    def test_trusted_root_must_be_absolute(self):
        with self.assertRaises(ManagedOutputError):
            open_managed_output('relative', 'out.md')
        with self.assertRaises(ManagedOutputError):
            open_managed_output(None, 'out.md')

    @unittest.skipUnless(os.name == 'nt', 'Windows fail-closed check')
    def test_windows_managed_open_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ManagedOutputError):
                open_managed_output(Path(tmp), 'out.md')
            self.assertFalse((Path(tmp) / 'out.md').exists())

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX no-follow only')
    def test_create_and_exclusive_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'exports'
            (root / 'reports').mkdir(parents=True)
            with open_managed_output(root, 'reports/incident.md') as f:
                f.write('safe')
            self.assertEqual((root / 'reports/incident.md').read_text(), 'safe')
            with self.assertRaises(ManagedOutputError):
                open_managed_output(root, 'reports/incident.md')
            self.assertEqual((root / 'reports/incident.md').read_text(), 'safe')

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX no-follow only')
    def test_symlink_ancestor_and_leaf_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'exports'
            outside = Path(tmp) / 'outside'
            root.mkdir()
            outside.mkdir()
            (root / 'link').symlink_to(outside, target_is_directory=True)
            (root / 'file.md').symlink_to(outside / 'target.md')
            for name in ('link/escape.md', 'file.md'):
                with self.subTest(name=name), self.assertRaises(ManagedOutputError):
                    open_managed_output(root, name)
            self.assertFalse((outside / 'escape.md').exists())
            self.assertFalse((outside / 'target.md').exists())
            alias = Path(tmp) / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ManagedOutputError):
                open_managed_output(alias, 'new.md')

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX no-follow only')
    def test_missing_parent_and_directory_leaf_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'exports'
            root.mkdir()
            (root / 'existing').mkdir()
            for name in ('missing/out.md', 'existing'):
                with self.subTest(name=name), self.assertRaises(ManagedOutputError):
                    open_managed_output(root, name)
            self.assertFalse((root / 'missing').exists())


    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX no-follow only')
    def test_renamed_trusted_root_is_not_path_contained(self):
        """Reproduce root rename after open: directory fds do not pin path names.

        This is a documented unresolved boundary, NOT a containment fix.
        Only temporary test directories are affected.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'exports'
            moved = Path(tmp) / 'relocated'
            root.mkdir()
            real_open = os.open
            renamed = False

            def swap_after_root_open(path, flags, *args, **kwargs):
                nonlocal renamed
                fd = real_open(path, flags, *args, **kwargs)
                if path == root.name and kwargs.get('dir_fd') is not None and not renamed:
                    root.rename(moved)
                    renamed = True
                return fd

            with patch('scripts.kdi_scribe_output.os.open', side_effect=swap_after_root_open):
                with open_managed_output(root, 'incident.md') as stream:
                    stream.write('race')
            self.assertTrue(renamed)
            self.assertFalse(root.exists())
            self.assertEqual((moved / 'incident.md').read_text(encoding='utf-8'), 'race')


    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX no-follow only')
    def test_trusted_root_swapped_before_open_is_not_inode_pinned(self):
        """Reproduce root-name substitution BEFORE open, without symlinks.

        A writable ancestor lets an attacker substitute a real directory at
        the trusted pathname. O_NOFOLLOW cannot authenticate directory identity.
        Only disposable temporary directories are touched; NOT a mitigation.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'exports'
            original = Path(tmp) / 'original'
            replacement = Path(tmp) / 'replacement'
            root.mkdir()
            replacement.mkdir()
            expected_identity = (root.stat().st_dev, root.stat().st_ino)
            real_open = os.open
            swapped = False

            def swap_before_root_open(path, flags, *args, **kwargs):
                nonlocal swapped
                if path == root.name and kwargs.get('dir_fd') is not None and not swapped:
                    root.rename(original)
                    replacement.rename(root)
                    swapped = True
                return real_open(path, flags, *args, **kwargs)

            with patch('scripts.kdi_scribe_output.os.open', side_effect=swap_before_root_open):
                with open_managed_output(root, 'incident.md') as stream:
                    stream.write('substituted')
            self.assertTrue(swapped)
            self.assertNotEqual((root.stat().st_dev, root.stat().st_ino), expected_identity)
            self.assertFalse((original / 'incident.md').exists())
            self.assertEqual((root / 'incident.md').read_text(encoding='utf-8'), 'substituted')


    @unittest.skipUnless(
        os.name == 'posix' and all(hasattr(os, flag) for flag in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_EXCL')),
        'POSIX directory fd only',
    )
    def test_preopened_root_fd_pins_inode_but_not_pathname(self):
        """Pre-opened fd preserves inode identity, NOT original pathname.

        Even a root opened by a trusted host can be renamed by an actor with
        write access to its parent. This is a boundary test, not a mitigation.
        All filesystem effects are confined to a disposable temporary tree.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'exports'
            moved = Path(tmp) / 'moved_original'
            substitute = Path(tmp) / 'substitute'
            root.mkdir()
            substitute.mkdir()
            expected = (root.stat().st_dev, root.stat().st_ino)
            root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                opened = os.fstat(root_fd)
                self.assertEqual((opened.st_dev, opened.st_ino), expected)
                root.rename(moved)
                substitute.rename(root)
                self.assertNotEqual((root.stat().st_dev, root.stat().st_ino), expected)
                opened = os.fstat(root_fd)
                self.assertEqual((opened.st_dev, opened.st_ino), expected)
                leaf_fd = os.open(
                    'incident.md', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=root_fd,
                )
                try:
                    os.write(leaf_fd, b'pinned-inode')
                finally:
                    os.close(leaf_fd)
            finally:
                os.close(root_fd)
            self.assertEqual((moved / 'incident.md').read_bytes(), b'pinned-inode')
            self.assertFalse((root / 'incident.md').exists())


    @unittest.skipUnless(
        os.name == 'posix' and all(hasattr(os, flag) for flag in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_EXCL')),
        'POSIX directory fd only',
    )
    def test_attacker_writable_ancestor_is_not_rejected_yet(self):
        """Known unsafe baseline: a world-writable parent is accepted.

        This reproduces the missing host-registration trust gate, not a
        containment PASS. Mode bits alone cannot prove effective permissions
        (ACLs, groups, namespaces and privileged actors remain unassessed).
        """
        with tempfile.TemporaryDirectory() as tmp:
            attacker_writable = Path(tmp) / 'attacker_writable'
            attacker_writable.mkdir()
            os.chmod(attacker_writable, 0o777)
            root = attacker_writable / 'exports'
            root.mkdir()
            self.assertTrue(attacker_writable.stat().st_mode & 0o002)
            with open_managed_output(root, 'incident.md') as stream:
                stream.write('untrusted-parent')
            self.assertEqual(
                (root / 'incident.md').read_text(encoding='utf-8'),
                'untrusted-parent',
            )


    @unittest.skipUnless(
        os.name == 'posix' and all(hasattr(os, flag) for flag in ('O_DIRECTORY', 'O_NOFOLLOW')),
        'POSIX registration preflight only',
    )
    def test_registration_preflight_rejects_writable_ancestor(self):
        """An unsafe ancestor is rejected without creating any output."""
        with tempfile.TemporaryDirectory() as tmp:
            attacker = Path(tmp) / 'attacker_writable'
            attacker.mkdir()
            os.chmod(attacker, 0o777)
            root = attacker / 'exports'
            root.mkdir()
            owners = {os.stat('/').st_uid, os.geteuid(), root.stat().st_uid}
            with self.assertRaises(ManagedOutputError):
                inspect_posix_root_mode_preconditions(root, approved_owner_uids=owners)
            self.assertFalse((root / 'incident.md').exists())

    @unittest.skipUnless(
        os.name == 'posix' and all(hasattr(os, flag) for flag in ('O_DIRECTORY', 'O_NOFOLLOW')),
        'POSIX registration preflight only',
    )
    def test_registration_preflight_requires_explicit_owner_policy(self):
        for owners in (None, (), [], ['0'], {True}, {-1}):
            with self.subTest(owners=repr(owners)), self.assertRaises(ManagedOutputError):
                inspect_posix_root_mode_preconditions('/', approved_owner_uids=owners)

    @unittest.skipUnless(
        os.name == 'posix' and all(hasattr(os, flag) for flag in ('O_DIRECTORY', 'O_NOFOLLOW')),
        'POSIX registration preflight only',
    )
    def test_registration_preflight_returns_evidence_not_authority(self):
        """The mode-only check returns inode evidence, not a trust grant."""
        root_owner = os.stat('/').st_uid
        evidence = inspect_posix_root_mode_preconditions('/', approved_owner_uids={root_owner})
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0][2], root_owner)


    @unittest.skipUnless(
        os.name == 'posix' and all(hasattr(os, flag) for flag in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_EXCL')),
        'POSIX managed-open reproduction only',
    )
    def test_forged_caller_registration_pathlike_currently_accepted(self):
        """Known unsafe trust boundary: caller's PathLike is not host registration.

        A forged issuer/audit claim on a path-like root is ignored; the isolated
        open helper still creates a file. This is a vulnerability reproduction,
        NOT an authorization PASS or a production exploit demonstration.
        All effects stay inside a disposable temporary directory.
        """
        class ForgedRegistration(os.PathLike):
            def __init__(self, root):
                self.root = root
                self.issuer = 'trusted-bootstrap'
                self.effective_rights_audit = {'verdict': 'PASS'}
                self.revocation_state = 'active'

            def __fspath__(self):
                return os.fspath(self.root)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'exports'
            root.mkdir()
            forged = ForgedRegistration(root)
            with open_managed_output(forged, 'incident.md') as stream:
                stream.write('caller-controlled-root')
            self.assertEqual(
                (root / 'incident.md').read_text(encoding='utf-8'),
                'caller-controlled-root',
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
