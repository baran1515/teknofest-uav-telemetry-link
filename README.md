# TEKNOFEST İHA Platformu — Telemetri Haberleşme Mimarisi

![CI](https://github.com/baran1515/teknofest-uav-telemetry-link/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![MAVLink](https://img.shields.io/badge/MAVLink-v2-orange)
![RF](https://img.shields.io/badge/RF-433%20%2F%20915%20MHz-red)
![License](https://img.shields.io/badge/license-MIT-green)

> TEKNOFEST için geliştirilen çift motorlu İHA ile yer kontrol istasyonu arasında, uçuş boyunca telemetri
> ve görev verisini **çift yönlü**, saha koşullarında **kararlı ve düşük gecikmeli** taşıyan haberleşme hattı.

| | |
|---|---|
| **Proje türü** | Takım projesi (TEKNOFEST) |
| **Ortam** | Saha testleri — 433 MHz ve 915 MHz bantları |
| **Rolüm** | Telemetri ve haberleşme mimarisi; uçuş kontrolcüsü–YKİ arayüzü; entegrasyon testleri |
| **Sonuç** | Saha testlerinde **%2'nin altında paket kaybı** ile düşük gecikmeli veri aktarımı |

> **Bu depo hakkında:** Takım projesinin mekanik tasarımı ve uçuş yazılımı bu depoda yer almaz.
> Burada, sorumlu olduğum **telemetri/haberleşme katmanının** yapılandırma dosyaları, arayüz dokümanı,
> test prosedürleri ve link analizi için yazdığım araçlar bulunur. Depoda paylaşılan örnek veriler
> masa testi için **sentetik** olarak üretilir; saha ölçüm logları paylaşılmamıştır.

---

## İçindekiler
1. [Sistem Mimarisi](#1-sistem-mimarisi)
2. [Sorumluluklarım](#2-sorumluluklarım)
3. [Araçlar](#3-araçlar)
4. [Yapılandırma](#4-yapılandırma)
5. [Kurulum ve Kullanım](#5-kurulum-ve-kullanım)
6. [Test Yaklaşımı](#6-test-yaklaşımı)
7. [Öğrendiklerim](#7-öğrendiklerim)

---

## 1. Sistem Mimarisi

```mermaid
flowchart LR
    subgraph AIR["İHA"]
        FC["Uçuş Kontrolcüsü<br/>ArduPilot"]
        RA["Telsiz (hava)<br/>433 / 915 MHz"]
        FC <-->|"UART 57600<br/>MAVLink v2"| RA
    end
    subgraph GND["Yer Kontrol İstasyonu"]
        RG["Telsiz (yer)"]
        QGC["QGroundControl"]
        MON["monitor.py<br/>link izleme"]
        RG <-->|USB| QGC
        QGC -. "MAVLink forward<br/>UDP 14551" .-> MON
    end
    RA <-->|"RF link<br/>FHSS, ECC, RSSI/SNR"| RG

Katman	Seçim	Neden
Fiziksel	SiK uyumlu telsiz, 433 MHz ve 915 MHz	İki bantta karşılaştırmalı saha testi
Link	64 kbps, ECC açık, FHSS, MAVLink çerçeveleme	Hata düzeltme + telsizin RADIO_STATUS üretmesi
Uygulama	MAVLink v2	ArduPilot ↔ QGroundControl standardı, hafif ikili protokol
Görev verisi	MAVLink mission protokolü	Öğe bazında istek/onay → kayıplı linkte güvenilir yükleme

Arayüz ayrıntıları: docs/ICD.md

2. Sorumluluklarım
MAVLink yapılandırması: telemetri ve görev verisi akışının belirlenmesi — mesaj seti, akış hızları
(SR1_*), GCS failsafe (config/ardupilot_telem.param).

RF saha testleri: 433 MHz ve 915 MHz bantlarında RSSI/SNR ölçümü ve optimizasyonu (anten
yerleşimi, hava hızı, ECC, akış hızları) — docs/RF_NOTES.md.

Arayüz gereksinimleri: mekanik ve yazılım ekipleriyle UK–YKİ arayüzünün tanımlanması
(docs/ICD.md).

Entegrasyon testleri: masa → yer → uçuş aşamalı test planı (docs/INTEGRATION_TESTS.md).

3. AraçlarModülNe yapar
telemetri/monitor.py	Canlı link izleme: MAVLink seq ile paket kaybı, RADIO_STATUS'tan RSSI/gürültü/SNR, TIMESYNC ile gidiş-dönüş gecikmesi, mesaj hızları; 1 Hz CSV log
telemetri/analyze.py	Test loglarından bant bazında özet tablo (kayıp, RSSI, SNR p5, RTT p50/p95, maks. mesafe), %2 hedef kontrolü, mesafe grafikleri
telemetri/mission_upload.py	Görev yükleme (MISSION_COUNT → REQUEST_INT → ITEM_INT → ACK) zaman aşımı ve tekrar denemeli; yükleme sonrası geri okuyup doğrulama
telemetri/sik_config.py	SiK telsizlerini AT/RT komutlarıyla profil dosyasından yapılandırma (yerel + uzak)
telemetri/link_budget.py	433 / 915 MHz serbest uzay link bütçesi, fade margin, Fresnel yarıçapı
telemetri/fake_vehicle.py	Donanımsız masa testi için sentetik MAVLink kaynağı (mesafeye bağlı kanal modeli, TIMESYNC yanıtı)
telemetri/linkstats.py	Saf Python yardımcıları: kayıp sayacı, SiK dönüşümleri, istatistik, FSPL
Paket kaybı nasıl ölçülüyor?
MAVLink'te her bileşen gönderdiği her pakette 8 bitlik seq alanını bir artırır. Alıcı tarafta
(sysid, compid) başına son seq tutulur; seq atlaması kaybolan paket sayısını verir
((yeni − eski − 1) mod 256). 128'den büyük atlamalar yeniden başlatma kabul edilir ve kayıp sayılmaz.
gap = (seq - last - 1) & 0xFF
if gap >= self.reset_gap:      # sender reboot / stream restart
    self.resets += 1
    return 0
self.lost += gap

Gecikme nasıl ölçülüyor?
YKİ TIMESYNC(tc1=0, ts1=t_gönderim) gönderir; ArduPilot tc1=kendi_zamanı, ts1=t_gönderim ile cevap verir.
Cevap geldiğinde RTT = şimdi − ts1. Saat senkronizasyonu gerekmez.

Örnek konsol çıktısı (masa testi, sentetik kaynak)

t=   5.1s loss(1s)=  0.0% total=0.00% RSSI=-67.5dBm SNR=50.0dB [EXCELLENT] RTT=35.2ms ATT=10Hz dist=2105.9m
t=   6.1s loss(1s)= 5.56% total=0.92% RSSI=-69.6dBm SNR=47.4dB [EXCELLENT] RTT=34.7ms ATT=8Hz dist=2351.5m

4. Yapılandırma

Dosya          İçerik
config/sik_433.txt433 MHz telsiz profili (S1–S15 kayıtları, açıklamalı)
config/sik_915.txt	915 MHz telsiz profili
config/ardupilot_telem.param	SERIAL1 protokol/baud, SR1_* akış hızları, GCS failsafe
config/example_mission.csv	Görev yükleme testi için örnek rota

5. Kurulum ve Kullanım
git clone [https://github.com/baran1515/teknofest-uav-telemetry-link.git](https://github.com/baran1515/teknofest-uav-telemetry-link.git) && cd teknofest-uav-telemetry-link
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Telsizi yapılandır (yerel + eşleşmiş uzak telsiz)
python -m telemetri.sik_config --port /dev/ttyUSB0 --profile config/sik_433.txt --remote

# Uçuş sırasında link izleme (QGroundControl'den MAVLink forward açıkken)
python -m telemetri.monitor --device udpin:0.0.0.0:14551 --band 433 --csv logs/433_ucus1.csv

# Görev yükleme + doğrulama
python -m telemetri.mission_upload --device /dev/ttyUSB0 --wp config/example_mission.csv

# Test sonrası rapor
python -m telemetri.analyze logs/*.csv --out reports/

# Link bütçesi
python -m telemetri.link_budget --dist 0.5 1 2 5

Donanımsız deneme: bash scripts/bench_test.sh — sentetik araç → izleme → analiz zincirini iki bant için
çalıştırır (CI'da da çalışır). ArduPilot SITL ile de kullanılabilir:sim_vehicle.py -v ArduCopter --out udp:127.0.0.1:14551 → monitor.py --device udpin:0.0.0.0:14551.

6. Test Yaklaşımı

flowchart LR
    B["Masa testi<br/>telsiz eşleşme, akış hızı,<br/>görev yükleme, failsafe"] --> G["Yer testi<br/>anten yönü, motor gürültüsü,<br/>mesafe yürüyüşü"]
    G --> F["Uçuş testi<br/>uzaklaşma, manevra,<br/>görev uçuşu, bant karşılaştırma"]
    F -->|"analyze.py raporu"| R{"Kayıp < %2 ?"}
    R -->|hayır| O["Optimizasyon<br/>anten / ECC / SR1_ hızları"] --> G
    R -->|evet| OK[Kabul]

Birim testler: python -m pytest tests (kayıp sayacı, 8 bit sarma, bileşen ayrımı, SiK dönüşümü,
yüzdelik, FSPL referans değerleri).

CI: her push'ta birim testler + sentetik masa testi.
