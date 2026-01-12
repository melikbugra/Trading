import pandas as pd
import yfinance as yf
from financia.analyzer import StockAnalyzer
import time
from tqdm import tqdm
import os

# BIST100 Tickers (Snapshot)
BIST100 = [
    "AEFES.IS", "AGHOL.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS",
    "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ANHYT.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS",
    "ASUZU.IS", "AYDEM.IS", "BAGFS.IS", "BASGZ.IS", "BERA.IS", "BIMAS.IS", "BIOEN.IS",
    "BOBET.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CEMTS.IS",
    "CIMSA.IS", "DOHOL.IS", "DOAS.IS", "ECILC.IS", "ECZYT.IS", "EGEEN.IS",
    "EKGYO.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUREN.IS", "FENER.IS",
    "FROTO.IS", "GARAN.IS", "GENIL.IS", "GESAN.IS", "GLYHO.IS", "GSDHO.IS", "GUBRF.IS",
    "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS", "ISCTR.IS", "ISDMR.IS", "ISFIN.IS",
    "ISGYO.IS", "ISMEN.IS", "KCAER.IS", "KCHOL.IS", "KONTR.IS", "KONYA.IS",
    "KORDS.IS", "KOZAL.IS", "KOZAA.IS", "KRDMD.IS", "KZBGY.IS", "MAVI.IS", "MGROS.IS",
    "MIATK.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PENTA.IS", "PETKM.IS", "PGSUS.IS",
    "PSGYO.IS", "QUAGR.IS", "SAHOL.IS", "SASA.IS", "SAYAS.IS", "SDTTR.IS", "SISE.IS",
    "SKBNK.IS", "SMRTG.IS", "SOKM.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS",
    "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUKAS.IS", "TUPRS.IS", "TURSG.IS",
    "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "YYLGD.IS",
    "ZOREN.IS"
]

def generate_dataset(horizon, output_file, period=None, interval=None):
    """
    Generates a massive dataset for the given horizon.
    """
    print(f"\nGenerators started for Horizon: {horizon.upper()}")
    print(f"Target File: {output_file}")
    
    all_data = []
    
    for ticker in tqdm(BIST100):
        try:
            # Instantiate Analyzer with extended period
            analyzer = StockAnalyzer(ticker, horizon=horizon, period=period, interval=interval)
            
            # Check if data is empty
            if analyzer.data is None or len(analyzer.data) < 200:
                print(f"Skipping {ticker}: Not enough data.")
                continue
                
            # Generate Features
            df_features = analyzer.prepare_rl_features()
            
            # Add Ticker column (for reference, though agent won't use it)
            df_features['Ticker'] = ticker
            
            # Add Timestamp (index)
            df_features.reset_index(inplace=True)
            
            all_data.append(df_features)
            
            # Be nice to API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    if not all_data:
        print("No data collected.")
        return
        
    # Concatenate
    final_df = pd.concat(all_data, ignore_index=True)
    
    # Save to Parquet
    final_df.to_parquet(output_file, index=False)
    print(f"Saved {len(final_df)} rows to {output_file}")
    print("Columns:", list(final_df.columns))

if __name__ == "__main__":
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # 1. Short Term (Hourly - 2 Years)
    generate_dataset('short', 'data/dataset_short.parquet', period='730d', interval='1h')
    
    # 1.5 Short-Mid Term (4 Hours - Resampled from 2 Years Hourly)
    generate_dataset('short-mid', 'data/dataset_short_mid.parquet', period='730d', interval='1h')
    
    # 2. Medium Term (Daily - 10 Years)
    generate_dataset('medium', 'data/dataset_medium.parquet', period='10y', interval='1d')
    
    # 3. Long Term (Weekly - Max)
    generate_dataset('long', 'data/dataset_long.parquet', period='max', interval='1wk')
