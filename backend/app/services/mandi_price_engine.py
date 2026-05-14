from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from backend.app.models import MandiPriceResponse


AGMARKNET_URL = "https://agmarknet.gov.in/SearchCmmMkt.aspx"


@dataclass(frozen=True)
class PriceObservation:
    date: str
    crop: str
    market: str
    state: str
    min_price: float
    modal_price: float
    max_price: float


class MandiPriceEngine:
    """Fetch mandi prices with Agmarknet-first, historical-CSV fallback logic."""

    def __init__(self, historical_csv_path: Path):
        self.historical_csv_path = historical_csv_path

    async def get_price(self, crop: str, market: str, state: str) -> MandiPriceResponse:
        normalized_crop = crop.strip().lower()
        normalized_market = market.strip().lower()
        normalized_state = state.strip().lower()

        try:
            live = await self._scrape_agmarknet(normalized_crop, normalized_market, normalized_state)
            if live:
                return MandiPriceResponse(
                    crop=crop,
                    market=market,
                    state=state,
                    min_price=live.min_price,
                    modal_price=live.modal_price,
                    max_price=live.max_price,
                    source="agmarknet.gov.in",
                    confidence=0.92,
                    explanation="Live mandi data was found on Agmarknet and returned directly.",
                    observations=[live.__dict__],
                )
        except Exception:
            pass

        prediction, observations = self._predict_from_csv(normalized_crop, normalized_market, normalized_state)
        return MandiPriceResponse(
            crop=crop,
            market=market,
            state=state,
            min_price=prediction["min_price"],
            modal_price=prediction["modal_price"],
            max_price=prediction["max_price"],
            source="historical_csv_ai_prediction",
            confidence=prediction["confidence"],
            explanation=(
                "Agmarknet was unavailable or did not return a usable row. "
                "The price is an AI-assisted prediction from recent historical CSV trends."
            ),
            observations=observations,
        )

    async def _scrape_agmarknet(
        self, crop: str, market: str, state: str
    ) -> PriceObservation | None:
        params = {
            "Tx_Commodity": crop.title(),
            "Tx_State": state.title(),
            "Tx_Market": market.title(),
            "DateFrom": datetime.utcnow().strftime("%d-%b-%Y"),
            "DateTo": datetime.utcnow().strftime("%d-%b-%Y"),
            "Fr_Date": datetime.utcnow().strftime("%d-%b-%Y"),
            "To_Date": datetime.utcnow().strftime("%d-%b-%Y"),
            "Tx_Trend": "0",
            "Tx_CommodityHead": crop.title(),
            "Tx_StateHead": state.title(),
            "Tx_MarketHead": market.title(),
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(AGMARKNET_URL, params=params)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tr")
        for row in rows:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
            if len(cells) < 6:
                continue
            row_text = " ".join(cells).lower()
            if crop not in row_text or market not in row_text:
                continue
            prices = [self._to_float(value) for value in cells]
            prices = [value for value in prices if value is not None and value > 0]
            if len(prices) >= 3:
                min_price, modal_price, max_price = sorted(prices[-3:])
                return PriceObservation(
                    date=datetime.utcnow().date().isoformat(),
                    crop=crop.title(),
                    market=market.title(),
                    state=state.title(),
                    min_price=min_price,
                    modal_price=modal_price,
                    max_price=max_price,
                )
        return None

    def _predict_from_csv(
        self, crop: str, market: str, state: str
    ) -> tuple[dict[str, float], list[dict[str, Any]]]:
        df = pd.read_csv(self.historical_csv_path, parse_dates=["date"])
        df["crop_norm"] = df["crop"].str.lower().str.strip()
        df["market_norm"] = df["market"].str.lower().str.strip()
        df["state_norm"] = df["state"].str.lower().str.strip()

        exact = df[
            (df["crop_norm"] == crop)
            & (df["market_norm"] == market)
            & (df["state_norm"] == state)
        ].copy()
        crop_state = df[(df["crop_norm"] == crop) & (df["state_norm"] == state)].copy()
        crop_only = df[df["crop_norm"] == crop].copy()

        if len(exact) >= 3:
            sample = exact
            confidence = 0.79
        elif len(crop_state) >= 3:
            sample = crop_state
            confidence = 0.66
        elif len(crop_only) >= 3:
            sample = crop_only
            confidence = 0.54
        else:
            sample = df.copy()
            confidence = 0.42

        sample = sample.sort_values("date").tail(8)
        weighted = self._weighted_prediction(sample)
        observations = sample[
            ["date", "crop", "market", "state", "min_price", "modal_price", "max_price"]
        ].copy()
        observations["date"] = observations["date"].dt.date.astype(str)
        return (
            {
                "min_price": round(weighted["min_price"], 2),
                "modal_price": round(weighted["modal_price"], 2),
                "max_price": round(weighted["max_price"], 2),
                "confidence": confidence,
            },
            observations.to_dict(orient="records"),
        )

    @staticmethod
    def _weighted_prediction(sample: pd.DataFrame) -> dict[str, float]:
        weights = pd.Series(range(1, len(sample) + 1), index=sample.index, dtype=float)
        trend_boost = 1.0
        if len(sample) >= 4:
            first_half = sample["modal_price"].head(len(sample) // 2).mean()
            second_half = sample["modal_price"].tail(len(sample) // 2).mean()
            if first_half:
                trend_boost += max(-0.07, min(0.07, (second_half - first_half) / first_half))

        result: dict[str, float] = {}
        for column in ["min_price", "modal_price", "max_price"]:
            result[column] = float((sample[column] * weights).sum() / weights.sum()) * trend_boost
        result["min_price"] = min(result["min_price"], result["modal_price"])
        result["max_price"] = max(result["max_price"], result["modal_price"])
        return result

    @staticmethod
    def _to_float(value: str) -> float | None:
        cleaned = value.replace(",", "").replace("Rs.", "").replace("₹", "").strip()
        try:
            number = float(cleaned)
            if math.isfinite(number):
                return number
        except ValueError:
            return None
        return None
