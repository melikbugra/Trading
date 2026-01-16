# RL Trading System Analysis Report
## Comprehensive Review for Intraday Trading Strategy

**Tarih:** 2026-01-16
**Amaç:** Gün içi al-sat ile küçük kar elde etme
**Piyasalar:** BIST100 (15dk gecikmeli yfinance) + Binance (canlı)

---

## Executive Summary

Bu rapor, mevcut RL trading sisteminizi bilimsel literatür ve endüstri best practice'leri ışığında analiz etmektedir. Sistemin güçlü yanları olduğu gibi, özellikle **veri gecikmesi**, **reward function tasarımı** ve **transaction cost modelleme** konularında kritik iyileştirme alanları tespit edilmiştir.

---

## 1. DATA PIPELINE ANALYSIS

### 1.1 Veri Kaynakları

| Piyasa | Kaynak | Gecikme | Sorun Seviyesi |
|--------|--------|---------|----------------|
| BIST100 | yfinance | 15 dakika | KRITIK |
| Binance | ccxt | ~0 | Uygun |

### 1.2 KRITIK SORUN: 15 Dakika Veri Gecikmesi

**Mevcut Durum:**
- Eğitim verisi: yfinance'ten 15dk gecikmeli
- Canlı işlem: Midas'tan gerçek zamanlı
- Bu uyumsuzluk **train-test distribution shift** yaratır

**Bilimsel Perspektif:**
> "If you test a trading strategy using delayed data, the amazing results you see are an illusion. The strategy might completely fall apart with live, real-time data because it was built on a flawed foundation."
> — [Intrinio Research](https://intrinio.com/blog/understanding-the-impact-of-15-minute-delayed-stock-prices-on-market-analysis)

**Problem Detayı:**
```
Senaryo: Model saat 10:00'da "BUY" sinyali üretir
- Eğitimde: 10:00 verisiyle 10:00 fiyatından al
- Canlıda: 10:00 verisiyle (aslında 09:45 verisi) al
  → 15dk içinde fiyat çoktan hareket etmiş olabilir
```

**Önerilen Çözümler:**

1. **Eğitimde Gecikme Simülasyonu** (Recommended)
   - Eğitim sırasında sinyalleri 15dk delay ile uygula
   - `evaluate.py:528` satırında bunu yapmışsınız, iyi!

2. **Daha Uzun Timeframe Kullanımı**
   - 1 saatlik mumlarla 15dk gecikme daha az kritik
   - 4 saatlik mumlarla neredeyse ihmal edilebilir

3. **Gerçek Zamanlı Veri Kaynağı**
   - Foreks/Matriks API
   - Interactive Brokers API (IBKR)

### 1.3 Timeframe Seçimi: 1 Saat

**Mevcut:** 1 saatlik mumlar (`interval='1h'`)

**Bilimsel Değerlendirme:**

| Timeframe | Avantajlar | Dezavantajlar |
|-----------|------------|---------------|
| 1 dakika | Çok sinyal, scalping | Gürültü, yüksek işlem maliyeti |
| 15 dakika | Dengeli | 15dk gecikme ile uyumsuz |
| **1 saat** | **Trend görünür, gürültü az** | **Daha az fırsat** |
| 4 saat | Güçlü trendler | Gün içi için yetersiz sinyal |

**Literatür Önerisi:**
> "The 1-hour to 4-hour interval is preferred by many active traders as it allows tracking intraday trends while filtering out short-term noise."
> — [RealTrading](https://realtrading.com/trading-blog/best-time-frame-day-trading/)

**SONUÇ:** 1 saatlik timeframe, 15dk gecikmeli veri için **UYGUN** bir seçim. Gecikme oranı sadece %25 (15dk/60dk).

---

## 2. STATE SPACE ANALYSIS

### 2.1 Mevcut Feature Set (~48 features)

```python
# analyzer.py:1925 - prepare_rl_features()

# Price Components (4)
Log_Return, Shadow_Up, Shadow_Down, Body

# Trend Indicators (12)
Dist_MA_Short, Dist_MA_Long, Dist_DEMA, Dist_KAMA,
Dist_SuperTrend, SuperTrend_Dir, Ichimoku_TK, Ichimoku_Cloud,
Dist_SAR, Alligator_Spread, Aroon_Osc, Dist_Median

# Momentum Oscillators (10)
RSI_Norm, Stoch_K_Norm, Williams_Norm, Fisher_Norm,
MACD_Norm, ADX_Norm, DMI_Dir, CMF, MFI_Norm, WaveTrend_Diff

# Volume & Volatility (4)
Rel_Volume, ATR_Pct, BB_Width, BB_Position

# Divergence Signals (5)
RSI_Div, MACD_Div, CMF_Div, MFI_Div, WaveTrend_Div

# Account State (3) - trading_env.py:95
in_position, unrealized_pnl, time_progress
```

### 2.2 Değerlendirme

**OLUMLU:**
- Feature normalization yapılmış ([-1,1] veya [0,1] aralığında)
- Account state dahil edilmiş (position awareness)
- Divergence sinyalleri rolling correlation ile hesaplanıyor (akıllı yaklaşım)

**EKSIK/IYILESTIRME ALANLARI:**

1. **Market Regime Indicator YOK**
   - Volatility regime (low/medium/high)
   - Trend strength regime

2. **Multi-Timeframe Features YOK**
   - Günlük trend yönü
   - Haftalık destek/direnç seviyeleri

3. **Order Flow / Depth YOK**
   - Bid-Ask spread
   - Volume profile

**Literatür Referansı:**
> "The state space in the trading environment consists of historical price data and technical indicators. A continuous action space can be applied with a range of 0 to 1."
> — [arXiv: RL Framework for Quant Trading](https://arxiv.org/html/2411.07585v1)

### 2.3 Önerilen Ek Features

```python
# Market Regime
df['Volatility_Regime'] = (atr / atr.rolling(100).mean()).clip(0.5, 2.0)
df['Trend_Regime'] = adx / 100.0  # Zaten var ama regime olarak kullanılabilir

# Multi-Timeframe (Eğer veri varsa)
df['Daily_Trend'] = ...  # Günlük MA yönü

# Time-based
df['Hour_of_Day'] = df.index.hour / 24.0  # Saat bilgisi
df['Day_of_Week'] = df.index.dayofweek / 5.0  # Gün bilgisi
```

---

## 3. ACTION SPACE ANALYSIS

### 3.1 Mevcut Tasarım

```python
# trading_env.py:21
self.action_space = spaces.Discrete(3)  # 0: HOLD, 1: BUY, 2: SELL
```

### 3.2 Değerlendirme

**SORUN: All-in / All-out Stratejisi**

```python
# trading_env.py:164-173
if action == 1:  # BUY
    shares_to_buy = int(self.balance / cost)  # TÜM BAKİYE İLE AL

if action == 2:  # SELL
    # TÜM HİSSELERİ SAT
```

**Problem:**
- Risk yönetimi yok
- Position sizing yok
- Partial entry/exit yok

**Literatür Önerisi:**
> "A hybrid action space with Discrete(3) for action type [Hold, Buy, Sell] and Continuous[0,1] for position size" performs better than pure discrete actions.
> — [Hugging Face: stock-trading-rl-agent](https://huggingface.co/Adilbai/stock-trading-rl-agent)

### 3.3 Önerilen İyileştirme: Hybrid Action Space

**Seçenek A: Discrete Position Sizes**
```python
# 5 seviyeli action space
# 0: HOLD
# 1: BUY 25%
# 2: BUY 50%
# 3: SELL 50%
# 4: SELL 100%
self.action_space = spaces.Discrete(5)
```

**Seçenek B: Continuous Action Space (Daha Gelişmiş)**
```python
# PPO için uygun
# Action: [-1, 1] -> -1 full sell, 0 hold, +1 full buy
self.action_space = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)
```

---

## 4. REWARD FUNCTION ANALYSIS

### 4.1 Mevcut Tasarım

```python
# trading_env.py:201-216
def _calculate_reward(self, prev_net_worth):
    # Net Worth değişimi
    reward = (self.net_worth - prev_net_worth) / self.initial_balance
    reward *= 100  # Scale up

    # Time penalty (pozisyondayken)
    if self.shares_held > 0:
        reward -= 0.001

    return reward
```

### 4.2 Kritik Değerlendirme

**SORUNLAR:**

1. **Sparse Reward Problemi**
   - Sadece net worth değişimi reward
   - Agent pozisyon almadan öğrenemez
   - Early training'de çok az sinyal

2. **Risk-Adjusted Return YOK**
   - Sharpe ratio yok
   - Max drawdown cezası yok
   - Volatility penalty yok

3. **Transaction Cost Reward'da YOK**
   - Commission environment'ta var ama reward'da explicit değil
   - Agent gereksiz trade'lerden kaçınmayı öğrenemiyor

**Literatür Referansı:**
> "Using just the PnL sign (positive/negative) as the reward works better as the model learns faster. This binary reward structure allows the model to focus on consistently making profitable trades."
> — [MDPI: Self-Rewarding RL](https://www.mdpi.com/2227-7390/12/24/4020)

### 4.3 Önerilen Reward Function

```python
def _calculate_reward(self, prev_net_worth, action):
    # 1. Base: Portfolio Return (Log Return daha stabil)
    if prev_net_worth > 0:
        log_return = np.log(self.net_worth / prev_net_worth)
    else:
        log_return = 0

    reward = log_return * 100  # Scale

    # 2. Risk Penalty: Drawdown
    peak = max(self.peak_net_worth, self.net_worth)
    self.peak_net_worth = peak
    drawdown = (peak - self.net_worth) / peak
    reward -= drawdown * 10  # Drawdown cezası

    # 3. Transaction Cost Penalty
    if action != 0:  # BUY or SELL
        reward -= 0.1  # Her işlem için küçük ceza

    # 4. Holding Penalty (Opsiyonel - mevcut sistemde var)
    # if self.shares_held > 0:
    #     reward -= 0.001

    # 5. Winning Trade Bonus (Opsiyonel)
    if action == 2 and hasattr(self, 'last_entry_price'):
        pnl = (self.prices[self.current_step] - self.last_entry_price) / self.last_entry_price
        if pnl > 0:
            reward += 0.5  # Karlı trade bonusu

    return reward
```

---

## 5. TRANSACTION COSTS & SLIPPAGE

### 5.1 Mevcut Durum

```python
# train.py:27-30
if market == 'binance':
    commission = 0.0015  # 0.15%
else:
    commission = 0.0  # BIST için 0% (Kullanıcı komisyon ödemiyor - DOĞRU)

# trading_env.py:162
slippage = 0.0  # Slippage kapalı
```

### 5.2 BIST100 Komisyon: %0 DOĞRU

Kullanıcı BIST100'de komisyon ödemediğini belirtti. Bu durumda %0 komisyon doğru.

### 5.3 SORUN: Slippage YOK

**Slippage (Gerçekçi Tahminler):**
- Likit hisseler (THYAO, GARAN): %0.05 - %0.1
- Orta likidite: %0.1 - %0.3
- Düşük likidite: %0.5 - %1.0

**Literatür Uyarısı:**
> "One of the most prevalent beginner mistakes when implementing trading models is to neglect (or grossly underestimate) the effects of transaction costs on a strategy."
> — [QuantStart](https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/)

### 5.4 Önerilen Düzeltme

```python
# trading_env.py - Slippage eklenmeli
slippage = 0.001  # 0.1% minimum slippage (komisyon 0 kalabilir)
```

---

## 6. TRAINING & EVALUATION

### 6.1 Mevcut Eğitim Konfigürasyonu

```python
# train.py:38-50
model = PPO(
    env=env,
    network_arch=[256, 256],
    time_steps=5_000_000,      # 5M timesteps
    learning_rate=0.0001,
    batch_size=256,
    gamma=0.99,
    entropy_coef=0.01,
    device='cpu',
)
```

### 6.2 Değerlendirme

**OLUMLU:**
- PPO algoritması intraday trading için uygun
- Network architecture yeterli (256x256)
- Learning rate conservative (0.0001) - stabil eğitim

**İYİLEŞTİRME ALANLARI:**

1. **Gamma (0.99) Çok Yüksek**
   - Intraday trading için 0.95-0.97 daha uygun
   - Uzun vadeli ödüllere çok ağırlık veriyor

2. **Entropy Coefficient (0.01) Düşük Olabilir**
   - Exploration yetersiz kalabilir
   - 0.02-0.05 deneyebilirsiniz

3. **Train/Val Split Sorunu**
   ```python
   # train.py:21-23
   split_idx = int(len(df) * 0.9)
   train_df = df.iloc[:split_idx]
   val_df = df.iloc[split_idx:]
   ```
   - Temporal split iyi (data leakage yok)
   - Ama validation sadece son %10 (tek market regime)

### 6.3 Önerilen Eğitim Stratejisi

```python
# Walk-Forward Validation
# Örnek: 6 aylık pencerelerle

# Period 1: Train 0-12 ay, Test 12-13 ay
# Period 2: Train 1-13 ay, Test 13-14 ay
# Period 3: Train 2-14 ay, Test 14-15 ay
# ...

# Final model: Ensemble veya son dönem modeli
```

---

## 7. INFERENCE & PRODUCTION

### 7.1 Mevcut Karar Mekanizması

```python
# get_model_decision.py - analyze_ticker()

# 1. Veriyi çek
# 2. Features hesapla
# 3. Model predict
# 4. Indicator konsensüsü ile karşılaştır
# 5. Final karar üret
```

### 7.2 Değerlendirme

**OLUMLU:**
- Model + Indicator hybrid yaklaşımı akıllı
- Score sistemi (0-100) anlaşılır
- Divergence sinyalleri dahil

**SORUNLAR:**

1. **Account State Eksik** (Kritik!)
   ```python
   # get_model_decision.py - RL prediction'da
   account_obs = np.array([0.0, 0.0, 0.0])  # Sabit!
   ```
   - Mevcut pozisyon bilgisi modele gitmiyor
   - Model "zaten pozisyondayım" bilmeden karar veriyor

2. **Confidence Threshold YOK**
   - Model ne kadar emin olursa olsun sinyal üretiyor
   - Düşük confidence'da HOLD olmalı

### 7.3 Önerilen İyileştirme

```python
def analyze_ticker(self, ticker, current_position=None, entry_price=None, ...):
    # Account state'i gerçek değerlerle doldur
    in_pos = 1.0 if current_position and current_position.shares > 0 else 0.0

    unrealized_pnl = 0.0
    if entry_price and current_position:
        unrealized_pnl = (current_price - entry_price) / entry_price

    account_obs = np.array([in_pos, unrealized_pnl, 0.5], dtype=np.float32)

    # Confidence threshold
    action_probs = model.get_action_probabilities(obs)
    max_prob = max(action_probs)

    if max_prob < 0.6:  # Düşük confidence
        return "HOLD"
```

---

## 8. SUMMARY: SCORECARD

| Kategori | Puan | Durum |
|----------|------|-------|
| **Data Pipeline** | 6/10 | 15dk gecikme - eğitimde simüle edilmeli |
| **Timeframe Seçimi** | 8/10 | 1H uygun |
| **State Space** | 7/10 | İyi, market regime eksik |
| **Action Space** | 5/10 | All-in/out riskli |
| **Reward Function** | 5/10 | Risk-adjusted yok |
| **Transaction Costs** | 6/10 | Komisyon OK, slippage eksik |
| **Training Setup** | 7/10 | Gamma çok yüksek |
| **Production Inference** | 6/10 | Account state eksik |

**GENEL PUAN: 6.3/10**

---

## 9. PRIORITIZED ACTION ITEMS

### Kritik (Hemen Yapılmalı)

1. **Signal Delay Simülasyonu Ekle (Eğitime)**
   - Model t anında karar alır, işlem t+1 bar open fiyatından yapılır
   - Bu 15dk gecikmeyi simüle eder

2. **Account State'i Inference'a Ekle**
   - Mevcut pozisyon bilgisini modele geçir

3. **Slippage Ekle**
   ```python
   slippage = 0.001  # %0.1
   ```

### Önemli (1-2 Hafta)

4. **Reward Function Güncelle**
   - Risk-adjusted (drawdown penalty)
   - Transaction cost penalty

5. **Gamma Düşür**
   ```python
   gamma = 0.97  # 0.99'dan düşür
   ```

6. **Position Sizing Ekle**
   - En az 3 seviyeli: %25, %50, %100

### İyileştirme (Uzun Vade)

7. **Multi-Timeframe Features**
   - Günlük trend bilgisi

8. **Walk-Forward Validation**
   - Daha robust model seçimi

9. **Ensemble Strategy**
   - PPO + A2C + DDPG ensemble

---

## 10. REFERENCES

### Academic Papers
- [Self-Rewarding Deep RL for Trading](https://www.mdpi.com/2227-7390/12/24/4020) - MDPI 2024
- [Deep RL for Automated Stock Trading: Ensemble Strategy](https://arxiv.org/html/2511.12120v1) - arXiv
- [RL Framework for Quantitative Trading](https://arxiv.org/html/2411.07585v1) - arXiv 2024
- [Deep RL with Positional Context for Intraday Trading](https://arxiv.org/html/2406.08013v1) - arXiv 2024

### Industry Resources
- [QuantStart: Backtesting Best Practices](https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/)
- [Intrinio: 15-Minute Delay Impact](https://intrinio.com/blog/understanding-the-impact-of-15-minute-delayed-stock-prices-on-market-analysis)
- [RealTrading: Best Timeframes](https://realtrading.com/trading-blog/best-time-frame-day-trading/)
- [LuxAlgo: Slippage & Liquidity](https://www.luxalgo.com/blog/backtesting-limitations-slippage-and-liquidity-explained/)

### Implementation Examples
- [FinRL Library](https://github.com/AI4Finance-Foundation/FinRL)
- [Hugging Face: Stock Trading RL Agent](https://huggingface.co/Adilbai/stock-trading-rl-agent)

---

*Bu rapor, mevcut sistemin bilimsel analizi ve iyileştirme önerileri içermektedir. Tüm öneriler piyasa koşullarına göre test edilmeli ve ayarlanmalıdır.*
