# Gece raporu — v0.6.3 temiz kurulum denetimi (2026-11-16 → 17)

Ortam: temiz Linux konteyneri (Ubuntu, glibc 2.39, x86-64), Python 3.11.18 (ayrıca 3.9.25),
her kurulum yolu için ayrı ve boş bir `HOME`. Claude Code kaydı ve giriş jetonu yok.
Dal: `gece/1117-kurulum-denetimi` (main'den, `8d43f68`). main'e, etiketlere ve yayına dokunulmadı.

## 1. En önemli 5 bulgu

| # | Önem | Yer | Kanıt | Öneri / durum |
|---|---|---|---|---|
| 1 | Orta (test kırmızı) | `tests/test_context.py:69` (main) | main'de iki dil ayarında da 744 testten 1'i düştü: `800000 != 550000`. Test, "canlı oturum" olarak kendi pid'ini kullanıyor; `usage/context.py:141` önce o sürecin ortamındaki `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` değerini okuyor. Değişken ortamda tanımlıyken test düşüyor, tanımsızken geçiyor (aynı kodla ölçüldü). Claude Code içinde çalışan herkes bu hatayı görür. Kodda hata yok, test ortamdan etkileniyor. | **Düzeltildi** (`062dd66`): canlı oturum artık ortamı test tarafından belirlenen bir alt süreç. Oturum ortamının settings.json'dan önce geldiğini ölçen ek bir test de eklendi. |
| 2 | Orta (yanıltıcı) | `server.py:455`, `server.py:477-482`, `usage/cli.py:1297-1300` | pip, pipx ve ikili dosyada `usagelens --version` çıktısı `usage-tracker 0.6.3`. `--help`, pipx ve ikili dosya kullanıcısına sahip olmadığı `python3 server.py` komutunu gösteriyor (üç yolda da çıktı alındı). | **Düzeltildi** (`2459b29`): `usagelens 0.6.3`, yardım ve argparse `usage:` satırı `usagelens`. `usage-tracker` komutu aynen çalışıyor. Sihirbaz sürümü son kelimeden okuduğu için eski satır da yenisi de ayrıştırılıyor (testli). |
| 3 | Orta (belge ↔ kod) | `usage/providers/__init__.py:42`, `README.tr.md:230`, `docs/GUIDE.md:251,518` | `aider.py:10` ve `continuedev.py:10` "Alan adları ADAY — canlı doğrulanacak" diyor, ama ikisi deneysel listesinde değildi ve belgelerde doğrulanmış sağlayıcıların arasında sayılıyordu. README.md (İngilizce) deneysel sağlayıcılardan hiç söz etmiyordu. | **Düzeltildi** (`0be42b4`): `EXPERIMENTAL` listesine `aider` ve `continue` eklendi, README.md/README.tr.md/GUIDE güncellendi. Panelde rozet görünüyor: Aider kartı `Aider \| LOCAL LOG \| EXPERIMENTAL` (Chromium ile ölçüldü). |
| 4 | Düşük-orta (kaldırma) | `usage/wizard.py` uninstall akışı (CLI çıktısı) | `usagelens setup --uninstall` tek bir soru soruyor: "Remove the autostart entry and the shortcut? [Y/n]". Evet denince status line da geri alınıyor (ölçüldü: `~/my-line.sh` geri geldi), ama soru bunu söylemiyor. stdin kapalıyken (`</dev/null`) "nothing done" yazıp **0** ile çıkıyor ve Claude Code hook'u yerinde kalıyor. README, `pipx uninstall`'dan **önce** bu komutun çalıştırılmasını istiyor; bir betik bunu sessizce atlayabilir. | Önerilen (yapılmadı, davranış değişikliği): soruya "status line" eklensin, TTY yokken sıfırdan farklı bir kodla çıkılsın ya da `--uninstall --yes` desteklensin. |
| 5 | Düşük (belge) | `README.md:47-51` (main) | Yayında `usage-tracker-0.6.3-linux-x64` ve `SHA256SUMS.txt` var ve çalışıyor, ama README'nin kurulum tablosu yalnız Windows `.exe` dosyasını anıyordu. | **Düzeltildi** (`a14ffb5`): indirme, `sha256sum -c` ve `chmod +x` satırı eklendi (testli). İkili dosyanın adı hâlâ `usage-tracker-*`; bkz. "Ölçülmeyen / yapılmayan". |

Kayda değer diğer küçük gözlemler (kod değişmedi):

- `start.sh:23` `exec python3 server.py` argümanları iletmiyor (`"$@"` yok). Linux'ta `server.py:599` (dalda) zaten tarayıcı açmadığı için etkisi az; `./start.sh --help` ise yardım yerine sunucuyu başlatır.
- pipx kurulumunda sihirbaz "source checkout" diyor (`setup` çıktısı: `(linux, source checkout)` / "Nothing to copy: this is a source checkout"). Kurulum bir kaynak klonu değil, pipx ortamı. Yalnız metin sorunu; yollar doğru.
- `usagelens usage --format waybar` yalnız tek yüzde basıyor (`◐ 52.1%`, demo veri). README'deki `◐ S13% W18%` biçimini klon yolundaki `surface/waybar-usage.sh` üretiyor (ölçüldü: `◐ S35% W52.1%`). pipx kullanıcısı README'deki rozeti bu komutla görmez.
- Sihirbaz stdin kapalıyken her adımı atlıyor ama sonunda "Done. The panel lives at …" diyor (ikili dosya ve pipx, `</dev/null`).
- Program içindeki başka metinler hâlâ eski adı taşıyor: açılış satırı `usage-tracker 0.6.3 → http://…` (`server.py`), `doctor`/`usage` başlıkları, `usage/i18n.py:34-96` ("`usage-tracker setup`", "`usage-tracker panel`"), HTTP `Server:` başlığı, sağlayıcı User-Agent'ları (`usage-tracker/0.2`). Bu gece yalnız `--version`/`--help`/`usage:` değiştirildi.

## 2. Kurulum yolları

Her yol ayrı, boş bir `HOME` ile denendi. "Dış bağlantı" sütunu `strace -f -e trace=connect` ile ölçüldü: sunucu açıkken tüm `/api/*` ve `/v1/usage` (`?all=1` dahil) uçları çağrıldı ve yerel olmayan `connect` sayıldı.

| Yol | Komut | Süre | Sonuç | Kanıt |
|---|---|---|---|---|
| pip, etiketten | `pip install "git+https://github.com/ihsandeniz/usagelens.git@v0.6.3"` (temiz venv) | 5,4 sn | Kuruldu, çalışıyor | `usagelens` ve `usage-tracker` komutları oluştu. İkisi de `--version` → `usage-tracker 0.6.3`. Panel açıldı; `/api/usage` 200 (863 B), boş durumda `"reason": "no_token"` ve okunabilir bir ipucu döndü; `/v1/usage`, `/`, `/app.js`, `/styles.css`, `/api/providers`, `/api/limit-kutu` hepsi 200. Dış bağlantı: **0**. |
| pipx (ilk kez ölçüldü) | `pipx install git+…@v0.6.3` (pipx 1.18.16) | 5,9 sn | Kuruldu, çalışıyor | İki komut da kuruldu. pipx yalnız "PATH'te değil" uyarısı verdi (beklenen). `doctor` 0 sorun, 3 uyarı (Claude verisi yok, sunucu kapalı, giriş yok). `usagelens panel --no-open` arka planda başladı, `/api/usage` ve `/` 200. `usage` boş durumda `—` ve `$0.00` gösterdi. `setup --probe`: 6 adım; `--preview autostart/shortcut/statusline` pipx venv yollarını doğru yazıyor. |
| GitHub yayını, Linux ikilisi | `curl -LO …/usage-tracker-0.6.3-linux-x64 -O …/SHA256SUMS.txt` · `sha256sum -c SHA256SUMS.txt --ignore-missing` | indirme 1,4 sn · `--version` 0,22 sn | Doğrulandı, çalışıyor | `usage-tracker-0.6.3-linux-x64: OK`, sha256 `a705b197…1765` (yayın API'sindeki digest ile aynı). ELF x86-64; gereken en yüksek glibc sembolü `GLIBC_2.14`. `--version` → `usage-tracker 0.6.3`. Panel: `/api/usage`, `/v1/usage`, `/`, `/app.js`, `/styles.css` 200. `panel --no-open` ile ayrılan sunucu 8 sn sonra da dosyaları sunuyor (200). `usage`, `doctor` 0; `guard --local --threshold 80` 3 (bilinmiyor, beklenen). `setup --probe`: `frozen: true`, 6 adım. Dış bağlantı: **0**. |
| Klon + `./setup.sh` (README'deki 4. yol) | `git clone --branch v0.6.3 …` · `./setup.sh --auto` · `./start.sh` | 2,1 sn (klon dahil) | Kısmen | `--auto` 0 ile bitti, "finished with warnings" dedi. systemd adımı düştü (`Failed to connect to bus` — konteynerde user systemd yok, ortam kısıtı). `./start.sh` ile panel açıldı, `/api/usage` 200. `--uninstall --auto` 0. |
| Windows `.exe` | — | — | **Ölçülmedi** | Linux konteynerinde çalıştırılamaz. Yalnız SHA256SUMS.txt'te listelendiği görüldü. |
| Arch (AUR) | — | — | Ölçülmedi | README'ye göre henüz yüklenmedi. |

## 3. README iddiaları ↔ kod

| İddia (README.md) | Sonuç | Kanıt |
|---|---|---|
| "Needs Python 3.9+" | Tutuyor | `pyproject.toml:23` `requires-python = ">=3.9"`. Python 3.9.25 ile tüm test paketi geçti (760/760 çalıştı, 4 atlandı, 0 hata). AST `feature_version=(3,9)` taraması temiz. `X \| None` açıklamaları yalnız `from __future__ import annotations` olan dosyalarda (`usage/wizard.py:20`, `usage/claude_statusline.py:22`). |
| "loopback only" | Tutuyor | `server.py:30` `HOST = '127.0.0.1'`. |
| "No account, no telemetry" | Tutuyor (ölçülen kapsamda) | Boş durumda dış bağlantı 0 (strace, pip ve ikili). Kodda kendiliğinden çalışan güncelleme kontrolü yok; `usage/catalog.py:280` `update()` yalnız elle çağrılınca çalışıyor. |
| "stdlib Python — nothing to compile" | Tutuyor | `pyproject.toml:35` `dependencies = []`; pip/pipx kurulumu başka paket çekmedi. |
| Canlı limit isteği: tek GET `api.anthropic.com/api/oauth/usage`, yerel jetonla | Tutuyor | `usage/live.py:26`, `usage/live.py:121-126`. |
| "at most every 2 minutes" | Tutuyor | `usage/live.py:29` `CACHE_TTL = 120.0`. |
| "older than 10 minutes" | Tutuyor | `usage/live.py:33` `LIVE_FRESHNESS_SEC = 10 * 60.0`, `usage/live.py:266`. |
| "waiting out any 429" | Tutuyor | `usage/live.py:34-42,136,281-283` (Retry-After, diskte saklanan bekleme süresi). |
| `User-Agent: claude-cli/2.1.197 (external, cli)`, `anthropic-beta: oauth-2025-04-20` | Tutuyor | `usage/live.py:27-28`. |
| "Nothing else is sent" | Kapsamına göre tutuyor | Anthropic isteğinde yalnız Authorization, beta, UA ve Accept başlıkları var (`usage/live.py:121-126`). Not: sağlayıcı anahtarı girilirse o sağlayıcılara da istek gidiyor (`usage/providers/openrouter.py:34` vb.); README bunu yalnız GUIDE bağlantısıyla anlatıyor. Ollama, LM Studio ve Jan yalnız `127.0.0.1` adresine bağlanıyor. |
| "without a Claude Code login … no request is made" | Tutuyor | `usage/live.py:115-117` erken dönüyor; strace ile 0 bağlantı ölçüldü. |
| "every file is backed up; `setup --uninstall` undoes it" | Tutuyor, bir uyarıyla | `settings.json.bak-usage-tracker` oluştu, `--uninstall` (evet cevabıyla) eski status line'ı geri getirdi. stdin kapalıyken hiçbir şey yapmıyor (bulgu 4). |
| "`usage-tracker` still works as a command name" | Tutuyor | `pyproject.toml:46`; üç yolda da komut çalıştı. |
| "`usagelens panel` opens the panel at :8770" | Tutuyor | pipx ve ikili dosyada `panel --no-open` → `started · http://127.0.0.1:<port>`. |
| waybar rozeti `◐ S13% W18%` | Kısmen | Klon yolu `surface/waybar-usage.sh:265` bu biçimi üretiyor (ölçüldü). `usagelens usage --format waybar` yalnız `◐ 52.1%` (`usage/cli.py:548`). |
| CLI: `usage`, `guard`, `watch --notify`, `kanit` | Tutuyor | `server.py` `CLI_COMMANDS`, `usage/cli.py:1346` `--notify`. |
| Windows: `.exe` Releases'ta | Tutuyor (varlık) | v0.6.3 yayınında `usage-tracker-0.6.3-windows-x64.exe` (10.439.805 B). Çalıştırılmadı. |
| Linux ikilisi | README'de **yoktu** | Bulgu 5, düzeltildi. |
| Desteklenen araçlar | README.md'de yalnız Claude Code vardı; Aider/Continue belgelerde doğrulanmış gibi duruyordu | Bulgu 3, düzeltildi. |
| `docs/GUIDE.md`, `CLI.md`, `WIRE.md`, `WINDOWS.md`, `README.tr.md`, `data/MODELS_DEV_LICENSE` bağlantıları | Tutuyor | Dosyalar mevcut. |

## 4. Commit'ler ve testler

| Commit | Ne | Test |
|---|---|---|
| `062dd66` | `test_context`: canlı oturum ortamı test tarafından belirlenen bir alt süreç; oturum ortamının settings.json'dan önce geldiğini ölçen ek test | 4 → 8 test; `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` ile de tanımsızken de geçiyor |
| `2459b29` | `--version`/`--help`/argparse adı `usagelens`; eski ad çalışıyor; sihirbaz iki sürüm satırını da okuyor | yeni `tests/test_ad_uyumu.py` (10 test). Düzeltmeden önce 5'i kırmızıydı. |
| `0be42b4` | Aider ve Continue deneysel; README.md, README.tr.md, GUIDE | `test_yayin_metin`: güncellenen 1 test, eklenen 2 test (düzeltmeden önce kırmızıydı); panel rozeti Chromium'da görüldü |
| `a14ffb5` | README: Linux ikilisi ve SHA256 doğrulaması | `test_yayin_metin`: eklenen 1 test (önce kırmızıydı) |
| (bu dosya) | GECE-RAPOR.md | — |

Tam paket (`python3 -m unittest discover -s tests -t .`):

| Durum | LANG | Çalıştı | Geçti | Kaldı | Atlandı |
|---|---|---|---|---|---|
| main `8d43f68`, Python 3.11 | C.UTF-8 | 744 | 739 | 1 (`test_context`) | 4 |
| main `8d43f68`, Python 3.11 | tr_TR.UTF-8 (`localedef` ile üretildi) | 744 | 739 | 1 (`test_context`) | 4 |
| dal, Python 3.11 | C.UTF-8 | 761 | 757 | 0 | 4 |
| dal, Python 3.11 | tr_TR.UTF-8 | 761 | 757 | 0 | 4 |
| dal (`0be42b4` anında), Python 3.9.25 | C.UTF-8 | 760 | 756 | 0 | 4 |

Atlanan 4 test: iki "gerçek veri" testi (`UT_GERCEK_VERI=1` gerekiyor), tepsi testi (Qt yok) ve demo ile makinede ortak adaptör kartı bulunmadığında atlanan bir test. tr_TR ayarında `'I'.lower()` → `i`; Türkçe yerel ayar hiçbir testi değiştirmedi.

Commit'lerin yazarı nötr bir yerel kimlik (`nightly-audit`); imza ve oturum bağlantısı eklenmedi.

## 5. Bu raporda ölçülmeyen / yapılmayan

- **İkili dosyanın adı değiştirilmedi.** PyInstaller çıktısı (`packaging/usage-tracker.spec`, `name='usage-tracker'`), kurulu kopyanın yolu (`usage/wizard.py:87` `install_dir()/usage-tracker[.exe]`) ve Windows Başlangıç/Başlat menüsü dosya adları aynı kaldı. Bunları değiştirmek mevcut kurulumların güncelleme, otomatik başlatma ve kaldırma yollarını etkiler. Windows tarafı da burada sınanamaz. Önerilen sıra: (1) spec'te `name='usagelens'`; (2) sihirbazın install adımı `usagelens` adıyla kopyalasın, eski `usage-tracker` yolunu da tanıyıp taşısın (`installed_binary()` iki adı da denesin); (3) yayın dosyaları `usagelens-<sürüm>-linux-x64` olsun, bir sürüm boyunca eski adlı kopya da yüklensin; (4) `package.yml:257,428` ve `docs/WINDOWS*.md` güncellensin. Yayın varlıkları workflow'da değil, elle adlandırılıyor gibi görünüyor (workflow yalnız `usage-tracker-linux-x64` artifact'ını yüklüyor).
- Windows `.exe`: ne çalıştırıldı ne de SHA'sı doğrulandı (yalnız Linux dosyası doğrulandı).
- Gerçek bir Claude Code girişi ve kaydıyla canlı limit, 429 davranışı ve status line hook'unun gerçek Claude Code içinde çalışması ölçülmedi (makinede giriş yok; boş durum ölçüldü).
- systemd ile otomatik başlatma (konteynerde user bus yok), waybar, widget ve tepsi (Qt yok) ölçülmedi.
- pipx'in Python < 3.9 için verdiği "cannot determine package name" hatası denenmedi.
- Python 3.9 yalnız test paketiyle sınandı; 3.9 ile pip/pipx kurulumu yapılmadı.
- `start.sh` argüman iletmeme sorunu, uninstall akışı ve diğer metin sorunları için kod değiştirilmedi (yalnız raporlandı).
- Yeni testlerin Windows CI'da geçtiği ölçülmedi. `SessionEnvWinsTest`, `/proc` olmayan sistemlerde kendini atlıyor; `test_context` alt süreci `sys.executable` ile başlatıyor.
