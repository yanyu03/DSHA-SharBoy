#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSHA BaseTool & Prerequisite Environment Assertion Architecture.

Design Principles:
  1. No Bundled Runtimes: DSHA does NOT bundle heavy external runtimes into the repository.
     External tools rely strictly on host-installed runtimes.
  2. Strict Prerequisite Assertion: Required runtimes must be declared. If missing or
     version unsatisfied, execution is STRICTLY REFUSED with a structured ErrBlock.
  3. Strict Anti-Privilege Escalation: Tools declare their RiskLevel (read-only, low,
     medium, admin) and cannot bypass active DSH permission tiers (e.g. read-only tier
     forbids medium/admin modifying operations).
  4. Class-Based Extensibility & Categorized Retrieval: Tools are organized by Category
     (ReverseEngineering, WebEdge, Archivist, SysAdmin, PolicyRadar) and extended via
     BaseTool inheritance for seamless, type-safe class extensions.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

# Ensure UTF-8 output across Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class ToolCategory(str, Enum):
    REVERSE_ENGINEERING = "ReverseEngineering"
    WEB_EDGE = "WebEdge"
    ARCHIVIST = "Archivist"
    SYSADMIN = "SysAdmin"
    POLICY_RADAR = "PolicyRadar"


class RiskLevel(str, Enum):
    READ_ONLY = "read-only"
    LOW = "low"
    MEDIUM = "medium"
    ADMIN = "admin"


def parse_semver(v_str):
    if not v_str:
        return (0, 0, 0)
    m = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(v_str))
    if m:
        return tuple(int(x or 0) for x in m.groups())
    return (0, 0, 0)


def get_active_tier():
    """Discover active DSH permission tier from tier.json."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent if script_dir.name in ("scripts", "bin") else script_dir
    user_home = Path(os.environ.get("USERPROFILE") or ".")

    candidates = [
        repo_root / "tier.json",
        repo_root / "plugins" / "dsh-permissions" / "tier.json",
        user_home / ".gemini" / "config" / "plugins" / "dsh-permissions" / "tier.json",
        user_home / ".gemini" / "config" / "tier.json",
    ]
    for c in candidates:
        if c.is_file():
            try:
                with open(c, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tier = data.get("tier")
                    if tier:
                        return str(tier).lower()
            except Exception:
                pass
    return "auto"


class HostEnvPerceiver:
    """
    Dynamic Host Environment Perception & Penetration Engine.
    Discovers installed runtimes (Python, Node, Wrangler, Pwsh, Bash, Git)
    dynamically from host environment variables, system directories, and standard package managers.
    Eliminates hardcoded drive letters and usernames to ensure portable execution across migrations.
    """

    @staticmethod
    def get_system_roots():
        """Resolve system roots dynamically without hardcoded drive letters, even in stripped environments."""
        try:
            raw_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
            if not raw_home:
                raw_home = str(Path.home())
        except Exception:
            raw_home = "."
        user_home = Path(raw_home or ".")

        try:
            sys_drive = os.environ.get("SystemDrive") or (Path(sys.executable).drive if hasattr(Path(sys.executable), "drive") and Path(sys.executable).drive else "C:")
        except Exception:
            sys_drive = "C:"

        sys_root = os.environ.get("SystemRoot") or str(Path(sys_drive) / "Windows")
        prog_files = os.environ.get("ProgramFiles") or str(Path(sys_drive) / "Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)") or str(Path(sys_drive) / "Program Files (x86)")
        local_data = os.environ.get("LOCALAPPDATA") or str(user_home / "AppData" / "Local")
        roam_data = os.environ.get("APPDATA") or str(user_home / "AppData" / "Roaming")
        prog_data = os.environ.get("ProgramData") or str(Path(sys_drive) / "ProgramData")

        return {
            "sys_drive": Path(sys_drive),
            "sys_root": Path(sys_root),
            "user_home": Path(user_home),
            "prog_files": Path(prog_files),
            "prog_files_x86": Path(prog_files_x86),
            "local_data": Path(local_data),
            "roam_data": Path(roam_data),
            "prog_data": Path(prog_data),
        }

    @classmethod
    def get_candidate_locations(cls, binary_name):
        """Generate dynamic probe paths for a given runtime without hardcoding."""
        roots = cls.get_system_roots()
        candidates = []

        # Package manager roots (Scoop, Chocolatey, NVM, FNM, Pyenv)
        scoop_shims = roots["user_home"] / "scoop" / "shims"
        choco_bin = roots["prog_data"] / "chocolatey" / "bin"
        pyenv_shims = roots["user_home"] / ".pyenv" / "pyenv-win" / "shims"

        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent if script_dir.name in ("scripts", "bin") else script_dir

        b = binary_name.lower()
        if b in ("python", "python3", "py"):
            candidates.append(Path(sys.executable))
            # Scan LocalAppData Python installations dynamically (Python310, Python311, Python312, etc.)
            py_local = roots["local_data"] / "Programs" / "Python"
            if py_local.is_dir():
                try:
                    for d in sorted(py_local.iterdir(), reverse=True):
                        if d.is_dir() and d.name.lower().startswith("python"):
                            candidates.append(d / "python.exe")
                except Exception:
                    pass
            # Scan ProgramFiles Python installations
            for pf in (roots["prog_files"], roots["prog_files_x86"]):
                if pf.is_dir():
                    try:
                        for d in sorted(pf.iterdir(), reverse=True):
                            if d.is_dir() and d.name.lower().startswith("python"):
                                candidates.append(d / "python.exe")
                    except Exception:
                        pass
            # Python launcher and package manager shims
            candidates.append(roots["sys_root"] / "py.exe")
            candidates.append(roots["local_data"] / "Programs" / "Python" / "Launcher" / "py.exe")
            candidates.append(pyenv_shims / "python.exe")
            candidates.append(scoop_shims / "python.exe")

        elif b in ("node", "nodejs"):
            candidates.append(roots["prog_files"] / "nodejs" / "node.exe")
            candidates.append(roots["prog_files_x86"] / "nodejs" / "node.exe")
            candidates.append(roots["local_data"] / "Programs" / "nodejs" / "node.exe")
            candidates.append(roots["roam_data"] / "npm" / "node.exe")
            candidates.append(scoop_shims / "node.exe")

        elif b == "wrangler":
            candidates.append(roots["roam_data"] / "npm" / "wrangler.cmd")
            candidates.append(roots["local_data"] / "Programs" / "nodejs" / "wrangler.cmd")
            candidates.append(roots["roam_data"] / "npm" / "wrangler")
            candidates.append(scoop_shims / "wrangler.cmd")

        elif b in ("pwsh", "powershell7"):
            candidates.append(roots["user_home"] / ".gemini" / "config" / "pwsh" / "pwsh.exe")
            candidates.append(repo_root / "bin" / "pwsh" / "pwsh.exe")
            for pf in (roots["prog_files"], roots["prog_files_x86"]):
                pwsh_dir = pf / "PowerShell"
                if pwsh_dir.is_dir():
                    try:
                        for v in sorted(pwsh_dir.iterdir(), reverse=True):
                            if (v / "pwsh.exe").is_file():
                                candidates.append(v / "pwsh.exe")
                    except Exception:
                        pass
            candidates.append(scoop_shims / "pwsh.exe")
            candidates.append(choco_bin / "pwsh.exe")

        elif b in ("bash", "sh"):
            candidates.append(roots["prog_files"] / "Git" / "bin" / "bash.exe")
            candidates.append(roots["prog_files"] / "Git" / "usr" / "bin" / "bash.exe")
            candidates.append(roots["prog_files"] / "Git" / "cmd" / "bash.exe")
            candidates.append(roots["prog_files_x86"] / "Git" / "bin" / "bash.exe")
            candidates.append(roots["local_data"] / "Programs" / "Git" / "bin" / "bash.exe")
            candidates.append(scoop_shims / "bash.exe")

        elif b == "git":
            candidates.append(roots["prog_files"] / "Git" / "cmd" / "git.exe")
            candidates.append(roots["prog_files"] / "Git" / "bin" / "git.exe")
            candidates.append(roots["prog_files_x86"] / "Git" / "cmd" / "git.exe")
            candidates.append(roots["local_data"] / "Programs" / "Git" / "cmd" / "git.exe")
            candidates.append(scoop_shims / "git.exe")

        return candidates

    @classmethod
    def locate(cls, binary_name, custom_paths=None):
        """Locate binary, filtering out 0-byte WindowsApps execution alias stubs."""
        if custom_paths:
            for p in custom_paths:
                po = Path(os.path.expandvars(str(p)))
                if po.is_file() and cls._is_valid_executable(po):
                    return str(po)

        # 0. Check via unified dsha_env with explicit/DSHA_* precedence if available
        try:
            try:
                import dsha_env
            except ImportError:
                import scripts.dsha_env as dsha_env
            found = dsha_env.find_binary(binary_name)
            if found and cls._is_valid_executable(Path(found)):
                return found
        except Exception:
            pass

        # 1. Search PATH (filtering out 0-byte WindowsApps stubs)
        which_p = shutil.which(binary_name)
        if which_p and cls._is_valid_executable(Path(which_p)):
            return which_p

        # 2. Search dynamic candidate locations
        for cand in cls.get_candidate_locations(binary_name):
            if cand.is_file() and cls._is_valid_executable(cand):
                return str(cand)

        return None

    @staticmethod
    def _is_valid_executable(path_obj):
        """Reject 0-byte WindowsApps execution alias stubs."""
        p_str = str(path_obj).lower()
        if "windowsapps" in p_str:
            try:
                if path_obj.stat().st_size == 0:
                    return False
            except Exception:
                return False
        return True

    @staticmethod
    def can_invoke(binary_path, tool_name=None, timeout=1.5):
        """
        Phase 3: Live Smoke Probe (实测拉起验证).
        Executes an isolated, minimal probe to verify the binary actually runs
        without crashing, segfaulting, or missing dynamic links (.so/.dll).
        """
        if not binary_path or not Path(binary_path).is_file():
            return False, "binary not found on disk"

        name = (tool_name or Path(binary_path).stem).lower()
        if "python" in name:
            probe_cmd = [str(binary_path), "-c", "print('DSHA_SMOKE_OK')"]
        elif "node" in name:
            probe_cmd = [str(binary_path), "-e", "console.log('DSHA_SMOKE_OK')"]
        elif "pwsh" in name or "powershell" in name:
            probe_cmd = [str(binary_path), "-NoProfile", "-Command", "Write-Output DSHA_SMOKE_OK"]
        elif "bash" in name or "sh" in name:
            probe_cmd = [str(binary_path), "-c", "echo DSHA_SMOKE_OK"]
        else:
            probe_cmd = [str(binary_path), "--version"]

        try:
            r = subprocess.run(
                probe_cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if r.returncode == 0:
                return True, "live_probe_passed"
            return False, f"probe exited with status {r.returncode}"
        except subprocess.TimeoutExpired:
            return False, "probe_timed_out"
        except Exception as e:
            return False, f"probe_exception: {e}"

    @classmethod
    def get_penetrated_path(cls):
        """Build penetrated PATH string by injecting discovered runtime directories."""
        current_path = os.environ.get("PATH", "")
        existing_dirs = [os.path.normcase(os.path.abspath(d)) for d in current_path.split(os.pathsep) if d]

        injected_dirs = []
        for b in ("python", "node", "wrangler", "pwsh", "git", "bash"):
            loc = cls.locate(b)
            if loc:
                parent_dir = os.path.dirname(loc)
                norm_parent = os.path.normcase(os.path.abspath(parent_dir))
                if norm_parent not in existing_dirs and norm_parent not in [os.path.normcase(d) for d in injected_dirs]:
                    injected_dirs.append(parent_dir)

        if injected_dirs:
            return os.pathsep.join(injected_dirs + [current_path])
        return current_path

    @staticmethod
    def get_topology():
        """Retrieve host OS and architecture telemetry."""
        import platform
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "os_name": os.name,
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
        }

    @classmethod
    def get_topology_string(cls):
        """Human-readable topology summary string."""
        topo = cls.get_topology()
        return f"{topo['system']} {topo['release']} {topo['machine']} ({topo['os_name']})"

    @classmethod
    def probe_all(cls):
        """Returns diagnostic map of host runtimes with locations, status and live invocation."""
        runtimes = ["python", "node", "wrangler", "pwsh", "bash", "git"]
        status = {}
        for r in runtimes:
            loc = cls.locate(r)
            can_inv = False
            inv_msg = "not_located"
            lat_ms = 0
            if loc:
                t0 = time.time()
                can_inv, inv_msg = cls.can_invoke(loc, r, timeout=1.5)
                lat_ms = int((time.time() - t0) * 1000)
            status[r] = {
                "located": loc is not None,
                "path": loc,
                "can_invoke": can_inv,
                "invoke_message": inv_msg,
                "latency_ms": lat_ms,
            }
        return status

    @classmethod
    def render_radar(cls, tool_id=None, as_json=False):
        """Renders comprehensive Host Perception Radar HUD or returns JSON payload."""
        topo = cls.get_topology()
        probe_map = cls.probe_all()
        tier = get_active_tier()

        registry = globals().get("TOOL_REGISTRY")
        tools_telemetry = {}
        if registry:
            target_tools = [registry.get(tool_id)] if tool_id else list(registry.all().values())
            for t in target_tools:
                if not t:
                    continue
                ok_env, err_env = t.assert_environment()
                ok_auth, err_auth = t.assert_authorization()
                exec_p = t.resolve_executable()
                tools_telemetry[t.id] = {
                    "name": t.name,
                    "category": t.category.value,
                    "risk_level": t.risk_level.value,
                    "executable": exec_p,
                    "env_ready": ok_env,
                    "auth_ready": ok_auth,
                    "overall_ready": bool(exec_p and ok_env and ok_auth),
                    "prerequisites": [
                        {
                            "binary": pr.binary,
                            "min_version": pr.min_version,
                            "status": pr.verify(),
                        }
                        for pr in t.prerequisites
                    ],
                }

        payload = {
            "dsha_protocol": "v1.1.0-std",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "topology": topo,
            "active_tier": tier,
            "core_runtimes": probe_map,
            "tools": tools_telemetry,
        }

        if as_json:
            return json.dumps(payload, ensure_ascii=False, indent=2)

        lines = [
            "========================================================================",
            "🌐 DSHA EnvFeel 宿主自感知雷达 (Host Perception Radar · v1.1.0-std)",
            "========================================================================",
            f"  • 宿主拓扑架构: {cls.get_topology_string()}",
            f"  • 宿主解释器:   Python {topo['python_version']} ({topo['python_executable']})",
            f"  • 当前权限档位: {tier}",
            "",
            "📡 核心工具链寻径与探针实时拉起感知 (Core Runtimes Telemetry):",
        ]

        try:
            from dsha_env import redact
        except Exception:
            try:
                from scripts.dsha_env import redact
            except Exception:
                redact = lambda s: s

        for r_name, r_info in probe_map.items():
            loc = r_info["path"]
            if loc:
                disp_loc = redact(loc)
                if r_info["can_invoke"]:
                    status_badge = "🟢 [可用]"
                    probe_detail = f"实测拉起正常 (耗时: {r_info.get('latency_ms', 0)}ms)"
                else:
                    status_badge = "🔴 [不可拉起]"
                    probe_detail = f"探针异常: {r_info['invoke_message']}"
            else:
                status_badge = "⚪ [未发现]"
                disp_loc = "未寻获可执行文件"
                probe_detail = "未配置/未安装"

            lines.append(f"  {status_badge} {r_name.ljust(10)}: {disp_loc}")
            lines.append(f"     └─ 探针状态: {probe_detail}")

        lines.append("")
        lines.append("🛠️ DSHA 标准工具链感知与就绪态势 (DSHA Toolchain Readiness):")
        for tid, tmeta in tools_telemetry.items():
            if tmeta["overall_ready"]:
                badge = "🟢 [就绪]"
            elif not tmeta["env_ready"]:
                badge = "🟡 [缺少环境]"
            elif not tmeta["auth_ready"]:
                badge = "🔒 [越权阻断]"
            else:
                badge = "🔴 [未就绪]"

            prereq_names = ", ".join([p["binary"] for p in tmeta["prerequisites"]]) or "无需外部运行时"
            lines.append(f"  {badge} {tid.ljust(8)}: [{tmeta['category']}] {tmeta['name']} (依赖: {prereq_names})")

        lines.append("========================================================================")
        return "\n".join(lines)



class ExecutionEnvelope:
    """
    Unidirectional Execution Parameter Envelope.
    Sanitizes caller parameters and builds a strictly whitelisted minimal environment,
    preventing session secret leakage and unintended parent context inheritance.
    """
    ALLOWED_CONTEXT_KEYS = {"tier", "timeout", "cwd", "proxy", "capture", "custom_env", "trace_id", "caller", "trace"}
    ALLOWED_TIERS = {"read-only", "workspace-write", "danger-full-access", "auto"}
    WHITELIST_ENV_VARS = {
        "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT",
        "TEMP", "TMP", "USERPROFILE", "USERNAME", "LOCALAPPDATA", "APPDATA",
        "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "ALLUSERSPROFILE",
        "HOMEDRIVE", "HOMEPATH", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
        "LANG", "LC_ALL",
    }

    def __init__(self, tier=None, timeout=180, cwd=None, proxy=None, capture=True, custom_env=None, trace_id=None, caller=None):
        self.tier = str(tier).lower().strip() if tier else None
        try:
            self.timeout = max(1, min(int(timeout), 3600))
        except (ValueError, TypeError):
            self.timeout = 180
        self.cwd = str(Path(cwd).resolve()) if cwd and Path(cwd).is_dir() else str(Path.cwd())
        self.proxy = proxy.strip() if proxy and isinstance(proxy, str) else None
        self.capture = bool(capture)
        self.custom_env = custom_env if isinstance(custom_env, dict) else {}
        self.trace_id = str(trace_id).strip() if trace_id else None
        self.caller = str(caller).strip() if caller else "ai-assistant"

    @classmethod
    def from_context(cls, context=None):
        if not context:
            return cls()
        return cls(
            tier=context.get("tier"),
            timeout=context.get("timeout", 180),
            cwd=context.get("cwd"),
            proxy=context.get("proxy"),
            capture=context.get("capture", True),
            custom_env=context.get("custom_env"),
            trace_id=context.get("trace_id"),
            caller=context.get("caller"),
        )

    def build_subprocess_env(self):
        """Construct sanitized minimal environment via unidirectional whitelisting and env penetration."""
        clean_env = {}
        for var_name, var_val in os.environ.items():
            if var_name.upper() in self.WHITELIST_ENV_VARS:
                clean_env[var_name] = var_val

        # Inject penetrated PATH ensuring host runtimes are reachable
        clean_env["PATH"] = HostEnvPerceiver.get_penetrated_path()

        # Enforce UTF-8 consistency
        clean_env["PYTHONUTF8"] = "1"
        clean_env["PYTHONIOENCODING"] = "utf-8"

        # Apply unidirectional proxy if configured
        if self.proxy:
            clean_env["ALL_PROXY"] = self.proxy
            clean_env["HTTPS_PROXY"] = self.proxy
            clean_env["HTTP_PROXY"] = self.proxy

        # Apply caller's explicitly whitelisted custom environment variables
        for k, v in self.custom_env.items():
            clean_env[str(k)] = str(v)

        return clean_env


class PrerequisiteEnv:
    """Declares a host runtime dependency required by a tool."""

    def __init__(self, binary, min_version=None, version_flag="--version", version_pattern=None, remediation=None, custom_paths=None):
        self.binary = binary
        self.min_version = min_version
        self.version_flag = version_flag
        self.version_pattern = version_pattern or r"(\d+\.\d+(?:\.\d+)?)"
        self.remediation = remediation or f"Please install '{binary}' and ensure it is available in PATH."
        self.custom_paths = custom_paths or []

    def locate_binary(self):
        return HostEnvPerceiver.locate(self.binary, self.custom_paths)

    def verify(self):
        loc = self.locate_binary()
        if not loc:
            return {
                "satisfied": False,
                "binary": self.binary,
                "located_path": None,
                "detected_version": None,
                "can_invoke": False,
                "required_version": f">={self.min_version}" if self.min_version else "any",
                "message": f"Prerequisite binary '{self.binary}' not found on system.",
                "remediation": self.remediation,
            }

        if not self.min_version:
            can_inv, inv_msg = HostEnvPerceiver.can_invoke(loc, self.binary)
            if not can_inv:
                return {
                    "satisfied": False,
                    "binary": self.binary,
                    "located_path": loc,
                    "detected_version": "corrupted",
                    "can_invoke": False,
                    "required_version": "any",
                    "message": f"Prerequisite binary '{self.binary}' failed live invocation probe: {inv_msg}",
                    "remediation": self.remediation,
                }
            return {
                "satisfied": True,
                "binary": self.binary,
                "located_path": loc,
                "detected_version": "available",
                "can_invoke": True,
                "required_version": "any",
                "message": "Binary located and verified via live probe.",
                "remediation": None,
            }

        # Check version
        try:
            r = subprocess.run(
                [loc, self.version_flag],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            out = r.stdout + " " + r.stderr
            if r.returncode != 0:
                raise RuntimeError(f"version probe exited with status {r.returncode}")
            m = re.search(self.version_pattern, out)
            detected_ver_str = m.group(1) if m else "unknown"

            detected_ver = parse_semver(detected_ver_str)
            required_ver = parse_semver(self.min_version)

            if detected_ver >= required_ver:
                return {
                    "satisfied": True,
                    "binary": self.binary,
                    "located_path": loc,
                    "detected_version": detected_ver_str,
                    "can_invoke": True,
                    "required_version": f">={self.min_version}",
                    "message": "Version requirement satisfied.",
                    "remediation": None,
                }
            else:
                return {
                    "satisfied": False,
                    "binary": self.binary,
                    "located_path": loc,
                    "detected_version": detected_ver_str,
                    "can_invoke": True,
                    "required_version": f">={self.min_version}",
                    "message": f"Version mismatch: found {detected_ver_str}, requires >={self.min_version}.",
                    "remediation": self.remediation,
                }
        except Exception as e:
            return {
                "satisfied": False,
                "binary": self.binary,
                "located_path": loc,
                "detected_version": "probe_error",
                "can_invoke": False,
                "required_version": f">={self.min_version}",
                "message": f"Failed probing binary version: {e}",
                "remediation": self.remediation,
            }



class ErrBlock:
    """Structured refusal message block when execution is rejected."""

    def __init__(self, error_code, tool_id, tool_name, category, refusal_statement, details, remediations):
        self.error_code = error_code
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.category = category
        self.refusal_statement = refusal_statement
        self.details = details
        self.remediations = remediations

    def to_dict(self):
        return {
            "status": "REFUSED",
            "error_code": self.error_code,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "category": str(self.category),
            "refusal_statement": self.refusal_statement,
            "details": self.details,
            "remediations": self.remediations,
        }

    def format_cli(self):
        lines = [
            "非常抱歉，DSHA 在当前运行环境中探测到必需工具链无法拉起执行，下游调用链条已即刻安全阻断。",
            f"❌ [DSHA 拒绝执行 · {self.error_code}]",
            f"  受限工具: [{self.category}] {self.tool_name} (id: {self.tool_id})",
            f"  阻断原因: {self.refusal_statement}",
        ]
        if self.details:
            lines.append("  详细判据:")
            for d in self.details:
                if "binary" in d:
                    req = d.get("required_version", "any")
                    cur = d.get("detected_version") or "missing"
                    lines.append(f"    - {d.get('binary')}: 要求 {req} (实测: {cur})")
                elif "active_tier" in d:
                    lines.append(f"    - 当前权限档位: {d.get('active_tier')}, 工具风险级别: {d.get('tool_risk_level')}")
        if self.remediations:
            lines.append("  环境修复指引:")
            for r in self.remediations:
                lines.append(f"    💡 {r}")
        return "\n".join(lines)


class TraceStage(str, Enum):
    INGRESS_VALIDATION = "ingress_validation"
    INTENT_ROUTING = "intent_routing"
    ENVFEEL_PREREQUISITES = "envfeel_prerequisites"
    TIER_AUTHORIZATION = "tier_authorization"
    CATALOG_CONTAINMENT = "catalog_containment"
    SANDBOX_EXECUTION = "sandbox_execution"
    EGRESS_PACKAGING = "egress_packaging"


class StageRecord:
    """Telemetry record for a single stage in the execution lifecycle."""

    def __init__(self, stage, status, latency_ms=0, message="", evidence=None):
        self.stage = stage.value if isinstance(stage, TraceStage) else str(stage)
        self.status = str(status).upper()  # PASS, FAIL, SKIP
        self.latency_ms = int(latency_ms)
        self.message = str(message)
        self.evidence = evidence if isinstance(evidence, dict) else {}

    def to_dict(self):
        return {
            "stage": self.stage,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "evidence": self.evidence,
        }


class TraceReceipt:
    """
    Standardized Cryptographic/Deterministic Execution Receipt.
    Provides complete bidirectional traceability across all 7 lifecycle stages.
    """

    def __init__(self, trace_id=None, caller="ai-assistant", tool_id="", tool_name="", category="", args=None, context=None):
        self.trace_id = trace_id or f"tr_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.caller = caller or "ai-assistant"
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.category = category
        self.args = list(args) if args else []
        self.context = context if isinstance(context, dict) else {}
        self.stages = []
        self.status = "PENDING"
        self.exit_code = 0
        self.duration_ms = 0
        self.causal_chain = None
        self.reproducer = {}
        self.rollback = {}
        self.host_fingerprint = HostEnvPerceiver.get_topology()

    def record_stage(self, stage, status, latency_ms=0, message="", evidence=None):
        rec = StageRecord(stage, status, latency_ms, message, evidence)
        self.stages.append(rec)
        return rec

    def finalize(self, status, exit_code, duration_ms, causal_chain=None, reproducer=None, rollback=None):
        self.status = str(status).upper()
        self.exit_code = int(exit_code)
        self.duration_ms = int(duration_ms)
        self.causal_chain = causal_chain
        self.reproducer = reproducer or self._default_reproducer()
        self.rollback = rollback or self._default_rollback()

    def _default_reproducer(self):
        cmd_args = " ".join([f'"{a}"' if " " in a else a for a in self.args])
        cli = f"dsha {self.tool_id} {cmd_args}".strip()
        py = f"from index import Call_Tools; res = Call_Tools('{self.tool_id}', {self.args})"
        return {
            "cli_command": cli,
            "powershell_command": f"powershell -Command \"& {cli}\"",
            "python_snippet": py,
        }

    def _default_rollback(self):
        is_safe = self.exit_code in (0, 124, 125, 126, 127)
        if self.tool_id in ("tier",):
            return {
                "action": "revert_tier",
                "command": "powershell -File bin/agy-tier.ps1 auto",
                "safe": True,
            }
        return {
            "action": "inspect_audit_and_revert" if self.exit_code != 0 else "no_side_effects",
            "command": "powershell -Command \"Get-Content logs/gate.log -Tail 20\"" if self.exit_code != 0 else "none",
            "safe": is_safe,
        }

    def to_dict(self):
        return {
            "protocol": "dsha-1.2.0-std",
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "caller": self.caller,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "category": self.category,
            "args": self.args,
            "host_fingerprint": self.host_fingerprint,
            "stages": [s.to_dict() for s in self.stages],
            "causal_chain": self.causal_chain,
            "reproducer": self.reproducer,
            "rollback": self.rollback,
        }

    def format_retrace(self):
        """Format backward lifecycle trace walk for AI and developers."""
        lines = [
            "========================================================================",
            "🔍 [DSHA 接口生命周期逆向回溯 · Retrace Engine v1.2.0-std]",
            "========================================================================",
            f"  • 追踪标识 (Trace ID): {self.trace_id}",
            f"  • 调用发起 (Caller):   {self.caller}",
            f"  • 目标工具 (Tool):     [{self.category}] {self.tool_name} (id: {self.tool_id})",
            f"  • 终态裁决 (Verdict):  {self.status} (退出码: {self.exit_code}, 总耗时: {self.duration_ms}ms)",
            f"  • 宿主拓扑 (Topology): {HostEnvPerceiver.get_topology_string()}",
            "",
            "⏪ 逆向调用链回溯 (Reverse Traversal: Stage 7 -> Stage 1):",
        ]

        all_stage_names = [
            TraceStage.EGRESS_PACKAGING.value,
            TraceStage.SANDBOX_EXECUTION.value,
            TraceStage.CATALOG_CONTAINMENT.value,
            TraceStage.TIER_AUTHORIZATION.value,
            TraceStage.ENVFEEL_PREREQUISITES.value,
            TraceStage.INTENT_ROUTING.value,
            TraceStage.INGRESS_VALIDATION.value,
        ]

        stage_dict = {s.stage: s for s in self.stages}

        stage_titles = {
            "egress_packaging": "7/7: 响应封套封装 (Egress Packaging)",
            "sandbox_execution": "6/7: 沙箱子进程执行 (Sandbox Execution)",
            "catalog_containment": "5/7: 白名单根收容 (Catalog Containment)",
            "tier_authorization": "4/7: 权限档位核验 (Tier Authorization)",
            "envfeel_prerequisites": "3/7: 宿主环境自感知 (EnvFeel Prerequisites)",
            "intent_routing": "2/7: 意图路由匹配 (Intent Routing)",
            "ingress_validation": "1/7: 入口封套校验 (Ingress Validation)",
        }

        for s_name in all_stage_names:
            s_title = stage_titles.get(s_name, s_name)
            if s_name in stage_dict:
                rec = stage_dict[s_name]
                if rec.status == "PASS":
                    badge = "✓ [PASS]"
                elif rec.status == "FAIL":
                    badge = "❌ [FAIL]"
                else:
                    badge = f"? [{rec.status}]"
                lat_str = f"({rec.latency_ms}ms)" if rec.latency_ms > 0 else ""
                lines.append(f"  [{s_title}] {badge} {lat_str}")
                if rec.message:
                    lines.append(f"      └─ 状态: {rec.message}")
                if rec.evidence:
                    lines.append(f"      └─ 证据: {json.dumps(rec.evidence, ensure_ascii=False)}")
            else:
                lines.append(f"  [{s_title}] ⊘ [SKIP] (因上游熔断拦截未下发)")

        if self.causal_chain:
            lines.append("")
            lines.append("🎯 根因归因与证据链 (Root Cause & Forensic Evidence):")
            lines.append(f"  • 阻断阶段: {self.causal_chain.get('failed_stage')}")
            lines.append(f"  • 错误编码: {self.causal_chain.get('error_code')}")
            lines.append(f"  • 阻断原因: {self.causal_chain.get('root_cause')}")
            rems = self.causal_chain.get("remediations")
            if rems:
                lines.append("  • 修复建议:")
                for r in rems:
                    lines.append(f"      💡 {r}")

        lines.append("")
        lines.append("🔁 依契约复现命令 (L4 Reproducer):")
        lines.append(f"  CLI:        {self.reproducer.get('cli_command', 'none')}")
        lines.append(f"  PowerShell: {self.reproducer.get('powershell_command', 'none')}")

        lines.append("")
        lines.append("↩️ 依契约回滚操作 (L4 Rollback):")
        lines.append(f"  动作: {self.rollback.get('action', 'none')}")
        lines.append(f"  命令: {self.rollback.get('command', 'none')}")
        lines.append(f"  安全: {'安全无害' if self.rollback.get('safe') else '需谨慎'}")
        lines.append("========================================================================")
        return "\n".join(lines)


class TraceStore:
    """Persists and retrieves standardized execution trace receipts with automatic rotation."""

    @classmethod
    def get_trace_dir(cls):
        # 1. If inside repo/workspace, locate project root
        p = Path(__file__).resolve().parent
        repo_root = None
        for cand in [p, p.parent, p.parent.parent, p.parent.parent.parent]:
            if (cand / ".git").exists() or (cand / "VERSION_SCHEME.md").exists():
                repo_root = cand
                break
        if repo_root:
            primary = repo_root / "logs" / "traces"
        else:
            user_home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~") or ".")
            primary = user_home / ".gemini" / "config" / "logs" / "traces"

        try:
            primary.mkdir(parents=True, exist_ok=True)
            return primary
        except Exception:
            user_home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~") or ".")
            sec = user_home / ".gemini" / "config" / "logs" / "traces"
            sec.mkdir(parents=True, exist_ok=True)
            return sec

    @classmethod
    def save(cls, receipt):
        if not receipt or not receipt.trace_id:
            return None
        try:
            d = cls.get_trace_dir()
            out_file = d / f"{receipt.trace_id}.json"
            data = receipt.to_dict()
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            traces = sorted(d.glob("tr_*.json"), key=lambda p: p.stat().st_mtime)
            if len(traces) > 100:
                for old in traces[:-100]:
                    try:
                        old.unlink()
                    except Exception:
                        pass
            return str(out_file)
        except Exception:
            return None

    @classmethod
    def get(cls, trace_id):
        if not trace_id:
            return None
        tid = Path(trace_id).stem
        d = cls.get_trace_dir()
        target = d / f"{tid}.json"
        if not target.is_file():
            user_home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~") or ".")
            alt = user_home / ".gemini" / "config" / "logs" / "traces" / f"{tid}.json"
            if alt.is_file():
                target = alt
            else:
                alt_repo = Path.cwd() / "logs" / "traces" / f"{tid}.json"
                if alt_repo.is_file():
                    target = alt_repo
                else:
                    return None
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None



def retrace(target, as_json=False):
    """
    AI Reverse Traceability Engine (顺着接口回溯).
    Accepts a trace_id string, a response envelope dict, or a trace file path.
    Walks backwards from Stage 7 up to Stage 1 to explain execution causal factors.
    """
    data = None
    if isinstance(target, dict):
        if "trace_receipt" in target and isinstance(target["trace_receipt"], dict):
            data = target["trace_receipt"]
        elif "stages" in target:
            data = target
    elif isinstance(target, str):
        if Path(target).is_file():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        if not data:
            data = TraceStore.get(target)

    if not data:
        err_msg = f"[DSHA-RETRACE] Trace not found for target: {target}"
        if as_json:
            return json.dumps({"error": err_msg}, ensure_ascii=False)
        return err_msg

    receipt = TraceReceipt(
        trace_id=data.get("trace_id"),
        caller=data.get("caller", "ai-assistant"),
        tool_id=data.get("tool_id", ""),
        tool_name=data.get("tool_name", ""),
        category=data.get("category", ""),
        args=data.get("args", []),
    )
    receipt.timestamp = data.get("timestamp", receipt.timestamp)
    receipt.status = data.get("status", "UNKNOWN")
    receipt.exit_code = data.get("exit_code", 0)
    receipt.duration_ms = data.get("duration_ms", 0)
    receipt.causal_chain = data.get("causal_chain")
    receipt.reproducer = data.get("reproducer", {})
    receipt.rollback = data.get("rollback", {})
    receipt.host_fingerprint = data.get("host_fingerprint", {})

    for s in data.get("stages", []):
        receipt.record_stage(
            stage=s.get("stage"),
            status=s.get("status"),
            latency_ms=s.get("latency_ms", 0),
            message=s.get("message", ""),
            evidence=s.get("evidence", {}),
        )

    if as_json:
        return json.dumps(receipt.to_dict(), ensure_ascii=False, indent=2)
    return receipt.format_retrace()


def dump_open_protocol_schema():
    """Returns official machine-readable Open Protocol JSON Schema specification (v1.2.0-std)."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "DSHA Open Protocol Specification (v1.2.0-std)",
        "description": "Standardized bidirectional execution, pre-flight assertion, and retraceability protocol for AI agents and developer tooling.",
        "definitions": {
            "DSHARequest": {
                "type": "object",
                "required": ["tool"],
                "properties": {
                    "trace_id": {"type": "string", "description": "Unique invocation trace ID"},
                    "caller": {"type": "string", "description": "Originating agent or user identifier"},
                    "tool": {"type": "string", "description": "Target tool ID (cf, rea, scribe, pwsh, sh, tier, meter)"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "CLI argument list"},
                    "context": {
                        "type": "object",
                        "properties": {
                            "tier": {"type": "string", "enum": ["read-only", "workspace-write", "danger-full-access", "auto"]},
                            "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
                            "cwd": {"type": "string"},
                            "proxy": {"type": "string"},
                            "capture": {"type": "boolean"},
                            "custom_env": {"type": "object"},
                        },
                    },
                },
            },
            "DSHAResponse": {
                "type": "object",
                "required": ["protocol", "trace_id", "success", "exit_code", "duration_ms", "envfeel"],
                "properties": {
                    "protocol": {"type": "string", "const": "dsha-1.2.0-std"},
                    "trace_id": {"type": "string"},
                    "success": {"type": "boolean"},
                    "tool": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "category": {"type": "string"},
                    "exit_code": {"type": "integer"},
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                    "duration_ms": {"type": "integer"},
                    "err_block": {"$ref": "#/definitions/ErrBlock"},
                    "envfeel": {"$ref": "#/definitions/EnvFeelTelemetry"},
                    "trace_receipt": {"$ref": "#/definitions/TraceReceipt"},
                },
            },
            "TraceReceipt": {
                "type": "object",
                "required": ["protocol", "trace_id", "timestamp", "status", "exit_code", "stages"],
                "properties": {
                    "protocol": {"type": "string", "const": "dsha-1.2.0-std"},
                    "trace_id": {"type": "string"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "status": {"type": "string", "enum": ["PASS", "REFUSED", "EXECUTION_ERROR", "TIMEOUT"]},
                    "exit_code": {"type": "integer"},
                    "duration_ms": {"type": "integer"},
                    "caller": {"type": "string"},
                    "tool_id": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "category": {"type": "string"},
                    "args": {"type": "array", "items": {"type": "string"}},
                    "host_fingerprint": {"type": "object"},
                    "stages": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/StageRecord"},
                    },
                    "causal_chain": {"type": ["object", "null"]},
                    "reproducer": {"type": "object"},
                    "rollback": {"type": "object"},
                },
            },
            "StageRecord": {
                "type": "object",
                "required": ["stage", "status"],
                "properties": {
                    "stage": {
                        "type": "string",
                        "enum": [
                            "ingress_validation",
                            "intent_routing",
                            "catalog_containment",
                            "envfeel_prerequisites",
                            "tier_authorization",
                            "sandbox_execution",
                            "egress_packaging",
                        ],
                    },
                    "status": {"type": "string", "enum": ["PASS", "FAIL", "SKIP"]},
                    "latency_ms": {"type": "integer"},
                    "message": {"type": "string"},
                    "evidence": {"type": "object"},
                },
            },
            "ErrBlock": {
                "type": ["object", "null"],
                "properties": {
                    "status": {"type": "string", "const": "REFUSED"},
                    "error_code": {"type": "string"},
                    "tool_id": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "category": {"type": "string"},
                    "refusal_statement": {"type": "string"},
                    "details": {"type": "array"},
                    "remediations": {"type": "array", "items": {"type": "string"}},
                },
            },
            "EnvFeelTelemetry": {
                "type": "object",
                "required": ["status", "platform"],
                "properties": {
                    "status": {"type": "string"},
                    "platform": {"type": "string"},
                    "reason": {"type": "string"},
                    "tier": {"type": "string"},
                    "cwd": {"type": "string"},
                    "details": {"type": "array"},
                },
            },
        },
    }


class BaseTool(ABC):
    """Abstract Base Class for all DSHA tools."""

    def __init__(
        self,
        tool_id,
        name,
        category,
        risk_level,
        version,
        description,
        cmd,
        script=None,
        prerequisites=None,
        keywords=None,
        extensions=None,
        exact_filenames=None,
        weight=1.0,
        trusted_executable_roots=None,
    ):
        self.id = tool_id
        self.name = name
        self.category = ToolCategory(category) if isinstance(category, str) else category
        self.risk_level = RiskLevel(risk_level) if isinstance(risk_level, str) else risk_level
        self.version = version
        self.description = description
        self.cmd = cmd
        self.script = script
        self.prerequisites = prerequisites or []
        self.keywords = keywords or []
        self.extensions = extensions or []
        self.exact_filenames = exact_filenames or []
        self.weight = weight
        # None preserves the legacy PATH fallback for third-party extensions.
        # An explicit sequence (including an empty one) disables that fallback.
        self.trusted_executable_roots = (
            None if trusted_executable_roots is None else tuple(trusted_executable_roots)
        )

    def assert_environment(self):
        """Verifies that all required host runtimes are installed."""
        failed_prereqs = []
        remediations = []
        for req in self.prerequisites:
            res = req.verify()
            if not res["satisfied"]:
                failed_prereqs.append(res)
                if res.get("remediation"):
                    remediations.append(res["remediation"])

        if failed_prereqs:
            err = ErrBlock(
                error_code="ERR_PREREQUISITE_MISSING",
                tool_id=self.id,
                tool_name=self.name,
                category=self.category.value,
                refusal_statement=f"DSHA 拒绝执行: 工具 '{self.id}' 缺少必需宿主运行环境，DSHA 坚持不臃肿合并运行时的纯净原则。",
                details=failed_prereqs,
                remediations=remediations,
            )
            return False, err
        return True, None

    def assert_authorization(self, active_tier=None):
        """Anti-privilege escalation gate: strictly blocks unauthorized operations."""
        # A caller's context may restrict, never replace the active host tier.
        tiers = [str(get_active_tier()).strip().lower()]
        if active_tier is not None:
            tiers.append(str(active_tier).strip().lower())
        valid = {"read-only", "workspace-write", "danger-full-access", "auto"}
        invalid = next((value for value in tiers if value not in valid), None)
        tier = "read-only" if "read-only" in tiers else tiers[0]

        # Strict permission tier rules:
        # read-only: blocks medium and admin tools from modifying or executing privileged operations
        if invalid is not None or (tier == "read-only" and self.risk_level in (RiskLevel.MEDIUM, RiskLevel.ADMIN)):
            err = ErrBlock(
                error_code="ERR_PERMISSION_DENIED",
                tool_id=self.id,
                tool_name=self.name,
                category=self.category.value,
                refusal_statement=f"DSHA 越权拦截: 当前权限处于 '{tier}' 档位，禁止调用具有修改/写操作风险等级 ({self.risk_level.value}) 的工具。",
                details=[{"active_tier": tiers[0], "requested_tier": active_tier, "invalid_tier": invalid, "tool_risk_level": self.risk_level.value}],
                remediations=["如需执行此操作，请先确认并将权限档位切换为 workspace-write、auto 或 danger-full-access。"],
            )
            return False, err

        return True, None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "version": self.version,
            "description": self.description,
            "cmd": self.cmd,
            "script": self.script,
            "prerequisites": [
                {
                    "binary": p.binary,
                    "min_version": p.min_version,
                    "remediation": p.remediation,
                }
                for p in self.prerequisites
            ],
            "keywords": self.keywords,
            "extensions": self.extensions,
            "exact_filenames": self.exact_filenames,
            "weight": self.weight,
        }

    def resolve_executable(self):
        cmd_name = self.cmd
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent if script_dir.name in ("scripts", "bin") else script_dir
        user_home = Path(os.environ.get("USERPROFILE") or ".")

        candidate_locations = [
            repo_root / "bin" / cmd_name,
            user_home / ".gemini" / "config" / cmd_name,
            repo_root / cmd_name,
        ]
        # Extensions opting into explicit roots search those roots first.
        # Never fall back to the ambient PATH in that mode.
        strict_extension = (
            self.id not in {"cf", "rea", "scribe", "pwsh", "sh", "tier", "meter"}
            and self.trusted_executable_roots is not None
        )
        if strict_extension:
            is_bare_command = (
                isinstance(cmd_name, str)
                and cmd_name not in ("", ".", "..")
                and not any(sep in cmd_name for sep in ("/", "\\", ":"))
            )
            if not is_bare_command:
                return None
            for configured_root in self.trusted_executable_roots:
                try:
                    root = Path(configured_root)
                    if not root.is_absolute():
                        continue
                    root = root.resolve()
                    candidate = shutil.which(cmd_name, path=str(root))
                    if candidate:
                        resolved_candidate = Path(candidate).resolve()
                        resolved_candidate.relative_to(root)
                        if resolved_candidate.is_file():
                            return str(resolved_candidate)
                except (OSError, TypeError, ValueError):
                    continue

        for p in candidate_locations:
            if p.is_file():
                return str(p)

        if strict_extension:
            return None
        which_path = shutil.which(cmd_name)
        if which_path:
            return which_path
        return None

    def assert_target_contained(self, exec_path):
        """解析出的可执行目标必须落在白名单根之内。

        前置断言证明“运行时存在”；这条证明“要跑的就是索引声明的那个东西”。
        元数据被改、或工具名被拼成相对路径时，前置断言挡不住，这条可以。
        """
        target = Path(exec_path).resolve()
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent if script_dir.name in ("scripts", "bin") else script_dir
        user_home = Path(os.environ.get("USERPROFILE") or ".")
        allowed_roots = [
            (repo_root / "bin").resolve(),
            (user_home / ".gemini" / "config").resolve(),
        ]
        for root in allowed_roots:
            try:
                target.relative_to(root)
                return True, None
            except ValueError:
                continue
        # PATH fallback is only for a bare declared command. shutil.which() also
        # accepts explicit paths; those must not bypass the trusted-root check.
        is_bare_command = (
            isinstance(self.cmd, str)
            and self.cmd not in ("", ".", "..")
            and not any(sep in self.cmd for sep in ("/", "\\", ":"))
        )
        # Built-in tools never gain extra roots through extension configuration.
        # Extensions may opt into explicit, absolute trusted roots. In that mode
        # an untrusted PATH match is rejected rather than silently accepted.
        is_builtin_tool = self.id in {"cf", "rea", "scribe", "pwsh", "sh", "tier", "meter"}
        if not is_builtin_tool and self.trusted_executable_roots is not None:
            for configured_root in self.trusted_executable_roots:
                configured_root = Path(configured_root)
                if not configured_root.is_absolute():
                    continue
                try:
                    target.relative_to(configured_root.resolve())
                    return True, None
                except ValueError:
                    continue
        which_path = (
            shutil.which(self.cmd)
            if is_bare_command and not is_builtin_tool and self.trusted_executable_roots is None
            else None
        )
        if which_path and Path(which_path).resolve() == target:
            return True, None
        err = ErrBlock(
            error_code="ERR_TARGET_OUTSIDE_SANDBOX",
            tool_id=self.id,
            tool_name=self.name,
            category=self.category.value,
            refusal_statement=(
                f"DSHA 拒绝执行: 解析出的目标 '{target}' 不在允许的根之内"
                "(仓库 bin/ 与 ~/.gemini/config/)。"
            ),
            details=[{"binary": str(target), "reason": "target-outside-sandbox"}],
            remediations=[
                "确认 DSHA-Index 里该工具的 cmd 未被改写成相对路径或仓库外路径。",
                "如确需仓库外目标，请先在白名单中显式声明它，再重试。",
            ],
        )
        return False, err

    def execute(self, args=None, context=None):
        if args is None:
            args = []
        if context is None:
            context = {}

        # 0. Convert context into unidirectional ExecutionEnvelope
        envelope = ExecutionEnvelope.from_context(context)
        trace_id = envelope.trace_id or f"tr_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        caller = envelope.caller

        receipt = TraceReceipt(
            trace_id=trace_id,
            caller=caller,
            tool_id=self.id,
            tool_name=self.name,
            category=self.category.value,
            args=args,
            context=context,
        )

        # Stage 1: Ingress Validation
        receipt.record_stage(
            TraceStage.INGRESS_VALIDATION,
            "PASS",
            latency_ms=0,
            message="Unidirectional execution envelope sanitized & parameter bounds enforced",
            evidence={"cwd": envelope.cwd, "timeout": envelope.timeout, "tier": envelope.tier},
        )

        # Stage 2: Intent Routing
        route_meta = context.get("route_meta")
        if route_meta:
            receipt.record_stage(
                TraceStage.INTENT_ROUTING,
                "PASS",
                latency_ms=0,
                message=f"Routed from intent with score_share {route_meta.get('score_share')}",
                evidence=route_meta,
            )
        else:
            receipt.record_stage(
                TraceStage.INTENT_ROUTING,
                "PASS",
                latency_ms=0,
                message="Direct catalog identifier dispatch (bypass router)",
            )

        # Stage 3: EnvFeel Pre-flight Prerequisite Assertion (No bundled runtime)
        t_env0 = time.time()
        ok_env, err_env = self.assert_environment()
        env_lat = int((time.time() - t_env0) * 1000)
        if not ok_env:
            receipt.record_stage(
                TraceStage.ENVFEEL_PREREQUISITES,
                "FAIL",
                latency_ms=env_lat,
                message="Host runtime prerequisite assertion failed",
                evidence={"failed_prereqs": err_env.details},
            )
            receipt.finalize(
                status="REFUSED",
                exit_code=126,
                duration_ms=env_lat,
                causal_chain={
                    "failed_stage": TraceStage.ENVFEEL_PREREQUISITES.value,
                    "error_code": "ERR_PREREQUISITE_MISSING",
                    "root_cause": err_env.refusal_statement,
                    "evidence": err_env.details,
                    "remediations": err_env.remediations,
                },
            )
            TraceStore.save(receipt)
            return {
                "protocol": "dsha-1.2.0-std",
                "trace_id": trace_id,
                "success": False,
                "tool": self.id,
                "tool_name": self.name,
                "category": self.category.value,
                "exit_code": 126,
                "stdout": "",
                "stderr": err_env.format_cli(),
                "err_block": err_env.to_dict(),
                "duration_ms": env_lat,
                "envfeel": {
                    "status": "REFUSED",
                    "platform": HostEnvPerceiver.get_topology_string(),
                    "reason": "prerequisites_missing",
                    "details": err_env.details,
                },
                "trace_receipt": receipt.to_dict(),
            }

        receipt.record_stage(
            TraceStage.ENVFEEL_PREREQUISITES,
            "PASS",
            latency_ms=env_lat,
            message="All declared host runtimes verified and probe satisfied",
        )

        # Stage 4: Tier Authorization Assertion (Anti-privilege escalation)
        active_tier = envelope.tier
        ok_auth, err_auth = self.assert_authorization(active_tier)
        if not ok_auth:
            receipt.record_stage(
                TraceStage.TIER_AUTHORIZATION,
                "FAIL",
                latency_ms=0,
                message=f"Denied by permission tier '{envelope.tier or get_active_tier()}'",
                evidence=err_auth.details[0] if err_auth and err_auth.details else {},
            )
            receipt.finalize(
                status="REFUSED",
                exit_code=126,
                duration_ms=env_lat,
                causal_chain={
                    "failed_stage": TraceStage.TIER_AUTHORIZATION.value,
                    "error_code": "ERR_PERMISSION_DENIED",
                    "root_cause": err_auth.refusal_statement,
                    "evidence": err_auth.details,
                    "remediations": err_auth.remediations,
                },
            )
            TraceStore.save(receipt)
            return {
                "protocol": "dsha-1.2.0-std",
                "trace_id": trace_id,
                "success": False,
                "tool": self.id,
                "tool_name": self.name,
                "category": self.category.value,
                "exit_code": 126,
                "stdout": "",
                "stderr": err_auth.format_cli(),
                "err_block": err_auth.to_dict(),
                "duration_ms": env_lat,
                "envfeel": {
                    "status": "REFUSED",
                    "platform": HostEnvPerceiver.get_topology_string(),
                    "reason": "authorization_denied",
                    "tier": active_tier or get_active_tier(),
                },
                "trace_receipt": receipt.to_dict(),
            }

        receipt.record_stage(
            TraceStage.TIER_AUTHORIZATION,
            "PASS",
            latency_ms=0,
            message=f"Operation authorized under tier '{active_tier or get_active_tier()}'",
        )

        # Stage 5: Catalog Resolution & Sandbox Containment Assertion
        exec_path = self.resolve_executable()
        if not exec_path:
            receipt.record_stage(
                TraceStage.CATALOG_CONTAINMENT,
                "FAIL",
                latency_ms=0,
                message=f"Launcher '{self.cmd}' could not be resolved on disk",
            )
            receipt.finalize(
                status="REFUSED",
                exit_code=127,
                duration_ms=0,
                causal_chain={
                    "failed_stage": TraceStage.CATALOG_CONTAINMENT.value,
                    "error_code": "ERR_LAUNCHER_NOT_FOUND",
                    "root_cause": f"Launcher '{self.cmd}' could not be resolved on disk.",
                    "evidence": {"tool_id": self.id, "cmd": self.cmd},
                    "remediations": ["Verify DSHA installation via `powershell -File install.ps1`"],
                },
            )
            TraceStore.save(receipt)
            return {
                "protocol": "dsha-1.2.0-std",
                "trace_id": trace_id,
                "success": False,
                "tool": self.id,
                "tool_name": self.name,
                "category": self.category.value,
                "exit_code": 127,
                "stdout": "",
                "stderr": f"[DSHA] Error: Launcher '{self.cmd}' could not be resolved on disk.",
                "duration_ms": 0,
                "err_block": None,
                "envfeel": {
                    "status": "REFUSED",
                    "platform": HostEnvPerceiver.get_topology_string(),
                    "reason": "launcher_not_found",
                },
                "trace_receipt": receipt.to_dict(),
            }

        ok_contained, err_contained = self.assert_target_contained(exec_path)
        if not ok_contained:
            receipt.record_stage(
                TraceStage.CATALOG_CONTAINMENT,
                "FAIL",
                latency_ms=0,
                message="Target executable outside allowed sandbox roots",
                evidence={"target": exec_path},
            )
            receipt.finalize(
                status="REFUSED",
                exit_code=125,
                duration_ms=0,
                causal_chain={
                    "failed_stage": TraceStage.CATALOG_CONTAINMENT.value,
                    "error_code": "ERR_TARGET_OUTSIDE_SANDBOX",
                    "root_cause": f"Target outside allowed roots: {exec_path}",
                    "evidence": {"target": exec_path},
                    "remediations": err_contained.remediations if err_contained else [],
                },
            )
            TraceStore.save(receipt)
            return {
                "protocol": "dsha-1.2.0-std",
                "trace_id": trace_id,
                "success": False,
                "tool": self.id,
                "tool_name": self.name,
                "category": self.category.value,
                "exit_code": 125,
                "stdout": "",
                "stderr": f"[DSHA] Error: target outside allowed roots: {exec_path}",
                "duration_ms": 0,
                "err_block": err_contained.to_dict() if err_contained is not None else {},
                "envfeel": {
                    "status": "REFUSED",
                    "platform": HostEnvPerceiver.get_topology_string(),
                    "reason": "target_outside_sandbox",
                },
                "trace_receipt": receipt.to_dict(),
            }

        receipt.record_stage(
            TraceStage.CATALOG_CONTAINMENT,
            "PASS",
            latency_ms=0,
            message="Target executable contained in allowed sandbox roots",
            evidence={"target": exec_path},
        )

        # Stage 6: Isolated Subprocess Execution
        start_time = time.time()
        exec_env = envelope.build_subprocess_env()
        cwd = envelope.cwd
        timeout = envelope.timeout

        if exec_path.endswith(".ps1"):
            script_dir = Path(__file__).resolve().parent
            pwsh_bin = script_dir.parent / "bin" / "pwsh.cmd"
            cmd_list = [str(pwsh_bin), "-NoProfile", "-File", exec_path] + args
        else:
            cmd_list = [exec_path] + args

        capture = envelope.capture

        try:
            if capture:
                proc = subprocess.run(
                    cmd_list,
                    cwd=cwd,
                    env=exec_env,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                duration_ms = int((time.time() - start_time) * 1000)
                sub_status = "PASS" if proc.returncode == 0 else "FAIL"
                receipt.record_stage(
                    TraceStage.SANDBOX_EXECUTION,
                    sub_status,
                    latency_ms=duration_ms,
                    message=f"Subprocess finished with exit code {proc.returncode}",
                    evidence={"exit_code": proc.returncode},
                )
                receipt.record_stage(
                    TraceStage.EGRESS_PACKAGING,
                    "PASS",
                    latency_ms=0,
                    message="Standard response envelope sealed with trace receipt",
                )
                receipt.finalize(
                    status="PASS" if proc.returncode == 0 else "EXECUTION_ERROR",
                    exit_code=proc.returncode,
                    duration_ms=duration_ms,
                    causal_chain=None if proc.returncode == 0 else {
                        "failed_stage": TraceStage.SANDBOX_EXECUTION.value,
                        "error_code": "ERR_SUBPROCESS_EXIT_NONZERO",
                        "root_cause": f"Subprocess exited with status {proc.returncode}",
                        "evidence": {"exit_code": proc.returncode, "stderr": proc.stderr[:300]},
                    },
                )
                TraceStore.save(receipt)
                return {
                    "protocol": "dsha-1.2.0-std",
                    "trace_id": trace_id,
                    "success": proc.returncode == 0,
                    "tool": self.id,
                    "tool_name": self.name,
                    "category": self.category.value,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "duration_ms": duration_ms,
                    "cmd": cmd_list,
                    "err_block": None,
                    "envfeel": {
                        "status": "HEALTHY" if proc.returncode == 0 else "EXECUTION_ERROR",
                        "platform": HostEnvPerceiver.get_topology_string(),
                        "tier": active_tier or get_active_tier(),
                        "cwd": cwd,
                    },
                    "trace_receipt": receipt.to_dict(),
                }
            else:
                proc = subprocess.run(cmd_list, cwd=cwd, env=exec_env, timeout=timeout)
                duration_ms = int((time.time() - start_time) * 1000)
                sub_status = "PASS" if proc.returncode == 0 else "FAIL"
                receipt.record_stage(
                    TraceStage.SANDBOX_EXECUTION,
                    sub_status,
                    latency_ms=duration_ms,
                    message=f"Subprocess finished with exit code {proc.returncode}",
                )
                receipt.record_stage(
                    TraceStage.EGRESS_PACKAGING,
                    "PASS",
                    latency_ms=0,
                    message="Standard response envelope sealed with trace receipt",
                )
                receipt.finalize(
                    status="PASS" if proc.returncode == 0 else "EXECUTION_ERROR",
                    exit_code=proc.returncode,
                    duration_ms=duration_ms,
                    causal_chain=None if proc.returncode == 0 else {
                        "failed_stage": TraceStage.SANDBOX_EXECUTION.value,
                        "error_code": "ERR_SUBPROCESS_EXIT_NONZERO",
                        "root_cause": f"Subprocess exited with status {proc.returncode}",
                        "evidence": {"exit_code": proc.returncode},
                    },
                )
                TraceStore.save(receipt)
                return {
                    "protocol": "dsha-1.2.0-std",
                    "trace_id": trace_id,
                    "success": proc.returncode == 0,
                    "tool": self.id,
                    "tool_name": self.name,
                    "category": self.category.value,
                    "exit_code": proc.returncode,
                    "stdout": "",
                    "stderr": "",
                    "duration_ms": duration_ms,
                    "cmd": cmd_list,
                    "err_block": None,
                    "envfeel": {
                        "status": "HEALTHY" if proc.returncode == 0 else "EXECUTION_ERROR",
                        "platform": HostEnvPerceiver.get_topology_string(),
                        "tier": active_tier or get_active_tier(),
                        "cwd": cwd,
                    },
                    "trace_receipt": receipt.to_dict(),
                }
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            receipt.record_stage(
                TraceStage.SANDBOX_EXECUTION,
                "FAIL",
                latency_ms=duration_ms,
                message=f"Execution timed out after {timeout} seconds",
                evidence={"timeout": timeout},
            )
            receipt.finalize(
                status="TIMEOUT",
                exit_code=124,
                duration_ms=duration_ms,
                causal_chain={
                    "failed_stage": TraceStage.SANDBOX_EXECUTION.value,
                    "error_code": "ERR_EXECUTION_TIMEOUT",
                    "root_cause": f"Execution timed out after {timeout} seconds.",
                    "evidence": {"timeout": timeout},
                    "remediations": ["Increase timeout in context or verify process is not deadlocked."],
                },
            )
            TraceStore.save(receipt)
            return {
                "protocol": "dsha-1.2.0-std",
                "trace_id": trace_id,
                "success": False,
                "tool": self.id,
                "tool_name": self.name,
                "category": self.category.value,
                "exit_code": 124,
                "stdout": "",
                "stderr": f"[DSHA] Execution timed out after {timeout} seconds.",
                "duration_ms": duration_ms,
                "err_block": None,
                "envfeel": {
                    "status": "TIMEOUT",
                    "platform": HostEnvPerceiver.get_topology_string(),
                    "timeout_seconds": timeout,
                },
                "trace_receipt": receipt.to_dict(),
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            receipt.record_stage(
                TraceStage.SANDBOX_EXECUTION,
                "FAIL",
                latency_ms=duration_ms,
                message=f"Execution error: {e}",
            )
            receipt.finalize(
                status="EXECUTION_ERROR",
                exit_code=1,
                duration_ms=duration_ms,
                causal_chain={
                    "failed_stage": TraceStage.SANDBOX_EXECUTION.value,
                    "error_code": "ERR_SUBPROCESS_EXCEPTION",
                    "root_cause": str(e),
                },
            )
            TraceStore.save(receipt)
            return {
                "protocol": "dsha-1.2.0-std",
                "trace_id": trace_id,
                "success": False,
                "tool": self.id,
                "tool_name": self.name,
                "category": self.category.value,
                "exit_code": 1,
                "stdout": "",
                "stderr": f"[DSHA] Execution error: {e}",
                "duration_ms": duration_ms,
                "err_block": None,
                "envfeel": {
                    "status": "ERROR",
                    "platform": HostEnvPerceiver.get_topology_string(),
                    "error": str(e),
                },
                "trace_receipt": receipt.to_dict(),
            }


# Concrete Tool Implementations


class CFTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="cf",
            name="Cloudflare Web & Edge Engine",
            category=ToolCategory.WEB_EDGE,
            risk_level=RiskLevel.MEDIUM,
            version="1.0.0",
            description="Cloudflare Workers, Pages, Tunnels, Web deployment, Edge APIs & Forge OpenAPI",
            cmd="cf.cmd",
            script="dsha_cf.py",
            prerequisites=[
                PrerequisiteEnv(
                    binary="node",
                    min_version="20.0.0",
                    remediation="Install Node.js >= 20.0.0 via 'winget install OpenJS.NodeJS.LTS' or https://nodejs.org",
                ),
                PrerequisiteEnv(
                    binary="wrangler",
                    remediation="Install Wrangler CLI via 'npm install -g wrangler' or use npx wrangler.",
                ),
            ],
            keywords=[
                "cloudflare", "wrangler", "worker", "workers", "pages", "tunnel",
                "web", "edge", "deploy", "serverless", "dns", "kv", "r2", "d1",
                "frontend", "http", "api", "ingress", "部署", "网页", "前端", "边缘计算", "函数计算", "隧道", "域名"
            ],
            extensions=[".html", ".css", ".ts", ".tsx", ".js", ".jsx", ".wasm", ".toml"],
            exact_filenames=["wrangler.toml", "wrangler.json", "package.json", "index.html"],
            weight=1.0,
        )


class REATool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="rea",
            name="Reverse Engineer Anything (REA)",
            category=ToolCategory.REVERSE_ENGINEERING,
            risk_level=RiskLevel.LOW,
            version="1.0.0",
            description="Binary analysis, PE/ELF/Mach-O inspection, ASAR unpack, APK decompilation",
            cmd="rea.cmd",
            script="dsha_rea_driver.py",
            prerequisites=[
                PrerequisiteEnv(
                    binary="python",
                    min_version="3.10.0",
                    remediation="Install Python >= 3.10 via 'winget install Python.Python.3.12' or https://python.org",
                ),
            ],
            keywords=[
                "reverse", "decompile", "disassemble", "unpack", "binary", "pe",
                "elf", "macho", "apk", "asar", "dex", "section", "iat", "import table",
                "inspect-artifact", "ghidra", "hopper", "ida", "strings",
                "逆向", "反编译", "解包", "脱壳", "查壳", "节表", "导入表", "二进制分析", "反汇编"
            ],
            extensions=[".exe", ".dll", ".so", ".dylib", ".apk", ".asar", ".dex", ".class", ".bin", ".sys"],
            exact_filenames=[],
            weight=1.0,
        )


class ScribeTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="scribe",
            name="DSHA Scribe (Chronicler & Archivist)",
            category=ToolCategory.ARCHIVIST,
            risk_level=RiskLevel.READ_ONLY,
            version="1.0.0",
            description="Log harvesting, error stack trace indexing, research dossier synthesis",
            cmd="scribe.cmd",
            script="scribe.py",
            prerequisites=[
                PrerequisiteEnv(
                    binary="python",
                    min_version="3.10.0",
                    remediation="Install Python >= 3.10 via 'winget install Python.Python.3.12' or https://python.org",
                ),
            ],
            keywords=[
                "log", "audit", "dossier", "triage", "trace", "error", "exception",
                "harvest", "chronicler", "incident", "briefing", "diagnose", "investigate",
                "stacktrace", "failed", "exit code",
                "日志", "收录", "简报", "审计", "崩溃", "报错", "异常", "排查", "门禁记录", "堆栈", "诊断", "复盘"
            ],
            extensions=[".log", ".jsonl"],
            exact_filenames=["gate.log", "transcript.jsonl"],
            weight=1.0,
        )


class PwshTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="pwsh",
            name="DSHA Dedicated PowerShell 7",
            category=ToolCategory.SYSADMIN,
            risk_level=RiskLevel.MEDIUM,
            version="7.6.6",
            description="Parenthesis-safe PowerShell 7 pipeline and Windows automation",
            cmd="dsha-pwsh.cmd",
            script=None,
            prerequisites=[
                PrerequisiteEnv(
                    binary="pwsh",
                    min_version="7.0.0",
                    remediation="Install PowerShell 7 via 'winget install Microsoft.PowerShell' or https://github.com/PowerShell/PowerShell",
                ),
            ],
            keywords=[
                "powershell", "pwsh", "cmdlet", "pipeline", "wmi", "cim", "get-process",
                "set-executionpolicy", "active directory", "windows service",
                "管道", "进程", "脚本执行", "注册表"
            ],
            extensions=[".ps1", ".psm1", ".psd1"],
            exact_filenames=[],
            weight=1.0,
        )


class ShTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="sh",
            name="DSHA Safe GNU Bash",
            category=ToolCategory.SYSADMIN,
            risk_level=RiskLevel.MEDIUM,
            version="5.3",
            description="POSIX shell automation, Git Bash utilities (grep, awk, sed, curl)",
            cmd="dsha-sh.cmd",
            script=None,
            prerequisites=[
                PrerequisiteEnv(
                    binary="bash",
                    remediation="Install Git for Windows (includes GNU Bash) via 'winget install Git.Git' or https://git-scm.com",
                ),
            ],
            keywords=[
                "bash", "sh", "posix", "shell", "grep", "sed", "awk", "curl", "chmod", "export", "终端脚本"
            ],
            extensions=[".sh", ".bash"],
            exact_filenames=["Makefile", "Dockerfile"],
            weight=0.8,
        )


class TierTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="tier",
            name="DSH Permission Tier Gate",
            category=ToolCategory.POLICY_RADAR,
            risk_level=RiskLevel.ADMIN,
            version="1.0.0",
            description="Antigravity permission tier management (read-only, auto, danger-full-access, workspace-write)",
            cmd="agy-tier.ps1",
            script="gate.py",
            prerequisites=[
                PrerequisiteEnv(
                    binary="pwsh",
                    min_version="7.0.0",
                    remediation="Install PowerShell 7 via 'winget install Microsoft.PowerShell'",
                ),
            ],
            keywords=[
                "tier", "permission", "sandbox", "read-only", "danger-full-access",
                "workspace-write", "gate", "switch tier", "grant",
                "权限", "档位", "切档", "只读", "全权", "沙箱", "放行"
            ],
            extensions=[],
            exact_filenames=["tier.json"],
            weight=1.1,
        )


class MeterTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="meter",
            name="DSHA Quota Floating Radar",
            category=ToolCategory.POLICY_RADAR,
            risk_level=RiskLevel.LOW,
            version="1.0.0",
            description="5H / 7D sliding window token and quota visual monitoring HUD",
            cmd="agy-meter.ps1",
            script="meter.py",
            prerequisites=[
                PrerequisiteEnv(
                    binary="pwsh",
                    min_version="7.0.0",
                    remediation="Install PowerShell 7 via 'winget install Microsoft.PowerShell'",
                ),
            ],
            keywords=[
                "meter", "quota", "token", "floating window", "hud", "radar", "5h", "7d", "watermark",
                "额度", "悬浮窗", "雷达", "回血", "水位", "代币"
            ],
            extensions=[],
            exact_filenames=[],
            weight=1.1,
        )


class ToolRegistry:
    """Central registry supporting class-based tool registration and category queries."""

    def __init__(self):
        self._registry = {}

    def register(self, tool_or_cls):
        if isinstance(tool_or_cls, type) and issubclass(tool_or_cls, BaseTool):
            tool = tool_or_cls()
        elif isinstance(tool_or_cls, BaseTool):
            tool = tool_or_cls
        else:
            raise TypeError("Expected BaseTool instance or subclass")
        self._registry[tool.id.lower()] = tool
        return tool

    def get(self, tool_id):
        if not tool_id:
            return None
        return self._registry.get(str(tool_id).lower())

    def get_by_category(self, category):
        cat_str = (category.value if isinstance(category, ToolCategory) else str(category)).lower()
        results = []
        for tool in self._registry.values():
            if tool.category.value.lower() == cat_str or tool.category.name.lower() == cat_str:
                results.append(tool)
        return results

    def list_categories(self):
        cats = set()
        for tool in self._registry.values():
            cats.add(tool.category.value)
        return sorted(list(cats))

    def all(self):
        return dict(self._registry)

    def to_legacy_dict(self):
        """Backward-compatible dictionary matching the previous DSHA_INDEX format."""
        d = {}
        for t_id, t in self._registry.items():
            d[t_id] = {
                "id": t.id,
                "name": t.name,
                "category": t.category.value,
                "cmd": t.cmd,
                "script": t.script,
                "version": t.version,
                "description": t.description,
                "tags": [t.category.value.lower(), t.id] + [k for k in t.keywords[:3]],
                "extensions": t.extensions,
                "exact_filenames": t.exact_filenames,
                "risk_level": t.risk_level.value,
                "prerequisites": [
                    {"binary": p.binary, "min_version": p.min_version, "remediation": p.remediation}
                    for p in t.prerequisites
                ],
                "keywords": t.keywords,
                "weight": t.weight,
            }
        return d


# Initialize global registry and register all standard tools
TOOL_REGISTRY = ToolRegistry()
TOOL_REGISTRY.register(CFTool)
TOOL_REGISTRY.register(REATool)
TOOL_REGISTRY.register(ScribeTool)
TOOL_REGISTRY.register(PwshTool)
TOOL_REGISTRY.register(ShTool)
TOOL_REGISTRY.register(TierTool)
TOOL_REGISTRY.register(MeterTool)


def Call_Tools(tool_name, args=None, context=None):
    """
    Unified Parallel Tool Execution via BaseTool.
    Validates environment prerequisites and anti-privilege authorization before launch.
    """
    if args is None:
        args = []
    if context is None:
        context = {}

    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        trace_id = context.get("trace_id") or f"tr_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        caller = context.get("caller", "ai-assistant")
        receipt = TraceReceipt(
            trace_id=trace_id,
            caller=caller,
            tool_id=str(tool_name),
            tool_name="Unknown Tool",
            category="Unknown",
            args=args,
            context=context,
        )
        receipt.record_stage(TraceStage.INGRESS_VALIDATION, "PASS")
        receipt.record_stage(TraceStage.CATALOG_CONTAINMENT, "FAIL", message=f"Tool '{tool_name}' not registered in DSHA-Index")
        receipt.finalize(
            status="REFUSED",
            exit_code=127,
            duration_ms=0,
            causal_chain={
                "failed_stage": TraceStage.CATALOG_CONTAINMENT.value,
                "error_code": "ERR_TOOL_NOT_REGISTERED",
                "root_cause": f"Tool '{tool_name}' not registered in DSHA ToolRegistry.",
                "remediations": ["Check tool list via `dsha-index list`"],
            },
        )
        TraceStore.save(receipt)
        return {
            "protocol": "dsha-1.2.0-std",
            "trace_id": trace_id,
            "success": False,
            "tool": tool_name,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"[DSHA] Error: Tool '{tool_name}' not registered in DSHA ToolRegistry.",
            "duration_ms": 0,
            "err_block": None,
            "envfeel": {
                "status": "REFUSED",
                "platform": HostEnvPerceiver.get_topology_string(),
                "reason": "tool_not_registered",
            },
            "trace_receipt": receipt.to_dict(),
        }

    return tool.execute(args, context)


def run_selftest():
    tests = []

    # Test 1: Registry completeness (7 tools)
    tests.append(("registry_7_tools", len(TOOL_REGISTRY.all()) == 7))

    # Test 2: Category query WebEdge
    we_tools = TOOL_REGISTRY.get_by_category(ToolCategory.WEB_EDGE)
    tests.append(("category_query_webedge", len(we_tools) == 1 and we_tools[0].id == "cf"))

    # Test 3: Category query SysAdmin
    sa_tools = TOOL_REGISTRY.get_by_category("SysAdmin")
    tests.append(("category_query_sysadmin", len(sa_tools) == 2 and {t.id for t in sa_tools} == {"pwsh", "sh"}))

    # Test 4: Category query Archivist
    ar_tools = TOOL_REGISTRY.get_by_category("Archivist")
    tests.append(("category_query_archivist", len(ar_tools) == 1 and ar_tools[0].id == "scribe"))

    # Test 5: Category query PolicyRadar
    pr_tools = TOOL_REGISTRY.get_by_category("PolicyRadar")
    tests.append(("category_query_policyradar", len(pr_tools) == 2 and {t.id for t in pr_tools} == {"tier", "meter"}))

    # Test 6: Category query ReverseEngineering
    re_tools = TOOL_REGISTRY.get_by_category("ReverseEngineering")
    tests.append(("category_query_reverse", len(re_tools) == 1 and re_tools[0].id == "rea"))

    # Test 7: List all categories (5 distinct categories)
    cats = TOOL_REGISTRY.list_categories()
    tests.append(("list_categories_5", len(cats) == 5))

    # Test 8: Host Python prerequisite verified
    scribe_tool = TOOL_REGISTRY.get("scribe")
    ok_env, _ = scribe_tool.assert_environment()
    tests.append(("scribe_env_satisfied", ok_env))

    # Test 9: Host Pwsh prerequisite verified
    pwsh_tool = TOOL_REGISTRY.get("pwsh")
    ok_env_pwsh, _ = pwsh_tool.assert_environment()
    tests.append(("pwsh_env_satisfied", ok_env_pwsh))

    # Test 10: Missing prerequisite triggers ErrBlock refusal
    class MissingPrereqTool(BaseTool):
        def __init__(self):
            super().__init__(
                tool_id="missing_tool",
                name="Tool with Missing Binary",
                category=ToolCategory.SYSADMIN,
                risk_level=RiskLevel.LOW,
                version="1.0.0",
                description="Test tool",
                cmd="missing.cmd",
                prerequisites=[
                    PrerequisiteEnv(binary="nonexistent_virtual_binary_999", min_version="9.9.9")
                ],
            )

    missing_tool = MissingPrereqTool()
    res_missing = missing_tool.execute()
    tests.append((
        "missing_prereq_err_block",
        not res_missing["success"]
        and res_missing["exit_code"] == 126
        and "ERR_PREREQUISITE_MISSING" in res_missing["stderr"]
        and "err_block" in res_missing
    ))

    # Test 11: Anti-privilege escalation blocks modifying tool under read-only tier
    res_auth = pwsh_tool.execute(context={"tier": "read-only"})
    tests.append((
        "anti_privilege_escalation_read_only",
        not res_auth["success"]
        and res_auth["exit_code"] == 126
        and "ERR_PERMISSION_DENIED" in res_auth["stderr"]
    ))

    # Test 12: Read-only tool permitted under read-only tier
    ok_auth_scribe, err_auth_scribe = scribe_tool.assert_authorization("read-only")
    tests.append(("read_only_tool_permitted_under_read_only", ok_auth_scribe and err_auth_scribe is None))

    # Test 13: Class extensibility - custom tool subclassing BaseTool and registering
    class CustomTelemetryTool(BaseTool):
        def __init__(self):
            super().__init__(
                tool_id="custom_telemetry",
                name="Custom Telemetry Extension",
                category=ToolCategory.POLICY_RADAR,
                risk_level=RiskLevel.READ_ONLY,
                version="2.0.0",
                description="User custom extension tool",
                cmd="scribe.cmd",
            )

    custom_instance = TOOL_REGISTRY.register(CustomTelemetryTool)
    tests.append((
        "class_extensibility_registration",
        TOOL_REGISTRY.get("custom_telemetry") is not None
        and TOOL_REGISTRY.get("custom_telemetry").version == "2.0.0"
    ))

    # Test 11: Containment refuses a target outside the sandbox
    _probe = TOOL_REGISTRY.get("scribe")
    outside_target = str(Path(os.environ.get("SystemRoot") or "/outside_sandbox").resolve() / "System32" / "cmd.exe")
    _ok_out, _ = _probe.assert_target_contained(outside_target)
    tests.append(("containment_refuses_outside", not _ok_out))

    # Test 12: Containment allows the declared launcher
    _declared = _probe.resolve_executable()
    _ok_in, _ = _probe.assert_target_contained(_declared) if _declared else (False, None)
    tests.append(("containment_allows_declared", bool(_ok_in)))

    # Test 13: HostEnvPerceiver probes all 6 runtimes dynamically without hardcoded paths
    probe_map = HostEnvPerceiver.probe_all()
    tests.append((
        "host_env_perceiver_dynamic_probe",
        isinstance(probe_map, dict)
        and len(probe_map) == 6
        and probe_map["python"]["located"] is True
    ))

    # Test 14: ExecutionEnvelope strictly isolates parent secrets (unidirectional sanitization)
    old_token = os.environ.get("SENSITIVE_LEAK_TOKEN")
    try:
        os.environ["SENSITIVE_LEAK_TOKEN"] = "stolen_session_secret"
        env_envelope = ExecutionEnvelope.from_context({"tier": "auto", "custom_env": {"EXPLICIT_SAFE": "1"}})
        sanitized_env = env_envelope.build_subprocess_env()
        tests.append((
            "execution_envelope_secret_isolation",
            "SENSITIVE_LEAK_TOKEN" not in sanitized_env
            and sanitized_env.get("EXPLICIT_SAFE") == "1"
            and sanitized_env.get("PYTHONUTF8") == "1"
            and "PATH" in sanitized_env
        ))
    finally:
        if old_token is not None:
            os.environ["SENSITIVE_LEAK_TOKEN"] = old_token
        else:
            os.environ.pop("SENSITIVE_LEAK_TOKEN", None)

    # Test 15: ExecutionEnvelope unidirectional parameter bounds
    bounded_envelope = ExecutionEnvelope.from_context({"timeout": 999999, "tier": " READ-ONLY "})
    tests.append((
        "execution_envelope_param_bounds",
        bounded_envelope.timeout == 3600
        and bounded_envelope.tier == "read-only"
    ))

    # Test 16: HostEnvPerceiver renders radar telemetry HUD and JSON
    radar_text = HostEnvPerceiver.render_radar()
    radar_json = HostEnvPerceiver.render_radar(as_json=True)
    tests.append((
        "host_env_perceiver_radar_hud",
        "DSHA EnvFeel" in radar_text
        and "v1.1.0-std" in radar_text
        and isinstance(json.loads(radar_json), dict)
    ))

    # Test 17: Standard response envelope always includes envfeel payload
    res_feel_check = Call_Tools("scribe", ["status"], {"timeout": 10})
    tests.append((
        "standard_response_envelope_envfeel",
        "envfeel" in res_feel_check
        and "status" in res_feel_check["envfeel"]
        and "platform" in res_feel_check["envfeel"]
    ))

    # Test 18: Forward execution generates trace_receipt with 7-stage records
    res_trace_check = Call_Tools("scribe", ["status"], {"timeout": 10})
    tests.append((
        "trace_receipt_forward_success",
        "trace_receipt" in res_trace_check
        and res_trace_check["trace_receipt"]["status"] == "PASS"
        and len(res_trace_check["trace_receipt"]["stages"]) >= 6
    ))

    # Test 19: Retrace engine walks backward from Stage 7 to Stage 1
    retrace_text = retrace(res_trace_check)
    tests.append((
        "trace_receipt_reverse_retrace",
        "逆向调用链回溯" in retrace_text
        and "7/7: 响应封套封装" in retrace_text
        and "1/7: 入口封套校验" in retrace_text
        and "依契约复现命令" in retrace_text
    ))

    # Test 20: Retrace on prerequisite missing failure isolates Stage 3 failure
    res_missing_trace = missing_tool.execute()
    retrace_missing = retrace(res_missing_trace)
    tests.append((
        "trace_receipt_retrace_prereq_failure",
        "ERR_PREREQUISITE_MISSING" in retrace_missing
        and "3/7: 宿主环境自感知" in retrace_missing
        and "❌ [FAIL]" in retrace_missing
    ))

    # Test 21: Retrace on authorization failure isolates Stage 4 failure
    res_auth_trace = pwsh_tool.execute(context={"tier": "read-only"})
    retrace_auth = retrace(res_auth_trace)
    tests.append((
        "trace_receipt_retrace_auth_failure",
        "ERR_PERMISSION_DENIED" in retrace_auth
        and "4/7: 权限档位核验" in retrace_auth
        and "❌ [FAIL]" in retrace_auth
    ))

    # Test 22: TraceStore persistence and retrieval by trace_id
    tid_sample = res_trace_check["trace_id"]
    loaded_trace = TraceStore.get(tid_sample)
    tests.append((
        "trace_store_persistence",
        loaded_trace is not None
        and loaded_trace.get("trace_id") == tid_sample
        and loaded_trace.get("status") == "PASS"
    ))

    # Test 23: Open Protocol Schema dump
    schema_dump = dump_open_protocol_schema()
    tests.append((
        "open_protocol_schema_dump",
        isinstance(schema_dump, dict)
        and schema_dump.get("title") == "DSHA Open Protocol Specification (v1.2.0-std)"
        and "DSHARequest" in schema_dump.get("definitions", {})
        and "DSHAResponse" in schema_dump.get("definitions", {})
        and "TraceReceipt" in schema_dump.get("definitions", {})
    ))

    passed = sum(1 for _, ok in tests if ok)
    total = len(tests)
    print(f"selftest: {passed}/{total}")
    for name, ok in tests:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    return passed == total


def main():
    parser = argparse.ArgumentParser(description="DSHA BaseTool & Prerequisite Environment Architecture")
    subparsers = parser.add_subparsers(dest="subcmd", help="Subcommand")

    # list
    list_p = subparsers.add_parser("list", help="List registered tools")
    list_p.add_argument("-c", "--category", help="Filter by category (WebEdge, Archivist, etc.)")
    list_p.add_argument("--json", action="store_true", help="Output in JSON format")

    # categories
    subparsers.add_parser("categories", help="List all tool categories")

    # check
    check_p = subparsers.add_parser("check", help="Check prerequisite environments")
    check_p.add_argument("tool", nargs="?", help="Tool ID to check (optional)")

    # feel
    feel_p = subparsers.add_parser("feel", help="Display host environment perception radar HUD")
    feel_p.add_argument("tool", nargs="?", help="Specific tool ID to inspect (optional)")
    feel_p.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    # trace
    trace_p = subparsers.add_parser("trace", help="Inspect execution trace receipt by trace_id")
    trace_p.add_argument("trace_id", help="Trace ID to inspect")
    trace_p.add_argument("--json", action="store_true", help="Output trace in JSON format")

    # retrace
    retrace_p = subparsers.add_parser("retrace", help="Reverse causal trace walk from Stage 7 to Stage 1")
    retrace_p.add_argument("target", help="Trace ID or JSON file path to retrace")
    retrace_p.add_argument("--json", action="store_true", help="Output retrace analysis in JSON format")

    # schema
    subparsers.add_parser("schema", help="Output official Open Protocol JSON Schema")

    # selftest
    subparsers.add_parser("selftest", help="Run automated unit tests")

    args = parser.parse_args()

    if args.subcmd == "selftest":
        ok = run_selftest()
        sys.exit(0 if ok else 1)

    if args.subcmd == "schema":
        print(json.dumps(dump_open_protocol_schema(), ensure_ascii=False, indent=2))
        return 0

    if args.subcmd == "trace":
        data = TraceStore.get(args.trace_id)
        if not data:
            print(f"Error: Trace '{args.trace_id}' not found.", file=sys.stderr)
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.subcmd == "retrace":
        out = retrace(args.target, as_json=getattr(args, "json", False))
        print(out)
        return 0

    if args.subcmd == "feel":
        out = HostEnvPerceiver.render_radar(tool_id=getattr(args, "tool", None), as_json=getattr(args, "json", False))
        print(out)
        return 0

    if args.subcmd == "categories":
        for cat in TOOL_REGISTRY.list_categories():
            count = len(TOOL_REGISTRY.get_by_category(cat))
            print(f"  • {cat.ljust(22)} ({count} tools)")
        return 0

    if args.subcmd == "check":
        tools_to_check = [TOOL_REGISTRY.get(args.tool)] if args.tool else list(TOOL_REGISTRY.all().values())
        all_ok = True
        for t in tools_to_check:
            if not t:
                print(f"Tool '{args.tool}' not found.", file=sys.stderr)
                return 1
            ok, err = t.assert_environment()
            if ok:
                print(f"  [PASS] [{t.category.value}] {t.name} (id: {t.id}) - All prerequisites satisfied.")
            else:
                all_ok = False
                print(err.format_cli())
        return 0 if all_ok else 1

    if args.subcmd == "list" or not args.subcmd:
        tools = list(TOOL_REGISTRY.all().values())
        if getattr(args, "category", None):
            tools = TOOL_REGISTRY.get_by_category(args.category)

        if getattr(args, "json", False):
            print(json.dumps([t.to_dict() for t in tools], ensure_ascii=False, indent=2))
            return 0

        print(f"=== 🛠️ DSHA 工具类目与环境声明清单 ({len(tools)} 工具) ===")
        print(f"| {'标识'.ljust(8)} | {'类目'.ljust(20)} | {'工具名称'.ljust(30)} | {'风险等级'.ljust(10)} | {'依赖环境'} |")
        print(f"|{'-'*10}|{'-'*22}|{'-'*32}|{'-'*12}|{'-'*20}|")
        for t in tools:
            prereq_str = ", ".join([p.binary for p in t.prerequisites]) or "none"
            print(f"| {t.id.ljust(8)} | {t.category.value.ljust(20)} | {t.name.ljust(30)} | {t.risk_level.value.ljust(10)} | {prereq_str} |")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

