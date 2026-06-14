"""Explanation layer natural-language generation.

This module converts rule-engine outputs, SHAP drivers, sentiment, and risk
signals into the exact explanation JSON shape consumed by the React frontend.
It connects upstream intelligence/explainability services to recommendation API
responses.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from app.explain.shap_explainer import ShapDriver
from app.services.risk_analyzer import RiskProfile
from app.services.rule_engine import SignalOutput
from app.utils.enums import RecommendationAction, RiskLevel

logger = logging.getLogger(__name__)


class NLGGenerator:
    """Generate concise institutional-style recommendation explanations."""

    def generate(
        self,
        signal: SignalOutput,
        shap_values: list[ShapDriver],
        sentiment_label: str = "Neutral",
        risk_profile: RiskProfile | None = None,
    ) -> dict[str, Any]:
        """Return the explanation object required by the recommendation API."""

        drivers = [self._driver_to_dict(driver) for driver in shap_values[:5]]
        headline = self._headline(signal)
        summary = self._summary(signal, drivers, sentiment_label, risk_profile)
        caution = self._caution(signal, risk_profile, sentiment_label)
        confidence_label = self._confidence_label(signal.confidence)

        explanation = {
            "headline": headline,
            "summary": summary,
            "drivers": drivers,
            "caution": caution,
            "confidence_label": confidence_label,
        }
        logger.info("Generated NLG explanation for %s: %s", signal.ticker, headline)
        return explanation

    def _headline(self, signal: SignalOutput) -> str:
        """Create the recommendation headline."""

        strength = "Strong " if signal.signal_strength.value == "STRONG" else ""
        return f"{strength}{signal.recommendation.value} signal for {signal.ticker}"

    def _summary(
        self,
        signal: SignalOutput,
        drivers: list[dict[str, Any]],
        sentiment_label: str,
        risk_profile: RiskProfile | None,
    ) -> str:
        """Create a compact explanation summary."""

        dominant_driver = drivers[0]["factor"] if drivers else "model drivers"
        recommendation = signal.recommendation
        risk_text = (
            f"{risk_profile.risk_level.value.title()} risk at {risk_profile.risk_score:.1f}/100"
            if risk_profile
            else f"risk score at {signal.risk_score:.1f}/100"
        )

        if recommendation == RecommendationAction.BUY:
            stance = "Momentum and probability signals are constructive"
        elif recommendation == RecommendationAction.WATCHLIST:
            stance = "The setup is improving but still needs confirmation"
        elif recommendation == RecommendationAction.SELL:
            stance = "Downside signals are currently stronger than upside support"
        elif recommendation == RecommendationAction.AVOID:
            stance = "Risk-adjusted conditions are unfavorable"
        else:
            stance = "Signals are mixed, so capital preservation is preferred"

        return (
            f"{stance}. The main driver is {dominant_driver}, sentiment is {sentiment_label.lower()}, "
            f"and {risk_text}. Ensemble probability is {signal.ensemble_prob:.3f}."
        )

    def _caution(
        self,
        signal: SignalOutput,
        risk_profile: RiskProfile | None,
        sentiment_label: str,
    ) -> str | None:
        """Generate caution text when risk or sentiment warrants it."""

        cautions: list[str] = []
        if risk_profile and risk_profile.risk_level == RiskLevel.HIGH:
            risk_names = ", ".join(flag.name.replace("_", " ") for flag in risk_profile.flags[:3])
            cautions.append(f"High risk conditions detected: {risk_names}.")
        elif signal.risk_score >= 65:
            cautions.append("Risk score is elevated, so position sizing should be conservative.")

        if sentiment_label.lower() == "negative":
            cautions.append("Negative sentiment may pressure near-term price action.")
        if signal.recommendation in {RecommendationAction.AVOID, RecommendationAction.SELL}:
            cautions.append("Wait for risk, sentiment, or momentum to improve before considering fresh exposure.")

        if not cautions:
            return None
        return " ".join(cautions)

    def _confidence_label(self, confidence: float) -> str:
        """Map numeric confidence into the frontend confidence label."""

        if confidence >= 70:
            return "High confidence"
        if confidence >= 55:
            return "Medium confidence"
        return "Low confidence"

    def _driver_to_dict(self, driver: ShapDriver) -> dict[str, Any]:
        """Convert a SHAP driver dataclass into API JSON."""

        data = asdict(driver)
        data["shap"] = round(float(data["shap"]), 6)
        return data
