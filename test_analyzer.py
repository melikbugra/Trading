from financia.analyzer import StockAnalyzer
import pandas as pd

def test_binance_fetch():
    print("Testing Binance Fetch (BTCUSDT)...")
    try:
        # Test 1: Auto-detection
        print("\nTest 1: Auto-detection (BTCUSDT)")
        analyzer = StockAnalyzer('BTCUSDT', horizon='short')
        print(f"Market: {analyzer.market}")
        print(f"Data Shape: {analyzer.data.shape}")
        if not analyzer.data.empty:
            print(f"Last Candle: {analyzer.data.index[-1]}")
            print(analyzer.data.tail(1))
        else:
            print("❌ Data is empty!")
            
        # Test 2: Explicit Market
        print("\nTest 2: Explicit Market (ETHUSDT -> binance)")
        analyzer2 = StockAnalyzer('ETHUSDT', horizon='short', market='binance')
        print(f"Market: {analyzer2.market}")
        if not analyzer2.data.empty:
            print("✅ Data fetched successfully")
        else:
            print("❌ Data is empty!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_bist_fetch():
    print("\nTesting BIST Fetch (THYAO.IS)...")
    try:
        analyzer = StockAnalyzer('THYAO.IS', horizon='short')
        print(f"Market: {analyzer.market}")
        print(f"Data Shape: {analyzer.data.shape}")
        if not analyzer.data.empty:
            print("✅ Data fetched successfully")
        else:
            print("❌ Data is empty!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_binance_fetch()
    test_bist_fetch()
