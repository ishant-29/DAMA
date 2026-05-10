
import requests

BACKEND_URL = "http://localhost:8090"

def check_signal_analyze(symbol):
    url = f"{BACKEND_URL}/signals/analyze/{symbol}"
    print(f"Fetching signal analysis for {symbol} from {url}...")
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response: Success JSON")
        else:
            print(f"Response Text: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching signal analysis: {e}")

if __name__ == "__main__":
    check_signal_analyze("IDEAFORGE.NS")
