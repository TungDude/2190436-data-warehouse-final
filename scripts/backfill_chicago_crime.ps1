param(
    [string] $StartDate = "2019-01-01",
    [string] $EndDate,
    [string] $FunctionName = "data-warehouse-final-fetch-chicago-crime",
    [string] $Profile = "data-warehouse-final",
    [string] $Region = "ap-southeast-1",
    [int] $SourceLookbackDays = 8
)

$ErrorActionPreference = "Stop"

$start = [DateTime]::ParseExact($StartDate, "yyyy-MM-dd", $null)
if ($EndDate) {
    $end = [DateTime]::ParseExact($EndDate, "yyyy-MM-dd", $null)
} else {
    $end = [DateTime]::Today.AddDays(-1 * $SourceLookbackDays)
}

if ($end -lt $start) {
    throw "EndDate $($end.ToString('yyyy-MM-dd')) is before StartDate $($start.ToString('yyyy-MM-dd'))."
}

$payloadPath = Join-Path $env:TEMP "dw-final-backfill-payload.json"
$responsePath = Join-Path $env:TEMP "dw-final-backfill-response.json"

$cursor = $start
$totalRows = 0
$chunkCount = 0

while ($cursor -le $end) {
    $chunkStart = $cursor
    $chunkEnd = $cursor.AddMonths(1).AddDays(-1)
    if ($chunkEnd -gt $end) {
        $chunkEnd = $end
    }

    $payload = @{
        start_date = $chunkStart.ToString("yyyy-MM-dd")
        end_date   = $chunkEnd.ToString("yyyy-MM-dd")
    } | ConvertTo-Json -Compress

    Set-Content -LiteralPath $payloadPath -Value $payload -NoNewline -Encoding ascii

    aws lambda invoke `
        --profile $Profile `
        --region $Region `
        --function-name $FunctionName `
        --cli-binary-format raw-in-base64-out `
        --payload "fileb://$payloadPath" `
        $responsePath | Out-Null

    $result = Get-Content -Raw -LiteralPath $responsePath | ConvertFrom-Json
    $totalRows += [int] $result.row_count
    $chunkCount += 1

    Write-Host ("{0} to {1}: {2} rows -> s3://{3}/{4}" -f `
        $result.start_date, `
        $result.end_date, `
        $result.row_count, `
        $result.bucket, `
        $result.key)

    $cursor = $chunkEnd.AddDays(1)
}

Remove-Item -LiteralPath $payloadPath, $responsePath -ErrorAction SilentlyContinue

Write-Host ("Backfill complete: {0} chunks, {1} rows." -f $chunkCount, $totalRows)
