# ============================================================================
# OpenTerminalUI — локальный установщик для Windows (PowerShell).
#
#   ./install.ps1
#
# Создаёт .env, генерирует секреты и пароль администратора, устанавливает
# Python-зависимости, собирает frontend и запускает сервер на
# http://localhost:8000.
# ============================================================================
$ErrorActionPreference = "Stop"

$RootDir = $PSScriptRoot
Set-Location $RootDir
$EnvFile = Join-Path $RootDir ".env"
$Port = if ($env:APP_PORT) { $env:APP_PORT } else { "8000" }

function Write-Cyan($m)  { Write-Host $m -ForegroundColor Cyan }
function Write-Green($m) { Write-Host $m -ForegroundColor Green }
function Write-Yellow($m){ Write-Host $m -ForegroundColor Yellow }

function Get-PyBin {
  foreach ($c in @("python", "python3", "py")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { return $c }
  }
  return $null
}

function New-Secret {
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

function Get-EnvVar($key) {
  if (-not (Test-Path $EnvFile)) { return "" }
  $line = Select-String -Path $EnvFile -Pattern "^$key=" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($line) { return ($line.Line -replace "^$key=", "") }
  return ""
}

function Set-EnvVar($key, $value) {
  $content = if (Test-Path $EnvFile) { Get-Content $EnvFile } else { @() }
  if ($content -match "^$key=") {
    $content = $content | ForEach-Object { if ($_ -match "^$key=") { "$key=$value" } else { $_ } }
  } else {
    $content += "$key=$value"
  }
  Set-Content -Path $EnvFile -Value $content
}

function Initialize-EnvVar($key, $value) {
  if ([string]::IsNullOrEmpty((Get-EnvVar $key))) { Set-EnvVar $key $value }
}

Write-Cyan "==> Установщик OpenTerminalUI (Windows)"

$PyBin = Get-PyBin
if (-not $PyBin) { Write-Yellow "    Python не найден; установите Python 3.11+"; exit 1 }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Yellow "    npm не найден; установите Node 20+"; exit 1 }

Write-Green "    обнаружена ОС: windows  (python: $PyBin)"

# --- 1. Создание .env -------------------------------------------------------
if (-not (Test-Path $EnvFile)) {
  Copy-Item (Join-Path $RootDir ".env.example") $EnvFile
  Write-Green "    создан .env из .env.example"
} else {
  Write-Yellow "    .env уже существует - сохраняем значения, заполняем пустые поля"
}

# --- 2. Генерация секретов и администратора ---------------------------------
Initialize-EnvVar "JWT_SECRET_KEY"    (New-Secret)
Initialize-EnvVar "CACHE_SIGNING_KEY" (New-Secret)
Initialize-EnvVar "BOOTSTRAP_ADMIN_EMAIL" "admin@openterminal.local"

$AdminPass = Get-EnvVar "BOOTSTRAP_ADMIN_PASSWORD"
if ([string]::IsNullOrEmpty($AdminPass)) {
  $AdminPass = (New-Secret).Substring(0, 20)
  Set-EnvVar "BOOTSTRAP_ADMIN_PASSWORD" $AdminPass
}
$AdminEmail = Get-EnvVar "BOOTSTRAP_ADMIN_EMAIL"
Write-Green "    секреты и учётная запись администратора настроены"

# --- 3. Установка зависимостей и сборка frontend ----------------------------
Write-Green "    настройка Python-бэкенда..."
if (-not (Test-Path (Join-Path $RootDir ".venv"))) { & $PyBin -m venv (Join-Path $RootDir ".venv") }
$VenvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
& $VenvPy -m pip install --quiet --upgrade pip
& $VenvPy -m pip install --quiet -r (Join-Path $RootDir "backend\requirements.txt")

Write-Green "    сборка frontend..."
Push-Location (Join-Path $RootDir "frontend"); & npm ci; & npm run build; Pop-Location

# --- 4. Миграции и создание администратора ----------------------------------
Write-Green "    выполнение миграций базы данных..."
$env:PYTHONPATH = $RootDir
& $VenvPy -m alembic -c (Join-Path $RootDir "backend\alembic.ini") upgrade head

Write-Green "    создание учётной записи администратора..."
& $VenvPy (Join-Path $RootDir "scripts\seed_admin.py")

function Show-Credentials {
  Write-Host ""
  Write-Green "============================================================"
  Write-Green " OpenTerminalUI готов -> http://localhost:$Port"
  Write-Green "------------------------------------------------------------"
  Write-Green "  Войдите, используя:"
  Write-Green "    email:    $AdminEmail"
  Write-Green "    password: $AdminPass"
  Write-Green "  (также сохранено в .env - смените пароль после первого входа)"
  Write-Green "============================================================"
  Write-Host ""
  Write-Cyan "  Добавить API-ключи: ./scripts/setup-keys.sh"
}

Show-Credentials
Start-Process "http://localhost:$Port"
Write-Green "    запуск сервера на http://localhost:$Port (Ctrl+C для остановки)..."
& $VenvPy -m uvicorn backend.main:app --host 0.0.0.0 --port $Port
