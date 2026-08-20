<#
    .SINOPSIS
    Reproduce en local, en el mismo orden, exactamente lo que corre el CI.

    .DESCRIPCION
    No se detiene en el primer fallo: ejecuta los cinco pasos (lint, formato,
    tests, arranque del sistema completo y hardening de producción) y acumula
    los resultados para resumirlos al final. Pensado para correr antes de cada
    commit, desde cualquier directorio.

    El paso de arranque es el que suele olvidarse al verificar a mano, y es
    justamente el que detecta lo que ningún test cubre: que la API levante, que
    la interfaz sirva y que el ingreso devuelva un token.

    .EJEMPLO
    powershell -File scripts\verificar.ps1
#>

$ErrorActionPreference = "Continue"

# Raíz del subproyecto: el padre de la carpeta donde vive este script, sin
# importar desde dónde se invoque.
$raizProyecto = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raizProyecto ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No se encontró el intérprete en $python. ¿Existe .venv y se instalaron las dependencias?" -ForegroundColor Red
    exit 1
}

$directorioLogs = Join-Path $env:TEMP "arriendos-verificar"
New-Item -ItemType Directory -Force -Path $directorioLogs | Out-Null

$script:pasos = @()
$script:fallidos = @()

function Ejecutar-Paso {
    param(
        [Parameter(Mandatory = $true)][string]$Nombre,
        [Parameter(Mandatory = $true)][string[]]$Argumentos,
        [hashtable]$VariablesEntorno = @{}
    )

    Write-Host ""
    Write-Host "== $Nombre ==" -ForegroundColor Cyan

    $nombreArchivo = ($Nombre -replace '[^a-zA-Z0-9]+', '-').Trim('-')
    $logPath = Join-Path $directorioLogs "$nombreArchivo.log"

    # Variables de entorno propias del paso: se restauran al terminar para no
    # contaminar los pasos siguientes.
    $entornoPrevio = @{}
    foreach ($clave in $VariablesEntorno.Keys) {
        $entornoPrevio[$clave] = [System.Environment]::GetEnvironmentVariable($clave)
        [System.Environment]::SetEnvironmentVariable($clave, $VariablesEntorno[$clave])
    }

    Push-Location $raizProyecto
    try {
        & $python @Argumentos *> $logPath
        $exitoPaso = ($LASTEXITCODE -eq 0)
    } finally {
        Pop-Location
        foreach ($clave in $entornoPrevio.Keys) {
            [System.Environment]::SetEnvironmentVariable($clave, $entornoPrevio[$clave])
        }
    }

    if ($exitoPaso) {
        Write-Host "OK" -ForegroundColor Green
    } else {
        Write-Host "FALLO (log completo: $logPath)" -ForegroundColor Red
    }

    $script:pasos += [pscustomobject]@{ Nombre = $Nombre; Exito = $exitoPaso; Log = $logPath }
    if (-not $exitoPaso) {
        $script:fallidos += $Nombre
    }
}

# --- 1. Lint y formato --------------------------------------------------

Ejecutar-Paso -Nombre "ruff check" -Argumentos @("-m", "ruff", "check", ".")
Ejecutar-Paso -Nombre "ruff format --check" -Argumentos @("-m", "ruff", "format", "--check", ".")

# --- 2. Tests con cobertura ----------------------------------------------

Ejecutar-Paso -Nombre "pytest" -Argumentos @(
    "-m", "pytest", "-ra", "--cov", "--cov-report=term-missing", "--cov-fail-under=80"
)

# --- 3. Arranque del sistema completo -------------------------------------
# Reproduce el job `arranque` del CI: migra sobre una base desechable, carga
# los datos de demostración, levanta los dos procesos y comprueba que ambos
# responden y que el ingreso devuelve un token. Un pipeline que solo lintea da
# falsa seguridad; los fallos reales aparecen al construir y ejecutar.

function Ejecutar-Arranque {
    Write-Host ""
    Write-Host "== arranque del sistema ==" -ForegroundColor Cyan

    $logPath = Join-Path $directorioLogs "arranque.log"
    "" | Set-Content -Path $logPath -Encoding utf8

    $baseDesechable = Join-Path $directorioLogs "db-arranque.sqlite3"
    if (Test-Path $baseDesechable) { Remove-Item $baseDesechable -Force }

    $entorno = @{
        DJANGO_SETTINGS_MODULE = "config.settings.dev"
        SECRET_KEY             = "clave-efimera-solo-para-verificacion-local"
        DATABASE_URL           = "sqlite:///$baseDesechable"
    }
    $entornoPrevio = @{}
    foreach ($clave in $entorno.Keys) {
        $entornoPrevio[$clave] = [System.Environment]::GetEnvironmentVariable($clave)
        [System.Environment]::SetEnvironmentVariable($clave, $entorno[$clave])
    }

    $procesos = @()
    $exitoPaso = $false
    Push-Location $raizProyecto
    try {
        # Si ya hay algo escuchando en el 8080, este paso daría OK sin haber
        # probado nada: mediría la instancia ajena. Mejor fallar y decirlo.
        $ocupado = $false
        try {
            Invoke-WebRequest -Uri "http://127.0.0.1:8080/" -UseBasicParsing -TimeoutSec 2 | Out-Null
            $ocupado = $true
        } catch { }
        if ($ocupado) {
            throw "El puerto 8080 ya está ocupado. Detén esa instancia antes de verificar: si no, este paso mediría la que ya está corriendo en vez de la recién levantada."
        }

        & $python "backend/manage.py" migrate --noinput *>> $logPath
        if ($LASTEXITCODE -ne 0) { throw "Falló migrate." }

        & $python "backend/manage.py" seed_demo *>> $logPath
        if ($LASTEXITCODE -ne 0) { throw "Falló seed_demo." }

        # Puertos distintos a los de desarrollo: así la comprobación no choca
        # con una instancia que Nicolás tenga levantada mientras trabaja.
        $entornoApi = "http://127.0.0.1:8901"
        [System.Environment]::SetEnvironmentVariable("API_BASE_URL", "$entornoApi/api/v1")

        $procesos += Start-Process -FilePath $python -PassThru -WindowStyle Hidden `
            -ArgumentList @("backend/manage.py", "runserver", "8901", "--noreload") `
            -RedirectStandardOutput (Join-Path $directorioLogs "arranque-backend.log") `
            -RedirectStandardError (Join-Path $directorioLogs "arranque-backend.err")

        $procesos += Start-Process -FilePath $python -PassThru -WindowStyle Hidden `
            -ArgumentList @("frontend/main.py") `
            -RedirectStandardOutput (Join-Path $directorioLogs "arranque-frontend.log") `
            -RedirectStandardError (Join-Path $directorioLogs "arranque-frontend.err")

        $backendListo = $false
        $frontendListo = $false
        foreach ($intento in 1..30) {
            if (-not $backendListo) {
                try {
                    Invoke-WebRequest -Uri "$entornoApi/healthz/" -UseBasicParsing -TimeoutSec 3 | Out-Null
                    $backendListo = $true
                } catch { }
            }
            if (-not $frontendListo) {
                try {
                    Invoke-WebRequest -Uri "http://127.0.0.1:8080/" -UseBasicParsing -TimeoutSec 3 | Out-Null
                    $frontendListo = $true
                } catch { }
            }
            if ($backendListo -and $frontendListo) { break }
            Start-Sleep -Seconds 2
        }

        if (-not $backendListo) { throw "La API no respondió en ~60 s." }
        if (-not $frontendListo) { throw "La interfaz no respondió en ~60 s (¿puerto 8080 ocupado?)." }

        $salud = Invoke-RestMethod -Uri "$entornoApi/healthz/" -TimeoutSec 5
        if ($salud.estado -ne "ok") { throw "healthz no devolvió estado ok." }

        $credenciales = @{ email = "admin@estacionamiento.cl"; password = "1234" } | ConvertTo-Json
        $ingreso = Invoke-RestMethod -Uri "$entornoApi/api/v1/auth/login/" -Method Post `
            -ContentType "application/json" -Body $credenciales -TimeoutSec 5
        if (-not $ingreso.token) { throw "El ingreso no devolvió token." }

        "API, interfaz e ingreso verificados." | Add-Content -Path $logPath -Encoding utf8
        $exitoPaso = $true
    } catch {
        $_.Exception.Message | Add-Content -Path $logPath -Encoding utf8
        foreach ($archivo in @("arranque-backend.err", "arranque-frontend.err")) {
            $ruta = Join-Path $directorioLogs $archivo
            if (Test-Path $ruta) {
                "---- $archivo ----" | Add-Content -Path $logPath -Encoding utf8
                Get-Content $ruta | Add-Content -Path $logPath -Encoding utf8
            }
        }
    } finally {
        foreach ($proceso in $procesos) {
            if ($proceso -and -not $proceso.HasExited) {
                Stop-Process -Id $proceso.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Pop-Location
        [System.Environment]::SetEnvironmentVariable("API_BASE_URL", $null)
        foreach ($clave in $entornoPrevio.Keys) {
            [System.Environment]::SetEnvironmentVariable($clave, $entornoPrevio[$clave])
        }
    }

    if ($exitoPaso) {
        Write-Host "OK" -ForegroundColor Green
    } else {
        Write-Host "FALLO (log completo: $logPath)" -ForegroundColor Red
    }

    $script:pasos += [pscustomobject]@{ Nombre = "arranque del sistema"; Exito = $exitoPaso; Log = $logPath }
    if (-not $exitoPaso) {
        $script:fallidos += "arranque del sistema"
    }
}

Ejecutar-Arranque

# --- 4. Hardening de producción -------------------------------------------
# Sin una SECRET_KEY fuerte, `check --deploy` falla por la clave débil y no
# por el hardening real, que es justamente lo que queremos verificar. Se
# genera una efímera en el momento, solo para este chequeo.

$claveSecreta = (& $python -c "import secrets; print(secrets.token_urlsafe(64))").Trim()

Ejecutar-Paso -Nombre "manage.py check --deploy" -Argumentos @(
    "backend/manage.py", "check", "--deploy", "--fail-level", "WARNING"
) -VariablesEntorno @{
    DJANGO_SETTINGS_MODULE = "config.settings.prod"
    ALLOWED_HOSTS           = "arriendos.example.cl"
    SECURE_HTTPS            = "True"
    DATABASE_URL            = "sqlite:///db-check.sqlite3"
    SECRET_KEY              = $claveSecreta
}

# --- Resumen ---------------------------------------------------------------

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host " Resumen"
Write-Host "===================================" -ForegroundColor Cyan

if ($script:fallidos.Count -eq 0) {
    Write-Host "Todo en verde." -ForegroundColor Green
    exit 0
}

Write-Host "Pasos fallidos:" -ForegroundColor Red
foreach ($nombre in $script:fallidos) {
    $paso = $script:pasos | Where-Object { $_.Nombre -eq $nombre } | Select-Object -Last 1
    Write-Host ""
    Write-Host "  - $nombre" -ForegroundColor Red
    Write-Host "    Últimas líneas de $($paso.Log):"
    # -Encoding utf8 explícito: sin él Get-Content lee el log como ANSI y
    # destroza las tildes justo en el mensaje que hay que leer para arreglar.
    Get-Content $paso.Log -Tail 25 -Encoding utf8 | ForEach-Object { Write-Host "      $_" }
}

exit 1
