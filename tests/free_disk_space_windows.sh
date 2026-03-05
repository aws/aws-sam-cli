#!/bin/bash
# Free up disk space on Windows GitHub Actions runners.
# Removes large pre-installed tools and caches that are not needed for SAM CLI tests.
set -e

echo "=== Windows Disk Usage Before Cleanup ==="
powershell.exe -Command "Get-PSDrive -PSProvider FileSystem | Format-Table Name, @{N='Used(GB)';E={[math]::Round(\$_.Used/1GB,1)}}, @{N='Free(GB)';E={[math]::Round(\$_.Free/1GB,1)}}, @{N='Total(GB)';E={[math]::Round((\$_.Used+\$_.Free)/1GB,1)}} -AutoSize"

echo "=== Cleaning up Windows runner disk space ==="

# Remove large pre-installed SDKs and tools not needed for SAM CLI tests
powershell.exe -Command "
  \$paths = @(
    'C:\Program Files\Microsoft Visual Studio',
    'C:\Program Files (x86)\Microsoft Visual Studio',
    'C:\Program Files\dotnet\sdk',
    'C:\Program Files\Android',
    'C:\Android',
    'C:\Program Files (x86)\Android',
    'C:\Program Files\Microsoft SQL Server',
    'C:\Program Files (x86)\Microsoft SQL Server',
    'C:\Program Files\MySQL',
    'C:\Program Files\PostgreSQL',
    'C:\Program Files\MongoDB',
    'C:\Program Files\LLVM',
    'C:\Strawberry',
    'C:\ProgramData\chocolatey\lib\mingw',
    'C:\ProgramData\chocolatey\lib\llvm'
  )
  foreach (\$p in \$paths) {
    if (Test-Path \$p) {
      Write-Host \"Removing \$p\"
      Remove-Item -Recurse -Force \$p -ErrorAction SilentlyContinue
    }
  }
"

# Clean npm cache
npm cache clean --force 2>/dev/null || true

# Clean pip cache
pip cache purge 2>/dev/null || true

# Clean uv cache
uv cache clean 2>/dev/null || true

echo "=== Windows Disk Usage After Cleanup ==="
powershell.exe -Command "Get-PSDrive -PSProvider FileSystem | Format-Table Name, @{N='Used(GB)';E={[math]::Round(\$_.Used/1GB,1)}}, @{N='Free(GB)';E={[math]::Round(\$_.Free/1GB,1)}}, @{N='Total(GB)';E={[math]::Round((\$_.Used+\$_.Free)/1GB,1)}} -AutoSize"
