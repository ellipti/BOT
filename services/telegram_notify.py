import requests
from settings import settings

TG_TOKEN = settings.TELEGRAM_BOT_TOKEN or ""
# Олон хүлээн авагч: TELEGRAM_CHAT_IDS (comma-separated). Хуучин CHAT_ID байвал fallback.
RAW_IDS = (settings.__dict__.get("TELEGRAM_CHAT_IDS") or
           getattr(settings, "TELEGRAM_CHAT_ID", "") or "")

def _targets():
    ids = []
    for x in str(RAW_IDS).split(","):
        x = x.strip()
        if not x:
            continue
        # -100..., 5721..., эсвэл @channelusername аль нь ч байж болно
        try:
            ids.append(int(x))
        except ValueError:
            ids.append(x)   # @channelusername бол string хэвээр
    return ids

def _enabled() -> bool:
    return bool(TG_TOKEN and _targets())

def send_text(text: str) -> None:
    if not _enabled():
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    for chat_id in _targets():
        try:
            requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=12)
        except Exception:
            pass

def send_photo(path: str, caption: str = "") -> None:
    if not _enabled():
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    for chat_id in _targets():
        try:
            with open(path, "rb") as f:
                requests.post(url, data={"chat_id": chat_id, "caption": caption},
                            files={"photo": f}, timeout=20)
        except Exception:
            pass
