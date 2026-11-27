# Arayüz Kontrol Dokümanı (ICD) — Uçuş Kontrolcüsü ↔ Yer Kontrol İstasyonu

Bu doküman, mekanik ve yazılım ekipleriyle birlikte belirlenen uçuş kontrolcüsü (UK) – yer kontrol
istasyonu (YKİ) arayüz gereksinimlerini özetler.

## 1. Fiziksel Katman

| Kalem | Hava tarafı | Yer tarafı |
|---|---|---|
| Telemetri modülü | SiK uyumlu telsiz (433 MHz veya 915 MHz sürümü) | Aynı model, USB-UART |
| UK bağlantısı | TELEM1 (SERIAL1), 57600 8N1, akış kontrolü yok | USB CDC → YKİ bilgisayarı |
| Anten | Dikey dipol, gövde altında, GPS ve ESC kablolarından uzak | Dikey dipol, tripod, ≥ 2 m yükseklik |
| Besleme | UK TELEM portu 5 V (telsiz tepe akımı kontrol edildi) | USB |

**Montaj gereksinimleri (mekanik ekiple):** anten karbon fiber gövdenin gölgesinde kalmamalı; anten ile GPS
arasında ≥ 10 cm; telsiz modülü titreşim sönümleyici bant ile sabitlenmeli; konnektörler uçuş öncesi
kontrol listesinde.

## 2. Bağlantı (Link) Katmanı

| Parametre | Değer | Gerekçe |
|---|---|---|
| Hava hızı (AIR_SPEED) | 64 kbps | Menzil / bant genişliği dengesi |
| ECC | Açık | Bit hatalarını telsiz seviyesinde düzeltir, kayıp paket oranını düşürür |
| MAVLINK çerçeveleme | Açık | Telsiz MAVLink paket sınırlarını bilir, RADIO_STATUS ekler |
| NETID | Takıma özel | Yarışma alanındaki diğer takımlarla eşleşmeyi önler |
| Frekans atlamalı kanal | 433: 10 kanal, 915: 20 kanal | Dar bantlı girişime karşı dayanım |

Profil dosyaları: [`config/sik_433.txt`](../config/sik_433.txt), [`config/sik_915.txt`](../config/sik_915.txt)

## 3. Uygulama Katmanı — MAVLink v2

### 3.1 Aşağı link (İHA → YKİ)

| Mesaj | Hız | Akış grubu (SR1_) | İçerik |
|---|---|---|---|
| HEARTBEAT | 1 Hz | — | mod, arm durumu |
| ATTITUDE | 10 Hz | EXTRA1 | roll/pitch/yaw |
| GLOBAL_POSITION_INT | 5 Hz | POSITION | konum, irtifa, hız |
| VFR_HUD | 5 Hz | EXTRA2 | hava hızı, yer hızı, irtifa |
| SYS_STATUS / BATTERY_STATUS | 2 Hz | EXT_STAT | batarya, sensör sağlığı |
| GPS_RAW_INT | 2 Hz | EXT_STAT | uydu sayısı, fix tipi |
| RC_CHANNELS | 2 Hz | RC_CHAN | kumanda kanalları |
| RADIO_STATUS | ~1 Hz | (telsiz ekler) | RSSI, gürültü, hata sayaçları |
| MISSION_CURRENT | 2 Hz | EXT_STAT | aktif görev adımı |

### 3.2 Yukarı link (YKİ → İHA)

| Mesaj | Kullanım |
|---|---|
| HEARTBEAT (1 Hz) | GCS failsafe: 5 s gelmezse RTL (`FS_GCS_ENABLE=1`, `FS_GCS_TIMEOUT=5`) |
| COMMAND_LONG | arm/disarm, mod, kalkış |
| MISSION_COUNT / MISSION_ITEM_INT | görev yükleme (bkz. `mission_upload.py`) |
| PARAM_SET / PARAM_REQUEST_* | parametre işlemleri (sadece yerde) |
| TIMESYNC | gidiş-dönüş gecikme ölçümü (izleme aracı) |

### 3.3 Bant genişliği bütçesi

| Mesaj | Boyut (MAVLink2, imzasız) | Hız | Bayt/s |
|---|---|---|---|
| ATTITUDE | 40 B | 10 | 400 |
| GLOBAL_POSITION_INT | 40 B | 5 | 200 |
| VFR_HUD | 32 B | 5 | 160 |
| SYS_STATUS | 43 B | 2 | 86 |
| GPS_RAW_INT | 42 B | 2 | 84 |
| RC_CHANNELS | 54 B | 2 | 108 |
| Diğer (HB, RADIO_STATUS, ...) | — | — | ~150 |
| **Toplam** | | | **≈ 1,2 kB/s ≈ 9,5 kbps** |

64 kbps hava hızında ECC açıkken kullanılabilir net kapasite yaklaşık yarıya iner; bütçe bu kapasitenin
belirgin şekilde altında tutularak görev yükleme ve parametre trafiğine pay bırakılmıştır.

## 4. Zamanlama ve Hata Durumları

| Durum | Tespit | Tepki |
|---|---|---|
| Link kaybı (YKİ tarafı) | HEARTBEAT > 3 s yok | İzleme aracında CRITICAL, operatör uyarısı |
| Link kaybı (İHA tarafı) | GCS HEARTBEAT > 5 s yok | ArduPilot GCS failsafe → RTL |
| Görev öğesi kaybı | MISSION_REQUEST tekrarı | Öğe yeniden gönderilir (retry sayacı loglanır) |
| SNR < 10 dB | RADIO_STATUS | MARGINAL uyarısı, pilot mesafeyi azaltır |

## 5. Doğrulama
Her madde [INTEGRATION_TESTS.md](INTEGRATION_TESTS.md) içindeki bir test ile eşleştirilmiştir.
