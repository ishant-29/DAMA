import sqlite3
conn = sqlite3.connect('test.db')
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', [r[0] for r in cur.fetchall()])

# Check DailyPerformance
try:
    cur.execute('SELECT * FROM daily_performance ORDER BY date DESC LIMIT 1')
    row = cur.fetchone()
    if row:
        print('\nDailyPerformance:', row)
    else:
        print('No DailyPerformance data')
except Exception as e:
    print(f'Error: {e}')

# Check Trades
try:
    cur.execute('SELECT COUNT(*), SUM(CASE WHEN pnl_percent > 0 THEN 1 ELSE 0 END), AVG(pnl_percent) FROM trades WHERE status IN ("CLOSED", "EXPIRED")')
    row = cur.fetchone()
    if row:
        total, wins, avg = row
        print(f'\nTrades - Total: {total}, Wins: {wins}, Avg PnL: {avg}')
except Exception as e:
    print(f'Error: {e}')

conn.close()
