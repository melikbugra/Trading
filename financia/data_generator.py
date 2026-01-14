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

from datetime import datetime, timedelta

def generate_dataset(horizon, output_file, period=None, interval=None):
    """
    Generates a massive dataset for the given horizon.
    Optimized: Uses incremental updates if file exists.
    """
    print(f"\nGenerators started for Horizon: {horizon.upper()}")
    print(f"Target File: {output_file}")
    
    existing_df = None
    last_date_map = {} # Ticker -> Last Timestamp
    
    # 1. Load Existing Data if Available
    if os.path.exists(output_file):
        print(f"File exists. Loading for incremental update...")
        try:
            existing_df = pd.read_parquet(output_file)
            print(f"Loaded {len(existing_df)} rows.")
            
            # Determine Date Column
            date_col = 'Date' if 'Date' in existing_df.columns else 'Datetime'
            
            if date_col in existing_df.columns:
                # Ensure datetime
                existing_df[date_col] = pd.to_datetime(existing_df[date_col], utc=True)
                
                # Group by Ticker to find max date per ticker
                max_dates = existing_df.groupby('Ticker')[date_col].max()
                last_date_map = max_dates.to_dict()
                print(f"Found existing data for {len(last_date_map)} tickers.")
        except Exception as e:
            print(f"Error loading existing file: {e}. Starting fresh.")
            existing_df = None

    all_data = [] # Will hold NEW data chunks
    
    total_new_rows = 0
    
    for ticker in tqdm(BIST100):
        try:
            start_date = None
            end_date = None
            
            # Determine Fetch Strategy
            if ticker in last_date_map:
                # Incremental Logic
                last_ts = last_date_map[ticker]
                
                # Safety Margin / Warmup for Indicators
                # We need context (e.g. 200 bars) before the last valid data to calculate fresh indicators for new data.
                # Heuristic: 
                # Hourly -> 60 days
                # Daily -> 365 days
                # Weekly -> 730 days
                
                warmup_days = 60
                if interval == '1d': warmup_days = 400
                elif interval == '1wk': warmup_days = 800
                
                # Fetch Start
                start_dt = last_ts - timedelta(days=warmup_days)
                
                # yfinance expects str 'YYYY-MM-DD' or datetime
                # Using datetime directly is fine
                start_date = start_dt
                end_date = datetime.now()
                
                # If gap is too small (e.g. run twice same hour), skip?
                # yfinance handles minimal fetches well.
                
                # print(f" {ticker}: Updating from {last_ts} (Fetch start: {start_date})")
                
                # Instantiate with Start/End
                analyzer = StockAnalyzer(ticker, horizon=horizon, interval=interval, start=start_date, end=end_date)
            else:
                # Fresh Fetch
                # print(f" {ticker}: Fresh Fetch")
                analyzer = StockAnalyzer(ticker, horizon=horizon, period=period, interval=interval)
            
            # Check if data is empty
            if analyzer.data is None or len(analyzer.data) < 5: # Minimal checks
                 # print(f"Skipping {ticker}: Not enough data.")
                 continue
                 
            # Generate Features
            # This calculates indicators on the WHOLE fetched chunk (Warmup + New)
            df_features = analyzer.prepare_rl_features()
            
            # Add Metrics
            df_features['Ticker'] = ticker
            df_features.reset_index(inplace=True)
            
            # Rename index to generic 'Date'/'Datetime' if needed, usually reset_index gives 'Date' or 'Datetime' or 'index' depending on yfinance
            # prepare_rl_features usually keeps index as DatetimeIndex, reset makes it a column.
            
            # Identify Date Column in New Data
            new_date_col = 'Date' if 'Date' in df_features.columns else 'Datetime'
            if new_date_col not in df_features.columns and 'index' in df_features.columns:
                 # Sometimes reset_index makes 'index'
                 df_features.rename(columns={'index': 'Datetime'}, inplace=True)
                 new_date_col = 'Datetime'

            # Ensure UTC for comparison
            if new_date_col in df_features.columns:
                df_features[new_date_col] = pd.to_datetime(df_features[new_date_col], utc=True)
            
                # FILTER: Keep only NEW rows
                if ticker in last_date_map:
                    last_ts = last_date_map[ticker]
                    # Filter > last_ts
                    new_rows = df_features[df_features[new_date_col] > last_ts]
                    
                    if not new_rows.empty:
                        all_data.append(new_rows)
                        total_new_rows += len(new_rows)
                else:
                    # All are new
                    all_data.append(df_features)
                    total_new_rows += len(df_features)
            
            # Be nice to API
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    # Merge Logic
    if total_new_rows == 0:
        print("No new data found for any ticker.")
        # If we have existing data, we should probably just return or ensure it's saved?
        # If output file exists, we are good.
        return
        
    print(f"Collected {total_new_rows} new rows.")
    
    # Concatenate New Data
    new_data_df = pd.concat(all_data, ignore_index=True)
    
    # SAVE INCREMENTAL UPDATE (BACKUP)
    update_dir = "data/updates"
    os.makedirs(update_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{update_dir}/update_{horizon.lower()}_{timestamp_str}.parquet"
    try:
        new_data_df.to_parquet(backup_file, index=False)
        print(f"Archived incremental update to: {backup_file}")
    except Exception as e:
        print(f"Warning: Could not save update backup: {e}")
    
    # Merge with Existing
    if existing_df is not None:
        # Align columns?
        # Improve robustness: use concat
        final_df = pd.concat([existing_df, new_data_df], ignore_index=True)
        
        # Deduplicate just in case (e.g. overlaps)
        # Sort by Date
        date_col = 'Date' if 'Date' in final_df.columns else 'Datetime'
        if date_col in final_df.columns:
             final_df[date_col] = pd.to_datetime(final_df[date_col], utc=True)
             final_df.drop_duplicates(subset=['Ticker', date_col], keep='last', inplace=True)
             final_df.sort_values(by=['Ticker', date_col], inplace=True)
    else:
        final_df = new_data_df
        
    # Determine Date Range for Archival Filename
    date_col = 'Date' if 'Date' in final_df.columns else 'Datetime'
    
    if date_col in final_df.columns:
        final_df[date_col] = pd.to_datetime(final_df[date_col])
        # min_date = final_df[date_col].min().strftime("%Y%m%d")
        # max_date = final_df[date_col].max().strftime("%Y%m%d")
        
        # Archival versioning is good but can fill disk. Let's stick to overwriting target for now as per user flow.
        # Maybe save backup?
        # base_name, ext = os.path.splitext(output_file)
        # versioned_file = f"{base_name}_{max_date}{ext}"
        # final_df.to_parquet(versioned_file, index=False)
        
    # Save Standard Copy (For Pipeline/Training)
    final_df.to_parquet(output_file, index=False)
    print(f"Saved {len(final_df)} rows to Standard Path: {output_file}")

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
