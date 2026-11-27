# RF Notları — 433 MHz ve 915 MHz

## 1. Temel Kavramlar

| Terim | Anlamı |
|---|---|
| **RSSI** | Alınan sinyal gücü (dBm). Daha az negatif = daha güçlü. |
| **Gürültü tabanı** | Ortamdaki arka plan gürültüsü (dBm). |
| **SNR** | Sinyal − gürültü (dB). Link kalitesinin asıl göstergesi. |
| **Fade margin** | Alınan güç − alıcı hassasiyeti. Sönümlenmeye karşı yedek pay; ≥ 10 dB hedeflenir. |
| **FSPL** | Serbest uzay yol kaybı: `20·log10(d_km) + 20·log10(f_MHz) + 32.44` |
| **Fresnel bölgesi** | Sinyalin taşındığı elips; ilk bölgenin ≥ %60'ı engelsiz olmalı. |

SiK telsizlerde RADIO_STATUS ham değerdir: `dBm ≈ ham / 1.9 − 127`, `SNR ≈ (rssi − noise) / 1.9`
(`telemetri/linkstats.py`).

## 2. Bant Karşılaştırması

`python -m telemetri.link_budget` çıktısı (20 dBm, 2,15 dBi antenler, 1 dB kablo kaybı, −108 dBm hassasiyet):

| Mesafe | 433 MHz FSPL | 915 MHz FSPL | 433 marj | 915 marj | Fresnel r (433 / 915) |
|---|---|---|---|---|---|
| 1 km | 85,2 dB | 91,7 dB | 46,1 dB | 39,6 dB | 13,2 m / 9,1 m |
| 5 km | 99,1 dB | 105,6 dB | 32,2 dB | 25,7 dB | 29,4 m / 20,2 m |

| | 433 MHz | 915 MHz |
|---|---|---|
| Yol kaybı | ~6,5 dB daha az | daha fazla |
| Engelleri aşma | daha iyi | daha zayıf |
| Anten boyu (λ/2) | ~35 cm | ~16 cm |
| Fresnel bölgesi | daha geniş → yer etkisi büyük | daha dar |
| Kullanılabilir bant | dar (433,05–434,79 MHz) | geniş (bölgeye bağlı) |
| Yerel mevzuat | KMC sınırları (güç) kontrol edilmeli | Türkiye'de lisanssız kullanım bant planına göre kontrol edilmeli; alternatif 868 MHz |

## 3. Sahada Yapılan İyileştirmeler (kontrol listesi)

1. **Anten polarizasyonu:** hava ve yer antenleri aynı (dikey) polarizasyonda.
2. **Yer anteninin yüksekliği:** Fresnel bölgesi için tripod ile yükseltme.
3. **Gövde gölgelemesi:** hava anteni gövde altına, aşağı bakar şekilde.
4. **EMI:** telsiz ve antenin ESC, güç dağıtım kartı ve GPS'ten uzaklaştırılması.
5. **ECC ve hava hızı:** hata oranı ile bant genişliği arasında denge.
6. **Akış hızları:** gereksiz mesajları kısarak telsiz tamponunun taşmasını önleme.

Her değişiklikten sonra aynı test profili tekrarlanır ve `analyze.py` ile önce/sonra karşılaştırılır.
