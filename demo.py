from financia.analyzer import StockAnalyzer

if __name__ == "__main__":
    try:
        ticker = "ENKAI.IS"
        indicators = ["RSI", "MACD", "BB", "MA", "DMI", "SAR", "STOCH", "STOCHRSI", "SUPERTREND", "ICHIMOKU", "ALLIGATOR", "AWESOME", "MFI", "CMF", "WAVETREND", "KAMA", "GATOR", "DEMAND_INDEX", "WILLIAMS_R", "AROON", "DEMA", "MEDIAN", "FISHER"]
        
        stock_short = StockAnalyzer(ticker, horizon='short')
        # --- Short Term ---
        print(f"\n--- Analyzing {ticker} (Short Term - Hourly) ---")
        df_short = stock_short.get_indicator_decisions(*indicators)
        vol_short, vol_ratio_short = stock_short.get_volume_info()
        print(f"Volume: {vol_short} | Ratio: {vol_ratio_short}x")
        print(df_short[['Indicator', 'Decision', 'Divergence', 'Value']])
        
        score_short, details_short = stock_short.calculate_final_score(df_short)
        sentiment_short = "NEUTRAL"
        if score_short >= 80: sentiment_short = "STRONG BUY"
        elif score_short >= 60: sentiment_short = "BUY"
        elif score_short <= 20: sentiment_short = "STRONG SELL"
        elif score_short <= 40: sentiment_short = "SELL"
        
        print("\n" + "="*40)
        print(f" FINAL SCORECARD: {score_short:.2f}/100")
        print(f" SENTIMENT: {sentiment_short}")
        print("-" * 40)
        print(" Category Breakdown:")
        for cat, val in details_short.items():
            print(f"  - {cat:<10}: {val:.2f}/100")
        print("="*40)

        # --- Medium Term ---
        print(f"\n--- Analyzing {ticker} (Medium Term - Daily) ---")
        stock_medium = StockAnalyzer(ticker, horizon='medium')
        df_medium = stock_medium.get_indicator_decisions(*indicators)
        vol_medium, vol_ratio_medium = stock_medium.get_volume_info()
        print(f"Volume: {vol_medium} | Ratio: {vol_ratio_medium}x")
        print(df_medium[['Indicator', 'Decision', 'Divergence', 'Value']])
        
        score_med, details_med = stock_medium.calculate_final_score(df_medium)
        sentiment_med = "NEUTRAL"
        if score_med >= 80: sentiment_med = "STRONG BUY"
        elif score_med >= 60: sentiment_med = "BUY"
        elif score_med <= 20: sentiment_med = "STRONG SELL"
        elif score_med <= 40: sentiment_med = "SELL"
        
        print("\n" + "="*40)
        print(f" FINAL SCORECARD: {score_med:.2f}/100")
        print(f" SENTIMENT: {sentiment_med}")
        print("-" * 40)
        print(" Category Breakdown:")
        for cat, val in details_med.items():
            print(f"  - {cat:<10}: {val:.2f}/100")
        print("="*40)
        
        # --- Long Term ---
        print(f"\n--- Analyzing {ticker} (Long Term - Weekly) ---")
        stock_long = StockAnalyzer(ticker, horizon='long')
        df_long = stock_long.get_indicator_decisions(*indicators)
        vol_long, vol_ratio_long = stock_long.get_volume_info()
        print(f"Volume: {vol_long} | Ratio: {vol_ratio_long}x")
        print(df_long[['Indicator', 'Decision', 'Divergence', 'Value']])
        
        score_long, details_long = stock_long.calculate_final_score(df_long)
        sentiment_long = "NEUTRAL"
        if score_long >= 80: sentiment_long = "STRONG BUY"
        elif score_long >= 60: sentiment_long = "BUY"
        elif score_long <= 20: sentiment_long = "STRONG SELL"
        elif score_long <= 40: sentiment_long = "SELL"
        
        print("\n" + "="*40)
        print(f" FINAL SCORECARD: {score_long:.2f}/100")
        print(f" SENTIMENT: {sentiment_long}")
        print("-" * 40)
        print(" Category Breakdown:")
        for cat, val in details_long.items():
            print(f"  - {cat:<10}: {val:.2f}/100")
        print("="*40)
        
    except Exception as e:
        print(f"An error occurred: {e}")
