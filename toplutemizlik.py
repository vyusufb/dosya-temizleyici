import os
import sys
import re
import time
import json
import shutil
import hashlib
import logging
import heapq
import argparse
import platform
import concurrent.futures
from datetime import datetime
from pathlib import Path
from collections import Counter

OTURUM_ID = datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_DOSYASI = f"kale_gunluk_{OTURUM_ID}.log"
DENETIM_DOSYASI = f"kale_gunluk_{OTURUM_ID}.log.sha256"
KARANTINA_KLASORU = f".karantina_{OTURUM_ID}"
SNAPSHOT_DOSYASI = f"snapshot_{OTURUM_ID}.json"
IO_GECIKMESI = 0.001

logging.basicConfig(
    filename=LOG_DOSYASI,
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    encoding='utf-8'
)

def sunucu_modu_mu():
    if platform.system() == "Linux":
        return os.environ.get('DISPLAY') is None
    return False

def yasakli_yollari_getir():
    yollar = set()
    kullanici_ana_dizin = Path(os.path.expanduser("~")).resolve()
    
    if platform.system() == "Windows":
        yollar.add(Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve())
        yollar.add(Path(os.environ.get("ProgramFiles", r"C:\Program Files")).resolve())
        yollar.add(Path(os.environ.get("ProgramData", r"C:\ProgramData")).resolve())
        yollar.add(kullanici_ana_dizin)
        yollar.add(kullanici_ana_dizin / "AppData")
    else:
        kritik_unix = ["/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/root", "/run", "/sbin", "/sys", "/usr", "/var"]
        for p in kritik_unix:
            yollar.add(Path(p).resolve())
        yollar.add(kullanici_ana_dizin)
    return list(yollar)

KORUNAN_YOLLAR = yasakli_yollari_getir()

def guvenli_yol_mu(hedef_yol: Path):
    try:
        hedef = hedef_yol.resolve(strict=True)
    except FileNotFoundError:
        hedef = hedef_yol.parent.resolve()

    kullanici_ana_dizin = Path(os.path.expanduser("~")).resolve()
    
    if hedef == kullanici_ana_dizin:
        return False, "Kullanıcı Ana Dizini (Root) Seçilemez"

    if hedef.is_relative_to(kullanici_ana_dizin):
        if platform.system() == "Windows" and hedef.is_relative_to(kullanici_ana_dizin / "AppData"):
             return False, "AppData (Sistem Verisi)"
        return True, "UYGUN (Kullanıcı Alanı)"

    for korunan in KORUNAN_YOLLAR:
        if hedef == korunan or hedef.is_relative_to(korunan):
            return False, f"Sistem Dizini ({korunan})"

    return True, "UYGUN"

def sha256_hesapla(dosya_yolu, blok_boyutu=65536):
    sha = hashlib.sha256()
    try:
        with open(dosya_yolu, 'rb') as f:
            while True:
                veri = f.read(blok_boyutu)
                if not veri: break
                sha.update(veri)
        return sha.hexdigest()
    except: return None

class RiskMotoru:
    @staticmethod
    def degerlendir(dosya_yolu: Path):
        isim = dosya_yolu.name.lower()
        
        if re.search(r'\b(backup|yedek|wallet|private|key|git|pass|sifre|shadow|config|tez|final|proje)\b', isim):
            return 100, "KRİTİK (Yasaklı Kelime)"
                
        uzanti = dosya_yolu.suffix.lower()
        if uzanti in ['.tmp', '.log', '.chk', '.dmp', '.bak', '.old', '.thumbs']:
            return 10, "DÜŞÜK (Çöp)"
        if uzanti in ['.pyc', '.cache', '.ds_store']:
            return 20, "DÜŞÜK (Önbellek)"
            
        return 50, "ORTA (Standart Dosya)"

class KarantinaKasasi:
    def __init__(self, kok_dizin: Path):
        self.kok = kok_dizin.resolve()
        self.karantina_dizini = self.kok / KARANTINA_KLASORU
        
    def kasaya_tasi(self, dosya_yolu: Path):
        if not self.karantina_dizini.exists():
            self.karantina_dizini.mkdir(parents=True)
            if platform.system() == "Windows":
                os.system(f'attrib +h "{self.karantina_dizini}"')

        gercek_dosya = dosya_yolu.resolve()
        try:
            bagil_yol = gercek_dosya.relative_to(self.kok)
        except ValueError:
            logging.error(f"GUVENLIK: Dizin Disina Cikma Girisimi Engellendi: {dosya_yolu}")
            return False

        hedef_yol = self.karantina_dizini / bagil_yol
        
        if not hedef_yol.parent.exists():
            hedef_yol.parent.mkdir(parents=True, exist_ok=True)
            
        if hedef_yol.exists():
            zaman = int(time.time())
            hedef_yol = hedef_yol.with_name(f"{hedef_yol.stem}_{zaman}{hedef_yol.suffix}")

        try:
            shutil.move(str(gercek_dosya), str(hedef_yol))
            return True
        except Exception as e:
            logging.error(f"KASA HATASI: {dosya_yolu} -> {e}")
            return False

    def dogrula_ve_geri_yukle(self):
        print(f"\n[KASA] Geri Yükleme İşlemi Başlatılıyor...")
        print(f"Konum: {self.karantina_dizini}")
        
        snapshot_yolu = self.kok / SNAPSHOT_DOSYASI
        snapshot_db = {}
        if snapshot_yolu.exists():
            try:
                with open(snapshot_yolu, 'r', encoding='utf-8') as f:
                    veri = json.load(f)
                    for oge in veri:
                        snapshot_db[oge['path']] = oge.get('hash')
            except: pass

        if not self.karantina_dizini.exists():
            print("❌ HATA: Karantina kasası bulunamadı.")
            return

        sayac = 0
        atlanan = 0
        
        for root, dirs, files in os.walk(self.karantina_dizini):
            for file in files:
                kaynak = Path(root) / file
                try:
                    bagil_yol = kaynak.relative_to(self.karantina_dizini)
                    orijinal_yol = self.kok / bagil_yol
                    
                    str_bagil = str(bagil_yol).replace('\\', '/')
                    beklenen_hash = snapshot_db.get(str_bagil)
                    
                    if beklenen_hash and beklenen_hash != "HIZ_ICIN_ATLANDI":
                        mevcut_hash = sha256_hesapla(kaynak)
                        if mevcut_hash != beklenen_hash:
                            logging.critical(f"BUTUNLUK HATASI: {kaynak} hash uyusmuyor! Geri yukleme iptal.")
                            print(f"🚨 BOZUK DOSYA: {file} (Hash tutmuyor, geri yüklenmedi)")
                            atlanan += 1
                            continue

                    if not orijinal_yol.parent.exists():
                        orijinal_yol.parent.mkdir(parents=True)
                        
                    shutil.move(str(kaynak), str(orijinal_yol))
                    sayac += 1
                except Exception as e:
                    logging.error(f"GERI YUKLEME HATASI: {kaynak} -> {e}")
        
        if atlanan == 0:
            try:
                shutil.rmtree(self.karantina_dizini)
                if snapshot_yolu.exists(): os.remove(snapshot_yolu)
            except: pass
            
        print(f"✅ İşlem Tamamlandı.")
        print(f"   Kurtarılan Dosya: {sayac}")
        print(f"   Reddedilen (Bozuk): {atlanan}")

def kale_tarayici(kok_dizin: Path):
    try:
        kok_cihaz_id = kok_dizin.stat().st_dev
    except Exception as e:
        print(f"Kök dizin okunamadı: {e}")
        return

    for root, dirs, files in os.walk(kok_dizin, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != KARANTINA_KLASORU]
        
        gecerli_dizinler = []
        for d in dirs:
            try:
                d_yolu = Path(root) / d
                if d_yolu.stat().st_dev == kok_cihaz_id:
                    gecerli_dizinler.append(d)
                else:
                    logging.warning(f"SINIR ENGELI: Harici disk/mount atlandi {d_yolu}")
            except: pass
        dirs[:] = gecerli_dizinler

        for file in files:
            yield Path(root) / file

def snapshot_olustur(dosya_listesi, kok_klasor: Path, hash_dahil=False):
    veri = []
    print("Snapshot (Kurtarma Kaydı) alınıyor...")
    
    if hash_dahil:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_path = {executor.submit(sha256_hesapla, p): p for p in dosya_listesi}
            for future in concurrent.futures.as_completed(future_to_path):
                p = future_to_path[future]
                try:
                    st = p.stat()
                    rel = str(p.resolve().relative_to(kok_klasor.resolve())).replace('\\', '/')
                    veri.append({
                        "path": rel,
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                        "hash": future.result()
                    })
                except: pass
    else:
        for p in dosya_listesi:
            try:
                st = p.stat()
                rel = str(p.resolve().relative_to(kok_klasor.resolve())).replace('\\', '/')
                veri.append({
                    "path": rel,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "hash": "HIZ_ICIN_ATLANDI"
                })
            except: pass

    with open(kok_klasor / SNAPSHOT_DOSYASI, 'w', encoding='utf-8') as f:
        json.dump(veri, f, indent=2)

def temizligi_uygula(dosya_listesi, kok_dizin: Path, simulasyon: bool, sebep: str, hash_gerekli=False):
    if not dosya_listesi:
        print(">>> Kriterlere uygun dosya bulunamadı.")
        return

    toplam_boyut = sum(f.stat().st_size for f in dosya_listesi)
    print(f"\n" + "="*40)
    print(f" RAPOR: {sebep}")
    print(f"="*40)
    print(f" Dosya Sayısı : {len(dosya_listesi)}")
    print(f" Toplam Boyut : {toplam_boyut / 1024 / 1024:.2f} MB")
    print("-" * 40)
    
    if simulasyon:
        print("🚨 [SİMÜLASYON] Değişiklik yapılmadı (Dry-Run).")
        return

    onay = input(">>> Bu dosyalar karantinaya taşınsın mı? (E/H): ")
    if onay.lower() != 'e':
        print("İşlem iptal edildi.")
        return

    snapshot_olustur(dosya_listesi, kok_dizin, hash_dahil=hash_gerekli)
    kasa = KarantinaKasasi(kok_dizin)
    basarili = 0
    
    print("\nİşlem Başlıyor...")
    for f in dosya_listesi:
        if kasa.kasaya_tasi(f):
            logging.info(f"{sebep} | TASINDI | {f}")
            basarili += 1
            sys.stdout.write(f"\rİşlenen: {basarili}/{len(dosya_listesi)}")
            sys.stdout.flush()
        time.sleep(IO_GECIKMESI) 
            
    print(f"\n\n✅ Tamamlandı. Başarılı: {basarili}")
    
    if os.path.exists(LOG_DOSYASI):
        h = sha256_hesapla(LOG_DOSYASI)
        with open(DENETIM_DOSYASI, "w") as f:
            f.write(f"{datetime.now()}|{h}")

def modulleri_calistir(kok_dizin: Path, secim: str, ek_arg=None):
    hedefler = []
    sebep = "BILINMIYOR"
    hash_gerekli = False 

    print("Tarama yapılıyor, lütfen bekleyin...")
    generator = kale_tarayici(kok_dizin)

    if secim == '1': 
        sebep = "HASH_ISIMLI_DOSYALAR_(32HEX)"
        pat = re.compile(r'^[a-fA-F0-9]{32}$')
        for p in generator:
            if pat.match(p.stem): hedefler.append(p)

    elif secim == '2': 
        sebep = "JSON_DOSYALARI"
        for p in generator:
            if p.suffix.lower() == '.json': hedefler.append(p)

    elif secim == '3': 
        sebep = "KELIME_ARAMA"
        if not ek_arg: return
        anahtar_kelimeler = [k.strip().lower() for k in ek_arg.split(',') if k.strip()]
        for p in generator:
            if any(k in p.name.lower() for k in anahtar_kelimeler): hedefler.append(p)

    elif secim == '4': 
        sebep = "35KB_ALTI_DOSYALAR"
        limit = 35 * 1024
        for p in generator:
            if p.stat().st_size <= limit: hedefler.append(p)

    elif secim == '5': 
        sebep = "1MB_ALTI_TUM_DOSYALAR"
        limit = 1024 * 1024
        for p in generator:
            if p.stat().st_size <= limit: hedefler.append(p)

    elif secim == '6': 
        sebep = "KUCUK_VIDEOLAR"
        limit = 1024 * 1024
        exts = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv'}
        for p in generator:
            if p.suffix.lower() in exts and p.stat().st_size < limit: hedefler.append(p)

    elif secim == '7': 
        sebep = "BOS_DOSYALAR_(0_BYTE)"
        for p in generator:
            if p.stat().st_size == 0: hedefler.append(p)

    elif secim == '8': 
        sebep = "SISTEM_COPLERI"
        exts = {'.tmp', '.log', '.bak', '.old', '.chk', '.dmp'}
        for p in generator:
            if p.suffix.lower() in exts: hedefler.append(p)

    elif secim == '9': 
        sebep = "ISLETIM_SISTEMI_ARTIKLARI"
        isimler = {'thumbs.db', 'desktop.ini', '.ds_store'}
        for p in generator:
            if p.name.lower() in isimler: hedefler.append(p)

    elif secim == '10': 
        sebep = "ARSIVLER"
        exts = {'.zip', '.rar', '.7z', '.tar', '.gz'}
        for p in generator:
            if p.suffix.lower() in exts: hedefler.append(p)

    elif secim == '11': 
        sebep = "KURULUM_DOSYALARI"
        exts = {'.exe', '.msi', '.pkg', '.dmg'}
        for p in generator:
            if p.suffix.lower() in exts: hedefler.append(p)

    elif secim == '12': 
        sebep = "KOPYA_DOSYALAR_(DUPLICATE)"
        hash_gerekli = True
        print("Duplicate (Kopya) analizi başlatılıyor (Bu işlem yavaş olabilir)...")
        boyut_haritasi = {}
        for p in generator:
            s = p.stat().st_size
            if s > 0: boyut_haritasi.setdefault(s, []).append(p)
        
        adaylar = [g for g in boyut_haritasi.values() if len(g) > 1]
        hashlenecekler = [f for g in adaylar for f in g]
        
        hash_haritasi = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_path = {executor.submit(sha256_hesapla, p): p for p in hashlenecekler}
            for future in concurrent.futures.as_completed(future_to_path):
                p = future_to_path[future]
                h = future.result()
                if h: hash_haritasi.setdefault(h, []).append(p)

        for grup in hash_haritasi.values():
            if len(grup) > 1:
                grup.sort(key=lambda x: x.stat().st_mtime)
                hedefler.extend(grup[1:]) 
        
    elif secim == '13': 
        sebep = "ESKI_DOSYALAR_(6_AY+)"
        limit = 180 * 86400
        simdi = time.time()
        for p in generator:
            if (simdi - p.stat().st_mtime) > limit: hedefler.append(p)

    elif secim == '14': 
        sebep = "OFFICE_KILIT_DOSYALARI"
        for p in generator:
            if p.name.startswith("~$"): hedefler.append(p)

    elif secim == '15': 
        sebep = "YAZILIMCI_ARTIKLARI"
        exts = {'.pyc', '.class', '.o', '.obj'}
        for p in generator:
            if p.suffix.lower() in exts: hedefler.append(p)

    elif secim == '16': 
        sebep = "KOTA_YONETICISI"
        try:
            hedef_mb = int(ek_arg)
        except: 
            print("Hata: Geçersiz MB değeri.")
            return
        
        tum_dosyalar = []
        for p in generator:
            skor, _ = RiskMotoru.degerlendir(p)
            tum_dosyalar.append({
                "path": p,
                "size": p.stat().st_size,
                "score": skor
            })
        
        mevcut_toplam = sum(x['size'] for x in tum_dosyalar)
        hedef_byte = hedef_mb * 1024 * 1024
        
        if mevcut_toplam > hedef_byte:
            gereken = mevcut_toplam - hedef_byte
            print(f"Temizlenmesi gereken alan: {gereken/1024/1024:.2f} MB")
            tum_dosyalar.sort(key=lambda x: (x['score'], -x['size']))
            biriken = 0
            for f in tum_dosyalar:
                if f['score'] >= 80: continue
                hedefler.append(f['path'])
                biriken += f['size']
                if biriken >= gereken: break
        else:
            print("Klasör zaten hedef kotanın altında.")
            return

    temizligi_uygula(hedefler, kok_dizin, False, sebep, hash_gerekli)

def guvenli_klasor_sec():
    if sunucu_modu_mu():
        print("Sunucu (Headless) ortam tespit edildi. Lütfen CLI --path argümanını kullanın.")
        return None
    
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        yol = filedialog.askdirectory(title="KALE Tarayıcı: Klasör Seç")
        root.destroy()
        return yol
    except ImportError:
        print("Hata: Tkinter modülü bulunamadı. Grafik arayüz açılamıyor.")
        return None

def ekran_temizle():
    os.system('cls' if os.name == 'nt' else 'clear')

def ana_menu_goster():
    print("\n" + "█"*60)
    print("      ULTRA CLEANER V8 - KALE SÜRÜMÜ (THE CITADEL)")
    print("      Güvenli Veri Yönetimi ve Temizlik Platformu")
    print("█"*60)
    print("\n--- TEMEL TEMİZLİK ---")
    print(" 1. Hash İsimli Dosyalar (32 Karakter Hex)")
    print(" 2. JSON Dosyaları")
    print(" 3. Kelime Bazlı Arama ve Silme")
    print(" 4. 35 KB Altı Dosyalar")
    print(" 5. 1 MB Altı Tüm Dosyalar")
    print(" 6. 1 MB Altı Videolar")
    print(" 7. 0 Byte (Boş) Dosyalar")
    
    print("\n--- SİSTEM ve BAKIM ---")
    print(" 8. Sistem Çöpleri (.tmp, .log, .bak)")
    print(" 9. İşletim Sistemi Artıkları (Thumbs.db)")
    print("10. Arşiv Dosyaları (.zip, .rar)")
    print("11. Kurulum Dosyaları (.exe, .msi)")
    print("12. Kopya Dosya Bulucu (Hash Analizi)")
    print("13. Eski Dosyalar (6 Aydan Eski)")
    print("14. Office Kilit Dosyaları (~$)")
    print("15. Yazılımcı Artıkları (.pyc, .obj)")
    
    print("\n--- GELİŞMİŞ YÖNETİM ---")
    print("16. Akıllı Kota Yöneticisi (Hedef Boyuta İndir)")
    print(" R. GERİ YÜKLE (ROLLBACK - Karantinadan Döndür)")
    print(" Q. ÇIKIŞ")
    print("-" * 60)

def main():
    parser = argparse.ArgumentParser(description="Ultra Cleaner V8 - Kale Sürümü (Türkçe)")
    parser.add_argument('--path', type=str, help="Hedef Dizin")
    parser.add_argument('--module', type=str, help="Modül Numarası (1-16) veya 'restore'")
    parser.add_argument('--arg', type=str, help="Ek argüman (Kelime listesi veya Kota MB)")
    args = parser.parse_args()

    kok_dizin = None

    if args.path:
        kok_dizin = Path(args.path).resolve()
    else:
        yol_str = guvenli_klasor_sec()
        if yol_str: kok_dizin = Path(yol_str).resolve()
    
    if not kok_dizin:
        print("\nUyarı: Klasör seçilmedi veya işlem iptal edildi.")
        return

    uygun, sebep = guvenli_yol_mu(kok_dizin)
    if not uygun:
        print(f"\n🛑 GÜVENLİK ENGELİ: {sebep}")
        print("Kurumsal güvenlik politikası gereği bu dizine işlem yapılamaz.")
        return

    print(f"\n🔒 Hedef Kilitlendi: {kok_dizin}")

    if args.module:
        if args.module == 'restore':
            kasa = KarantinaKasasi(kok_dizin)
            kasa.dogrula_ve_geri_yukle()
        else:
            modulleri_calistir(kok_dizin, args.module, args.arg)
    else:
        while True:
            ana_menu_goster()
            secim = input("Seçiminiz: ").upper()
            
            if secim == 'Q': 
                print("Çıkış yapılıyor...")
                break
            
            if secim == 'R':
                kasa = KarantinaKasasi(kok_dizin)
                kasa.dogrula_ve_geri_yukle()
                input("\nDevam etmek için Enter'a basın...")
                continue
            
            ekstra = None
            if secim == '3': ekstra = input("Aranacak kelimeler (virgülle ayırın): ")
            if secim == '16': ekstra = input("Hedef Klasör Boyutu (MB): ")
            
            modulleri_calistir(kok_dizin, secim, ekstra)
            input("\nAna menüye dönmek için Enter'a basın...")
            ekran_temizle()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSistem güvenli şekilde kapatıldı.")