"""Regression tests for dispatch boundaries; no real target or shell is executed."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeContracts(unittest.TestCase):
    def copies(self, filename):
        for folder in (ROOT / 'scripts', ROOT / 'plugins/dsh-permissions/scripts'):
            path = folder / filename
            if path.exists():
                yield load(path, 'regression_' + str(folder.name) + filename[:-3])

    def test_failed_version_probe_is_not_ready(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__), patch.object(m.PrerequisiteEnv, 'locate_binary', return_value=sys.executable), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=7, stdout='24.99.0', stderr='probe failed')):
                self.assertFalse(m.PrerequisiteEnv('node', min_version='24.11.0').verify()['satisfied'])

    def test_context_cannot_elevate_actual_read_only(self):
        for m in self.copies('base_tool.py'):
            tool = m.PwshTool()
            with self.subTest(module=m.__file__), patch.object(m, 'get_active_tier', return_value='read-only'), patch.object(tool, 'assert_environment', return_value=(True, None)), patch.object(tool, 'resolve_executable', return_value=sys.executable), patch.object(tool, 'assert_target_contained', return_value=(True, None)), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='', stderr='')) as run:
                result = tool.execute(['--version'], {'tier': 'danger-full-access'})
                self.assertEqual(result['exit_code'], 126)
                run.assert_not_called()

    def test_successful_version_probe_still_passes(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__), patch.object(m.PrerequisiteEnv, 'locate_binary', return_value=sys.executable), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='24.14.1', stderr='')):
                self.assertTrue(m.PrerequisiteEnv('node', min_version='24.11.0').verify()['satisfied'])

    def test_context_can_restrict_actual_permissive_tier(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__), patch.object(m, 'get_active_tier', return_value='danger-full-access'):
                self.assertFalse(m.PwshTool().assert_authorization('read-only')[0])

    def test_explicit_proxy_is_preserved(self):
        for m in self.copies('base_tool.py'):
            tool = m.ScribeTool()
            with self.subTest(module=m.__file__), patch.object(m, 'get_active_tier', return_value='auto'), patch.object(tool, 'assert_environment', return_value=(True, None)), patch.object(tool, 'resolve_executable', return_value=sys.executable), patch.object(tool, 'assert_target_contained', return_value=(True, None)), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='', stderr='')) as run:
                self.assertTrue(tool.execute(context={'proxy': 'http://127.0.0.1:9999'})['success'])
                self.assertEqual(run.call_args.kwargs['env']['HTTPS_PROXY'], 'http://127.0.0.1:9999')

    def test_unknown_tier_is_refused(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__), patch.object(m, 'get_active_tier', return_value='typo-tier'):
                self.assertFalse(m.PwshTool().assert_authorization()[0])

    def test_proxy_is_not_invented(self):
        for m in self.copies('base_tool.py'):
            tool = m.ScribeTool()
            with self.subTest(module=m.__file__), patch.dict(os.environ, {}, clear=True), patch.object(m, 'get_active_tier', return_value='auto'), patch.object(tool, 'assert_environment', return_value=(True, None)), patch.object(tool, 'resolve_executable', return_value=sys.executable), patch.object(tool, 'assert_target_contained', return_value=(True, None)), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='', stderr='')) as run:
                self.assertTrue(tool.execute()['success'])
                self.assertNotIn('ALL_PROXY', run.call_args.kwargs['env'])

    def test_env_penetration_blocks_secrets(self):
        for m in self.copies('base_tool.py'):
            tool = m.ScribeTool()
            with self.subTest(module=m.__file__), patch.dict(os.environ, {'LEAKY_API_KEY': 'secret123', 'SYSTEMROOT': 'C:/Windows'}, clear=True), patch.object(m, 'get_active_tier', return_value='auto'), patch.object(tool, 'assert_environment', return_value=(True, None)), patch.object(tool, 'resolve_executable', return_value=sys.executable), patch.object(tool, 'assert_target_contained', return_value=(True, None)), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='', stderr='')) as run:
                res = tool.execute(context={'custom_env': {'SAFE_CONFIG': 'abc'}})
                self.assertTrue(res['success'])
                called_env = run.call_args.kwargs['env']
                self.assertNotIn('LEAKY_API_KEY', called_env)
                self.assertEqual(called_env.get('SAFE_CONFIG'), 'abc')
                self.assertEqual(called_env.get('PYTHONUTF8'), '1')

    def test_envelope_bounds_and_tier_normalization(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__):
                env = m.ExecutionEnvelope.from_context({'timeout': -5, 'tier': ' DANGER-FULL-ACCESS '})
                self.assertEqual(env.timeout, 1)
                self.assertEqual(env.tier, 'danger-full-access')

                env_max = m.ExecutionEnvelope.from_context({'timeout': 999999})
                self.assertEqual(env_max.timeout, 3600)
    def test_router_failure_does_not_fall_back_to_raw_execution(self):
        for m in self.copies('router.py'):
            def broken(*args, **kwargs):
                raise RuntimeError('dispatcher unavailable')
            with self.subTest(module=m.__file__), patch.dict(sys.modules, {'index': types.SimpleNamespace(Call_Tools=broken)}), patch.object(sys, 'argv', ['router.py', 'pwsh', '--version']), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)) as run:
                self.assertEqual(m.main(), 126)
                run.assert_not_called()

    def test_err_block_contains_polite_apology_and_short_circuits(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__):
                err = m.ErrBlock(
                    error_code="ERR_PREREQUISITE_MISSING",
                    tool_id="mock_alien",
                    tool_name="Mock Alien Tool",
                    category="SysAdmin",
                    refusal_statement="Missing alien runtime.",
                    details=[{"binary": "alien_cc", "detected_version": "missing"}],
                    remediations=["Install alien_cc"],
                )
                formatted = err.format_cli()
                self.assertTrue(formatted.startswith("非常抱歉"))
                self.assertIn("ERR_PREREQUISITE_MISSING", formatted)

    def test_envfeel_standard_response_envelope(self):
        for m in self.copies('base_tool.py'):
            tool = m.ScribeTool()
            with self.subTest(module=m.__file__), patch.object(m, 'get_active_tier', return_value='auto'), patch.object(tool, 'assert_environment', return_value=(True, None)), patch.object(tool, 'resolve_executable', return_value=sys.executable), patch.object(tool, 'assert_target_contained', return_value=(True, None)), patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='ok', stderr='')):
                res = tool.execute()
                self.assertIn('envfeel', res)
                self.assertEqual(res['envfeel']['status'], 'HEALTHY')
                self.assertIn('platform', res['envfeel'])

    def test_prerequisite_live_can_invoke_flag(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__), patch.object(m.PrerequisiteEnv, 'locate_binary', return_value=sys.executable), patch.object(m.HostEnvPerceiver, 'can_invoke', return_value=(True, 'live_probe_passed')):
                res = m.PrerequisiteEnv('mock_tool').verify()
                self.assertTrue(res['can_invoke'])
                self.assertTrue(res['satisfied'])

    def test_router_feel_command(self):
        for m in self.copies('router.py'):
            with self.subTest(module=m.__file__), patch.object(sys, 'argv', ['router.py', 'feel']):
                code = m.main()
                self.assertEqual(code, 0)

    def test_normalize_environment_case_insensitivity_and_collision(self):
        for m in self.copies('dsha_env.py'):
            with self.subTest(module=m.__file__):
                norm = m.normalize_environment({'path': 'abc', 'PathExt': '.COM'})
                if os.name == 'nt':
                    self.assertEqual(norm.get('PATH'), 'abc')
                    self.assertEqual(norm.get('PATHEXT'), '.COM')
                    with self.assertRaises(ValueError):
                        m.normalize_environment({'PATH': 'one', 'path': 'two'})

    def test_machine_environment_registry_recovery_under_empty_env(self):
        for m in self.copies('dsha_env.py'):
            with self.subTest(module=m.__file__):
                stripped = m.machine_environment({})
                if os.name == 'nt':
                    self.assertIn('PROGRAMFILES', stripped)
                    self.assertTrue(Path(stripped['PROGRAMFILES']).is_dir())

    def test_forward_trace_receipt_generation_and_stages(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__):
                tool = m.TOOL_REGISTRY.get('scribe')
                # Unit-test the receipt, not the platform-specific scribe.cmd launcher.
                with (
                    patch.object(m, 'get_active_tier', return_value='auto'),
                    patch.object(tool, 'assert_environment', return_value=(True, None)),
                    patch.object(tool, 'resolve_executable', return_value=sys.executable),
                    patch.object(tool, 'assert_target_contained', return_value=(True, None)),
                    patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='ok', stderr='')) as run,
                    patch.object(m.TraceStore, 'save', return_value=None),
                ):
                    res = tool.execute(['status'], {'timeout': 10})
                    run.assert_called_once()
                self.assertIn('trace_receipt', res)
                receipt = res['trace_receipt']
                self.assertEqual(receipt['protocol'], 'dsha-1.2.0-std')
                self.assertEqual(receipt['status'], 'PASS')
                self.assertGreaterEqual(len(receipt['stages']), 6)
                stage_names = [s['stage'] for s in receipt['stages']]
                self.assertIn('ingress_validation', stage_names)
                self.assertIn('envfeel_prerequisites', stage_names)
                self.assertIn('egress_packaging', stage_names)

    def test_reverse_retrace_causal_attribution(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__):
                # 1. Success retrace
                tool = m.TOOL_REGISTRY.get('scribe')
                res_pass = tool.execute(['status'], {'timeout': 10})
                retrace_pass = m.retrace(res_pass)
                self.assertIn('逆向调用链回溯', retrace_pass)
                self.assertIn('7/7: 响应封套封装', retrace_pass)
                self.assertIn('1/7: 入口封套校验', retrace_pass)

                # 2. Refusal retrace on tier authorization
                pwsh = m.TOOL_REGISTRY.get('pwsh')
                # This is a Stage 4 unit test: do not depend on the host's pwsh probe.
                with (
                    patch.object(pwsh, 'assert_environment', return_value=(True, None)),
                    patch.object(m, 'get_active_tier', return_value='auto'),
                    patch.object(pwsh, 'resolve_executable') as resolve,
                    patch.object(m.subprocess, 'run') as run,
                    patch.object(m.TraceStore, 'save', return_value=None),
                ):
                    res_deny = pwsh.execute(context={'tier': 'read-only'})
                    resolve.assert_not_called()
                    run.assert_not_called()
                self.assertEqual(res_deny['exit_code'], 126)
                self.assertEqual(res_deny['trace_receipt']['causal_chain']['failed_stage'], 'tier_authorization')
                retrace_deny = m.retrace(res_deny)
                self.assertIn('ERR_PERMISSION_DENIED', retrace_deny)
                self.assertIn('4/7: 权限档位核验', retrace_deny)
                self.assertIn('❌ [FAIL]', retrace_deny)

    def test_trace_store_persistence_and_retrieval(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__):
                tool = m.TOOL_REGISTRY.get('scribe')
                # Exercise real receipt serialization in a disposable directory.
                with tempfile.TemporaryDirectory() as trace_dir:
                    with (
                        patch.object(m, 'get_active_tier', return_value='auto'),
                        patch.object(tool, 'assert_environment', return_value=(True, None)),
                        patch.object(tool, 'resolve_executable', return_value=sys.executable),
                        patch.object(tool, 'assert_target_contained', return_value=(True, None)),
                        patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='ok', stderr='')) as run,
                        patch.object(m.TraceStore, 'get_trace_dir', return_value=Path(trace_dir)),
                    ):
                        res = tool.execute(['status'], {'timeout': 10})
                        run.assert_called_once()
                        tid = res['trace_id']
                        self.assertTrue((Path(trace_dir) / f'{tid}.json').is_file())
                        retrieved = m.TraceStore.get(tid)
                        self.assertIsNotNone(retrieved)
                        self.assertEqual(retrieved.get('trace_id'), tid)
                        self.assertEqual(retrieved.get('status'), 'PASS')

    def test_stage5_path_fallback_blocks_builtin_shadow_and_explicit_paths(self):
        # Built-in launchers must use trusted roots; extensions retain legacy PATH fallback.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            external = str(Path(tmp) / 'external-tool')
            for m in self.copies('base_tool.py'):
                tool = m.PwshTool()
                for declared in (external, './external-tool', r'C:\tools\external-tool.exe', 'C:external-tool.exe'):
                    tool.cmd = declared
                    with self.subTest(module=m.__file__, declared=declared), patch.object(m.shutil, 'which', return_value=external) as which:
                        accepted, err = tool.assert_target_contained(external)
                        self.assertFalse(accepted)
                        self.assertEqual(err.error_code, 'ERR_TARGET_OUTSIDE_SANDBOX')
                        which.assert_not_called()
                tool.cmd = 'external-tool'
                with self.subTest(module=m.__file__, declared='builtin-PATH-shadow'), patch.object(m.shutil, 'which', return_value=external) as which:
                    accepted, err = tool.assert_target_contained(external)
                    self.assertFalse(accepted)
                    self.assertEqual(err.error_code, 'ERR_TARGET_OUTSIDE_SANDBOX')
                    which.assert_not_called()
                tool.id = 'external-extension'
                with self.subTest(module=m.__file__, declared='extension-bare-PATH'), patch.object(m.shutil, 'which', return_value=external) as which:
                    self.assertTrue(tool.assert_target_contained(external)[0])
                    which.assert_called_once_with('external-tool')
                trusted = Path(m.__file__).resolve().parent.parent / 'bin' / 'trusted-tool'
                tool.cmd = str(trusted)
                with self.subTest(module=m.__file__, declared='trusted-root'), patch.object(m.shutil, 'which', return_value=None):
                    self.assertTrue(tool.assert_target_contained(str(trusted))[0])

    def test_extension_explicit_trusted_roots_are_fail_closed(self):
        # Opt-in extension roots must not inherit PATH trust or widen built-in roots.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            trusted = Path(tmp) / 'trusted'
            untrusted = Path(tmp) / 'untrusted'
            trusted.mkdir()
            untrusted.mkdir()
            trusted_target = str(trusted / 'ext-tool')
            shadow = str(untrusted / 'ext-tool')
            for m in self.copies('base_tool.py'):
                def extension(roots=None):
                    return m.BaseTool(
                        tool_id='external-extension', name='External extension',
                        category=m.ToolCategory.SYSADMIN,
                        risk_level=m.RiskLevel.LOW, version='0.1',
                        description='Fixture', cmd='ext-tool',
                        trusted_executable_roots=roots,
                    )

                with self.subTest(module=m.__file__, case='opt-in-shadow'), patch.object(m.shutil, 'which', return_value=shadow) as which:
                    ok, err = extension([str(trusted)]).assert_target_contained(shadow)
                    self.assertFalse(ok)
                    self.assertEqual(err.error_code, 'ERR_TARGET_OUTSIDE_SANDBOX')
                    which.assert_not_called()

                with self.subTest(module=m.__file__, case='opt-in-trusted'), patch.object(m.shutil, 'which', return_value=shadow) as which:
                    self.assertTrue(extension([str(trusted)]).assert_target_contained(trusted_target)[0])
                    which.assert_not_called()

                with self.subTest(module=m.__file__, case='empty-roots'), patch.object(m.shutil, 'which', return_value=shadow) as which:
                    self.assertFalse(extension([]).assert_target_contained(shadow)[0])
                    which.assert_not_called()

                with self.subTest(module=m.__file__, case='relative-root'), patch.object(m.shutil, 'which', return_value=shadow) as which:
                    self.assertFalse(extension(['relative-root']).assert_target_contained(shadow)[0])
                    which.assert_not_called()

                with self.subTest(module=m.__file__, case='legacy-compatibility'), patch.object(m.shutil, 'which', return_value=shadow) as which:
                    self.assertTrue(extension().assert_target_contained(shadow)[0])
                    which.assert_called_once_with('ext-tool')

                with self.subTest(module=m.__file__, case='builtin-cannot-opt-in'), patch.object(m.shutil, 'which', return_value=shadow) as which:
                    builtin = m.PwshTool()
                    builtin.trusted_executable_roots = (str(untrusted),)
                    self.assertFalse(builtin.assert_target_contained(shadow)[0])
                    which.assert_not_called()

    def test_extension_trusted_root_resolution_ignores_path_shadow(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            trusted, shadow = root / 'trusted', root / 'shadow'
            trusted.mkdir()
            shadow.mkdir()
            trusted_file = trusted / 'kdi-fatfish-fixture'
            shadow_file = shadow / 'kdi-fatfish-fixture'
            trusted_file.write_text('trusted', encoding='utf-8')
            shadow_file.write_text('shadow', encoding='utf-8')

            def which_for_trusted(name, path=None):
                return str(trusted_file) if path == str(trusted.resolve()) else str(shadow_file)

            for m in self.copies('base_tool.py'):
                def extension(roots=None, cmd='kdi-fatfish-fixture'):
                    return m.BaseTool(
                        tool_id='external-extension', name='External extension',
                        category=m.ToolCategory.SYSADMIN,
                        risk_level=m.RiskLevel.LOW, version='0.1',
                        description='Fixture', cmd=cmd,
                        trusted_executable_roots=roots,
                    )

                with self.subTest(module=m.__file__, case='trusted-first'), patch.object(m.shutil, 'which', side_effect=which_for_trusted) as which:
                    self.assertEqual(extension([str(trusted)]).resolve_executable(), str(trusted_file.resolve()))
                    which.assert_called_once_with('kdi-fatfish-fixture', path=str(trusted.resolve()))

                with self.subTest(module=m.__file__, case='shadow-rejected'), patch.object(m.shutil, 'which', return_value=str(shadow_file)) as which:
                    self.assertIsNone(extension([str(trusted)]).resolve_executable())
                    which.assert_called_once_with('kdi-fatfish-fixture', path=str(trusted.resolve()))

                with self.subTest(module=m.__file__, case='empty-roots'), patch.object(m.shutil, 'which', return_value=str(shadow_file)) as which:
                    self.assertIsNone(extension([]).resolve_executable())
                    which.assert_not_called()

                with self.subTest(module=m.__file__, case='relative-root'), patch.object(m.shutil, 'which', return_value=str(shadow_file)) as which:
                    self.assertIsNone(extension(['relative-root']).resolve_executable())
                    which.assert_not_called()

                with self.subTest(module=m.__file__, case='path-like-command'), patch.object(m.shutil, 'which', return_value=str(shadow_file)) as which:
                    self.assertIsNone(extension([str(trusted)], cmd='../kdi-fatfish-fixture').resolve_executable())
                    which.assert_not_called()

                with self.subTest(module=m.__file__, case='legacy-compatibility'), patch.object(m.shutil, 'which', return_value=str(shadow_file)) as which:
                    self.assertEqual(extension().resolve_executable(), str(shadow_file))
                    which.assert_called_once_with('kdi-fatfish-fixture')

    def test_open_protocol_schema_definitions(self):
        for m in self.copies('base_tool.py'):
            with self.subTest(module=m.__file__):
                schema = m.dump_open_protocol_schema()
                self.assertIn('definitions', schema)
                self.assertIn('DSHARequest', schema['definitions'])
                self.assertIn('DSHAResponse', schema['definitions'])
                self.assertIn('TraceReceipt', schema['definitions'])
                self.assertIn('StageRecord', schema['definitions'])
                self.assertIn('ErrBlock', schema['definitions'])


if __name__ == '__main__':
    unittest.main(verbosity=2)



