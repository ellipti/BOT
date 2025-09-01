import time
from typing import Optional
import pandas as pd
import MetaTrader5 as mt5

from .logger import get_logger
logger = get_logger("mt5")

class MT5Client:
    def __init__(self):
        self.initialized = False

    def connect(self, login: int = 0, password: str = "", server: str = "", path: Optional[str] = None, attach_mode: bool = False) -> bool:
        try:
            # Initialize MT5
            ok = mt5.initialize(path) if path else mt5.initialize()
            if not ok:
                logger.error(f"MT5 эхлүүлж чадсангүй: {mt5.last_error()}")
                return False

            # --- ATTACH MODE: аль хэдийн логин хийсэн терминалд наалдах ---
            if attach_mode:
                acc = mt5.account_info()
                if acc is None:
                    logger.error("MT5 нэвтрээгүй байна. Terminal нээж login хийнэ үү.")
                    return False
                ti = mt5.terminal_info()
                logger.info(
                    f"MT5 амжилттай холбогдлоо | "
                    f"Терминал={getattr(ti,'build',None)} | "
                    f"Зам={getattr(ti,'path',None)} | "
                    f"Данс={acc.login} | "
                    f"Брокер={acc.server} | "
                    f"Нэр={acc.name} | "
                    f"Хөшүүрэг={acc.leverage} | "
                    f"Үлдэгдэл=${acc.balance:.2f} | "
                    f"Equity=${acc.equity:.2f}"
                )
                self.initialized = True
                return True

            # --- LOGIN MODE: креденшлээр нэвтрэх ---
            if not login or not password or not server:
                logger.error("Login горимд MT5 нэвтрэх мэдээлэл дутуу байна")
                return False

            authorized = mt5.login(login=login, password=password, server=server)
            if not authorized:
                logger.error(f"MT5 руу нэвтэрч чадсангүй: {mt5.last_error()}")
                return False

            acc = mt5.account_info()
            if acc is None:
                logger.error("Данс руу нэвтэрсэн ч мэдээлэл авч чадсангүй")
                return False

            ti = mt5.terminal_info()
            logger.info(
                f"MT5 connected | terminal_build={getattr(ti,'build',None)} | path={getattr(ti,'path',None)} | "
                f"account_login={acc.login} | server={acc.server} | name={acc.name} | leverage={acc.leverage} | "
                f"balance={acc.balance:.2f} | equity={acc.equity:.2f}"
            )
            self.initialized = True
            return True

        except Exception as e:
            logger.error(f"MT5 холболтын алдаа: {str(e)}")
            return False

        finally:
            if not self.initialized:
                try:
                    mt5.shutdown()
                except:
                    pass

    def ensure_symbol(self, symbol: str) -> bool:
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Валютын хос олдсонгүй: {symbol}")
            return False
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Валютын хос сонгож чадсангүй: {symbol}")
                return False
        return True

    def _parse_timeframe(self, tf_str: str) -> int:
        """Convert timeframe string to MT5 timeframe constant"""
        import MetaTrader5 as mt5
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1,
        }
        tf = tf_map.get(tf_str.upper())
        if tf is None:
            logger.error(f"Буруу интервал: {tf_str}. M30 руу шилжүүлж байна.")
            return mt5.TIMEFRAME_M30  # safe default
        return tf

    def get_rates(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        if not self.ensure_symbol(symbol):
            return pd.DataFrame()
        tf = self._parse_timeframe(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            logger.error(f"{symbol} хосын түүх татаж чадсангүй: {mt5.last_error()}")
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def account_snapshot(self) -> Optional[dict]:
        acc = mt5.account_info()
        if acc is None:
            logger.error("Дансны мэдээлэл авч чадсангүй")
            return None
        snap = {
            "login": acc.login,
            "server": acc.server,
            "name": acc.name,
            "company": acc.company,
            "currency": acc.currency,
            "leverage": acc.leverage,
            "balance": float(acc.balance),
            "equity": float(acc.equity),
            "margin_free": float(acc.margin_free),
        }
        logger.info(f"Дансны мэдээлэл | "
                   f"ID={snap['login']} | "
                   f"Нэр={snap['name']} | "
                   f"Брокер={snap['company']} | "
                   f"Валют={snap['currency']} | "
                   f"Хөшүүрэг={snap['leverage']} | "
                   f"Үлдэгдэл=${snap['balance']:.2f} | "
                   f"Equity=${snap['equity']:.2f} | "
                   f"Чөлөөт маржин=${snap['margin_free']:.2f}")
        return snap

    def shutdown(self):
        if self.initialized:
            mt5.shutdown()
            self.initialized = False
            logger.info("MT5-аас амжилттай салгалаа")
