# PPTX -> PDF 批量转换（每个文件用独立 PowerPoint 实例，避免 COM 资源累积）
# 用法：powershell -ExecutionPolicy Bypass -File pptx_to_pdf.ps1 -SrcDir "源目录" -OutDir "输出目录"
param(
    [string]$SrcDir = "C:\Users\HB\Desktop\文档添加水印\香文化",
    [string]$OutDir = "C:\Users\HB\Desktop\文档添加水印\香文化_PDF"
)

$ErrorActionPreference = "Continue"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

function Convert-PptxFile {
    param([string]$InputPath, [string]$OutputPath)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    $app = New-Object -ComObject PowerPoint.Application
    $pres = $null
    try {
        $pres = $app.Presentations.Open($InputPath, $true, $false, $false)
        $pres.SaveAs($OutputPath, 32)  # ppSaveAsPDF
        $sz = [math]::Round((Get-Item $OutputPath).Length / 1MB, 1)
        return "    ✓ 完成 $sz MB, 耗时 $($sw.Elapsed.ToString('mm\:ss'))"
    }
    catch {
        return "    ✗ 失败: $($_.Exception.Message)"
    }
    finally {
        if ($pres -ne $null) {
            $pres.Close()
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
        }
        $app.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
        [System.GC]::Collect()
        [System.GC]::WaitForPendingFinalizers()
    }
}

$files = Get-ChildItem -Path $SrcDir -Filter *.pptx | Sort-Object Name
$total = $files.Count
$i = 0
Write-Output "待转换 $total 个 PPTX"
Write-Output ("=" * 60)

foreach ($f in $files) {
    $i++
    $out = Join-Path $OutDir ($f.BaseName + ".pdf")

    if (Test-Path $out) {
        Write-Output "[$i/$total] 跳过(已存在): $($f.Name)"
        continue
    }

    Write-Output "[$i/$total] 转换中: $($f.Name)"
    $r = Convert-PptxFile -InputPath $f.FullName -OutputPath $out
    Write-Output $r
}

Write-Output ("=" * 60)
Write-Output "转换全部结束"