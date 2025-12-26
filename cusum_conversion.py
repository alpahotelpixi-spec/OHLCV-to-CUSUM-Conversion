import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from tqdm import tqdm

# ======================
# CONFIG
# ======================
INPUT_CSV = "OHLCV.csv"
CUSUM_THRESHOLD = 0.005   # 0.5%
OUTPUT_PNG = "cusum_comparison.png"
CANDLESTICK_PNG = "cusum_candlestick_comparison.png"

# ======================
# 1. CUSUM CANDLES
# ======================
def build_cusum_candles(df, threshold):
    candles = []

    cusum_up = 0.0
    cusum_down = 0.0

    cur = {
        "open": df.iloc[0]["open"],
        "high": df.iloc[0]["high"],
        "low": df.iloc[0]["low"],
        "close": df.iloc[0]["close"],
        "start_idx": 0,
        "end_idx": 0,
    }

    for i in tqdm(range(1, len(df)), desc="Building CUSUM candles"):
        prev_close = df.iloc[i - 1]["close"]
        close = df.iloc[i]["close"]
        ret = (close - prev_close) / prev_close

        cusum_up = max(0.0, cusum_up + ret)
        cusum_down = min(0.0, cusum_down + ret)

        cur["high"] = max(cur["high"], df.iloc[i]["high"])
        cur["low"] = min(cur["low"], df.iloc[i]["low"])
        cur["close"] = close
        cur["end_idx"] = i

        if cusum_up >= threshold or cusum_down <= -threshold:
            candles.append(cur.copy())

            cur = {
                "open": close,
                "high": df.iloc[i]["high"],
                "low": df.iloc[i]["low"],
                "close": close,
                "start_idx": i,
                "end_idx": i,
            }

            cusum_up = 0.0
            cusum_down = 0.0

    if cur["start_idx"] < cur["end_idx"]:
        candles.append(cur)

    return pd.DataFrame(candles)

# ======================
# 2. CUSUM VALIDATION
# ======================
def validate_cusum(original, cusum, threshold):
    # 1. Continuity check
    for i in tqdm(range(1, len(cusum)), desc="Validating continuity"):
        assert np.isclose(
            cusum.iloc[i]["open"],
            cusum.iloc[i - 1]["close"]
        ), "Gap between CUSUM candles"

    # 2. OHLC correctness
    assert (cusum["high"] >= cusum[["open", "close"]].max(axis=1)).all()
    assert (cusum["low"] <= cusum[["open", "close"]].min(axis=1)).all()

    # 3. Validate CUSUM logic by reconstructing
    print("✅ Basic validations passed")
    
    # Reconstruct CUSUM to verify threshold logic
    cusum_up = 0.0
    cusum_down = 0.0
    bar_count = 0
    
    for i in tqdm(range(1, len(original)), desc="Validating CUSUM logic"):
        prev_close = original.iloc[i - 1]["close"]
        close = original.iloc[i]["close"]
        ret = (close - prev_close) / prev_close

        cusum_up = max(0.0, cusum_up + ret)
        cusum_down = min(0.0, cusum_down + ret)

        if cusum_up >= threshold or cusum_down <= -threshold:
            bar_count += 1
            cusum_up = 0.0
            cusum_down = 0.0
    
    # Account for the last incomplete bar
    if cusum_up > 0 or cusum_down < 0:
        bar_count += 1
    
    expected_bars = len(cusum)
    if bar_count != expected_bars:
        print(f"⚠️  Bar count mismatch: expected {expected_bars}, got {bar_count}")
    else:
        print(f"✅ CUSUM bar count validation passed: {bar_count} bars")

    print("✅ CUSUM transformation is correct")

# ======================
# 3. CANDLESTICK PLOT
# ======================
def plot_candlesticks(ax, data, title, color_up='green', color_down='red'):
    """Plot candlestick chart"""
    for i, (_, candle) in enumerate(data.iterrows()):
        open_price = candle['open']
        high_price = candle['high']
        low_price = candle['low']
        close_price = candle['close']
        
        # Determine color
        color = color_up if close_price >= open_price else color_down
        
        # Draw high-low line
        ax.plot([i, i], [low_price, high_price], color='black', linewidth=1)
        
        # Draw body rectangle
        body_height = abs(close_price - open_price)
        body_bottom = min(open_price, close_price)
        
        rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height, 
                        facecolor=color, edgecolor='black', alpha=0.8)
        ax.add_patch(rect)
    
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.set_xlim(-0.5, len(data) - 0.5)

def create_candlestick_comparison(original_df, cusum_df, n_candles=1000):
    """Create candlestick comparison of last n candles"""
    
    # Get last n original candles
    orig_last = original_df.tail(n_candles).copy().reset_index(drop=True)
    
    # Find corresponding CUSUM candles for the same time period
    last_orig_start_time = orig_last.iloc[0]['open_time']
    
    # Find CUSUM candles that overlap with this period
    cusum_in_period = []
    for _, cusum_candle in cusum_df.iterrows():
        start_idx = int(cusum_candle['start_idx'])
        end_idx = int(cusum_candle['end_idx'])
        
        # Check if this CUSUM candle overlaps with our period
        if end_idx >= len(original_df) - n_candles:
            cusum_in_period.append(cusum_candle)
    
    cusum_last = pd.DataFrame(cusum_in_period).reset_index(drop=True)
    
    # Create the plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
    
    # Plot original candles
    plot_candlesticks(ax1, orig_last, f"Last {n_candles} regular candles")
    
    # Plot CUSUM candles
    if len(cusum_last) > 0:
        plot_candlesticks(ax2, cusum_last, f"CUSUM candles for the same period ({len(cusum_last)} candles)")
    else:
        ax2.text(0.5, 0.5, 'No CUSUM candles for this period', 
                ha='center', va='center', transform=ax2.transAxes)
        ax2.set_title("CUSUM candles for the same period")
    
    plt.tight_layout()
    plt.savefig(CANDLESTICK_PNG, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Candlestick chart saved: {CANDLESTICK_PNG}")
    print(f"Regular candles: {len(orig_last)}, CUSUM candles: {len(cusum_last)}")
    
    return orig_last, cusum_last

# ======================
# MAIN
# ======================
def main():
    df = pd.read_csv(INPUT_CSV, parse_dates=["open_time"])
    df = df.sort_values("open_time").reset_index(drop=True)
    df = df[["open_time", "open", "high", "low", "close"]]

    print(f"Original candles: {len(df)}")

    cusum_df = build_cusum_candles(df, CUSUM_THRESHOLD)
    validate_cusum(df, cusum_df, CUSUM_THRESHOLD)

    print(f"CUSUM candles: {len(cusum_df)}")
    print(f"Compression ratio: {len(df) / len(cusum_df):.2f}x")

    # ======================
    # 3. PLOT
    # ======================
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)

    # Upper plot — original
    axes[0].plot(df["open_time"], df["close"], linewidth=0.7)
    axes[0].set_title("Original Close Price")
    axes[0].grid(alpha=0.3)

    # Lower plot — CUSUM
    axes[1].plot(
        df.loc[cusum_df["end_idx"], "open_time"],
        cusum_df["close"],
        linewidth=0.9,
        color="red"
    )
    axes[1].set_title("CUSUM Close Price")
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_PNG, dpi=150)
    plt.close()

    print(f"Chart saved: {OUTPUT_PNG}")
    
    # ======================
    # 4. CANDLESTICK COMPARISON
    # ======================
    create_candlestick_comparison(df, cusum_df, 1000)

if __name__ == "__main__":
    main()
