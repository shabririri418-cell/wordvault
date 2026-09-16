[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist/windows-preview",
    [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutputRoot = Join-Path $ProjectRoot $OutputDirectory
$BuildRoot = Join-Path $ProjectRoot "build/windows-preview"
$AppRoot = Join-Path $BuildRoot "文澜资料库-Windows预览版"
$Executable = Join-Path $AppRoot "文澜资料库.exe"
$LauncherBuildRoot = Join-Path $ProjectRoot "build/windows-launcher"
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

$OriginalPath = $env:PATH
$PythonHome = Split-Path -Parent $PythonExecutable
$env:PATH = @(
    (Join-Path $VenvRoot "Scripts")
    $PythonHome
    (Join-Path $env:SystemRoot "System32")
    $env:SystemRoot
) -join ";"
try {
    & $BuildPython -m PyInstaller --noconfirm --clean `
        --distpath $BuildRoot --workpath (Join-Path $BuildRoot "work") `
        (Join-Path $ProjectRoot "packaging/WordVault.windows.spec")
    if ($LASTEXITCODE -ne 0) { throw "Windows 主程序构建失败。" }
    & $BuildPython -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name "文澜资料库" --distpath $LauncherBuildRoot `
        --workpath (Join-Path $LauncherBuildRoot "work") `
        --specpath (Join-Path $LauncherBuildRoot "spec") `
        (Join-Path $ProjectRoot "src/wordvault/windows_launcher.py")
    if ($LASTEXITCODE -ne 0) { throw "Windows 兼容启动器构建失败。" }
} finally {
    $env:PATH = $OriginalPath
}
Copy-Item -LiteralPath (Join-Path $LauncherBuildRoot "文澜资料库.exe") `
    -Destination $Executable -Force

$PackageToc = Join-Path $BuildRoot "work/WordVault.windows/COLLECT-00.toc"
$UnsafeRuntime = Select-String -LiteralPath $PackageToc `
    -Pattern "native\\\\libheif|\('ucrtbase\.dll'," -Quiet
if ($UnsafeRuntime) {
    throw "发现外部工具的 Windows 运行库，已阻止发布。"
}

$Archive = Join-Path $OutputRoot "文澜资料库-Windows预览测试包.zip"
Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
$Readme = Join-Path $ProjectRoot "acceptance/README.md"
$Samples = Join-Path $ProjectRoot "acceptance/samples"
Copy-Item -LiteralPath $Readme -Destination (Join-Path $AppRoot "使用说明.md") -Force
Copy-Item -LiteralPath $Samples -Destination $AppRoot -Recurse -Force
Compress-Archive -Path $AppRoot `
    -DestinationPath $Archive -CompressionLevel Optimal
Write-Host "已生成 $Archive"
