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
if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {
    Clear-DnsClientCache
}

$writtenHosts = Get-Content -LiteralPath $hostsPath -Raw
$escapedMapping = (
    "(?m)^\s*" +
    [Regex]::Escape($ServerIp) +
    "\s+" +
    [Regex]::Escape($ServerName) +
    "(?:\s|$)"
)
if ($writtenHosts -notmatch $escapedMapping) {
    throw "Windows did not save the NVGS hostname mapping in the hosts file."
}

$publicDesktop = [Environment]::GetFolderPath("CommonDesktopDirectory")
if ([string]::IsNullOrWhiteSpace($publicDesktop)) {
    $publicDesktop = [Environment]::GetFolderPath("DesktopDirectory")
}
$shortcutPath = Join-Path $publicDesktop "NVGS Ticketing.url"
$fallbackShortcutPath = Join-Path $publicDesktop "NVGS Ticketing - IP fallback.url"
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

$resolvedAddresses = @()
try {
    $resolvedAddresses = @(
        [System.Net.Dns]::GetHostAddresses($ServerName) |
            ForEach-Object { $_.IPAddressToString }
    )
}
catch {
    $resolvedAddresses = @()
}
$nameResolved = $resolvedAddresses -contains $ServerIp

$serverReachable = $false
try {
    $connection = Test-NetConnection `
        -ComputerName $ServerIp `
        -Port 443 `
        -WarningAction SilentlyContinue
    $serverReachable = [bool]$connection.TcpTestSucceeded
}
catch {
    $serverReachable = $false
}

$websiteVerified = $false
if ($nameResolved -and $serverReachable) {
    try {
        Invoke-WebRequest `
            -Uri $TicketingUrl `
            -UseBasicParsing `
            -TimeoutSec 15 |
            Out-Null
        $websiteVerified = $true
    }
    catch {
        $websiteVerified = $false
    }
}

$connectionMessage = @"
NVGS client setup completed.

Certificate trusted: Yes
Windows hostname mapping: $(if ($nameResolved) { "Working" } else { "Needs attention" })
Server port 443: $(if ($serverReachable) { "Reachable" } else { "Not reachable right now" })
Website test: $(if ($websiteVerified) { "Passed" } else { "Not completed" })

Close every browser window, reopen the browser, then use the
"NVGS Ticketing" desktop shortcut.
"@

if (-not $nameResolved) {
    $fallbackContent = @"
[InternetShortcut]
URL=https://$ServerIp/tickets/
IconFile=$env:SystemRoot\System32\SHELL32.dll
IconIndex=220
"@
    [IO.File]::WriteAllText(
        $fallbackShortcutPath,
        $fallbackContent,
        [Text.Encoding]::ASCII
    )
    $connectionMessage += @"

Windows did not resolve $ServerName even though its hosts entry was saved.
An "NVGS Ticketing - IP fallback" shortcut was also created.
This usually means a company name-resolution policy is overriding .local.
"@
}
elseif (Test-Path -LiteralPath $fallbackShortcutPath) {
    Remove-Item -LiteralPath $fallbackShortcutPath -Force
}

if (-not $serverReachable) {
    $connectionMessage += @"

The setup is installed, but this laptop cannot currently reach $ServerIp on
port 443. Check that NVGS Server Control is open and that both laptops are on
the same production LAN. A building-network firewall or Wi-Fi client isolation
cannot be repaired by this installer.
"@
}

[System.Windows.Forms.MessageBox]::Show(
    $connectionMessage,
    "NVGS Client Setup",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null

exit 0
