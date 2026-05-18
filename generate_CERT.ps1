# 1. Ask the user for the project location
$projectPath = Read-Host "Enter the absolute path to your Python project (e.g., C:\Users\546493)"
$projectPath = $projectPath.Trim()

# 2. Ask the user for the IP address
$ipAddress = Read-Host "Enter the IP address of your webserver (e.g., 192.168.1.100)"
$ipAddress = $ipAddress.Trim()

# 3. Create the target ssl folder if it doesn't exist
$sslFolder = Join-Path $projectPath "ssl"
if (!(Test-Path $sslFolder)) {
    New-Item -ItemType Directory -Force -Path $sslFolder | Out-Null
    Write-Host "`n[+] Created folder: $sslFolder" -ForegroundColor Green
}

Write-Host "[*] Generating SSL keys for IP: $ipAddress..." -ForegroundColor Cyan

# 4. Generate the self-signed certificate natively in Windows
$cert = New-SelfSignedCertificate -DnsName $ipAddress -CertStoreLocation "Cert:\CurrentUser\My" -KeyExportPolicy Exportable -KeySpec Signature

# 5. Format and write the Certificate Chain (cert.pem)
$certBytes = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
$certBase64 = [Convert]::ToBase64String($certBytes, [Base64FormattingOptions]::InsertLineBreaks)
$certPem = "-----BEGIN CERTIFICATE-----`n$certBase64`n-----END CERTIFICATE-----"
$certFilePath = Join-Path $sslFolder "cert.pem"
Set-Content -Path $certFilePath -Value $certPem

# 6. Format and write the Private Key (key.pem)
$key = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
$keyBytes = $key.ExportPkcs8PrivateKey()
$keyBase64 = [Convert]::ToBase64String($keyBytes, [Base64FormattingOptions]::InsertLineBreaks)
$keyPem = "-----BEGIN PRIVATE KEY-----`n$keyBase64`n-----END PRIVATE KEY-----"
$keyFilePath = Join-Path $sslFolder "key.pem"
Set-Content -Path $keyFilePath -Value $keyPem

Write-Host "`n[SUCCESS] Files created successfully inside your project folder!" -ForegroundColor Green
Write-Host "-> $certFilePath" -ForegroundColor Yellow
Write-Host "-> $keyFilePath`n" -ForegroundColor Yellow
