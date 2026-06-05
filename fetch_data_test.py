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
        
    print("\n--- Testing Symbol Resolution ---")
    symbols_to_test = ["SBIN", "NSE:SBIN-EQ", "NFO:SBIN-FUT"]
    for s in symbols_to_test:
        res = client.resolve_symbol(s, from_date="2024-05-20")
        if res:
            print(f"Symbol '{s}' resolved to: token={res.get('token')}, symbol={res.get('symbol')}, exch_seg={res.get('exch_seg')}, inst_type={res.get('instrumenttype')}, expiry={res.get('expiry')}")
        else:
            print(f"Symbol '{s}' failed to resolve.")
            
    print("\nAttempting to fetch historical candles for NSE:SBIN-EQ...")
    df = client.fetch_historical_candles(
        symbol="NSE:SBIN-EQ",
        from_date="2026-06-02 09:15",
        to_date="2026-06-02 15:30",
        interval="FIVE_MINUTE"
    )
    
    print("\nData fetch result:")
    if df is not None and not df.empty:
        print(f"Fetched {len(df)} records.")
        print("Data columns:", list(df.columns))
        print("First 5 records:")
        print(df.head())
    else:
        print("No records fetched.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
