import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from core.logger import get_logger

logger = get_logger("strategy")

@dataclass
class TradingContext:
    price: float
    atr: float
    rsi: float
    ma_fast: float
    ma_slow: float
    spread: float
    next_news_minutes: Optional[int]
    last_trade_minutes: Optional[int]

@dataclass
class TradeDecision:
    decision: str  # "BUY", "SELL", "WAIT"
    confidence: float
    reason: str
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    confluences: Optional[list] = None

def ma_crossover_signal(df: pd.DataFrame) -> dict:
    """
    Энгийн MA crossover сигнал (MA20 vs MA50)
    Returns: dict with "signal" ("BUY"/"SELL"/"HOLD") and "reason"
    """
    if len(df) < 51:  # MA50 тооцоход хамгийн багадаа 50 бар хэрэгтэй
        return {
            "signal": "HOLD",
            "reason": "Хангалттай түүхэн дата байхгүй"
        }

    # MA тооцох
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["MA50"] = df["close"].rolling(window=50).mean()

    # Хамгийн сүүлийн 2 бар
    last1, last2 = df.iloc[-1], df.iloc[-2]

    # MA20 өмнөх бар дээр MA50-с доогуур байснаа дээгүүр гарсан = BUY сигнал
    if last2["MA20"] <= last2["MA50"] and last1["MA20"] > last1["MA50"]:
        return {
            "signal": "BUY",
            "reason": f"MA20 ({last1['MA20']:.2f}) MA50-г ({last1['MA50']:.2f}) дээш огтолж гарлаа"
        }

    # MA20 өмнөх бар дээр MA50-с дээгүүр байснаа доогуур орсон = SELL сигнал
    if last2["MA20"] >= last2["MA50"] and last1["MA20"] < last1["MA50"]:
        return {
            "signal": "SELL", 
            "reason": f"MA20 ({last1['MA20']:.2f}) MA50-г ({last1['MA50']:.2f}) доош огтолж орлоо"
        }

    return {
        "signal": "HOLD",
        "reason": f"MA20 ({last1['MA20']:.2f}) MA50-тэй ({last1['MA50']:.2f}) огтлолцоогүй"
    }

class MultimodalAnalyst:
    def __init__(self):
        self.min_confidence = 0.60
        self.min_risk_reward = 1.5
        self.min_confluences = 2

    def analyze_chart_and_context(self, chart_data: bytes, context: Dict[str, Any]) -> TradeDecision:
        """
        Analyze chart image and numeric context to produce a trade decision
        
        Args:
            chart_data: Binary image data of the chart
            context: JSON context with numeric values (price, indicators, etc.)
            
        Returns:
            TradeDecision object with the analysis result
        """
        # Parse context into TradingContext
        trading_ctx = TradingContext(
            price=context["price"],
            atr=context["atr"],
            rsi=context["rsi"],
            ma_fast=context["ma_fast"],
            ma_slow=context["ma_slow"],
            spread=context["spread"],
            next_news_minutes=context.get("next_news_minutes"),
            last_trade_minutes=context.get("last_trade_minutes")
        )

        # Check risk/ops gates first
        if not self._check_gates(trading_ctx):
            return TradeDecision(
                decision="WAIT",
                confidence=0.0,
                reason="Risk gates not passed (spread/news/cooldown)",
                confluences=[]
            )

        # Analyze confluences
        confluences = self._analyze_confluences(chart_data, trading_ctx)
        if len(confluences) < self.min_confluences:
            return TradeDecision(
                decision="WAIT",
                confidence=0.0,
                reason=f"Insufficient confluences ({len(confluences)})",
                confluences=confluences
            )

        # Calculate entry, SL, TP
        entry, sl, tp = self._calculate_levels(trading_ctx, confluences)
        if not entry or not sl or not tp:
            return TradeDecision(
                decision="WAIT",
                confidence=0.0,
                reason="Could not determine valid entry/SL/TP levels",
                confluences=confluences
            )

        # Calculate risk/reward
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        risk_reward = reward / risk if risk > 0 else 0

        if risk_reward < self.min_risk_reward:
            return TradeDecision(
                decision="WAIT",
                confidence=0.0,
                reason=f"Insufficient risk/reward ratio ({risk_reward:.2f})",
                confluences=confluences,
                risk_reward=risk_reward
            )

        # Determine final decision
        confidence = self._calculate_confidence(confluences, risk_reward, trading_ctx)
        decision = self._make_decision(confidence, trading_ctx)

        return TradeDecision(
            decision=decision,
            confidence=confidence,
            reason=self._generate_reason(confluences, decision),
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            risk_reward=risk_reward,
            confluences=confluences
        )

    def _check_gates(self, ctx: TradingContext) -> bool:
        """Check risk/operational gates"""
        if ctx.spread > ctx.atr * 0.1:  # Spread should be < 10% of ATR
            return False
        if ctx.next_news_minutes and ctx.next_news_minutes < 30:  # No high impact news in next 30m
            return False
        if ctx.last_trade_minutes and ctx.last_trade_minutes < 60:  # 1h cooldown between trades
            return False
        return True

    def _analyze_confluences(self, chart_data: bytes, ctx: TradingContext) -> list:
        """Analyze chart for confluence factors"""
        confluences = []
        
        # MA Cross check
        if ctx.ma_fast > ctx.ma_slow:
            confluences.append("MA fast crossed above slow MA")
        elif ctx.ma_fast < ctx.ma_slow:
            confluences.append("MA fast crossed below slow MA")

        # RSI extremes
        if ctx.rsi > 70:
            confluences.append("RSI overbought")
        elif ctx.rsi < 30:
            confluences.append("RSI oversold")

        # TODO: Add chart pattern recognition from image
        # This would analyze the chart_data for patterns, trendlines, etc.
            
        return confluences

    def _calculate_levels(self, ctx: TradingContext, confluences: list) -> tuple:
        """Calculate entry, SL, and TP levels"""
        entry = ctx.price
        
        # Use ATR for SL/TP calculation
        sl = entry - (ctx.atr * 1.5) if "MA fast crossed above slow MA" in confluences else entry + (ctx.atr * 1.5)
        tp = entry + (ctx.atr * 2.5) if "MA fast crossed above slow MA" in confluences else entry - (ctx.atr * 2.5)
        
        return entry, sl, tp

    def _calculate_confidence(self, confluences: list, risk_reward: float, ctx: TradingContext) -> float:
        """Calculate confidence score based on confluences and conditions"""
        base_confidence = 0.5
        
        # Add confidence based on number of confluences
        confluence_boost = min(0.1 * len(confluences), 0.3)
        
        # Add confidence based on risk/reward ratio
        rr_boost = min((risk_reward - self.min_risk_reward) * 0.1, 0.2)
        
        # Reduce confidence if RSI is extreme
        rsi_penalty = 0.1 if ctx.rsi > 70 or ctx.rsi < 30 else 0
        
        return min(base_confidence + confluence_boost + rr_boost - rsi_penalty, 1.0)

    def _make_decision(self, confidence: float, ctx: TradingContext) -> str:
        """Make final trading decision based on confidence and context"""
        if confidence < self.min_confidence:
            return "WAIT"
            
        if ctx.ma_fast > ctx.ma_slow and ctx.rsi < 70:
            return "BUY"
        elif ctx.ma_fast < ctx.ma_slow and ctx.rsi > 30:
            return "SELL"
            
        return "WAIT"

    def _generate_reason(self, confluences: list, decision: str) -> str:
        """Generate concise reason for the decision"""
        if decision == "WAIT":
            return "Insufficient conviction for trade entry"
            
        confluence_str = ", ".join(confluences[:2])  # List top 2 confluences
        return f"{decision} signal based on {confluence_str}"

class BaselineStrategy:
    def __init__(self, mt5_client):
        self.mt5_client = mt5_client
        self.analyst = MultimodalAnalyst()
        
    def analyze_market(self, symbol, timeframe, chart_data=None):
        """
        Analyze market using multimodal analysis of chart and market data
        """
        # Get market data
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
        if rates is None:
            raise Exception("Failed to get market data")
            
        df = pd.DataFrame(rates)
        
        # Calculate indicators
        df["MA20"] = df["close"].rolling(window=20).mean()
        df["MA50"] = df["close"].rolling(window=50).mean()
        df["RSI"] = self._calculate_rsi(df["close"])
        df["ATR"] = self._calculate_atr(df)
        
        # Prepare context for analyst
        last_bar = df.iloc[-1]
        context = {
            "price": last_bar["close"],
            "atr": last_bar["ATR"],
            "rsi": last_bar["RSI"],
            "ma_fast": last_bar["MA20"],
            "ma_slow": last_bar["MA50"],
            "spread": self.mt5_client.get_spread(symbol),
            "next_news_minutes": None,  # TODO: Implement news check
            "last_trade_minutes": None  # TODO: Implement trade history check
        }
        
        # Get decision from analyst
        decision = self.analyst.analyze_chart_and_context(chart_data, context)
        
        logger.info(f"Analysis for {symbol}: {decision.decision} (confidence: {decision.confidence:.2f})")
        logger.info(f"Reason: {decision.reason}")
        
        if decision.confluences:
            logger.info(f"Confluences: {', '.join(decision.confluences)}")
            
        if decision.risk_reward:
            logger.info(f"Risk/Reward: {decision.risk_reward:.2f}")
            
        return decision.decision

    def _calculate_rsi(self, prices, periods=14):
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_atr(self, df, periods=14):
        """Calculate ATR indicator"""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.DataFrame({"TR1": tr1, "TR2": tr2, "TR3": tr3}).max(axis=1)
        return tr.rolling(window=periods).mean()
        
    def execute_trade(self, signal, symbol, lot_size, stop_loss, take_profit):
        """Execute trade based on signal"""
        try:
            if signal == "BUY":
                self.mt5_client.place_order(
                    symbol=symbol,
                    order_type=mt5.ORDER_TYPE_BUY,
                    lot_size=lot_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                logger.info(f"Placed BUY order for {symbol}")
                
            elif signal == "SELL":
                self.mt5_client.place_order(
                    symbol=symbol,
                    order_type=mt5.ORDER_TYPE_SELL,
                    lot_size=lot_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                logger.info(f"Placed SELL order for {symbol}")
                
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            raise
