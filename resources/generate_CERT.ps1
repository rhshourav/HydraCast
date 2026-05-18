# ==========================================
# Hydracast SSL Certificate Generator
# - CN = IP/hostname
# - O  = Hydracast
# - OU = created by rhshourav
# Supports:
#   * PowerShell 7+ native export
#   * OpenSSL fallback
#   * OpenSSL auto-install via winget
# ==========================================

Clear-Host

function Write-Section {
    param([string]$Text)
    Write-Host ""
    Write-Host $Text -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Text)
    Write-Host $Text -ForegroundColor Green
}

function Write-Warn {
    param([string]$Text)
    Write-Host $Text -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Text)
    Write-Host $Text -ForegroundColor Red
}

function Test-ValidPath {
    param([string]$Path)
    return [bool](Test-Path -LiteralPath $Path)
}

function Test-IpAddress {
    param([string]$Value)
    $parsed = $null
    return [System.Net.IPAddress]::TryParse($Value, [ref]$parsed)
}

function Get-OpenSslPath {
    $paths = @(
        "openssl.exe",
        "C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
        "C:\Program Files\OpenSSL-Win32\bin\openssl.exe",
        "C:\Program Files\Git\usr\bin\openssl.exe"
    )

    foreach ($p in $paths) {
        $cmd = Get-Command $p -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }

    return $null
}

function Ensure-OpenSsl {
    $openSslExe = Get-OpenSslPath
    if ($openSslExe) {
        return $openSslExe
    }

    Write-Warn "[!] OpenSSL not found."

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "[*] Installing OpenSSL using winget..." -ForegroundColor Cyan
        try {
            winget install -e --id ShiningLight.OpenSSL --silent --accept-package-agreements --accept-source-agreements | Out-Null
        }
        catch {
            Write-Warn "[!] winget install command returned an error."
        }

        Start-Sleep -Seconds 3

        $possible = @(
            "C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
            "C:\Program Files\OpenSSL-Win32\bin\openssl.exe"
        )

        foreach ($p in $possible) {
            if (Test-Path $p) {
                return $p
            }
        }
    }

    return $null
}

function Export-NativePem {
    param(
        [Parameter(Mandatory = $true)] $Cert,
        [Parameter(Mandatory = $true)] [string] $CertFilePath,
        [Parameter(Mandatory = $true)] [string] $KeyFilePath
    )

    $certBytes = $Cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
    $certPem = @"
-----BEGIN CERTIFICATE-----
$([Convert]::ToBase64String($certBytes, [Base64FormattingOptions]::InsertLineBreaks))
-----END CERTIFICATE-----
"@
    Set-Content -LiteralPath $CertFilePath -Value $certPem -Encoding ascii

    $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($Cert)
    if (-not $rsa) {
        throw "RSA private key could not be read from the certificate."
    }

    $keyBytes = $rsa.ExportPkcs8PrivateKey()
    $keyPem = @"
-----BEGIN PRIVATE KEY-----
$([Convert]::ToBase64String($keyBytes, [Base64FormattingOptions]::InsertLineBreaks))
-----END PRIVATE KEY-----
"@
    Set-Content -LiteralPath $KeyFilePath -Value $keyPem -Encoding ascii
}

function Generate-OpenSslConfig {
    param(
        [Parameter(Mandatory = $true)] [string] $IpOrHost,
        [Parameter(Mandatory = $true)] [string] $ConfigPath
    )

    $isIp = Test-IpAddress $IpOrHost

    if ($isIp) {
        @"
[req]
default_bits = 2048
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
CN = $IpOrHost
O = Hydracast
OU = created by rhshourav

[v3_req]
subjectAltName = @alt_names

[alt_names]
IP.1 = $IpOrHost
"@ | Set-Content -LiteralPath $ConfigPath -Encoding ascii
    }
    else {
        @"
[req]
default_bits = 2048
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
CN = $IpOrHost
O = Hydracast
OU = created by rhshourav

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = $IpOrHost
"@ | Set-Content -LiteralPath $ConfigPath -Encoding ascii
    }
}

# ------------------------------------------
# Input
# ------------------------------------------

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Hydracast SSL Certificate Generator    " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$projectPath = (Read-Host "`nEnter the absolute path to your Python project").Trim()
$ipAddress   = (Read-Host "Enter the IP address or hostname for the certificate").Trim()

if (-not (Test-ValidPath $projectPath)) {
    Write-Err "`n[ERROR] Project path does not exist."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($ipAddress)) {
    Write-Err "`n[ERROR] IP address/hostname cannot be empty."
    exit 1
}

# ------------------------------------------
# Create ssl folder
# ------------------------------------------

$sslFolder = Join-Path $projectPath "ssl"
if (-not (Test-Path -LiteralPath $sslFolder)) {
    New-Item -ItemType Directory -Force -Path $sslFolder | Out-Null
    Write-Ok "`n[+] Created folder: $sslFolder"
}

$certFilePath = Join-Path $sslFolder "cert.pem"
$keyFilePath  = Join-Path $sslFolder "key.pem"

Write-Section "[*] Starting SSL generation for: $ipAddress"

# ------------------------------------------
# Strategy 1: Native PowerShell 7+
# ------------------------------------------

$generated = $false

if ($PSVersionTable.PSVersion.Major -ge 7 -and $IsWindows) {
    try {
        Write-Ok "[+] PowerShell 7+ detected. Trying native generation..."

        $subject = "CN=$ipAddress, O=Hydracast, OU=created by rhshourav"

        # Use SAN for IP or DNS
        if (Test-IpAddress $ipAddress) {
            $textExt = @("2.5.29.17={text}IP=$ipAddress")
        }
        else {
            $textExt = @("2.5.29.17={text}DNS=$ipAddress")
        }

        $cert = New-SelfSignedCertificate `
            -Subject $subject `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -KeyExportPolicy Exportable `
            -KeyLength 2048 `
            -KeyAlgorithm RSA `
            -KeyUsage DigitalSignature, KeyEncipherment `
            -NotAfter (Get-Date).AddYears(5) `
            -TextExtension $textExt

        Export-NativePem -Cert $cert -CertFilePath $certFilePath -KeyFilePath $keyFilePath

        Write-Ok "`n[SUCCESS] Certificate generated natively."
        Write-Host "Certificate: $certFilePath" -ForegroundColor Yellow
        Write-Host "Private Key : $keyFilePath" -ForegroundColor Yellow
        $generated = $true
    }
    catch {
        Write-Warn "`n[WARNING] Native generation failed. Falling back to OpenSSL."
        Write-Warn $_.Exception.Message
    }
}

# ------------------------------------------
# Strategy 2: OpenSSL fallback
# ------------------------------------------

if (-not $generated) {
    $openSslExe = Ensure-OpenSsl

    if (-not $openSslExe) {
        Write-Err "`n[ERROR] OpenSSL could not be found or installed."
        Write-Host "Install OpenSSL manually or use PowerShell 7 on Windows." -ForegroundColor Red
        exit 1
    }

    Write-Ok "[+] Using OpenSSL: $openSslExe"

    $tempConfig = Join-Path $env:TEMP ("openssl-hydracast-" + [Guid]::NewGuid().ToString("N") + ".cnf")
    Generate-OpenSslConfig -IpOrHost $ipAddress -ConfigPath $tempConfig

    try {
        Write-Host "[*] Generating certificate with OpenSSL..." -ForegroundColor Cyan

        & $openSslExe req `
            -x509 `
            -newkey rsa:2048 `
            -nodes `
            -days 1825 `
            -keyout $keyFilePath `
            -out $certFilePath `
            -config $tempConfig `
            -extensions v3_req 2>$null

        if ((Test-Path -LiteralPath $certFilePath) -and (Test-Path -LiteralPath $keyFilePath)) {
            Write-Ok "`n[SUCCESS] SSL files created successfully using OpenSSL."
            Write-Host "Certificate: $certFilePath" -ForegroundColor Yellow
            Write-Host "Private Key : $keyFilePath" -ForegroundColor Yellow
            $generated = $true
        }
        else {
            Write-Err "`n[ERROR] OpenSSL did not create the files."
        }
    }
    finally {
        if (Test-Path -LiteralPath $tempConfig) {
            Remove-Item -LiteralPath $tempConfig -Force -ErrorAction SilentlyContinue
        }
    }
}

# ------------------------------------------
# Final validation
# ------------------------------------------

if ($generated) {
    Write-Section "[+] Done"
    Write-Host "  OU = created by rhshourav" -ForegroundColor Yellow
}
else {
    Write-Err "`n[ERROR] SSL generation failed."
    exit 1
}
