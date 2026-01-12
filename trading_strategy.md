# RL Trading Bot Strategy Guide

Bu doküman, oluşturulan **RL (Reinforcement Learning) Trading Botu** ile BIST gibi **15 dakika gecikmeli veri** sunan piyasalarda nasıl güvenli işlem yapılacağını anlatır.

## 1. Temel Felsefe: "Bot Önerir, İnsan Onaylar"

Botunuz bir **"Otomatik Pilot"** değil, 7/24 çalışan bir **"Radar"** sistemidir.
*   **Botun Görevi:** Tüm portföyü sürekli taramak ve teknik olarak olgunlaşan fırsatları (AL/SAT) yakalayıp size bildirmek.
*   **Sizin Göreviniz:** Bildirim geldiğinde **CANLI FİYATA** bakıp, tetiği çekip çekmemeye karar vermek.

---

## 2. 15 Dakika Gecikme Nasıl Yönetilir?

Botun kullandığı veri (örn: `yfinance`) 15 dakika geriden gelir.
*   Bot saat **14:15**'te bir sinyal ürettiğinde, aslında **14:00**'daki mum kapanışına göre karar vermiştir.
*   O 15 dakika içinde piyasada ani haberler veya fiyat hareketleri olabilir.

### İşlem Akışı
1.  **Bildirim Gelir:** Bot "THYAO AL (Fiyat: 100.00)" der.
2.  **Canlı Kontrol:** Banka/Aracı Kurum uygulamasını açıp anlık fiyata bakarsınız.
3.  **Karar Anı:**
    *   **Fiyat Benzer (örn: 100.10 - 100.20):** Trend devam ediyor, güvenli. -> **İŞLEM YAP**
    *   **Fiyat Çok Uçmuş (örn: 103.00):** Tren kaçmış olabilir veya tepeden alıyor olabilirsiniz. -> **BEKLE / İPTAL**
    *   **Fiyat Tersine Dönmüş (örn: 98.00):** Sinyal o 15 dakikada bozulmuş. -> **İPTAL**

---

## 3. Emir Tipi: Neden "Limit Emir"?

Asla **Piyasa Emri (Market Order)** kullanmayın. Piyasa emri, o an tahtada hangi fiyat varsa oradan işlem yapar ve sığ tahtalarda (veya oynak anlarda) çok pahalıya patlayabilir.

Her zaman **Limit Emir** kullanın.

### Sayısal Örnekler (THYAO)

#### Senaryo A: ALIM (BUY)
Botun gördüğü (15 dk önceki) fiyat: **100.00 TL**

| Durum | Canlı Fiyat | Strateji | Limit Emir Fiyatı | Mantık |
| :--- | :--- | :--- | :--- | :--- |
| **Normal** | 100.20 TL | **AL** | **100.25 TL** | Canlı fiyatın 1-2 kademe üstü. "100.25'e kadar alırım ama daha pahalıya almam." |
| **Uçmuş** | 103.50 TL | **BEKLE** | **100.50 TL** | Botun gördüğü fiyata yakın (destek) emir girip geri çekilmesini (pullback) bekle. |
| **Düşmüş** | 99.00 TL | **İNCEL** | **99.00 TL** | Fiyat düşüyor, destekten dönmesini bekle, acele etme. |

#### Senaryo B: SATIM (SELL)
Botun gördüğü (15 dk önceki) fiyat: **110.00 TL**

| Durum | Canlı Fiyat | Strateji | Limit Emir Fiyatı | Mantık |
| :--- | :--- | :--- | :--- | :--- |
| **Düşüyor** | 109.50 TL | **SAT** | **109.40 TL** | Canlı fiyatın 1-2 kademe altı. "Hemen satılsın diye azıcık iniyorum." |
| **Çakılmış** | 105.00 TL | **STOP** | **104.90 TL** | Zarar kes (Stop Loss). Daha fazla düşmeden elden çıkar. |
| **Artmış** | 111.00 TL | **SAT** | **110.90 TL** | Şanslısın! Ekstra kârı al ve hemen sat. |

---

## 4. Altın Kural

> **Limit Emir Fiyatı = Canlı Fiyat +/- 1 veya 2 Kademe**

*   **Alırken:** Canlı Fiyat + Bir miktar tolerans (Hemen almak için).
*   **Satarken:** Canlı Fiyat - Bir miktar tolerans (Hemen satmak için).

Bu strateji, **"Slippage" (Fiyat Kayması)** riskini ortadan kaldırır ve sizi piyasa yapıcıların anlık fiyat manipülasyonlarından korur.
