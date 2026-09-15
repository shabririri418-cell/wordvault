[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist/arm64"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutputPath = Join-Path $ProjectRoot $OutputDirectory

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "未检测到 Docker Desktop，请先安装并启动 Docker Desktop。"
}

$BuilderPlatforms = docker buildx inspect --bootstrap 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    throw "Docker 构建器不可用，请确认 Docker Desktop 已启动。"
}
if ($BuilderPlatforms -notmatch "linux/arm64") {
    Write-Host "正在为 Docker 注册 ARM64/QEMU 模拟支持……"
    docker run --privileged --rm tonistiigi/binfmt --install arm64
    if ($LASTEXITCODE -ne 0) {
        throw "无法注册 ARM64 模拟支持。请检查 Docker Hub 网络连接后重试。"
    }
    $EmulatedArchitecture = docker run --rm --platform linux/arm64 alpine uname -m
    if ($LASTEXITCODE -ne 0 -or $EmulatedArchitecture.Trim() -ne "aarch64") {
        throw "ARM64 模拟器注册后未能通过运行验证，请重启 Docker Desktop 后重试。"
    }
}

New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
docker buildx build `
    --platform linux/arm64 `
    --pull=false `
    --file (Join-Path $ProjectRoot "packaging/Dockerfile.arm64") `
    --output "type=local,dest=$OutputPath" `
    $ProjectRoot

if ($LASTEXITCODE -ne 0) {
    throw "ARM64 模拟构建失败，请保留终端输出用于诊断。"
}

Write-Host "ARM64 安装包已输出到 $OutputPath"
