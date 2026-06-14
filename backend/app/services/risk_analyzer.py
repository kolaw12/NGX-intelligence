"""Intelligence layer risk analysis for NGX equities.

This module scores stock risk from engineered market features and optional NGX
macro context. It connects upstream `FeatureEngineer` outputs to the rule engine,
recommendation API, NLG explanation layer, and persisted signal records.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.utils.enums import RiskLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskFlag:
    """One risk contributor with score impact and explanation."""

    name: str
    impact: float
    severity: RiskLevel
    description: str


@dataclass(frozen=True)
class RiskProfile:
    """Risk analysis result for one stock."""

    ticker: str
    date: date
    risk_score: float
    risk_level: RiskLevel
    volatility_flag: bool
    atr_score: float
    drawdown_score: float
    volume_spike: bool
    flags: list[RiskFlag] = field(default_factory=list)
    regime_alert: bool = False
    regime_reason: str = ""


class RiskAnalyzer:
    """Analyze volatility, drawdown, liquidity, volume, macro, and NGX calendar risk."""

    EARNINGS_MONTHS = {3, 6, 9, 12}

    def analyse(
        self,
        df: pd.DataFrame,
        ticker: str,
        macro_df: pd.DataFrame | None = None,
        sentiment_score: float | None = None,
    ) -> RiskProfile:
        """Return a risk profile for the latest available row of a ticker.

        Args:
            df: Engineered feature DataFrame containing one or more tickers.
            ticker: NGX ticker to analyze.
            macro_df: Optional macro/index DataFrame with `indicator`, `date`, and
                `value` columns. `nse_asi_change_pct <= -2` adds 15 risk points.
            sentiment_score: Optional NLP sentiment score in [-1, 1]. Negative
                scores add up to 12 risk points; positive scores credit up to 3.
        """

        return self.analyze(df=df, ticker=ticker, macro_df=macro_df, sentiment_score=sentiment_score)

    def analyze(
        self,
        df: pd.DataFrame,
        ticker: str,
        macro_df: pd.DataFrame | None = None,
        sentiment_score: float | None = None,
    ) -> RiskProfile:
        """Return a risk profile for the latest available row of a ticker."""

        self._validate_input(df)
        normalized_ticker = ticker.upper().strip()
        stock_df = df[df["ticker"].astype(str).str.upper() == normalized_ticker].copy()
        if stock_df.empty:
            raise ValueError(f"No engineered market data found for ticker: {normalized_ticker}")

        stock_df["date"] = pd.to_datetime(stock_df["date"], errors="coerce")
        stock_df = stock_df.dropna(subset=["date"]).sort_values("date")
        if stock_df.empty:
            raise ValueError(f"No valid dated market data found for ticker: {normalized_ticker}")

        latest = stock_df.iloc[-1]
        as_of_date = latest["date"].date()
        flags: list[RiskFlag] = []
        score = 20.0

        volatility_score, volatility_flag = self._volatility_risk(latest)
        score += volatility_score
        if volatility_score >= 8:
            flags.append(
                RiskFlag(
                    name="volatility",
                    impact=volatility_score,
                    severity=RiskLevel.HIGH if volatility_score >= 28 else RiskLevel.MEDIUM,
                    description="Realized 20-day volatility is elevated",
                )
            )

        atr_score = self._atr_risk(latest)
        score += atr_score
        if atr_score >= 10:
            flags.append(
                RiskFlag(
                    name="atr",
                    impact=atr_score,
                    severity=RiskLevel.MEDIUM,
                    description="Average true range is high relative to closing price",
                )
            )

        drawdown_score = self._drawdown_risk(latest)
        score += drawdown_score
        if drawdown_score >= 6:
            flags.append(
                RiskFlag(
                    name="drawdown",
                    impact=drawdown_score,
                    severity=RiskLevel.HIGH if drawdown_score >= 24 else RiskLevel.MEDIUM,
                    description="Price is materially below its 52-week high",
                )
            )

        liquidity_score = self._liquidity_risk(latest)
        score += liquidity_score
        if liquidity_score >= 8:
            flags.append(
                RiskFlag(
                    name="liquidity",
                    impact=liquidity_score,
                    severity=RiskLevel.MEDIUM,
                    description="Trading volume is weak versus recent history",
                )
            )

        volume_spike, volume_spike_score = self._volume_spike_risk(latest)
        score += volume_spike_score
        if volume_spike:
            flags.append(
                RiskFlag(
                    name="volume_spike",
                    impact=volume_spike_score,
                    severity=RiskLevel.MEDIUM,
                    description="Volume is unusually high, suggesting event-driven risk",
                )
            )

        asi_score = self._asi_shock_risk(macro_df, as_of_date)
        score += asi_score
        if asi_score:
            flags.append(
                RiskFlag(
                    name="ngx_asi_shock",
                    impact=asi_score,
                    severity=RiskLevel.HIGH,
                    description="NGX ASI fell more than 2%, increasing broad-market risk",
                )
            )

        calendar_score = self._calendar_risk(as_of_date)
        score += calendar_score
        if calendar_score:
            flags.append(
                RiskFlag(
                    name="earnings_season",
                    impact=calendar_score,
                    severity=RiskLevel.MEDIUM,
                    description="Earnings season can increase single-stock volatility on the NGX",
                )
            )

        trend_credit = self._trend_credit(latest)
        score -= trend_credit
        if trend_credit:
            flags.append(
                RiskFlag(
                    name="trend_credit",
                    impact=-trend_credit,
                    severity=RiskLevel.LOW,
                    description="Constructive trend reduces risk score slightly",
                )
            )

        sentiment_adjustment, sentiment_description = self._sentiment_risk(sentiment_score)
        score += sentiment_adjustment
        if sentiment_adjustment != 0:
            flags.append(
                RiskFlag(
                    name="news_sentiment",
                    impact=sentiment_adjustment,
                    severity=RiskLevel.HIGH if sentiment_adjustment >= 10 else RiskLevel.MEDIUM if sentiment_adjustment > 0 else RiskLevel.LOW,
                    description=sentiment_description,
                )
            )

        regime_alert, regime_reason, regime_score = self._volatility_regime(latest, stock_df)
        score += regime_score
        if regime_alert:
            flags.append(
                RiskFlag(
                    name="volatility_regime",
                    impact=regime_score,
                    severity=RiskLevel.HIGH,
                    description=f"Abnormal market regime: {regime_reason}",
                )
            )

        final_score = float(np.clip(score, 0, 100))
        risk_level = self._risk_level(final_score)
        if not flags:
            flags.append(
                RiskFlag(
                    name="baseline",
                    impact=0.0,
                    severity=RiskLevel.LOW,
                    description="No major volatility, liquidity, drawdown, macro, or calendar risk detected",
                )
            )

        logger.info(
            "Risk profile for %s on %s: score=%.1f level=%s volatility_flag=%s regime_alert=%s",
            normalized_ticker,
            as_of_date,
            final_score,
            risk_level.value,
            volatility_flag,
            regime_alert,
        )
        return RiskProfile(
            ticker=normalized_ticker,
            date=as_of_date,
            risk_score=round(final_score, 1),
            risk_level=risk_level,
            volatility_flag=volatility_flag,
            atr_score=round(atr_score, 1),
            drawdown_score=round(drawdown_score, 1),
            volume_spike=volume_spike,
            flags=flags,
            regime_alert=regime_alert,
            regime_reason=regime_reason,
        )

    def _validate_input(self, df: pd.DataFrame) -> None:
        """Validate required engineered market columns."""

        required = {"ticker", "date", "close"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError("RiskAnalyzer requires columns: " + ", ".join(missing))
        if df.empty:
            raise ValueError("RiskAnalyzer received an empty DataFrame")

    def _volatility_risk(self, row: pd.Series) -> tuple[float, bool]:
        """Score annualized realized volatility."""

        volatility = self._float(row.get("volatility_20"), 0.0)
        if volatility >= 0.75:
            return 35.0, True
        if volatility >= 0.50:
            return 28.0, True
        if volatility >= 0.30:
            return 18.0, False
        if volatility >= 0.18:
            return 8.0, False
        return 0.0, False

    def _atr_risk(self, row: pd.Series) -> float:
        """Score ATR as a percentage of closing price."""

        close = max(self._float(row.get("close"), 0.0), 0.0001)
        atr_pct = self._float(row.get("atr_14"), 0.0) / close
        if atr_pct >= 0.08:
            return 22.0
        if atr_pct >= 0.05:
            return 15.0
        if atr_pct >= 0.025:
            return 8.0
        return 0.0

    def _drawdown_risk(self, row: pd.Series) -> float:
        """Score drawdown from 52-week high."""

        drawdown = abs(min(self._float(row.get("drawdown_52w"), 0.0), 0.0))
        if drawdown >= 40:
            return 30.0
        if drawdown >= 25:
            return 24.0
        if drawdown >= 12:
            return 14.0
        if drawdown >= 6:
            return 6.0
        return 0.0

    def _liquidity_risk(self, row: pd.Series) -> float:
        """Score weak volume relative to recent history."""

        volume_ratio = self._float(row.get("volume_ratio_20"), 1.0)
        if volume_ratio <= 0.35:
            return 18.0
        if volume_ratio <= 0.60:
            return 10.0
        return 0.0

    def _volume_spike_risk(self, row: pd.Series) -> tuple[bool, float]:
        """Detect event-risk volume spikes."""

        volume_ratio = self._float(row.get("volume_ratio_20"), 1.0)
        volume_change = self._float(row.get("volume_change"), 0.0)
        if volume_ratio >= 3.0 or volume_change >= 2.0:
            return True, 10.0
        if volume_ratio >= 2.0 or volume_change >= 1.25:
            return True, 6.0
        return False, 0.0

    def _asi_shock_risk(self, macro_df: pd.DataFrame | None, as_of_date: date) -> float:
        """Apply NGX ASI broad-market stress adjustment."""

        if macro_df is None or macro_df.empty:
            return 0.0
        required = {"date", "indicator", "value"}
        if not required.issubset(macro_df.columns):
            logger.warning("Macro data missing required ASI risk columns: %s", sorted(required - set(macro_df.columns)))
            return 0.0

        macro = macro_df.copy()
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.date
        asi_rows = macro[
            (macro["date"] <= as_of_date)
            & (macro["indicator"].astype(str).str.lower() == "nse_asi_change_pct")
        ].sort_values("date")
        if asi_rows.empty:
            return 0.0

        latest_asi_change = self._float(asi_rows.iloc[-1]["value"], 0.0)
        if latest_asi_change <= -2.0:
            logger.warning("NGX ASI shock detected: %.2f%%", latest_asi_change)
            return 15.0
        return 0.0

    def _calendar_risk(self, as_of_date: date) -> float:
        """Apply NGX earnings-season risk adjustment."""

        if as_of_date.month in self.EARNINGS_MONTHS:
            return 5.0
        return 0.0

    def _trend_credit(self, row: pd.Series) -> float:
        """Reduce risk slightly when moving-average and momentum trends are constructive."""

        ma_gap = self._float(row.get("ma_50_gap_pct"), 0.0)
        return_20d = self._float(row.get("return_20d"), 0.0)
        if ma_gap >= 5.0 and return_20d >= 0.03:
            return 6.0
        if ma_gap >= 2.0 and return_20d >= 0:
            return 3.0
        return 0.0

    def _volatility_regime(self, latest: pd.Series, stock_df: pd.DataFrame) -> tuple[bool, str, float]:
        """Detect abnormal volatility regime from short-term technical signals.

        Returns (alert, human-readable reason, extra risk score to add).
        A regime alert means the statistical environment the model was trained on
        has changed — confidence should be reduced even before retraining.
        """
        reasons: list[str] = []
        extra_score = 0.0

        vol_5 = self._float(latest.get("vol_5"), 0.0)
        if vol_5 >= 0.05:
            reasons.append(f"5-day realized volatility is extreme ({vol_5:.2%} per day)")
            extra_score += 18.0
        elif vol_5 >= 0.035:
            reasons.append(f"5-day realized volatility is elevated ({vol_5:.2%} per day)")
            extra_score += 8.0

        if "BB_WIDTH" in stock_df.columns:
            bb_series = stock_df["BB_WIDTH"].dropna().tail(30)
            if len(bb_series) >= 10:
                avg_bb = float(bb_series.mean())
                curr_bb = self._float(latest.get("BB_WIDTH"), 0.0)
                if avg_bb > 0:
                    ratio = curr_bb / avg_bb
                    if ratio >= 2.5:
                        reasons.append(f"Bollinger Bands are {ratio:.1f}× their 30-day average — extreme expansion")
                        extra_score += 14.0
                    elif ratio >= 1.8:
                        reasons.append(f"Bollinger Bands are {ratio:.1f}× their 30-day average — rapid expansion")
                        extra_score += 7.0

        volume_ratio = self._float(latest.get("volume_ratio_20"), 1.0)
        if volume_ratio >= 5.0:
            reasons.append(f"Volume is {volume_ratio:.1f}× 20-day average — extreme event-driven trading")
            extra_score += 14.0

        close = max(self._float(latest.get("close"), 0.0), 0.0001)
        atr = self._float(latest.get("atr_14"), 0.0)
        atr_pct = atr / close
        if atr_pct >= 0.12:
            reasons.append(f"ATR is {atr_pct:.1%} of price — extreme intraday range")
            extra_score += 12.0

        alert = extra_score >= 14.0
        reason_str = "; ".join(reasons)
        return alert, reason_str, min(extra_score, 25.0)

    def _sentiment_risk(self, sentiment_score: float | None) -> tuple[float, str]:
        """Adjust risk score based on NLP news sentiment for the ticker.

        Sentiment score is in [-1, 1]. Strongly negative news raises risk because
        it signals potential adverse events not yet priced in. Positive news earns
        a small credit. When no sentiment data is available the adjustment is zero.
        """

        if sentiment_score is None:
            return 0.0, ""
        s = float(sentiment_score)
        if s <= -0.6:
            return 12.0, f"News sentiment is strongly negative ({s:.2f}), signalling elevated adverse-event risk"
        if s <= -0.3:
            return 7.0, f"News sentiment is negative ({s:.2f}), suggesting potential headwinds"
        if s <= -0.1:
            return 3.0, f"News sentiment is mildly negative ({s:.2f})"
        if s >= 0.4:
            return -3.0, f"News sentiment is positive ({s:.2f}), providing a modest risk credit"
        return 0.0, ""

    def _risk_level(self, risk_score: float) -> RiskLevel:
        """Map risk score into Low, Medium, or High."""

        if risk_score < 35:
            return RiskLevel.LOW
        if risk_score < 65:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH

    @staticmethod
    def _float(value: object, default: float) -> float:
        """Safely parse numeric values from pandas rows."""

        try:
            if pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default
