# Generate an RSA key-pair for Snowflake key-pair auth.
#
# openssl ships with Git for Windows but is NOT on PATH by default, so we call
# it by full path. Keys are written OUTSIDE the repo (~/.snowflake), mirroring
# how the GCP key lives in ~/.gcp. Nothing here is committed.
#
# Run:  .\snowflake\generate_key.ps1

$ErrorActionPreference = "Stop"

$openssl = "C:\Program Files\Git\usr\bin\openssl.exe"
if (-not (Test-Path $openssl)) {
    throw "openssl not found at $openssl. Install Git for Windows, or edit this path."
}

$keyDir = Join-Path $HOME ".snowflake"
New-Item -ItemType Directory -Force -Path $keyDir | Out-Null
$priv = Join-Path $keyDir "snowflake_rsa_key.p8"
$pub  = Join-Path $keyDir "snowflake_rsa_key.pub"

# Unencrypted PKCS#8 private key (no passphrase — simplest for a local/trial
# setup). To use a passphrase instead, add `-aes256` and set
# SNOWFLAKE_PRIVATE_KEY_PASSPHRASE for both dbt and the ingestion script.
& $openssl genpkey -algorithm RSA -out $priv -pkeyopt rsa_keygen_bits:2048
& $openssl rsa -in $priv -pubout -out $pub

Write-Host "`nPrivate key : $priv"
Write-Host "Public key  : $pub"

# Print the public-key BODY (no header/footer, no line breaks) — this is exactly
# what goes into 02_register_key.sql for RSA_PUBLIC_KEY.
$body = (Get-Content $pub) |
    Where-Object { $_ -notmatch "PUBLIC KEY" } |
    ForEach-Object { $_.Trim() }
Write-Host "`nRSA_PUBLIC_KEY value to paste into 02_register_key.sql:`n"
Write-Host ($body -join "")
