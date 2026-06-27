import sys
sys.path.insert(0, 'backend_v2')
from sqlalchemy import create_engine, text
from src.settings import Settings

settings = Settings()
engine = create_engine(settings.mysql_url)

with engine.connect() as conn:
    result = conn.execute(text("SELECT MAX(date) as latest_date FROM daily_ohlcv WHERE symbol = 'VHM'"))
    row = result.fetchone()
    print(f'Latest VHM date in MySQL: {row[0]}')
    
    result = conn.execute(text("SELECT COUNT(*) FROM daily_ohlcv WHERE symbol = 'VHM' AND date > '2026-04-28'"))
    count = result.fetchone()[0]
    print(f'VHM records after 2026-04-28: {count}')
