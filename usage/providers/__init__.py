#!/usr/bin/env python3
"""
Çok-sağlayıcı adaptör kayıt defteri (FAZ 2).

Her adaptör tek bir `collect(days) -> dict | None` fonksiyonu sunar:
  - None  → sağlayıcı yapılandırılmamış/bulunamadı → UI kart AÇMAZ ("no dead cards").
  - dict  → {'id','name','kind','status','available',...} → UI kart açar
            (status='offline'/'error' olsa bile — yapılandırılmış ama şu an erişilemez demek).

Kart 'kind' türleri:
  'spend'  → gerçek $ (currency/spend/balance/limit)     — OpenRouter
  'tokens' → token hacmi + $ tahmini (subscription)       — Codex
  'local'  → yerel/ücretsiz (models/running)              — Ollama
  'quota'  → karakter/birim kotası + reset ($ yok)        — ElevenLabs

Claude ayrı tutulur (engine.compute_spend/compute_usage) — burada tekrar edilmez.
Tümü stdlib-only, salt-okunur, kısa timeout + TTL cache (429/ağ nezaketi).
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from . import (openrouter, openai, deepseek, together, novita, deepinfra, huggingface,
               elevenlabs, ollama, lmstudio, jan,
               codex, aider, continuedev, cody, windsurf)

# Sıra = UI kart sırası: gerçek-$ API → kota → yerel → lokal-log
_ADAPTERS = (openrouter, openai, deepseek, together, novita, deepinfra, huggingface,  # spend/quota API
             elevenlabs,                                                     # quota (karakter)
             ollama, lmstudio, jan,                                          # yerel/ücretsiz
             codex, aider, continuedev, cody, windsurf)                      # lokal-log token

TOTAL_TIMEOUT = 10  # tüm adaptörlerin toplam bütçesi (saniye) — deadline-based paylaşım

def _collect_single(mod, days):
    """Tek bir adaptörü çalıştır ve sonucunu iste. İstisnalar caller'da işlenir."""
    return mod.collect(days)


#: Başarılı bir yanıtı hiç görülmemiş adaptörler (anahtarı olan kimse doğrulamadı): kartları
#: `experimental: True` taşır, panel rozetini gösterir, belge onları ayrı listeler (v0.6.2).
#: Biri doğrulanınca buradan çıkar — tek yer.
EXPERIMENTAL = frozenset({'deepseek', 'novita', 'deepinfra', 'huggingface', 'together',
                          'cody', 'windsurf'})


def name_of(provider_id: str):
    """Kart adı — gizli (hiç sorgulanmayan) sağlayıcıyı ayar ekranında listelemek için."""
    for mod in _ADAPTERS:
        if getattr(mod, 'PROVIDER_ID', None) == provider_id:
            return getattr(mod, 'PROVIDER_NAME', provider_id)
    return None


def collect(days: int = 30, skip=(), only=None) -> list:
    """Tüm yapılandırılmış sağlayıcıların kartlarını paralel topla. Bir adaptörün patlaması
       diğerlerini düşürmez (izole try/except).

       Timeout: deadline-based (tüm adaptörlerin toplam bütçesi TOTAL_TIMEOUT saniye).
       Adaptörler paralel koşuyor; her biri deadline'a kadar bekler.
       Örn: 3 asılı → ~10s (3×10 değil), 8 asılı → ~10s, hep doğru.
    """
    cards = []
    executor = ThreadPoolExecutor(max_workers=max(1, len(_ADAPTERS)))
    deadline = time.monotonic() + TOTAL_TIMEOUT

    try:
        # Her adaptör için future oluştur, sırayı tut
        # Gizli kart = hiç sorgulanmaz (API-F001): süzmek yetmez, istek gitmemeli.
        mods = [m for m in _ADAPTERS if getattr(m, 'PROVIDER_ID', None) not in set(skip or ())
                and (only is None or getattr(m, 'PROVIDER_ID', None) in set(only))]
        futures = {i: executor.submit(_collect_single, mod, days) for i, mod in enumerate(mods)}

        # Tamamlanma sırasına bakılmaksızın, _ADAPTERS sırasında sonuçları topla
        # Her adaptör için kalan bütçeyi hesapla (deadline paylaşımı)
        for i, mod in enumerate(mods):
            remaining = max(0.0, deadline - time.monotonic())
            try:
                card = futures[i].result(timeout=remaining)
            except TimeoutError:
                provider_id = getattr(mod, 'PROVIDER_ID', mod.__name__.split('.')[-1])
                provider_name = getattr(mod, 'PROVIDER_NAME', '?')
                provider_kind = getattr(mod, 'PROVIDER_KIND', 'spend')
                print(f'Provider {provider_id} error: TimeoutError: exceeded {TOTAL_TIMEOUT}s total', file=sys.stderr)
                card = {'id': provider_id,
                        'name': provider_name, 'kind': provider_kind,
                        'status': 'error', 'available': True,
                        'error': f'No response ({TOTAL_TIMEOUT}s exceeded)'}
            except Exception as e:                       # adaptör beklenmedik hata → kart açma
                provider_id = getattr(mod, 'PROVIDER_ID', mod.__name__.split('.')[-1])
                provider_name = getattr(mod, 'PROVIDER_NAME', '?')
                provider_kind = getattr(mod, 'PROVIDER_KIND', 'spend')
                # Tam exception detayını stderr'e logla (iç tanı için)
                print(f'Provider {provider_id} error: {type(e).__name__}: {e}', file=sys.stderr)
                # UI'da gösterilebilir mesaj: sadece exception tipi
                card = {'id': provider_id,
                        'name': provider_name, 'kind': provider_kind,
                        'status': 'error', 'available': True,
                        'error': f'Error ({type(e).__name__})'}
            if card and card.get('available'):
                if card.get('id') in EXPERIMENTAL:
                    card['experimental'] = True
                cards.append(card)
    finally:
        # Asılabilen thread'leri iptal et; shutdown'u beklemeden hemen dön (wait=False)
        # cancel_futures=True (py3.9+) henüz çalışmayan future'ları iptal eder
        executor.shutdown(wait=False, cancel_futures=True)

    return cards


if __name__ == '__main__':
    import json
    print(json.dumps(collect(30), ensure_ascii=False, indent=2))
