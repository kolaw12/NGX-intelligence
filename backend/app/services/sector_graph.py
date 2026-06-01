"""Intelligence layer sector graph for NGX relationship signals.

This module builds a NetworkX graph from the master ticker universe and sector
relationships. It connects upstream ticker metadata and peer signals to the rule
engine by producing a sector momentum boost or drag for a selected stock.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TICKERS_PATH = PROJECT_ROOT / "data" / "master" / "tickers.csv"


@dataclass(frozen=True)
class SectorSignal:
    """Sector and peer momentum context for one ticker."""

    ticker: str
    canonical_ticker: str
    sector: str | None
    adjustment: float
    peer_average: float | None
    sector_average: float | None
    connected_tickers: list[str] = field(default_factory=list)
    explanation: str = "No sector signal available"


class SectorGraph:
    """Build and query NGX sector relationships for recommendation adjustments."""

    MAX_ADJUSTMENT = 0.10

    # Explicit relationships capture broad NGX factor links beyond same-sector peers.
    THEMATIC_RELATIONSHIPS = {
        "banking_macro": ["ZEN", "GTB", "ACC", "UBA", "FBN"],
        "telecom": ["MTN", "AAF"],
        "cement_construction": ["DANGCEM", "LAFARGE", "BUACEMENT"],
        "oil_fx": ["SEPLAT", "OANDO", "TOTAL"],
        "consumer_defensive": ["NES", "GUI", "NBL", "DANGSUGAR"],
        "insurance": ["AIICO", "NEM", "MANSARD"],
    }

    TICKER_ALIASES = {
        "ZENITHBANK": "ZEN",
        "GTCO": "GTB",
        "ACCESSCORP": "ACC",
        "FBNH": "FBN",
        "MTNN": "MTN",
        "AIRTELAFRI": "AAF",
        "NESTLE": "NES",
        "GUINNESS": "GUI",
        "NB": "NBL",
    }

    def __init__(self, tickers_path: str | Path | None = None) -> None:
        """Create a sector graph from the NGX master ticker file."""

        self.tickers_path = Path(tickers_path or DEFAULT_TICKERS_PATH)
        self.tickers = self._load_tickers(self.tickers_path)
        self.graph = self._build_graph(self.tickers)
        logger.info(
            "SectorGraph built with %s nodes and %s edges",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )

    def get_sector_signal(self, ticker: str, all_signals: dict[str, float] | pd.DataFrame) -> SectorSignal:
        """Return sector momentum boost or drag for a ticker.

        Args:
            ticker: Target NGX ticker.
            all_signals: Mapping or DataFrame containing ticker-level probabilities,
                returns, or scores. DataFrames must include `ticker` and one of
                `ensemble_prob`, `probability`, `signal`, `return_20d`, or
                `daily_return`.
        """

        requested_ticker = ticker.upper().strip()
        normalized_ticker = self._canonical_ticker(requested_ticker)
        signal_map = self._normalize_signals(all_signals)
        if normalized_ticker not in self.graph:
            logger.warning("Ticker %s is not present in the sector graph", normalized_ticker)
            return SectorSignal(
                ticker=requested_ticker,
                canonical_ticker=normalized_ticker,
                sector=None,
                adjustment=0.0,
                peer_average=None,
                sector_average=None,
                explanation="Ticker is not present in the sector graph",
            )

        neighbors = sorted(
            node
            for node in self.graph.neighbors(normalized_ticker)
            if self.graph.nodes[node].get("node_type") == "ticker"
        )
        peer_values = [signal_map[node] for node in neighbors if node in signal_map]
        peer_average = float(np.mean(peer_values)) if peer_values else None

        sector = self.graph.nodes[normalized_ticker].get("sector")
        sector_tickers = [
            node
            for node, attrs in self.graph.nodes(data=True)
            if attrs.get("node_type") == "ticker" and attrs.get("sector") == sector and node != normalized_ticker
        ]
        sector_values = [signal_map[node] for node in sector_tickers if node in signal_map]
        sector_average = float(np.mean(sector_values)) if sector_values else None

        reference_value = peer_average if peer_average is not None else sector_average
        if reference_value is None:
            return SectorSignal(
                ticker=requested_ticker,
                canonical_ticker=normalized_ticker,
                sector=sector,
                adjustment=0.0,
                peer_average=None,
                sector_average=None,
                connected_tickers=neighbors,
                explanation="No peer signals were available for sector adjustment",
            )

        adjustment = self._score_to_adjustment(reference_value)
        explanation = self._explain_adjustment(adjustment, sector, reference_value)
        logger.info(
            "Sector signal for %s: sector=%s adjustment=%+.3f peer_average=%s",
            normalized_ticker,
            sector,
            adjustment,
            f"{peer_average:.3f}" if peer_average is not None else "n/a",
        )
        return SectorSignal(
            ticker=requested_ticker,
            canonical_ticker=normalized_ticker,
            sector=sector,
            adjustment=adjustment,
            peer_average=peer_average,
            sector_average=sector_average,
            connected_tickers=neighbors,
            explanation=explanation,
        )

    def get_peers(self, ticker: str, limit: int = 10) -> list[str]:
        """Return connected peer tickers for a selected ticker."""

        normalized_ticker = self._canonical_ticker(ticker.upper().strip())
        if normalized_ticker not in self.graph:
            return []
        peers = [
            node
            for node in self.graph.neighbors(normalized_ticker)
            if self.graph.nodes[node].get("node_type") == "ticker"
        ]
        return sorted(peers)[:limit]

    def _load_tickers(self, path: Path) -> pd.DataFrame:
        """Load ticker metadata from the master data layer."""

        if not path.exists():
            raise FileNotFoundError(f"Ticker master file not found: {path}")
        df = pd.read_csv(path)
        required = {"ticker", "sector"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError("Ticker master file missing required columns: " + ", ".join(sorted(missing)))
        df = df.copy()
        df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
        df["sector"] = df["sector"].astype(str).str.strip()
        df = df.dropna(subset=["ticker", "sector"]).drop_duplicates(subset=["ticker"])
        logger.info("Loaded %s tickers from %s", len(df), path)
        return df

    def _build_graph(self, tickers: pd.DataFrame) -> nx.Graph:
        """Build ticker-sector and thematic relationships."""

        graph = nx.Graph()
        for row in tickers.itertuples(index=False):
            ticker = str(row.ticker)
            sector = str(row.sector)
            sector_node = f"sector::{sector}"
            graph.add_node(ticker, node_type="ticker", sector=sector)
            graph.add_node(sector_node, node_type="sector", sector=sector)
            graph.add_edge(ticker, sector_node, relationship="member", weight=0.60)

        for sector, group in tickers.groupby("sector"):
            sector_tickers = sorted(group["ticker"].tolist())
            self._connect_peer_group(graph, sector_tickers, relationship=f"same_sector::{sector}", weight=0.35)

        for theme, theme_tickers in self.THEMATIC_RELATIONSHIPS.items():
            available = [ticker for ticker in theme_tickers if ticker in graph]
            self._connect_peer_group(graph, available, relationship=f"theme::{theme}", weight=0.75)

        return graph

    def _connect_peer_group(self, graph: nx.Graph, tickers: list[str], relationship: str, weight: float) -> None:
        """Connect a peer group without creating self-edges."""

        for index, source in enumerate(tickers):
            for target in tickers[index + 1 :]:
                graph.add_edge(source, target, relationship=relationship, weight=weight)

    def _normalize_signals(self, all_signals: dict[str, float] | pd.DataFrame) -> dict[str, float]:
        """Normalize mappings or DataFrames into ticker-to-score values."""

        if isinstance(all_signals, dict):
            return {self._canonical_ticker(str(key).upper().strip()): float(value) for key, value in all_signals.items()}

        if not isinstance(all_signals, pd.DataFrame):
            raise TypeError("all_signals must be a dict[str, float] or a pandas DataFrame")
        if "ticker" not in all_signals.columns:
            raise ValueError("Signal DataFrame must include a ticker column")

        value_column = self._select_signal_column(all_signals)
        frame = all_signals[["ticker", value_column]].dropna().copy()
        frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip().map(self._canonical_ticker)
        return dict(zip(frame["ticker"], frame[value_column].astype(float), strict=False))

    def _canonical_ticker(self, ticker: str) -> str:
        """Map market-facing symbols to the data-layer ticker code when needed."""

        return self.TICKER_ALIASES.get(ticker, ticker)

    def _select_signal_column(self, signals: pd.DataFrame) -> str:
        """Select the best available signal column from a DataFrame."""

        for column in ("ensemble_prob", "probability", "signal", "return_20d", "daily_return"):
            if column in signals.columns:
                return column
        raise ValueError(
            "Signal DataFrame must include one of: ensemble_prob, probability, signal, return_20d, daily_return"
        )

    def _score_to_adjustment(self, score: float) -> float:
        """Convert peer score into a bounded rule-engine probability adjustment."""

        if 0.0 <= score <= 1.0:
            centered = score - 0.50
        else:
            centered = score
        return float(np.clip(centered * 0.30, -self.MAX_ADJUSTMENT, self.MAX_ADJUSTMENT))

    def _explain_adjustment(self, adjustment: float, sector: str | None, reference_value: float) -> str:
        """Generate a concise explanation for the sector adjustment."""

        sector_label = sector or "Unknown sector"
        if adjustment > 0.02:
            return f"{sector_label} peers are supportive, adding a sector momentum boost."
        if adjustment < -0.02:
            return f"{sector_label} peers are weak, applying a sector momentum drag."
        return f"{sector_label} peer signal is neutral; no material sector adjustment."
