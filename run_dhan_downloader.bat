@echo off
:: run_dhan_downloader.bat
:: One-click runner for NIFTY Jan–May 2026 options download

:: Load credentials
set DHAN_CLIENT_ID=2606304333
set DHAN_ACCESS_TOKEN=eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbkNvbnN1bWVyVHlwZSI6IlNFTEYiLCJwYXJ0bmVySWQiOiIiLCJkaGFuQ2xpZW50SWQiOiIyNjA2MzA0MzMzIiwid2ViaG9va1VybCI6Imh0dHBzOi8vc2FuZGJveC5kaGFuLmNvL3YyIiwiaXNzIjoiZGhhbiIsImV4cCI6MTc4NTM5NDgwNX0.fw1ixYi42Hd1FDkfUkLnXgfOXmNhTBA4AYAnqNYY1OcpgFVsGd1MgkseefQ22LVtOjCjWiwlI6Sd9GDPnRWGIA

:: Run downloader for Jan–May 2026
py dhan_options_downloader.py --start 2026-01-01 --end 2026-05-31 --symbol NIFTY --lot-size 75

pause
