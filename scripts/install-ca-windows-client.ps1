param(
    [Parameter(Mandatory = $true)]
    [string]$CertificatePath,

    [switch]$Install
)

$ErrorActionPreference = "Stop"
$resolvedCertificate = (Resolve-Path -LiteralPath $CertificatePath).Path
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
    $resolvedCertificate
)

Write-Host "NVGS certificate subject: $($certificate.Subject)"
Write-Host "SHA-1 thumbprint: $($certificate.Thumbprint)"
Write-Host "SHA-256 fingerprint:"
certutil.exe -hashfile $resolvedCertificate SHA256

if (-not $Install) {
    Write-Host ""
    Write-Host "No trust setting was changed."
    Write-Host "After approval and fingerprint verification, run PowerShell as Administrator:"
    Write-Host ".\scripts\install-ca-windows-client.ps1 -CertificatePath `"$resolvedCertificate`" -Install"
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdministrator) {
    throw "Run PowerShell as Administrator to install a trusted root certificate."
}

Import-Certificate `
    -FilePath $resolvedCertificate `
    -CertStoreLocation "Cert:\LocalMachine\Root" | Out-Null

Write-Host "NVGS certificate installed for this Windows laptop."
Write-Host "Close and reopen the browser before testing."
