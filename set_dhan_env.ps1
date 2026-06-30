# set_dhan_env.ps1
# Run this before executing the downloader on Windows PowerShell
# .\set_dhan_env.ps1

$env:DHAN_CLIENT_ID = "2606304333"
$env:DHAN_ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbkNvbnN1bWVyVHlwZSI6IlNFTEYiLCJwYXJ0bmVySWQiOiIiLCJkaGFuQ2xpZW50SWQiOiIyNjA2MzA0MzMzIiwid2ViaG9va1VybCI6Imh0dHBzOi8vc2FuZGJveC5kaGFuLmNvL3YyIiwiaXNzIjoiZGhhbiIsImV4cCI6MTc4NTM5NDgwNX0.fw1ixYi42Hd1FDkfUkLnXgfOXmNhTBA4AYAnqNYY1OcpgFVsGd1MgkseefQ22LVtOjCjWiwlI6Sd9GDPnRWGIA"

Write-Host "Dhan environment variables set." -ForegroundColor Green
Write-Host "Client ID: $($env:DHAN_CLIENT_ID)"
