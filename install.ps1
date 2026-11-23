# DSHA 安装器（幂等 · 带备份 · 可回滚）
#
#   pwsh -File install.ps1                      # 插件默认 read-only；原生宿主权限须另行同步
#   pwsh -File install.ps1 -EnableHook          # 同时启用工程锁钩子（写类工具机械校验）
#   pwsh -File install.ps1 -Strict              # 工程锁置严格模式（L5/L6/L9.1 直接拒绝）
#   pwsh -File install.ps1 -WhatIfOnly          # 只检查环境与将要做的动作，不改任何文件
#   pwsh -File install.ps1 -Uninstall           # 卸载（从备份恢复）

[CmdletBinding()]
param(
  [ValidateSet('read-only', 'workspace-write', 'danger-full-access', 'auto')]
  [string]$Tier = 'read-only',        # 对新用户采用保守的插件档位；不代表原生宿主已同步
  [switch]$KeepTier,                      # 保留现有档位，不覆盖
  [switch]$EnableHook,
  [switch]$Strict,
  [switch]$WhatIfOnly,
  [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfg   = Join-Path $env:USERPROFILE '.gemini\config'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$bak   = Join-Path $cfg "_rollback\DSHA_$stamp"

function Say($m){ Write-Host "[DSHA] $m" }
function Step($m){ Write-Host "`n=== $m ===" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 卸载
if ($Uninstall) {
  Step "卸载"
  $rec = Get-ChildItem (Join-Path $cfg '_rollback') -Directory -Filter 'DSHA_*' -ErrorAction SilentlyContinue |
         Sort-Object Name -Descending | Select-Object -First 1
  if (-not $rec) { Say "找不到任何 DSHA_* 备份，无法自动卸载。请手动删除 plugins\dsh-permissions 与 skills\DSHA。"; exit 1 }
  Say "从最近备份恢复：$($rec.FullName)"
  Get-ChildItem $rec.FullName -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($rec.FullName.Length + 1)
    $dst = Join-Path $cfg $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item $_.FullName $dst -Force
    Say "  恢复 $rel"
  }
  # 备份里不存在的（本次新增）→ 删除
  $lockDir = Join-Path $cfg 'plugins\dsha-englock'
  if (Test-Path $lockDir) { Remove-Item $lockDir -Recurse -Force; Say '  删除独立插件 plugins\dsha-englock' }
  $cfgPath = Join-Path $cfg 'config.json'
  if (Test-Path $cfgPath) {
    try {
      $conf = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json
      if ($conf.plugins -and $conf.plugins.'dsha-englock') {
        $conf.plugins.PSObject.Properties.Remove('dsha-englock')
        ($conf | ConvertTo-Json -Depth 40) | Set-Content -Encoding utf8 $cfgPath
        Say '  从 config.json 注销 dsha-englock'
      }
    } catch { }
  }
  $pjPath = Join-Path $cfg 'plugins.json'
  if (Test-Path $pjPath) {
    try {
      $pj = Get-Content $pjPath -Raw -Encoding utf8 | ConvertFrom-Json
      $keep = @($pj.entries | Where-Object { $_.path -ne $lockDir })
      ([pscustomobject]@{ entries = $keep } | ConvertTo-Json -Depth 10) | Set-Content -Encoding utf8 $pjPath
      Say "  plugins.json 剩余 $($keep.Count) 条"
    } catch { }
  }
  foreach ($f in @("plugins\dsh-permissions\scripts\englock.py","plugins\dsh-permissions\scripts\englock.cmd",
                   "plugins\dsh-permissions\englock.json","plugins\dsh-permissions\lexicon.json",
                   "plugins\dsh-permissions\hooks.englock.example.json",
                   "skills\DSHA\engineering-lock.md","skills\DSHA\language-norm.md")) {
    $p = Join-Path $cfg $f
    if ((Test-Path $p) -and -not (Test-Path (Join-Path $rec.FullName $f))) { Remove-Item $p -Force; Say "  删除新增文件 $f" }
  }
  Say "卸载完成。若 hooks.json 被改过，已一并恢复。"
  exit 0
}

# ---------------------------------------------------------------- 0. 环境检查
Step "0/6 环境检查"
$pyExe = $null
$cands = @(
  (Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
  'C:\python312\python.exe',
  (Get-Command python.exe -ErrorAction SilentlyContinue).Source,
  (Get-Command py.exe -ErrorAction SilentlyContinue).Source
)
foreach ($cand in $cands) {
  if ($cand -and (Test-Path $cand)) {
    try { $v = & $cand -c "import sys;print(sys.version.split()[0])" 2>$null; if ($v) { $pyExe = $cand; $pyVer = $v; break } } catch {}
  }
}
if (-not $pyExe) { Say "❌ 找不到可用的 Python 解释器。请安装 Python 3.10+ 并加入 PATH 后重试。"; exit 1 }
Say "Python：$pyExe （$pyVer）"

$agDir = Join-Path $env:LOCALAPPDATA 'Programs\antigravity'
if (Test-Path $agDir) { Say "Antigravity：已安装（$agDir）" } else { Say "⚠ 未在默认路径找到 Antigravity；若装在别处，本插件仍可用，只是档位切换脚本的重启路径需自行确认。" }
# -WhatIfOnly must exit before ANY write, including creating ~/.gemini/config.
if ($WhatIfOnly) {
  Say "— WhatIfOnly：以下动作将被执行（本次不改动任何文件）"
  Say "  备份到：$bak"
  Say "  复制 plugins\dsh-permissions → $cfg\plugins\dsh-permissions"
  Say "  复制 skills\DSHA          → $cfg\skills\DSHA"
  Say "  复制 bin\agy-*.ps1        → $cfg\"
  Say "  用 $pyExe 重写 run-gate.cmd / englock.cmd（消除硬编码路径）"
  Say "  请求的插件档位：$Tier；-KeepTier 将在安装时优先保留已有档位（若存在）"
  Say "  注意：预演不会修改原生宿主设置；正式安装也不会自动切换 Antigravity 原生权限"
  Say "  工程锁模式：$(if($Strict){'strict'}else{'advisory'})；-EnableHook=$(if($EnableHook){'on'}else{'off'})"
  exit 0
}

# Capture the current tier BEFORE robocopy overwrites the installed template.
$previousTier = $null
$priorTierPath = Join-Path $cfg 'plugins\dsh-permissions\tier.json'
if ($KeepTier -and (Test-Path -LiteralPath $priorTierPath)) {
  try {
    $candidate = (Get-Content -LiteralPath $priorTierPath -Raw -Encoding utf8 | ConvertFrom-Json).tier
    if (@('read-only','workspace-write','danger-full-access','auto') -notcontains $candidate) {
      throw "unsupported saved tier: $candidate"
    }
    $previousTier = $candidate
  } catch { throw "无法保留当前权限档位；现有 tier.json 无效：$_" }
}
$effectiveTier = if ($null -ne $previousTier) { $previousTier } else { $Tier }

# ---------------------------------------------------------------- 1. 备份
Step "1/6 备份现有配置"
New-Item -ItemType Directory -Force -Path "$bak\plugins\dsh-permissions\scripts","$bak\plugins\dsh-permissions\rules","$bak\skills\DSHA" | Out-Null
foreach ($f in @('plugins\dsh-permissions\hooks.json','plugins\dsh-permissions\plugin.json',
                 'plugins\dsh-permissions\tier.json','plugins\dsh-permissions\rules\AGENTS.md',
                 'plugins\dsh-permissions\scripts\gate.py','plugins\dsh-permissions\README.md',
                 'skills\DSHA\SKILL.md','skills\DSHA\reference.md','skills\DSHA\widget.html',
                 'agy-tier.ps1','agy-verify.ps1','agy-audit.ps1')) {
  $src = Join-Path $cfg $f
  if (Test-Path $src) {
    $dst = Join-Path $bak $f
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item $src $dst -Force
  }
}
Say "已备份到 $bak"

# ---------------------------------------------------------------- 2. 插件
Step "2/6 安装插件（权限档位 + 工程锁 + 额度监视器）"
New-Item -ItemType Directory -Force -Path "$cfg\plugins","$cfg\skills" | Out-Null
robocopy (Join-Path $root 'plugins\dsh-permissions') "$cfg\plugins\dsh-permissions" /E /XD logs __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null

# D1/D41H 修复：保持 scripts\ 为单一事实源，安装时闭包分发所有运行时依赖脚本
foreach ($pyFile in @('base_tool.py','index.py','router.py','dsha_cf.py','scribe.py','test_skill_integration.py')) {
  $from = Join-Path $root "scripts\$pyFile"
  if (Test-Path $from) {
    Copy-Item $from "$cfg\plugins\dsh-permissions\scripts\$pyFile" -Force
    Say "scripts\$pyFile → plugins\dsh-permissions\scripts\"
  }
}
Say "插件已就位：$cfg\plugins\dsh-permissions"
if (Test-Path (Join-Path $root 'plugins\dsha-meter')) {
  robocopy (Join-Path $root 'plugins\dsha-meter') "$cfg\plugins\dsha-meter" /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
  Say "插件已就位：$cfg\plugins\dsha-meter"
}

# ---------------------------------------------------------------- 3. 技能
Step "3/6 安装技能（DSHA 核心 + REA 逆向套件）"
robocopy (Join-Path $root 'skills\DSHA') "$cfg\skills\DSHA" /E /NFL /NDL /NJH /NJS /NP | Out-Null
Say "技能已就位：$cfg\skills\DSHA"
if (Test-Path (Join-Path $root 'skills\reverse-engineer-anything')) {
  robocopy (Join-Path $root 'skills\reverse-engineer-anything') "$cfg\skills\reverse-engineer-anything" /E /XD node_modules /NFL /NDL /NJH /NJS /NP | Out-Null
  Say "技能已就位：$cfg\skills\reverse-engineer-anything"
}

# ---------------------------------------------------------------- 4. 档位切换器与工具链
Step "4/6 安装档位切换器与工具链（含防咬人 Shell 与 REA 启动器）"
Copy-Item (Join-Path $root 'bin\agy-tier.ps1')   "$cfg\agy-tier.ps1"   -Force
Copy-Item (Join-Path $root 'bin\agy-verify.ps1') "$cfg\agy-verify.ps1" -Force
Copy-Item (Join-Path $root 'bin\agy-audit.ps1')  "$cfg\agy-audit.ps1"  -Force
if (Test-Path (Join-Path $root 'bin\agy-meter.ps1')) {
  Copy-Item (Join-Path $root 'bin\agy-meter.ps1') "$cfg\agy-meter.ps1" -Force
  Say "agy-meter.ps1 → $cfg"
}
foreach ($cmd in @('bash.cmd','sh.cmd','dsha-sh.cmd','rea.cmd','pwsh.cmd','dsha-pwsh.cmd')) {
  $f = Join-Path $root "bin\$cmd"
  if (Test-Path $f) { Copy-Item $f "$cfg\$cmd" -Force; Say "$cmd → $cfg" }
}
Say "agy-tier.ps1 / agy-verify.ps1 / agy-audit.ps1 → $cfg"

# 引入 DSHA 专用 Pwsh 运行时（彻底摆脱 Win 原厂 PowerShell 5.1）
$localPwsh = Join-Path $root 'bin\pwsh'
$cfgPwsh = Join-Path $cfg 'pwsh'
if (-not (Test-Path "$localPwsh\pwsh.exe")) {
  Say "未检测到本地专用 Pwsh，尝试从镜像拉取..."
  try { & (Join-Path $root 'scripts\fetch-pwsh.ps1') -TargetDir $localPwsh } catch {}
}
if (Test-Path "$localPwsh\pwsh.exe") {
  New-Item -ItemType Directory -Force -Path $cfgPwsh | Out-Null
  robocopy $localPwsh $cfgPwsh /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
  Say "DSHA 专用 Pwsh 7 运行时已就位：$cfgPwsh\pwsh.exe"
}

# 注册 PATH 环境变量（优先 DSHA 专用工具与 Pwsh）
try {
  $uPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $addList = @($cfgPwsh, $cfg, (Join-Path $root 'bin'))
  $curList = $uPath -split ';' | Where-Object { $_ -ne '' }
  foreach ($ad in $addList) {
    if ($curList -notcontains $ad) {
      $curList = @($ad) + $curList
    }
  }
  $nPath = $curList -join ';'
  [Environment]::SetEnvironmentVariable("Path", $nPath, "User")
  $env:Path = "$nPath;$env:Path"
  Say "User PATH 已注册：优先指向 DSHA 专用 Pwsh 与安全 Shell"
} catch {}

# 合规 Shell 环境保障（防咬人 Shell 与执行策略）
try {
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force -ErrorAction SilentlyContinue
  Say "执行策略：CurrentUser = RemoteSigned"
} catch {}

# ---------------------------------------------------------------- 5. 可移植化：重写 .cmd
Step "5/6 生成钩子包装器（消除硬编码 Python 路径）"
$pScripts = "$cfg\plugins\dsh-permissions\scripts"
@"
@echo off
rem Generated by DSHA install.ps1 -- interpreter resolved at install time.
rem ASCII only, no leading quote, stderr discarded.
"$pyExe" "%~dp0gate.py" 2>nul
exit /b %ERRORLEVEL%
"@ | Set-Content -Encoding ascii (Join-Path $pScripts 'run-gate.cmd')
@"
@echo off
rem Generated by DSHA install.ps1 -- fail-open: always exit 0.
"$pyExe" "%~dp0englock.py" 2>nul
exit /b 0
"@ | Set-Content -Encoding ascii (Join-Path $pScripts 'englock.cmd')
Say "run-gate.cmd / englock.cmd 已指向 $pyExe"

# 工程锁模式
$mode = if ($Strict) { 'strict' } else { 'advisory' }
@{ mode = $mode; log = $true; report_path_hints = @('documents_md','报告','report') } |
  ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 "$cfg\plugins\dsh-permissions\englock.json"
Say "工程锁模式：$mode"

# Plugin tier state (host native permissions are NOT synchronized here).
$tierFile = "$cfg\plugins\dsh-permissions\tier.json"
@{ tier = $effectiveTier; auto_reviewer = 'local'; audit_logging = $true; log_allow = $false } |
  ConvertTo-Json | Set-Content -Encoding utf8 $tierFile
Say "插件权限档位：$effectiveTier $(if ($null -ne $previousTier) {'(-KeepTier preserved)'} else {''})"
if ($effectiveTier -eq 'danger-full-access') {
  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Yellow
  Write-Host "   ⚠  你已显式选择或保留 danger-full-access（全权）" -ForegroundColor Yellow
  Write-Host "  ============================================================" -ForegroundColor Yellow
  Write-Host "   · 终端命令不再有任何拦截；工作区外与联网全部 ALLOW；不弹审批" -ForegroundColor Yellow
  Write-Host "   · 没有沙箱、没有模型审查，兜底的只有你自己" -ForegroundColor Yellow
  Write-Host "   · 全权不再是新安装的默认值：详见 默认全权警告.md" -ForegroundColor Yellow
  Write-Host "   · 想立刻降档： agy-tier.ps1 read-only -Yes   （即时生效）" -ForegroundColor Yellow
  Write-Host "   · 想改为保守插件档位： .\install.ps1 -Tier read-only" -ForegroundColor Yellow
  Write-Host "   · 想保留现有档位： .\install.ps1 -KeepTier" -ForegroundColor Yellow
  Write-Host "  ============================================================" -ForegroundColor Yellow
  Write-Host ""
}

# 钩子（权限档位）：只挂 gate，工程锁交给独立插件
$gateCmd = Join-Path $pScripts 'run-gate.cmd'
# 权限钩子是否开，取决于档位：read-only / auto 由钩子承担（开），
# workspace-write / danger-full-access 由原生开关承担（关）。别和 agy-tier.ps1 抢所有权。
$curTier = if (Test-Path "$cfg\plugins\dsh-permissions\tier.json") {
  (Get-Content "$cfg\plugins\dsh-permissions\tier.json" -Raw -Encoding utf8 | ConvertFrom-Json).tier
} else { 'read-only' }
$gateOn = ($curTier -eq 'read-only' -or $curTier -eq 'auto')
$gateHooks = [ordered]@{
  'dsh-permissions' = [ordered]@{
    enabled    = [bool]$gateOn
    PreToolUse = @([ordered]@{
      matcher = '.*'
      hooks   = @([ordered]@{ type = 'command'; command = $gateCmd; timeout = 10 })
    })
  }
}
$gateHooks | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 "$cfg\plugins\dsh-permissions\hooks.json"
Say "权限钩子：enabled=$([bool]$gateOn)（插件档位 $curTier；不是原生设置的证明）"

# 独立工程锁插件：不寄生在 dsh-permissions —— agy-tier.ps1 每次切档都会重写那个目录的
# hooks.json（全权档会关掉钩子），工程锁一旦寄生，换个档位就失效。
$lockDir = "$cfg\plugins\dsha-englock"
$engScript = Join-Path $pScripts 'englock.py'
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
@"
@echo off
rem DSHA Engineering Lock (independent plugin). ASCII only, fail-open, always exit 0.
"$pyExe" "$engScript" 2>nul
exit /b 0
"@ | Set-Content -Encoding ascii (Join-Path $lockDir 'run-englock.cmd')
@{ name = 'DSHA-EngLock' } | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $lockDir 'plugin.json')
$lockHooks = [ordered]@{
  'dsha-englock' = [ordered]@{
    enabled    = [bool]$EnableHook
    PreToolUse = @([ordered]@{
      matcher = 'write_to_file|replace_file_content|create_file|apply_patch'
      hooks   = @([ordered]@{ type = 'command'; command = (Join-Path $lockDir 'run-englock.cmd'); timeout = 10 })
    })
  }
}
$lockHooks | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $lockDir 'hooks.json')
Say "独立工程锁插件：$lockDir（enabled=$([bool]$EnableHook)）"

# DSHA-Meter 包装器生成
$pywExe = Join-Path (Split-Path $pyExe) 'pythonw.exe'
if (-not (Test-Path $pywExe)) { $pywExe = $pyExe }
$meterDir = "$cfg\plugins\dsha-meter"
if (Test-Path $meterDir) {
@"
@echo off
rem Generated by DSHA install.ps1 -- portable background launcher
start "" "$pywExe" "%~dp0meter.py"
exit /b 0
"@ | Set-Content -Encoding ascii (Join-Path $meterDir 'run-meter.cmd')
  Say "run-meter.cmd 已指向 $pywExe"
}

# 注册插件：config.json 的 plugins.<目录名>.enabled
$cfgPath = "$cfg\config.json"
if (Test-Path $cfgPath) {
  $conf = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json
  $map = [ordered]@{}
  if ($conf.plugins) { foreach ($x in $conf.plugins.PSObject.Properties) { $map[$x.Name] = $x.Value } }
  $map['dsh-permissions'] = [ordered]@{ enabled = $true }
  $map['dsha-englock']    = [ordered]@{ enabled = $true }
  if (Test-Path $meterDir) {
    $map['dsha-meter']    = [ordered]@{ enabled = $true }
  }
  $conf | Add-Member -NotePropertyName plugins -NotePropertyValue ([pscustomobject]$map) -Force
  ($conf | ConvertTo-Json -Depth 40) | Set-Content -Encoding utf8 $cfgPath
  Say "config.json：插件均已 enable"
}
$pjPath = "$cfg\plugins.json"
if (Test-Path $pjPath) {
  $pj = Get-Content $pjPath -Raw -Encoding utf8 | ConvertFrom-Json
  $entries = @($pj.entries)
  $pluginDirs = @("$cfg\plugins\dsh-permissions", $lockDir)
  if (Test-Path $meterDir) { $pluginDirs += $meterDir }
  foreach ($d in $pluginDirs) {
    if (-not ($entries | Where-Object { $_.path -eq $d })) { $entries += [pscustomobject]@{ path = $d } }
  }
  ([pscustomobject]@{ entries = $entries } | ConvertTo-Json -Depth 10) | Set-Content -Encoding utf8 $pjPath
  Say "plugins.json：已注册 $($entries.Count) 条路径"
}

# ---------------------------------------------------------------- 6. 自检
Step "6/6 安装后自检"
& $pyExe "$pScripts\selftest.py" 2>$null | Select-String -Pattern 'pass=|fail=' | Select-Object -Last 1
& $pyExe "$pScripts\englock.py" selftest | Select-Object -Last 1
$agents = "$cfg\plugins\dsh-permissions\rules\AGENTS.md"
if (Test-Path $agents) {
  $bytes = [System.IO.File]::ReadAllBytes($agents); $bad = ($bytes | Where-Object { $_ -gt 127 }).Count
  Say "rules\AGENTS.md：$($bytes.Length) 字节，非 ASCII $bad 个 $(if($bad -eq 0){'✅'}else{'⚠ 应为 0'})"
}
Say "`n安装完成（仅插件档位已写入；原生 Antigravity 权限尚未同步）。"
Say "请先阅读 默认全权警告.md，确认会中断/重启宿主后再执行："
Say "  pwsh -NoProfile -File `"$cfg\agy-tier.ps1`" $effectiveTier -Yes"
Say "切换后核验： pwsh -NoProfile -File `"$cfg\agy-tier.ps1`" -Status"
Say "回滚： pwsh -File `"$($MyInvocation.MyCommand.Path)`" -Uninstall"
Say "备份位置：$bak"
