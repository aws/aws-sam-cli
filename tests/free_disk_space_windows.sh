#!/bin/bash
# Free up disk space on Windows GitHub Actions runners.
# Removes large pre-installed tools and caches that are not needed for SAM CLI tests.
# All heavy deletions run in background (non-blocking) via PowerShell Start-Job.
set -e

echo "=== Windows Disk Usage Before Cleanup ==="
powershell.exe -Command "Get-PSDrive -PSProvider FileSystem | Format-Table Name, @{N='Used(GB)';E={[math]::Round(\$_.Used/1GB,1)}}, @{N='Free(GB)';E={[math]::Round(\$_.Free/1GB,1)}}, @{N='Total(GB)';E={[math]::Round((\$_.Used+\$_.Free)/1GB,1)}} -AutoSize"

echo "=== Starting non-blocking cleanup of Windows runner disk space ==="

# Fire-and-forget: remove large pre-installed SDKs not needed for SAM CLI tests
powershell.exe -Command "
  Start-Job {
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
        Remove-Item -Recurse -Force \$p -ErrorAction SilentlyContinue
      }
    }
  } | Out-Null
"

# Clean caches in background (quick, but still non-blocking)
npm cache clean --force > /dev/null 2>&1 &
pip cache purge > /dev/null 2>&1 &
uv cache clean > /dev/null 2>&1 &

echo "Cleanup jobs started in background."
