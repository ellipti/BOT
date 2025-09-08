"""
Sample data generator for Strategy Lab testing

Creates synthetic OHLCV data in CSV format for backtesting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Set random seed for reproducible data
np.random.seed(42)

def generate_sample_ohlcv(symbol: str, timeframe_minutes: int, num_bars: int = 1000, 
                          initial_price: float = 1800.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data with realistic patterns"""
    
    # Generate timestamps
    start_date = datetime(2024, 1, 1)
    timestamps = []
    current_time = start_date
    
    for _ in range(num_bars):
        timestamps.append(int(current_time.timestamp()))
        current_time += timedelta(minutes=timeframe_minutes)
    
    # Generate price data with trends and noise
    data = []
    price = initial_price
    trend = 0.0
    
    for i, ts in enumerate(timestamps):
        # Add some trending behavior
        if i % 50 == 0:
            trend = np.random.normal(0, 0.002)  # New trend every 50 bars
        
        # Random walk with trend
        price_change = np.random.normal(trend, 0.01) * price
        price += price_change
        
        # Generate OHLC from close price
        volatility = abs(np.random.normal(0, 0.005)) * price
        
        # Open is close of previous bar (approximately)
        if i == 0:
            open_price = price
        else:
            open_price = data[-1]['close'] + np.random.normal(0, 0.001) * price
            
        close_price = price
        
        # High and low around the open/close range
        high_price = max(open_price, close_price) + np.random.exponential(volatility * 0.3)
        low_price = min(open_price, close_price) - np.random.exponential(volatility * 0.3)
        
        # Volume (random but realistic)
        volume = max(100, np.random.lognormal(5, 1))
        
        data.append({
            'ts': ts,
            'open': round(open_price, 5),
            'high': round(high_price, 5), 
            'low': round(low_price, 5),
            'close': round(close_price, 5),
            'volume': round(volume, 0)
        })
    
    return pd.DataFrame(data)

def create_all_sample_data():
    """Create sample data for all symbols and timeframes in params.yaml"""
    
    # Define the symbols and timeframes to generate
    symbols = ["XAUUSD", "EURUSD", "GBPUSD"]
    timeframes = [30, 60, 240]  # Minutes
    
    # Base prices for different symbols
    base_prices = {
        "XAUUSD": 2000.0,   # Gold
        "EURUSD": 1.1000,   # EUR/USD
        "GBPUSD": 1.2500    # GBP/USD
    }
    
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    for symbol in symbols:
        for tf_minutes in timeframes:
            # Generate data
            df = generate_sample_ohlcv(
                symbol=symbol,
                timeframe_minutes=tf_minutes,
                num_bars=2000,  # 2000 bars should be enough for testing
                initial_price=base_prices[symbol]
            )
            
            # Save to CSV
            filename = f"{symbol}_M{tf_minutes}.csv"
            filepath = data_dir / filename
            
            df.to_csv(filepath, index=False)
            print(f"Created {filepath} with {len(df)} bars")
            
            # Print sample data info
            print(f"  Date range: {pd.to_datetime(df['ts'].min(), unit='s').strftime('%Y-%m-%d')} to {pd.to_datetime(df['ts'].max(), unit='s').strftime('%Y-%m-%d')}")
            print(f"  Price range: {df['close'].min():.5f} - {df['close'].max():.5f}")
            print(f"  Average volume: {df['volume'].mean():.0f}")
            print()

if __name__ == "__main__":
    print("Generating sample data for Strategy Lab testing...")
    create_all_sample_data()
    print("Sample data generation complete!")
