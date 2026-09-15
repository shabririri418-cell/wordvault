[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist/windows-preview",
    [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutputRoot = Join-Path $ProjectRoot $OutputDirectory
$BuildRoot = Join-Path $ProjectRoot "build/windows-preview"
$Executable = Join-Path $BuildRoot "文澜资料库.exe"
$VenvRoot = Join-Path $ProjectRoot ".venv-windows-build"
$BuildPython = Join-Path $VenvRoot "Scripts/python.exe"

$Version = & $PythonExecutable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $Version -notin @("3.11", "3.12")) {
    throw "Windows 交付包必须使用 Python 3.11 或 3.12 构建，当前为 $Version。"
}
if (-not (Test-Path $BuildPython)) {
    & $PythonExecutable -m venv $VenvRoot
}
& $BuildPython -m pip install --disable-pip-version-check `
    -r (Join-Path $ProjectRoot "requirements-build-windows.txt")
if ($LASTEXITCODE -ne 0) { throw "Windows 构建依赖安装失败。" }

& $BuildPython -m PyInstaller --noconfirm --clean --windowed --onefile `
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
