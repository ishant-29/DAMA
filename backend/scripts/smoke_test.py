#!/usr/bin/env python3
"""
NSE Signal Engine — End-to-End Smoke Test
Validates all critical API endpoints are responding correctly.
Run: python -m scripts.smoke_test (from backend directory)
"""

import sys
import requests

BASE_URL = "http://localhost:8000"
PASS = 0
FAIL = 0
TOKEN = None


def check(name: str, url: str, method: str = "GET", expected_status: int = 200, timeout: int = 10, **kwargs):
    global PASS, FAIL, TOKEN
    try:
        # Add auth token if we have one
        if TOKEN and 'headers' not in kwargs:
            kwargs['headers'] = {"Authorization": f"Bearer {TOKEN}"}
        elif TOKEN and 'headers' in kwargs:
            kwargs['headers']["Authorization"] = f"Bearer {TOKEN}"

        resp = getattr(requests, method.lower())(f"{BASE_URL}{url}", timeout=timeout, **kwargs)
        
        # Special case for register (already exists is ok)
        if url == "/auth/register" and resp.status_code == 400:
            PASS += 1
            print(f"  ✅ {name} — 400 User already exists (OK)")
            return

        if resp.status_code == expected_status:
            PASS += 1
            print(f"  ✅ {name} — {resp.status_code}")
            
            # Save token if this was login
            if url == "/auth/login":
                TOKEN = resp.json().get("access_token")
        else:
            FAIL += 1
            print(f"  ❌ {name} — expected {expected_status}, got {resp.status_code}: {resp.text[:120]}")
    except requests.ConnectionError:
        FAIL += 1
        print(f"  ❌ {name} — Connection refused (is backend running?)")
    except requests.Timeout:
        FAIL += 1
        print(f"  ❌ {name} — Timed out ({timeout}s)")
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name} — {type(e).__name__}: {e}")


def main():
    print("\n═══════════════════════════════════════════")
    print("  NSE Signal Engine — Smoke Test")
    print("═══════════════════════════════════════════\n")

    # ── Health ──
    print("▸ Health Checks")
    check("Health endpoint", "/health")

    # ── Auth ──
    print("\n▸ Auth")
    check("Register user", "/auth/register",
          method="POST", json={"username": "smoketest", "password": "smoketest123"},
          expected_status=200)

    # Login uses form URL-encoded data format per OAuth2 specification
    check("Login", "/auth/login",
          method="POST", data={"username": "smoketest", "password": "smoketest123"},
          headers={"Content-Type": "application/x-www-form-urlencoded"},
          expected_status=200)

    # ── Signals ──
    print("\n▸ Signal Endpoints")
    check("Today's signals", "/signals/today")
    check("High-risk signals", "/signals/high-risk")

    # ── Sector ──
    print("\n▸ Sector")
    check("Sector sentiment", "/sector/sentiment")

    # ── Analytics ──
    print("\n▸ Analytics")
    check("Market mood", "/analytics/market-mood")
    check("Market regime", "/analytics/market-regime", timeout=30)
    check("Sector report", "/analytics/sectors", timeout=30)
    check("System stats", "/analytics/system-stats")

    # ── Performance ──
    print("\n▸ Performance")
    check("Active trades", "/performance/active-trades")
    check("Recent suggestions", "/performance/recent-suggestions?days=7")

    # ── Paper Trading ──
    print("\n▸ Paper Trading")
    check("Paper portfolio", "/paper/portfolio")

    # ── Fetch ──
    print("\n▸ Data Fetch")
    check("Stock list", "/fetch/stocks")

    # ── Summary ──
    total = PASS + FAIL
    print(f"\n═══════════════════════════════════════════")
    print(f"  Results: {PASS}/{total} passed, {FAIL} failed")
    print(f"═══════════════════════════════════════════\n")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
