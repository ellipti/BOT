# Trading Bot

This is a MetaTrader 5 trading bot that implements automated trading strategies with Telegram notifications.

## Features

- MetaTrader 5 integration
- Customizable trading strategies
- Telegram notifications

## AIVO Trading Bot — Товч танилцуулга

Энэ репозитор нь MetaTrader 5 (MT5)-тай холбогддог, автоматжуулсан худалдааны логик болон Telegram мэдэгдэлтэй жижиг хэмжээний trading bot жишээ юм. Проект нь MA crossover, ATR, RSI зэрэг энгийн индикатор дээр суурилсан шийдвэр гаргах, мөн "safety gate" хэлбэрээр нэмэлт баталгаажуулалт хийдэг.

Товч гол боломжууд:

- MT5-аас түүх, сүүлийн үнийн мэдээлэл татах
- Энгийн стратеги (MA20/MA50 crossover) болон индикатор (ATR, RSI)
- Safety gate: сешн шалгалт, cooldown (давхардал), улаан мэдээ шалгах (Trading Economics-ээр), сигнал валидаци, ATR дээр суурилсан lot sizing
- Зураг үүсгэх (charts/) — candlestick + volume, overlays
- Telegram мэдэгдэл

## Суурь шаардлага

- Python 3.11+ (эсвэл таны орчинтой нийцсэн шинэ хувилбар)
- MetaTrader 5 терминал / демо/реал данс ба MetaTrader5 Python пакет
- Docker ашиглах бол тохируулга өөрчилнө

## Түргэн эхлүүлэх

1. Репог clone хийгээд project фолдерт орно:

   git clone <repo>
   cd BOT

2. Шаардлагатай Python пакетуудыг суулгана:

   python -m pip install -r requirements.txt

3. `.env.example` файлыг ` .env` болгон хуулж, өөрийн тохиргоог оруулна (MT5 логин/пароль, TELEGRAM токен г.м.).

   Хэрэв Trading Economics‑ийн мэдээ шүүлтүүр (red‑news) хэрэглэхгүй бол `TE_API_KEY` хоосон байж болно — энэ тохиолдолд safety gate мэдээний шалгалтыг автоматаар үсэргүүлнэ.

4. Тестээр ажиллуулах:

   python app.py

   (Хэрэглэгч өөрийн орчинд MT5 холболт, dry_run тохиргоо зэргийг анхааран ашиглана.)

## Гол тохиргоонууд ( `.env`-д )

- MT5_LOGIN / MT5_PASSWORD / MT5_SERVER / MT5_PATH
- SYMBOLS (ж: XAUUSD,EURUSD)
- TIMEFRAME (ж: M30)
- RISK_PER_TRADE — дансны хэдэн хувийг эрсдэл болгох (0.01 = 1%)
- ATR_PERIOD, SL_ATR_MULTIPLIER, TP_R_MULTIPLIER
- DRY_RUN — үнэхээр ордер явуулахгүй турших бол true
- TE_API_KEY — Trading Economics API key (optional). Хэрэв ашиглавал safety_gate улаан мэдээ шалгана.
- USD_PER_LOT_PER_USD_MOVE — XAUUSD зэрэг хувьд 1 lot‑ын $1 хөдөлгөөнд хэр их USD PnL тооцохыг тохируулна (ж: 100)

Тухайн `.env` файл нь нууц мэдээлэл агуулж болох тул репост руу commit хийхээс зайлсхий.

## Safety gate (чимхүүр)

Safety gate нь дараах шалгуурыг хийнэ:

- Сешн цонх (TOKYO / LDN_NY / ANY)
- Cooldown: өмнөх гүйлгээний дараа тогтоосон хугацаанд дахин орж болохгүй
- Улаан мэдээ: Trading Economics API‑аар өндөр ач холбогдолтой мэдээг шалгана (API key шаардлагатай)
- Сигналын валидаци: ATR дээр доогуур сигнал, MA trend, RSI нөхцөл зэргээс хамааран HOLD
- ATR‑д суурилсан лот тооцоолол

Энэ логик нь `safety_gate.py` дотор байна. Safety gate‑ээр батлагдсан үед л `ex.place(...)` дуудаж нэг л ордер үүсгэх дүрэм хэрэгжинэ.

## Зураг ба overlays

`services/chart_renderer.py` нь candlestick + volume зураг үүсгэж, overlay (trendlines, zones, fibonacci) зурж чадна. Хугацааны axis‑ын 1970‑ын асуудлыг файл дотор date2num ашиглан шийдсэн бөгөөд overlays‑ын `ax` variable тодорхойлогдсон тул NameError‑ыг хаасан.

## Аюулгүй ажиллагаа / зөвлөмж

- Тестлэхдээ `DRY_RUN=true` ашигла. Жинхэнэ ордер явуулахын өмнө лог болон state файлыг шалга.
- Нууц түлхүүрүүдийг `.env`‑д хадгалах ба `.gitignore`‑д нэмж commit бүү хийгээрэй.
- Trading Economics API key‑г хэрэв репонд бүү оруул: орчинд `setx TE_API_KEY "<your key>"` ашиглан тохируул.

## Хэрвээ ямар нэг зүйл ажиллахгүй байвал

- Лог файлыг (logs/) шалга. Аливаа алдаа/exception дэлгэрэнгүй гарсан байх ёстой.
- `python -m pip install -r requirements.txt` дахин ажиллуулж шаардлагатай пакетуудыг суулга.
- Тусламж хэрэгтэй бол issue үүсгэнэ үү: багц тохиргоо, MT5 холболт, эсвэл chart rendering‑тэй холбоотой тусламж үзүүлнэ.

---

Жич: Энэ README нь таны local copy‑д зориулж богино зааварчилгаа өгсөн бөгөөд таны орчинд тохируулан засвар хийх шаардлагатай байж болно.
