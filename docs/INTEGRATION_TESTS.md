# Entegrasyon Test Prosedürleri

Testler üç aşamada yürütülür: **masa (bench)** → **yer (ground)** → **uçuş (flight)**.
Her test için sonuç tablosu doldurulur ve CSV logları `logs/` altında saklanır.

## Aşama 1 — Masa Testleri

| ID | Test | Adımlar | Kabul kriteri |
|---|---|---|---|
| B-01 | Telsiz eşleşmesi | `sik_config.py --show --remote`, iki telsizin parametrelerini karşılaştır | NETID, AIR_SPEED, frekans, ECC, MAVLINK aynı |
| B-02 | UK ↔ telsiz seri | `config/ardupilot_telem.param` yükle, YKİ'de HEARTBEAT gör | 1 Hz HEARTBEAT, BAD_DATA yok |
| B-03 | Akış hızları | `monitor.py` 60 s | ATTITUDE ≈ 10 Hz, GLOBAL_POSITION_INT ≈ 5 Hz |
| B-04 | Görev yükleme | `mission_upload.py --wp config/example_mission.csv` | `upload OK`, `verify: OK` |
| B-05 | GCS failsafe | YKİ telsizinin USB'sini çek | 5 s sonra UK'de failsafe (pervanesiz) |
| B-06 | Araç zinciri | `scripts/bench_test.sh` | Rapor üretilir, CI yeşil |

## Aşama 2 — Yer Testleri (İHA yerde, motorlar kapalı)

| ID | Test | Adımlar | Kabul kriteri |
|---|---|---|---|
| G-01 | Anten yerleşimi | İHA'yı 360° döndür, RSSI kaydet | Herhangi bir yönde RSSI düşüşü < 10 dB |
| G-02 | Motor/ESC gürültüsü | Pervanesiz motorları %50 gazda çalıştır | Gürültü tabanı artışı < 3 dB, kayıp < %1 |
| G-03 | Mesafe yürüyüşü | İHA'yı 50 m adımlarla 500 m'ye taşı | RSSI eğrisi FSPL modeline yakın, kayıp < %2 |

## Aşama 3 — Uçuş Testleri

| ID | Test | Profil | Kabul kriteri |
|---|---|---|---|
| F-01 | Uzaklaşma | Düz hat, 50 m irtifa, kademeli uzaklaşma | Yarışma alanı mesafesinde SNR > 10 dB |
| F-02 | Manevra | 360° dönüş, yatış ≥ 30° | Anten gölgelemesinde kesinti < 1 s |
| F-03 | Görev uçuşu | Görev yükle → AUTO → RTL | Tüm görev boyunca kayıp < %2 |
| F-04 | Bant karşılaştırma | F-01 ve F-03'ü 433 ve 915 MHz ile tekrarla | `analyze.py` raporu |

## Kayıt Şablonu

| Tarih | Test ID | Bant | Hava/rüzgâr | Süre | Kayıp [%] | RSSI min [dBm] | SNR p5 [dB] | RTT p95 [ms] | Sonuç | Not |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |

## Sorun Giderme Notları

| Belirti | Olası neden | Çözüm |
|---|---|---|
| Yerdeyken bile yüksek kayıp | Yanlış NETID / farklı AIR_SPEED | B-01'i tekrarla |
| Belirli yönde RSSI düşüşü | Anten gövde/batarya gölgesinde | Anteni gövde altına, dikey konuma al |
| Motor çalışınca gürültü artışı | ESC/güç kablosu antene yakın | Kablo düzeni, ferrit, mesafe |
| RTT çok yüksek, kayıp yok | Telsiz tamponu dolu (txbuf düşük) | SR1_ hızlarını azalt |
| Görev yüklemede tekrarlar | Link marjinal | Yüklemeyi yakın mesafede yap; retry sayısını kontrol et |
