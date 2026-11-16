#!/usr/bin/env python3
"""Claude Code durum satırı → canlı limit kaynağı (ağsız).

Claude Code her API cevabındaki limit başlıklarını durum satırı betiğine stdin JSON'unda
`rate_limits.{five_hour,seven_day}.{used_percentage,resets_at}` olarak verir. Bu betik onu
`state_dir()/statusline-limits.json`'a yazar; `usage/live.py` taze kayıt varken
`api/oauth/usage` ucuna hiç çıkmaz. O uç agresif rate-limit'li (2026-10-02: 429 +
Retry-After 2685 sn, panel 79 dk donuk) — bu yol ek istek üretmez.

Kurulum (~/.claude/settings.json):
    "statusLine": {"type": "command", "command": "python3 /…/surface/statusline.py"}

Hiçbir koşulda hata basmaz ve 0 dışında çıkmaz: durum satırı her oturumda koşar.
"""
from __future__ import annotations  # README Python 3.9 vaat ediyor: `X | None` 3.9'da yüklenirken patlar

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FILE_NAME = 'statusline-limits.json'
WINDOWS = ('five_hour', 'seven_day')


def extract(payload) -> dict:
    """stdin JSON'undan yalnız bilinen pencereleri al; sayı olmayan yüzdeyi at."""
    rl = payload.get('rate_limits') if isinstance(payload, dict) else None
    out = {}
    if not isinstance(rl, dict):
        return out
    for k in WINDOWS:
        w = rl.get(k)
        if not isinstance(w, dict):
            continue
        pct = w.get('used_percentage')
        if isinstance(pct, bool) or not isinstance(pct, (int, float)):
            continue
        out[k] = {'used_percentage': float(pct), 'resets_at': w.get('resets_at')}
    return out


# Aynı pencere sayılan sıfırlanma farkı (sn). Claude Code `resets_at`'i yuvarlanmış verir;
# küçük kayma yeni pencere demek değildir.
AYNI_PENCERE_SN = 60


def _reset(w):
    r = w.get('resets_at') if isinstance(w, dict) else None
    return r if isinstance(r, (int, float)) and not isinstance(r, bool) else None


# Elle sıfırlama (abonelik sayfasındaki "limiti sıfırla" hakkı) pencereyi DEĞİŞTİRMEZ:
# `resets_at` aynı kalır, yüzde düşer (2026-11-16 ölçüldü: 98 → 14, resets_at aynı).
# Bayat oturum gürültüsü (10-05: 69↔59) küçük düşüştür; sıfırlama en az yarıya iner.
SIFIRLAMA_MIN_DUSUS = 10.0


def sifirlama_mi(eski_pct: float, yeni_pct: float) -> bool:
    return eski_pct - yeni_pct >= SIFIRLAMA_MIN_DUSUS and yeni_pct <= eski_pct / 2 or (
        yeni_pct == 0 and eski_pct > 0)


def _at(w, ad='at') -> float:
    v = w.get(ad) if isinstance(w, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def _tasi(secilen: dict, eski: dict) -> dict:
    """Sıfırlama tabanı aynı pencere boyunca korunur (yeni gelen kayıt onu bilmez)."""
    if 'taban_at' in eski and 'taban_at' not in secilen:
        return dict(secilen, taban_at=eski['taban_at'])
    return secilen


def merge(eski: dict, yeni: dict, now: float) -> dict:
    """Dosyadaki kayıtla bu oturumun gördüğünü birleştir — son yazan kazanmasın.

    Açık her oturum durum satırını çizerken bu dosyaya yazar; boşta duran bir oturum ise
    SON API cevabındaki eski sayıyı taşır. Körlemesine yazınca taze %69'u bayat %59 ezdi
    (2026-10-05, rozet 59↔69 gidip geldi). Kurallar:
      - sıfırlanma anı geçmiş pencere atılır — eskisi de, yeni geleni de: pencere sıfırlandıktan
        sonra boşta duran oturum eski %95'i geçmiş `resets_at` ile getirir, o "canlı" sayılırsa
        `guard` yeni pencerede kritik döner;
      - yeni gelende pencere yoksa eldeki geçerli kayıt korunur;
      - yeni gelen daha ESKİ bir pencereye aitse yok sayılır;
      - aynı pencerede yüzde yalnız artar (kullanım pencere içinde azalmaz) → büyüğü kalır;
        eşitse gözlem anı (`at`) yeni olan kalır;
      - İSTİSNA elle sıfırlama: aynı pencerede yüzde büyük düştüyse (`sifirlama_mi`) ve bu
        gözlem eldekinden YENİYSE kabul edilir; anı `taban_at` olur ve o pencere boyunca bu
        andan önce gözlenmiş (sıfırlama öncesi) değerler yok sayılır (G-gb59vs).
    Oku-birleştir-yaz atomik değil; iki oturumun aynı milisaniyede yazması nadirdir ve
    sonraki çizim düzeltir.
    """
    def gecerli(w):
        if not isinstance(w, dict) or not isinstance(w.get('used_percentage'), (int, float)):
            return None
        r = _reset(w)
        return None if r is not None and r <= now else w

    out = {}
    for k in WINDOWS:
        o, n = gecerli((eski or {}).get(k)), gecerli((yeni or {}).get(k))
        if not n:
            if o:
                out[k] = o
            continue
        if not o:
            out[k] = n
            continue
        ro, rn = _reset(o), _reset(n)
        if ro is not None and rn is not None and rn < ro - AYNI_PENCERE_SN:
            out[k] = o                                   # bayat oturum, eski pencere
        elif ro is not None and rn is not None and abs(rn - ro) <= AYNI_PENCERE_SN:
            po, pn = o['used_percentage'], n['used_percentage']
            ao, an = _at(o), _at(n)
            taban = _at(o, 'taban_at')
            if taban and an < taban:
                out[k] = o                               # elle sıfırlamadan önce gözlenmiş
            elif an > ao and sifirlama_mi(po, pn):
                out[k] = dict(n, taban_at=an)            # elle sıfırlama: pencere aynı, yüzde düştü
            elif pn != po:
                out[k] = _tasi(n if pn > po else o, o)
            else:
                out[k] = _tasi(n if an >= ao else o, o)
        else:
            out[k] = n                                   # yeni pencere (ya da reset bilinmiyor)
    return out


# Panel dili ile aynı seçim (UT_LANG → Windows arayüz dili → LANG); varsayılan İngilizce.
METIN = {
    'tr': {'five_hour': '5s', 'seven_day': '7g', 'kademe': ('Rahat', 'Olağan', 'Kapanış noktası ara',
           'Compact yakın — kapat ya da devret'), 'compact': "compact'a", 'tur': 'tur', 'sabit': 'sabit'},
    'en': {'five_hour': '5h', 'seven_day': '7d', 'kademe': ('Comfortable', 'Normal', 'Find a stopping point',
           'Compact soon — wrap up or hand off'), 'compact': 'to compact', 'tur': 'turns', 'sabit': 'flat'},
}


def dil() -> dict:
    try:
        from usage import i18n
        return METIN.get(i18n.language(), METIN['en'])
    except Exception:
        return METIN['en']


def line(windows: dict) -> str:
    m = dil()
    parts = []
    for k, label in (('five_hour', m['five_hour']), ('seven_day', m['seven_day'])):
        w = windows.get(k)
        if w:
            pct = f"{w['used_percentage']:.0f}"
            parts.append(f"{label} %{pct}" if m is METIN['tr'] else f"{label} {pct}%")
    return ' · '.join(parts)


# ── Bağlam bandı (vault BL-519 #1; kaynak: dev-mod baglam-bandi, token-weather tabanlı)
# Kademeler pencereye değil COMPACT NOKTASINA göre: bu makinede
# CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=55 → 1M pencerede compact ~550k. "%40" rahat
# görünür ama compact'ın %73'üdür.
KADEME = ((50, '○', 0, '32'), (75, '◐', 1, '36'), (90, '◕', 2, '33'), (float('inf'), '●', 3, '31'))
CUBUK = '▁▂▃▄▅▆▇█'
GECMIS = 12


def kisa(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace('.0M', 'M')
    if n >= 1_000:
        return f"{round(n / 1_000)}k"
    return str(int(n))


# Override yokken Claude Code compact'ı pencerenin sonundan sabit bir tampon kadar önce yapar;
# `/context` bunu "Autocompact buffer ~33k" diye gösterir (usage/context.py). 200k'da ≈ %83.
# Eskiden %95 varsayılıyordu: override'sız herkeste bant ~170k'da hâlâ "compact'a 20k" diyordu.
AUTOCOMPACT_TAMPON = 33_000


def compact_pct():
    """CLAUDE_AUTOCOMPACT_PCT_OVERRIDE (0 < v ≤ 100) ya da None."""
    try:
        v = float(os.environ.get('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE', ''))
        return v if 0 < v <= 100 else None
    except ValueError:
        return None


def compact_hedef(pencere: int) -> float:
    pct = compact_pct()
    if pct is not None:
        return pencere * pct / 100
    return max(pencere * 0.5, pencere - AUTOCOMPACT_TAMPON)


def baglam_okuma(payload) -> tuple[int, int] | None:
    """stdin JSON'undan (tokens, pencere); yoksa None."""
    cw = payload.get('context_window') if isinstance(payload, dict) else None
    if not isinstance(cw, dict):
        return None
    pencere = cw.get('context_window_size')
    if not isinstance(pencere, (int, float)) or pencere <= 0:
        return None
    pct = cw.get('used_percentage')
    cu = cw.get('current_usage')
    if isinstance(cu, dict):
        tokens = sum(v for k, v in cu.items()
                     if k.endswith('input_tokens') and isinstance(v, (int, float)))
    elif isinstance(pct, (int, float)):
        tokens = pencere * pct / 100
    else:
        return None
    return int(tokens), int(pencere)


def gecmis_guncelle(sid: str, tokens: int) -> list[int]:
    """Oturum başına son GECMIS okuma; aynı değer tekrar yazılmaz."""
    try:
        from usage import platform as _paths
        yol = _paths.state_dir() / f'statusline-ctx-{sid or "x"}.json'
        try:
            dizi = json.loads(yol.read_text(encoding='utf-8'))
        except Exception:
            dizi = []
            buda(_paths.state_dir())          # yeni oturum: yalnız o an bir kez tara
        dizi = [t for t in dizi if isinstance(t, int) and t > 0]
        if tokens > 0 and (not dizi or dizi[-1] != tokens):
            dizi = (dizi + [tokens])[-GECMIS:]
            _paths.atomic_write_text(yol, json.dumps(dizi))
        return dizi
    except Exception:
        return [tokens] if tokens else []


CTX_OMUR_SN = 7 * 86_400


def buda(dizin, now=None):
    """Oturum başı geçmiş dosyaları sınırsız birikiyordu (bir günde 26): 7 günden eskiyi sil."""
    now = now or time.time()
    try:
        for f in dizin.glob('statusline-ctx-*.json'):
            try:
                if now - f.stat().st_mtime > CTX_OMUR_SN:
                    f.unlink()
            except OSError:
                pass
    except OSError:
        pass


def bant(tokens: int, pencere: int, gecmis: list[int]) -> str:
    m = dil()
    hedef = compact_hedef(pencere)
    oran = 100 * tokens / hedef
    _, ikon, sira, renk = next(k for k in KADEME if oran < k[0])
    kalan = max(0, hedef - tokens)
    parca = [f"\033[1;{renk}m{ikon} {m['kademe'][sira]}\033[0m",
             (f"%{round(100 * tokens / pencere)}" if m is METIN['tr']
              else f"{round(100 * tokens / pencere)}%"),
             f"\033[2m{kisa(tokens)}/{kisa(pencere)}\033[0m",
             f"{m['compact']} {kisa(kalan)}"]
    if len(gecmis) >= 3:
        ort = (gecmis[-1] - gecmis[0]) / (len(gecmis) - 1)
        if ort > 500:
            parca[-1] += f" (~{int(kalan // ort)} {m['tur']})"
    if len(gecmis) >= 2:
        tepe = max(gecmis) or 1
        grafik = ''.join(CUBUK[min(7, int(t / tepe * 7))] for t in gecmis)
        d = gecmis[-1] - gecmis[-2]
        egilim = f"▲ +{kisa(d)}" if d > 0 else (f"▼ {kisa(-d)}" if d < 0 else m['sabit'])
        parca.append(f"\033[{renk}m{grafik}\033[0m \033[2m{egilim}\033[0m")
    return '  '.join(parca)


def gozlem_ani(payload, now: float) -> float:
    """Bu yüzdelerin GÖZLENDİĞİ an — yazım anı değil.

    Durum satırı boşta duran oturumda da yeniden çizilir ve son API cevabındaki eski yüzdeyi
    getirir. Kayda `now` basılınca bu bayat değer sonsuza dek "canlı" kalıyor, `live.fetch`
    ağa hiç çıkmıyordu (yenile düğmesi dahil); başka cihazdaki kullanım görünmüyordu.
    Yüzde her API cevabıyla gelir ve cevap transcript'e hemen yazılır → transcript'in son
    değişme anı, gözlem anının iyi bir üst sınırıdır. Transcript yoksa `now`.
    """
    tp = payload.get('transcript_path') if isinstance(payload, dict) else None
    if isinstance(tp, str) and tp:
        try:
            return min(now, os.stat(tp).st_mtime)
        except OSError:
            pass
    return now


WRAP_TIMEOUT_SN = 5


def wrapped_line(raw: str):
    """`--wrap`: kurulum sihirbazı kullanıcının kendi statusLine'ını bizimkiyle sardıysa onu
    aynı stdin ile koştur ve çıktısını aynen döndür — kullanıcının satırı değişmesin. Komut
    yoksa, hata verirse ya da boş basarsa None (o zaman kendi satırımız basılır)."""
    try:
        from usage import claude_statusline
        cmd = claude_statusline.wrapped_command()
    except Exception:
        cmd = None
    if not cmd:
        return None
    import subprocess
    try:
        proc = subprocess.run(cmd, shell=True, input=raw, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=WRAP_TIMEOUT_SN)
    except Exception:
        return None
    out = (proc.stdout or '').rstrip('\n')
    return out or None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    raw = sys.stdin.read() or '{}'
    try:
        payload = json.loads(raw)
    except Exception:
        payload = None
    if '--wrap' in argv:
        if isinstance(payload, dict):
            kaydet(payload)
        out = wrapped_line(raw)
        if out is not None:
            _bas(out)
            return
        if not isinstance(payload, dict):
            return
        _ciz(payload, kaydedildi=True)
        return
    if payload is None:
        return
    _ciz(payload)


def _bas(metin: str):
    try:
        print(metin)
    except UnicodeEncodeError:  # Windows cp1252 konsolu bant karakterlerini basamıyor
        sys.stdout.buffer.write((metin + '\n').encode('utf-8', 'replace'))


def kaydet(payload) -> dict:
    """Limit yüzdelerini kayda yaz; çıkardığı pencereleri döndürür."""
    windows = extract(payload)
    if windows:
        try:
            from usage import platform as _paths
            yol = _paths.state_dir() / FILE_NAME
            now = time.time()
            gozlem = gozlem_ani(payload, now)
            for w in windows.values():
                w['at'] = gozlem
            try:
                d = json.loads(yol.read_text(encoding='utf-8'))
                eski = d.get('windows') or {}
                for w in eski.values():           # pencere başı `at` öncesi biçim
                    if isinstance(w, dict) and not isinstance(w.get('at'), (int, float)):
                        w['at'] = d.get('at') if isinstance(d.get('at'), (int, float)) else 0
            except Exception:
                eski = {}
            birlesik = merge(eski, windows, now)
            if birlesik:
                at = max(w.get('at') or 0 for w in birlesik.values())
                _paths.atomic_write_text(yol, json.dumps({'at': at, 'windows': birlesik}))
                from usage import limitseri          # zaman serisi: yalnız değer değişince 1 satır
                limitseri.ekle(birlesik, at, 'statusline')
        except Exception:
            pass
    return windows


def _ciz(payload, kaydedildi=False):
    windows = extract(payload) if kaydedildi else kaydet(payload)
    parcalar = []
    okuma = baglam_okuma(payload)
    if okuma and okuma[0] > 0:
        # dosya adına girer: yalnız güvenli karakterler
        sid = re.sub(r'[^A-Za-z0-9_-]', '', str(payload.get('session_id') or ''))[:64]
        parcalar.append(bant(*okuma, gecmis_guncelle(sid, okuma[0])))
    if windows:
        parcalar.append(line(windows))
    if parcalar:
        _bas('  · '.join(parcalar))



if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
