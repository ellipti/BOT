from datetime import datetime, time
import pytz

TZ = pytz.timezone("Asia/Ulaanbaatar")

def in_session(now: datetime, session: str = "LDN_NY") -> bool:
    """Танилцуулга: 
    - TOKYO: 09:00–12:00 UB
    - LDN_NY (санал): 16:00–02:00 UB (гол хөдөлгөөн)
    """
    now = now.astimezone(TZ)
    t = now.time()
    if session == "TOKYO":
        return time(9,0) <= t <= time(12,0)
    if session == "LDN_NY":
        return t >= time(16,0) or t <= time(2,0)  # шөнө давхиж гарна
    return True
