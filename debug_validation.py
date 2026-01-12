import pandas as pd

# Load Data
df = pd.read_parquet("data/dataset_short.parquet")

# Validation Split
split_idx = int(len(df) * 0.8)
val_df = df.iloc[split_idx:].reset_index(drop=True)

# Check Tickers in first 5000 rows
subset = val_df.iloc[:5000]
tickers = subset['Ticker'].unique()

print(f"Validation Set Start Index: {split_idx}")
print(f"First 5000 rows contain tickers: {tickers}")

# Find transition points
diffs = subset['Ticker'] != subset['Ticker'].shift(1)
transitions = subset[diffs]
print("\nTransitions:")
print(transitions[['Ticker', 'Close']].head())

# Show Price Jump at transition
for idx in transitions.index:
    if idx == 0: continue
    prev = subset.iloc[idx-1]
    curr = subset.iloc[idx]
    print(f"\nJump at index {idx}:")
    print(f"  {prev['Ticker']} Close: {prev['Close']}")
    print(f"  {curr['Ticker']} Close: {curr['Close']}")
    change = (curr['Close'] - prev['Close']) / prev['Close'] * 100
    print(f"  Change: {change:.2f}%")
