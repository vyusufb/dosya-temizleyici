# 🛡️ DOSYA TEMİZLEYİCİ: ULTRA CLEANER (KALE SÜRÜMÜ)

![Version](https://img.shields.io/badge/sürüm-v8.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-yellow.svg)
![Security](https://img.shields.io/badge/güvenlik-Ironclad-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)

**Dosya Temizleyici (Ultra Cleaner)**, sıradan bir temizlik aracı değildir. Veri bütünlüğünü koruyan, askeri düzeyde güvenlik protokollerine sahip, platform bağımsız bir **Veri Yönetişim ve Bakım Platformudur**.

"KALE" (Citadel) mimarisi üzerine inşa edilen bu sürüm, yanlışlıkla veri silmeyi imkansız hale getirmek, sistem kararlılığını korumak ve yapılan her işlemi denetlenebilir kılmak için tasarlanmıştır.

---

## 🚀 Öne Çıkan Özellikler

### 🔒 Güvenlik Çekirdeği
* **Disk Kilidi (Mount Lock):** Tarama işlemi başladığı disk bölümünü (partition) asla terk etmez. Harici disklere veya ağ sürücülerine sıçramayı engeller.
* **Sembolik Bağ (Symlink) Koruması:** Kısayolları ve sembolik bağları takip etmez. Bu sayede "Jailbreak" tarzı dizin dışına çıkma risklerini önler.
* **Kritik Yol Koruması:** Windows (`C:\Windows`) ve Linux (`/etc`, `/usr`) sistem dizinlerini ve kullanıcı kök dizinini (`User Root`) otomatik olarak kara listeye alır.
* **Akıllı Risk Motoru:** Dosyaları sadece uzantısına göre değil; adına, yaşına ve içeriğine göre analiz eder. `pass`, `wallet`, `backup`, `tez` gibi kelimeler içeren dosyalar **ASLA SİLİNMEZ**.

### 📦 Karantina ve Geri Yükleme (Rollback)
* **Silme Yok, Taşıma Var:** Hiçbir dosya doğrudan silinmez. İşlem gören dosyalar, taranan dizin içinde gizli bir `.karantina_{OTURUM_ID}` klasörüne taşınır.
* **Kriptografik Doğrulama:** Geri yükleme işlemi sırasında, dosyaların Hash (SHA256) değerleri `snapshot.json` ile karşılaştırılır. Dosya bütünlüğü bozulmuşsa geri yükleme reddedilir.
* **Tam Denetim (Audit Trail):** Her işlemin log kaydı tutulur ve log dosyası SHA256 ile mühürlenir (`.log.sha256`).

### ⚡ Performans
* **Headless Modu:** Grafik arayüzü olmayan sunucularda otomatik olarak CLI (Komut Satırı) moduna geçer.
* **Adaptive Throttling:** Sistem kaynaklarını sömürmemek için disk işlemlerine mikro saniyelik gecikmeler ekler.
* **Bellek Dostu:** Milyonlarca dosyayı tararken bile RAM şişmesi yaşatmaz.

---

## 🛠️ Kurulum

Bu araç Python'un standart kütüphanelerini kullanır. Harici bir paket yüklemenize (`pip install`) gerek yoktur.

1.  Bilgisayarınızda **Python 3.9** veya üzeri kurulu olduğundan emin olun.
2.  Terminal veya CMD üzerinden çalıştırın:
    ```bash
    python dosya_temizleyici.py
    ```

---

## 📖 Kullanım Kılavuzu

Program iki modda çalışabilir: **Görsel Arayüz (GUI)** ve **Komut Satırı (CLI)**.

### 1. Görsel Arayüz (Varsayılan)
Programı çift tıklayarak veya parametresiz çalıştırırsanız:
1.  Bir klasör seçim penceresi açılır.
2.  Seçilen klasörün güvenli olup olmadığı (Sistem dosyası mı?) denetlenir.
3.  16 seçenekli ana menü ekrana gelir.

### 2. Komut Satırı (Otomasyon)
Sunucu ortamları veya zamanlanmış görevler için parametrelerle çalıştırabilirsiniz.

**Örnekler:**

* **Duplicate (Kopya) Taraması Yap:**
    ```bash
    python dosya_temizleyici.py --path "/var/www/html" --module 12
    ```

* **Klasörü 500 MB Kotaya İndir:**
    ```bash
    python dosya_temizleyici.py --path "D:\Arsiv" --module 16 --arg 500
    ```

* **Karantinadan Geri Yükle (Rollback):**
    ```bash
    python dosya_temizleyici.py --path "D:\Arsiv" --module restore
    ```

* **Belirli Kelimeleri İçeren Dosyaları Temizle:**
    ```bash
    python dosya_temizleyici.py --path "C:\Indirilenler" --module 3 --arg "kopya,taslak,temp"
    ```

---

## 🧹 Temizlik Modülleri

| No | Modül Adı | Açıklama |
| :--- | :--- | :--- |
| **1** | Hash İsimli Dosyalar | 32 karakterli Hex isimler (Örn: `d41d8cd98f00b204e9800998ecf8427e`) |
| **2** | JSON Dosyaları | `.json` uzantılı tüm dosyalar. |
| **3** | Kelime Bazlı Arama | Kullanıcının girdiği kelimeleri içeren dosyalar. |
| **4** | 35 KB Altı | Çok küçük, genellikle önemsiz dosyalar. |
| **5** | 1 MB Altı Tümü | 1 MB altındaki her tür dosya. |
| **6** | Küçük Videolar | 1 MB altındaki video dosyaları (Genelde bozuktur). |
| **7** | 0 Byte Dosyalar | İçi tamamen boş dosyalar. |
| **8** | Sistem Çöpleri | `.tmp`, `.log`, `.bak`, `.chk`, `.old` dosyaları. |
| **9** | OS Artıkları | `Thumbs.db`, `Desktop.ini`, `.DS_Store`. |
| **10** | Arşivler | `.zip`, `.rar`, `.7z`, `.tar`, `.gz`. |
| **11** | Kurulum Dosyaları | `.exe`, `.msi`, `.dmg`, `.pkg`. |
| **12** | **Kopya Bulucu** | İçerik tabanlı (SHA256 Hash) kopya dosya bulucu. |
| **13** | Eski Dosyalar | 6 aydan uzun süredir değiştirilmemiş dosyalar. |
| **14** | Office Kilitleri | `~$` ile başlayan geçici Word/Excel dosyaları. |
| **15** | Yazılımcı Artıkları | `.pyc`, `.class`, `.o`, `.obj` derleme artıkları. |
| **16** | **Kota Yöneticisi** | Klasörü hedef boyuta (MB) inene kadar temizler. |

---

## 📂 Çalışma Yapısı

Program çalıştığında hedef klasörde şu yapıyı oluşturur:

```tex
Hedef_Klasör/
├── .karantina_20260218_120000/   # (Gizli) Silinen dosyalar burada tutulur
├── snapshot_20260218_120000.json # Dosyaların orijinal yolları ve Hash değerleri
├── kale_gunluk_... .log          # İşlem günlüğü
└── kale_gunluk_... .log.sha256   # Log dosyasının bütünlük mührü

⚠️ Yasal Uyarı
Bu yazılım "OLDUĞU GİBİ" sunulur. Geliştirici, veri kaybından sorumlu tutulamaz. Ancak yazılım, veri kaybını önlemek için endüstri standardı güvenlik önlemleri (Karantina, Snapshot, Hash Doğrulama) ile donatılmıştır. Her zaman önemli verilerinizin harici yedeğini alınız.
