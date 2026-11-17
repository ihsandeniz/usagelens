# İkinci Göz — gece/1117-kurulum-denetimi

Denetim tarihi: 2026-11-17
Denetlenen: `origin/gece/1117-kurulum-denetimi` (`8143c58`), taban `origin/main` (`8d43f68`), 5 commit.

## Hüküm

**DÜZELTME GEREKİR** (küçük düzeltmeler). Kod değişiklikleri doğru, testler gerçek hatayı yakalıyor ve hiçbir şey kırılmıyor. Birleştirmeden önce şunlar yapılmalı: (1) `--help` ikili dosya ve `.exe` kullanıcısına sahip olmadığı `usagelens` komutunu göstermesin, (2) demo verisindeki Aider kartı da `experimental` taşısın, (3) `--version` çıktısının değiştiği CHANGELOG'a yazılsın.

## Kendi test sayılarım

Komut (CI'nin `Unit tests` adımıyla aynı): `python3 -m unittest discover -s tests -t .`
Bu makinede ortamda `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` tanımlı. Bu yüzden iki durumda da koştum.

| Ağaç | Python | Ortam değişkeni | Çalıştı | Geçti | Kaldı | Atlandı |
|---|---|---|---|---|---|---|
| main 8d43f68 | 3.11.18 | 80 tanımlı | 744 | 739 | 1 (`test_context.test_drift_goes_to_messages`, `800000 != 550000`) | 4 |
| main 8d43f68 | 3.11.18 | `env -u` ile tanımsız | 744 | 740 | 0 | 4 |
| main 8d43f68 | 3.9.25 (uv) | 80 tanımlı | 744 | 739 | 1 (aynı test) | 4 |
| dal 8143c58 | 3.11.18 | 80 tanımlı | 761 | 757 | 0 | 4 |
| dal 8143c58 | 3.11.18 | tanımsız | 761 | 757 | 0 | 4 |
| dal 8143c58 | 3.13 | 80 tanımlı | 761 | 757 | 0 | 4 |
| dal 8143c58 | 3.9.25 (uv) | 80 tanımlı | 761 | 757 | 0 | 4 |

Ek: `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=30 python3 -m unittest tests.test_context` → dalda 8/8 geçti.

Yeni testler main kodu üzerinde (dosyayı geçici olarak main ağacına kopyaladım, sonra geri aldım):
- `tests/test_ad_uyumu.py`: 10 testin 5'i kırmızı.
- `tests/test_yayin_metin.py` (dal sürümü): 11 testin 3'ü kırmızı, alt testlerle birlikte 7 hata.
- `tests/test_context.py` (dal sürümü): main kodunda, değişken 80'ken 8/8 geçiyor. Beklenen sonuç bu, çünkü kodda hata yoktu, test ortama bağlıydı.

Yeni `ResourceWarning` yok: tam koşuda uyarı sayısı main'de de dalda da 64.

## Tutmayan iddialar

| Rapordaki iddia | Ölçümüm |
|---|---|
| Sayılar: main 744/739/1/4, dal 761/757/0/4, 3.9'da 760 (0be42b4 anında) | **Tutuyor.** Dalın son hâli 3.9'da 761/757/0/4. 0be42b4 ayrıca koşulmadı. |
| `test_ad_uyumu` 10 test, düzeltmeden önce 5'i kırmızı | **Tutuyor.** |
| Bulgu 2 "**Düzeltildi**": `--help` pipx ve ikili dosya kullanıcısına sahip olmadığı `python3 server.py` komutunu gösteriyordu | **Kısmen tutuyor.** pipx ve pip için düzeldi. İkili dosya ve `.exe` için düzelmedi: yeni yardım bu kez `usagelens` komutunu gösteriyor. Sihirbaz ikiliyi `usage-tracker` adıyla kuruyor (`usage/wizard.py:87`), `.exe` de `usage-tracker.exe`. Bu kullanıcıların PATH'inde `usagelens` yok. |
| Bulgu 3: "Panelde rozet görünüyor: Aider kartı … EXPERIMENTAL" | **Kısmen tutuyor.** Gerçek `collect()` için doğru. Demo modunda (`USAGE_DEMO=1`) Aider kartı rozetsiz kalıyor: `demo.collect()` → `aider None`, `together True`. |
| "Commit'lerin yazarı nötr bir yerel kimlik; imza … eklenmedi" | **Metin olarak tutuyor**, ama 5 commit'in 5'i de SSH ile kriptografik imzalı (`gpgsig -----BEGIN SSH SIGNATURE-----`). main'deki 8d43f68 imzasız. İmza, ortamın commit imzalama anahtarından geliyor. Metinde bir yapay zekâ imzası değil, ama "nötr kimlik" iddiasıyla tam örtüşmüyor. |
| Kurulum yolları, yayın indirme, SHA256 doğrulaması, strace ile 0 dış bağlantı, Chromium ekranı | **Ölçülmedi.** Dış istek yasağı nedeniyle (aşağıya bakınız). |

Rapordaki dosya:satır atıfları (`test_context.py:69`, `server.py:455/477-482`, `cli.py:1297-1300`, `providers/__init__.py:42`, `README.tr.md:230`, `GUIDE.md:251,518`, `start.sh:23`, `server.py:599`, `i18n.py:34-96`, `cli.py:548`, `waybar-usage.sh:265`) yerinde kontrol edildi, hepsi doğru. "README.md deneysel sağlayıcılardan ve Linux ikilisinden söz etmiyordu" iddiası main'de doğrulandı (grep sonucu 0).

## Bulgular

| # | Önem | Yer | Kanıt |
|---|---|---|---|
| 1 | Bilgi | `GECE-RAPOR.md` (kök) | Rapor dosyası dalın kökünde (gece koşusunun istenen çıktısı). Birleştirirken main'e taşınmaması önerilir; tek başına hüküm gerekçesi değil. |
| 2 | Orta | `server.py:483-492` | `--help` her dağıtım biçiminde `usagelens …` satırlarını basıyor. `.exe` ve Linux ikilisi kullanıcısının elindeki komut `usage-tracker`: kurulu yol `wizard.py:87`, README'nin yeni satırı `./usage-tracker-<version>-linux-x64 setup`. "`usage-tracker` is the same program" notu bunu kısmen kapatıyor, ama ilk satırlar yine olmayan bir komutu öneriyor. Öneri: donmuş ikilide (`sys.frozen`) ya da `sys.argv[0]`'dan çalışan adı göster. |
| 3 | Düşük | `usage/demo.py:412` | Demo Aider kartında `experimental` yok. Together kartında aynı alan elle yazılmış (`demo.py:383`). `EXPERIMENTAL` "tek yer" diyor (`providers/__init__.py:39-41`), ama demo bunu izlemiyor. Demo ekran görüntüsünde Aider doğrulanmış gibi görünür. |
| 4 | Düşük | `CHANGELOG.md` | `--version` ve hata satırının değiştiği (`usage-tracker X` → `usagelens X`) yazılmamış. Bu, kullanıcının görebileceği bir CLI çıktısı değişikliği. Depoda bu çıktıyı ayrıştıran bir betik yok: sihirbaz son kelimeyi okuyor (`wizard.py:154-156`), surface/packaging/CI içinde `--version` ayrıştırması yok. Yine de kullanıcı betiği `grep usage-tracker` yapıyorsa kırılır. |
| 5 | Düşük | `usage/cli.py:387,686,981,1060,1073`, `usage/platform.py:207`, `usage/i18n.py` | Ad değişikliği yarım kalmış. `usagelens usage` hâlâ `usage-tracker 0.6.3 · source: …` başlığını basıyor, `--version` ise `usagelens 0.6.3` diyor. Rapor bunu kabul ediyor. Hata değil, tutarsızlık. Argparse `prog` sabit: `usage-tracker guard -h` artık `usage: usagelens guard` gösteriyor (önceki durumun tersi). |
| 6 | Düşük (test zayıflığı) | `tests/test_yayin_metin.py:98-122` | `test_deneysel_listesi_belgeyle_ayni` yalnız adın dosyada **herhangi bir yerde** geçtiğine bakıyor. `test_deneysel_adlar_ana_listede_degil` README.md'yi denetlemiyor ve 9 adın yalnız 5'ini deniyor (Novita, DeepInfra, Hugging Face, Together yok). |
| 7 | Bilgi | `tests/test_context.py:105` | `SessionEnvWinsTest`, `ContextTest`'ten türüyor ve 3 testi ikinci kez koşuyor (4 → 8). `test_drift_goes_to_messages`'ı ezdiği için alt sınıfta drift (Messages 150 000) doğrulaması yapılmıyor, yalnız `compact_at` doğrulanıyor. Zararsız, gereksiz tekrar. Alt süreç `Popen` exec'i beklediği için `/proc/<pid>/environ` yarışı yok. Windows ve macOS'ta `/proc` yok, temel test settings.json'dan 55 okur, alt sınıf atlanır. Mantık doğru, ama Windows CI ölçülmedi. |
| 8 | Bilgi | commit gövdesi `062dd66` | `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, `usage/context.py:141-153` içinde okunan gerçek bir ortam değişkeninin adı. Yapay zekâ imzası değil, teknik içerik. Commit mesajlarında Co-Authored-By, oturum bağlantısı ya da URL yok. Eklenen satırlarda `/home/`, `/Users/`, kişisel e-posta ya da jeton yok. `~/my-line.sh` raporda örnek yol olarak geçiyor, kişisel değil. main'e dokunulmamış: `origin/main` = merge-base = `8d43f68`. |

Geriye dönük uyum:
- JSON'da `aider` ve `continue` kartlarına `experimental: true` ekleniyor. Bu yalnız ekleme, başka davranış değişmiyor (bayrağı yalnız `web/app.js:680` rozet için okuyor). Şema (`tests/golden/v1_usage.schema.json`) alanı zaten tanıyor.
- `usage-tracker` giriş noktası duruyor (`pyproject.toml:46`). HTTP `Server:` başlığı ve widget tanıması değişmedi.

## Mutasyon denemeleri

Her biri dal ağacında yapıldı ve `git checkout -- .` ile geri alındı.

| # | Bozma | Sonuç |
|---|---|---|
| M1 | `server.py` `--version` → `usage-tracker {VERSION}` | Kırmızı (1) |
| M2 | `cli.py` `prog='usage-tracker'` | Kırmızı (1) |
| M3 | `cli.py` argparse `version=` eski ad | Kırmızı (1) |
| M4 | `EXPERIMENTAL`'dan aider ve continue çıkarıldı | Kırmızı (2) |
| M5 | Yalnız continue çıkarıldı | Kırmızı (2) |
| M6 | `--help`'ten "`usage-tracker` is the same program" silindi | Kırmızı (1) |
| M7 | `--help`'ten "`python3 server.py` does the same" silindi | Kırmızı (1) |
| M8 | Sihirbaz yalnız `usage-tracker X` satırını ayrıştıracak biçimde değiştirildi | Kırmızı (1, `test_new_line`) |
| M9 | `context._compact_pct` `/proc` okumasını bıraktı | Kırmızı (1, `SessionEnvWinsTest`) |
| M10 | Oturum ortamı yok sayılıp hep 55 döndü | Kırmızı (1) |
| M11 | README.md deneysel listesinden Aider ve Continue silindi | Kırmızı (2) |
| M12 | README.md Linux ikilisi satırı silindi | Kırmızı (1) |
| M13 | README.tr.md doğrulanmış listeye Aider geri kondu | Kırmızı (1) |

13 mutasyonun 13'ü yakalandı. Not: README.md'nin doğrulanmış kısmına Aider eklemek ayrıca denenmedi. Bulgu 6'ya göre bu yakalanmaz.

## Ölçülmeyenler

- GitHub yayın varlıkları (`usage-tracker-0.6.3-linux-x64`, `SHA256SUMS.txt`), adları, digest'leri ve ikilinin çalışması ölçülmedi: dış istek yasağı vardı. Depodaki `package.yml` yayına dosya yüklemiyor, yalnız `usage-tracker-linux-x64` adlı workflow artifact'ını yüklüyor (`package.yml:425-429`). README'deki yeni satırın doğruluğu elle adlandırılan yayın varlıklarına bağlı.
- pip/pipx kurulumu, `strace` ile dış bağlantı sayımı, panelin Chromium'daki görünümü ve uninstall akışı (rapor bulgusu 4) ölçülmedi.
- Windows CI ve macOS'ta yeni `test_context` (alt süreç, `/proc` atlama) koşulmadı.
- Türkçe yerel ayar (`tr_TR.UTF-8`) ile koşu yapılmadı.
