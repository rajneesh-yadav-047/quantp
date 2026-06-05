import sys
import pandas as pd
from backend.smartapi import SmartAPIClient

client = SmartAPIClient(
    api_key="XVo1YSxt",
    client_code="AAAL440762",
    password="9572"
)
# we need to login
success = client.connect(totp="123456") # The TOTP is dynamic but let's see what happens. Wait, 123456 will fail.
print("Connected:", success)
