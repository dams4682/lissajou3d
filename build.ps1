$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pyinstaller.exe --noconfirm --windowed --name Lissajou3D app_3d.py

Write-Host "Built dist\Lissajou3D\Lissajou3D.exe"
