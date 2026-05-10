
import sys
import os
import requests
import socket
import time

BACKEND_URL = "http://localhost:8090"

def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        return s.connect_ex((host, port)) == 0

def check_backend_health():
    print(f"Checking if backend is running at {BACKEND_URL}...")
    if not check_port("localhost", 8090):
        print("❌ Port 8090 is NOT open. Backend is likely NOT running.")
        return False
    
    try:
        response = requests.get(f"{BACKEND_URL}/health")
        if response.status_code == 200:
            print("✅ Backend health check passed.")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code} for /health")
            return False
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")
        return False


def check_fetch_historical(symbol):
    url = f"{BACKEND_URL}/fetch/historical?symbol={symbol}"
    print(f"Fetching historical data for {symbol} from {url}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                print(f"✅ Successfully fetched {len(data)} records for {symbol}.")
            else:
                print(f"⚠️ Response OK but no data returned: {data}")
        else:
            print(f"❌ Failed to fetch historical data: Status {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching historical data: {e}")

def check_signal_analyze(symbol):
    url = f"{BACKEND_URL}/signals/analyze/{symbol}"
    print(f"Fetching signal analysis for {symbol} from {url}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Successfully fetched signal analysis for {symbol}.")
        else:
            print(f"❌ Failed to fetch signal analysis: Status {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching signal analysis: {e}")

def check_sector_sentiment():
    url = f"{BACKEND_URL}/sector/sentiment"
    print(f"Fetching sector sentiment from {url}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Successfully fetched sector sentiment (count: {len(data)}).")
            # Print first 3 items to check values
            for i, item in enumerate(data[:3]):
                print(f"  Sector {i+1}: {item.get('sector')} | Score: {item.get('score')} | AvgChange: {item.get('avg_change_percent')}")
        else:
            print(f"❌ Failed to fetch sector sentiment: Status {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching sector sentiment: {e}")

if __name__ == "__main__":
    if check_backend_health():
        check_fetch_historical("HGINFRA.NS")
        check_signal_analyze("HGINFRA.NS")
        check_sector_sentiment()
    else:
        print("Please start the backend server to fix this issue.")
