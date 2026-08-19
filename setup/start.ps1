# Sales Anomaly Studio launcher.
# Finds a Python to use (bundled runtime -> system Python -> downloads a private one),
# starts the app, waits until it answers, opens the browser and then shows the live log.
$ErrorActionPreference = 'Stop'
$App = Split-Path -Parent $PSScriptRoot
Set-Location $App
$Port = 8501
$LogDir = Join-Path $App 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'app.log'

function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Step([int]$n, [int]$of, [string]$m) { Write-Host ("[{0}/{1}] {2}" -f $n, $of, $m) -ForegroundColor Cyan }

Clear-Host
Write-Host ''
Write-Host '  ===========================================' -ForegroundColor DarkCyan
Write-Host '   SALES ANOMALY STUDIO' -ForegroundColor White
Write-Host '  ===========================================' -ForegroundColor DarkCyan
Write-Host ''

# ---------------------------------------------------------------- 1. find a Python
Step 1 4 'Looking for the app runtime...'
$Py = $null
$bundled = Join-Path $App 'runtime\python.exe'
$venv = Join-Path $App '.venv\Scripts\python.exe'

if (Test-Path $bundled) {
    $Py = $bundled
    Say '      Using the bundled runtime (no installation needed).' 'DarkGray'
}
elseif (Test-Path $venv) {
    $Py = $venv
    Say '      Using the private environment created on the first run.' 'DarkGray'
}
else {
    # is there a usable system Python?
    $sys = $null
    foreach ($c in @('python', 'py')) {
        try {
            $v = & $c -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v) {
                $parts = $v.Trim().Split('.')
                if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10) { $sys = $c; break }
            }
        } catch {}
    }
    if ($sys) {
        Say "      Found Python $v on this computer - creating a private environment (one time, 1-3 min)..." 'DarkGray'
        & $sys -m venv (Join-Path $App '.venv')
        if (-not (Test-Path $venv)) { throw 'Could not create the environment.' }
        $Py = $venv
    }
    else {
        Say '      No Python found - downloading a private one (one time, ~25 MB, needs internet)...' 'Yellow'
        $rt = Join-Path $App 'runtime'
        $tmp = Join-Path $env:TEMP 'sas_python.zip'
        $url = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
        try {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
            New-Item -ItemType Directory -Force -Path $rt | Out-Null
            Expand-Archive -Path $tmp -DestinationPath $rt -Force
            Remove-Item $tmp -Force
            $pth = Get-ChildItem $rt -Filter 'python3*._pth' | Select-Object -First 1
            (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ascii
            $getpip = Join-Path $env:TEMP 'get-pip.py'
            Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $getpip -UseBasicParsing
            & (Join-Path $rt 'python.exe') $getpip --no-warn-script-location -q
            Remove-Item $getpip -Force
            $Py = Join-Path $rt 'python.exe'
        }
        catch {
            Write-Host ''
            Write-Host '  Could not download Python automatically.' -ForegroundColor Red
            Write-Host '  Either connect to the internet and try again, or install Python 3.10+' -ForegroundColor Red
            Write-Host '  from https://www.python.org/downloads/ (tick "Add python.exe to PATH").' -ForegroundColor Red
            exit 1
        }
    }
}

# ---------------------------------------------------------------- 2. packages
Step 2 4 'Checking the required packages...'
$probe = & $Py -c "import streamlit,plotly,pandas,numpy,pyarrow,sklearn" 2>&1
if ($LASTEXITCODE -ne 0) {
    Say '      Installing packages (one time, 1-3 minutes, needs internet)...' 'Yellow'
    & $Py -m pip install --upgrade pip --quiet --no-warn-script-location 2>&1 | Out-Null
    & $Py -m pip install -r (Join-Path $App 'requirements.txt') --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host '  Package installation failed - check the internet connection and try again.' -ForegroundColor Red
        exit 1
    }
    Say '      Packages installed.' 'DarkGray'
} else {
    Say '      All packages present.' 'DarkGray'
}

# ---------------------------------------------------------------- 3. start
# free the port if a previous window was closed without stopping the app
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($b in $busy) { try { Stop-Process -Id $b.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }

Step 3 4 'Starting the app...'
if (Test-Path $Log) { Remove-Item $Log -Force -ErrorAction SilentlyContinue }
$args = @('-m', 'streamlit', 'run', 'app.py', '--server.port', $Port, '--server.headless', 'true',
          '--browser.gatherUsageStats', 'false', '--global.developmentMode', 'false')
$proc = Start-Process -FilePath $Py -ArgumentList $args -WorkingDirectory $App -PassThru -NoNewWindow `
                      -RedirectStandardOutput $Log -RedirectStandardError (Join-Path $LogDir 'app.err.log')

$url = "http://localhost:$Port"
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Milliseconds 700
    if ($proc.HasExited) { break }
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    if ($i % 7 -eq 6) { Write-Host '      still starting...' -ForegroundColor DarkGray }
}

if (-not $ready) {
    Write-Host ''
    Write-Host '  The app did not start. Details:' -ForegroundColor Red
    if (Test-Path (Join-Path $LogDir 'app.err.log')) { Get-Content (Join-Path $LogDir 'app.err.log') -Tail 25 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed } }
    if (Test-Path $Log) { Get-Content $Log -Tail 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed } }
    exit 1
}

Step 4 4 'Opening the dashboard in your browser...'
Start-Process $url | Out-Null
Write-Host ''
Write-Host "  The app is running at $url" -ForegroundColor Green
Write-Host '  Leave THIS WINDOW OPEN while you use the app.' -ForegroundColor Yellow
Write-Host '  Close it (or press Ctrl+C) to stop the app.' -ForegroundColor Yellow
Write-Host ''
Write-Host '  --- activity ------------------------------------------------' -ForegroundColor DarkCyan

# ---------------------------------------------------------------- 4. live activity
$stamp = Get-Date
$seen = 0
try {
    while (-not $proc.HasExited) {
        Start-Sleep -Seconds 2
        if (Test-Path $Log) {
            $lines = Get-Content $Log -ErrorAction SilentlyContinue
            if ($lines.Count -gt $seen) {
                $lines[$seen..($lines.Count - 1)] | ForEach-Object {
                    if ($_ -match '\[detect\]|\[clean\]|Traceback|Error|error') { Write-Host "  $_" -ForegroundColor White }
                    elseif ($_ -match '\S') { Write-Host "  $_" -ForegroundColor DarkGray }
                }
                $seen = $lines.Count
            }
        }
        if ((Get-Date) -gt $stamp.AddMinutes(5)) {
            Write-Host ("  [{0}] running..." -f (Get-Date -Format 'HH:mm')) -ForegroundColor DarkGray
            $stamp = Get-Date
        }
    }
}
finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host ''
    Write-Host '  App stopped.' -ForegroundColor Yellow
}
