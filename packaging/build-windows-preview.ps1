[CmdletBinding()]
param([string]$OutputDirectory = "dist/windows-preview")

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutputRoot = Join-Path $ProjectRoot $OutputDirectory
$BuildRoot = Join-Path $ProjectRoot "build/windows-preview"
$AppRoot = Join-Path $BuildRoot "WordVault"

python -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name WordVault --paths (Join-Path $ProjectRoot "src") `
    --distpath $BuildRoot --workpath (Join-Path $BuildRoot "work") `
    --specpath (Join-Path $BuildRoot "spec") `
    (Join-Path $ProjectRoot "src/wordvault/__main__.py")
if ($LASTEXITCODE -ne 0) { throw "Windows 预览版构建失败。" }

Rename-Item (Join-Path $AppRoot "WordVault.exe") "文澜资料库.exe"
Copy-Item -Recurse -Force (Join-Path $ProjectRoot "acceptance/samples") $AppRoot
Copy-Item -Force (Join-Path $ProjectRoot "acceptance/README.md") (Join-Path $AppRoot "测试说明.md")

$Archive = Join-Path $OutputRoot "文澜资料库-Windows预览测试包.zip"
Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
Compress-Archive -Path $AppRoot -DestinationPath $Archive -CompressionLevel Optimal
Write-Host "已生成 $Archive"
