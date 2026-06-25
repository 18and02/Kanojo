param(
    [string]$PackageDir = "exports-showcase-package",
    [string]$OutFile = "showcase-slideshow.mp4",
    [int]$SecondsPerImage = 4,
    [int]$Fps = 30,
    [switch]$RequireFfmpeg
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

if ([System.IO.Path]::IsPathRooted($PackageDir)) {
    $Target = (Resolve-Path -LiteralPath $PackageDir).Path
} else {
    $Target = (Resolve-Path -LiteralPath (Join-Path $Root $PackageDir)).Path
}

function ConvertTo-RepoRelativePath {
    param([string]$Path)
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    if ($FullPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $FullPath.Substring($Root.Length).TrimStart("\", "/").Replace("\", "/")
    }
    return $FullPath
}

function ConvertTo-FfmpegConcatPath {
    param([string]$Path)
    return $Path.Replace("\", "/").Replace("'", "'\''")
}

$ScreenshotDir = Join-Path $Target "screenshots"
$Screenshots = @(
    Get-ChildItem -LiteralPath $ScreenshotDir -Filter "*.png" -File -ErrorAction SilentlyContinue |
        Sort-Object Name
)

if ($Screenshots.Count -eq 0) {
    throw "No screenshot PNG files found in $ScreenshotDir. Run capture_showcase_screenshots.ps1 or build_showcase_package.ps1 first."
}

$FfmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$FfmpegAvailable = $null -ne $FfmpegCommand
if (-not $FfmpegAvailable -and $RequireFfmpeg) {
    throw "ffmpeg not found. Install ffmpeg or run without -RequireFfmpeg to generate only the recording plan."
}

$VideoPath = Join-Path $Target $OutFile
$ConcatPath = Join-Path $Target "recording-frames.ffconcat"
$PlanPath = Join-Path $Target "recording-plan.md"
$VideoCreated = $false

if ($FfmpegAvailable) {
    $ConcatLines = [System.Collections.Generic.List[string]]::new()
    $ConcatLines.Add("ffconcat version 1.0")
    foreach ($Screenshot in $Screenshots) {
        $ConcatLines.Add("file '$(ConvertTo-FfmpegConcatPath $Screenshot.FullName)'")
        $ConcatLines.Add("duration $SecondsPerImage")
    }
    $ConcatLines.Add("file '$(ConvertTo-FfmpegConcatPath $Screenshots[-1].FullName)'")
    Set-Content -LiteralPath $ConcatPath -Encoding ASCII -Value $ConcatLines

    $Filter = "fps=$Fps,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
    & $FfmpegCommand.Source `
        -hide_banner `
        -loglevel error `
        -y `
        -safe 0 `
        -f concat `
        -i $ConcatPath `
        -vf $Filter `
        -movflags +faststart `
        $VideoPath
    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg failed with exit code $LASTEXITCODE"
    }
    $VideoCreated = Test-Path -LiteralPath $VideoPath
}

$PlanLines = [System.Collections.Generic.List[string]]::new()
$PlanLines.Add("# Kanojo Showcase Recording Plan")
$PlanLines.Add("")
$PlanLines.Add("- Package directory: ``$(ConvertTo-RepoRelativePath $Target)``")
$PlanLines.Add("- ffmpeg available: ``$FfmpegAvailable``")
$PlanLines.Add("- Seconds per image: ``$SecondsPerImage``")
$PlanLines.Add("- FPS: ``$Fps``")
$PlanLines.Add("- Video file: ``$(ConvertTo-RepoRelativePath $VideoPath)``")
$PlanLines.Add("- Video created: ``$VideoCreated``")
$PlanLines.Add("")
$PlanLines.Add("## Frame Sequence")
$PlanLines.Add("")
$PlanLines.Add("| Order | File |")
$PlanLines.Add("| ---: | --- |")
$Index = 1
foreach ($Screenshot in $Screenshots) {
    $PlanLines.Add("| $Index | ``$(ConvertTo-RepoRelativePath $Screenshot.FullName)`` |")
    $Index += 1
}
$PlanLines.Add("")
$PlanLines.Add("## Next Steps")
$PlanLines.Add("")
if ($VideoCreated) {
    $PlanLines.Add("- Use the generated MP4 as a short visual fallback when live recording is not needed.")
    $PlanLines.Add("- For a real live demo recording, use OBS or Windows capture after running ``.\scripts\start_demo_stack.ps1 -Restart``.")
} else {
    $PlanLines.Add("- Install ffmpeg and rerun this script to build an MP4 from the screenshot sequence.")
    $PlanLines.Add("- Alternatively record the live desktop flow with OBS or Windows capture.")
}

Set-Content -LiteralPath $PlanPath -Encoding UTF8 -Value $PlanLines

[pscustomobject]@{
    package_dir = $Target
    plan = $PlanPath
    ffmpeg_available = $FfmpegAvailable
    video_created = $VideoCreated
    video = if ($VideoCreated) { $VideoPath } else { $null }
    screenshot_count = $Screenshots.Count
} | ConvertTo-Json -Depth 5
