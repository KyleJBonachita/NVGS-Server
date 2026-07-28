$ErrorActionPreference = "Stop"

$ServerName = "__NVGS_SERVER_NAME__"
$ServerIp = "__NVGS_SERVER_IP__"
$TicketingUrl = "__NVGS_TICKETING_URL__"
$ExpectedCertificateSha256 = "__NVGS_CERTIFICATE_SHA256__"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

if (-not (Test-IsAdministrator)) {
    $arguments = (
        "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    )
    try {
        $elevatedProcess = Start-Process `
            -FilePath "powershell.exe" `
            -Verb RunAs `
            -ArgumentList $arguments `
            -Wait `
            -PassThru
        exit $elevatedProcess.ExitCode
    }
    catch {
        Write-Error "Administrator approval was cancelled or unavailable."
        exit 1
    }
}

Add-Type -AssemblyName System.Windows.Forms

$confirmationMessage = @"
Install the approved NVGS client setup on this Windows laptop?

Server: $ServerName ($ServerIp)

This will:
- Trust only the public NVGS certificate authority
- Map $ServerName to $ServerIp
- Create an NVGS Ticketing desktop shortcut

It does not collect your Windows or NVIDIA password.
"@

$confirmation = [System.Windows.Forms.MessageBox]::Show(
    $confirmationMessage,
    "NVGS Client Setup",
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Information
)
if ($confirmation -ne [System.Windows.Forms.DialogResult]::Yes) {
    exit 2
}

$certificatePath = Join-Path $PSScriptRoot "nvgs-local-ca.crt"
if (-not (Test-Path -LiteralPath $certificatePath -PathType Leaf)) {
    throw "The NVGS certificate is missing from the setup folder."
}

$actualCertificateSha256 = (
    Get-FileHash -LiteralPath $certificatePath -Algorithm SHA256
).Hash.ToLowerInvariant()
if ($actualCertificateSha256 -ne $ExpectedCertificateSha256) {
    throw "The NVGS certificate fingerprint does not match this installer."
}

$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
    $certificatePath
)
$existingCertificate = Get-ChildItem "Cert:\LocalMachine\Root" |
    Where-Object { $_.Thumbprint -eq $certificate.Thumbprint } |
    Select-Object -First 1
if (-not $existingCertificate) {
    Import-Certificate `
        -FilePath $certificatePath `
        -CertStoreLocation "Cert:\LocalMachine\Root" |
        Out-Null
}

$hostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$beginMarker = "# BEGIN NVGS TICKETING"
$endMarker = "# END NVGS TICKETING"
$existingLines = @()
if (Test-Path -LiteralPath $hostsPath) {
    $existingLines = @(Get-Content -LiteralPath $hostsPath)
}

$updatedLines = [System.Collections.Generic.List[string]]::new()
$insideManagedBlock = $false
foreach ($line in $existingLines) {
    if ($line.Trim() -eq $beginMarker) {
        $insideManagedBlock = $true
        continue
    }
    if ($line.Trim() -eq $endMarker) {
        $insideManagedBlock = $false
        continue
    }
    if (-not $insideManagedBlock) {
        $updatedLines.Add($line)
    }
}

while (
    $updatedLines.Count -gt 0 -and
    [string]::IsNullOrWhiteSpace($updatedLines[$updatedLines.Count - 1])
) {
    $updatedLines.RemoveAt($updatedLines.Count - 1)
}
$updatedLines.Add("")
$updatedLines.Add($beginMarker)
$updatedLines.Add("$ServerIp $ServerName")
$updatedLines.Add($endMarker)

Set-Content `
    -LiteralPath $hostsPath `
    -Value $updatedLines `
    -Encoding Ascii
ipconfig.exe /flushdns | Out-Null

$publicDesktop = [Environment]::GetFolderPath("CommonDesktopDirectory")
if ([string]::IsNullOrWhiteSpace($publicDesktop)) {
    $publicDesktop = [Environment]::GetFolderPath("DesktopDirectory")
}
$shortcutPath = Join-Path $publicDesktop "NVGS Ticketing.url"
$shortcutContent = @"
[InternetShortcut]
URL=$TicketingUrl
IconFile=$env:SystemRoot\System32\SHELL32.dll
IconIndex=220
"@
[IO.File]::WriteAllText(
    $shortcutPath,
    $shortcutContent,
    [Text.Encoding]::ASCII
)

$connectionMessage = (
    "Installation completed. Close and reopen your browser, then use the " +
    "NVGS Ticketing desktop shortcut."
)
try {
    Invoke-WebRequest `
        -Uri $TicketingUrl `
        -UseBasicParsing `
        -TimeoutSec 15 |
        Out-Null
}
catch {
    $connectionMessage += (
        "`n`nThe server could not be tested right now. Make sure the NVGS " +
        "server is running and that this laptop is on the same approved LAN."
    )
}

[System.Windows.Forms.MessageBox]::Show(
    $connectionMessage,
    "NVGS Client Setup",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null

exit 0
