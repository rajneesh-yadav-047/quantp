import os
import sys
import pandas as pd
from dotenv import load_dotenv
from backend.smartapi import SmartAPIClient

load_dotenv()

def get_totp() -> str:
    return input("Enter current TOTP: ").strip()

def main():
    client = SmartAPIClient(
        api_key=os.getenv("SMARTAPI_API_KEY"),
        client_code=os.getenv("SMARTAPI_CLIENT_CODE"),
        password=os.getenv("SMARTAPI_PASSWORD"),
    )
    
    totp = get_totp()
    success = client.connect(totp=totp)
    
    if not success:
        print("Login failed, aborting data fetch test.")
        return 1
        
    print("Successfully connected. Attempting to fetch historical candles for SBIN...")
    
    df = client.fetch_historical_candles(
        symbol="SBIN",
        from_date="2024-05-20 09:15",
        to_date="2024-05-20 15:30",
        interval="FIVE_MINUTE"
    )
    
    print("Data fetch result:")
    if df is not None and not df.empty:
        print(f"Fetched {len(df)} records.")
        print(df.head())
    else:
        print("No records fetched.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
