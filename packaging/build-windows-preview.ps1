[CmdletBinding()]
param([string]$OutputDirectory = "dist/windows-preview")

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutputRoot = Join-Path $ProjectRoot $OutputDirectory
$BuildRoot = Join-Path $ProjectRoot "build/windows-preview"
$Executable = Join-Path $BuildRoot "文澜资料库.exe"

python -m PyInstaller --noconfirm --clean --windowed --onefile `
    --name "文澜资料库" --paths (Join-Path $ProjectRoot "src") `
    --distpath $BuildRoot --workpath (Join-Path $BuildRoot "work") `
    --specpath (Join-Path $BuildRoot "spec") `
    (Join-Path $ProjectRoot "src/wordvault/__main__.py")
if ($LASTEXITCODE -ne 0) { throw "Windows 预览版构建失败。" }

$Archive = Join-Path $OutputRoot "文澜资料库-Windows预览测试包.zip"
Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
$Readme = Join-Path $ProjectRoot "acceptance/README.md"
$Samples = Join-Path $ProjectRoot "acceptance/samples"
Compress-Archive -Path $Executable, $Readme, $Samples `
    -DestinationPath $Archive -CompressionLevel Optimal
Write-Host "已生成 $Archive"
