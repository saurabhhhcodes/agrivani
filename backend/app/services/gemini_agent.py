from __future__ import annotations

import httpx
from google import genai

from backend.app.config import Settings
from backend.app.models import FarmerQuery, MandiPriceResponse


SYSTEM_PROMPT = """
You are AgriVani, a practical multilingual agricultural advisor for Indian farmers.
Keep answers short, actionable, and locally useful. Use the farmer's language.
Never invent a government scheme, pesticide dosage, or price. If a mandi price is present,
explain it as an estimate unless the source is Agmarknet.
Prioritize low-cost interventions and low-bandwidth voice delivery.
"""


class GeminiAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = (
            genai.Client(api_key=settings.gemini_api_key)
            if self._has_real_key(settings.gemini_api_key)
            else None
        )

    async def answer(self, query: FarmerQuery, price: MandiPriceResponse | None) -> str:
        if self.settings.use_mock_ai:
            return self._mock_answer(query, price)

        prompt = self._build_prompt(query, price)
        provider = self.settings.ai_provider.lower().strip()
        if provider in {"ollama", "auto"}:
            ollama_answer = await self._answer_with_ollama(prompt)
            if ollama_answer:
                return ollama_answer

        if not self.client:
            return self._mock_answer(query, price)

        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config={"system_instruction": SYSTEM_PROMPT, "temperature": 0.35},
            )
            return (response.text or "").strip() or self._mock_answer(query, price)
        except Exception:
            return self._mock_answer(query, price)

    async def _answer_with_ollama(self, prompt: str) -> str | None:
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0.25, "num_predict": 320},
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.ollama_timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            data = response.json()
            text = data.get("message", {}).get("content", "")
            return text.strip() or None
        except Exception:
            return None

    @staticmethod
    def _has_real_key(value: str) -> bool:
        return bool(value and not value.startswith("replace_with"))

    @staticmethod
    def _build_prompt(query: FarmerQuery, price: MandiPriceResponse | None) -> str:
        mandi_context = "No mandi price requested."
        if price:
            mandi_context = (
                f"Crop: {price.crop}\nMarket: {price.market}, {price.state}\n"
                f"Min: {price.min_price}, Modal: {price.modal_price}, Max: {price.max_price} {price.unit}\n"
                f"Source: {price.source}\nConfidence: {price.confidence}\n"
                f"Explanation: {price.explanation}"
            )
        return f"""
Language code: {query.language.value}
Farmer question: {query.text}
Mandi context:
{mandi_context}

Return:
1. One direct answer.
2. Three short action points.
3. One risk/caution if relevant.
"""

    @staticmethod
    def _mock_answer(query: FarmerQuery, price: MandiPriceResponse | None) -> str:
        if query.language.value == "mr":
            intro = "तुमच्या प्रश्नासाठी जलद सल्ला:"
            price_line = (
                f"{price.market} मध्ये {price.crop} चा अंदाजे भाव {price.modal_price} रुपये/क्विंटल आहे."
                if price
                else "मंडी भावासाठी पीक आणि बाजार निवडा."
            )
            return f"{intro} {price_line} स्वच्छ नमुना तपासा, स्थानिक कृषी केंद्राशी खात्री करा, आणि विक्री टप्प्याटप्प्याने करा."
        if query.language.value == "en":
            price_line = (
                f"The expected modal price for {price.crop} in {price.market} is INR {price.modal_price}/quintal."
                if price
                else "Share crop and market to get a mandi price."
            )
            return (
                f"Quick advisory: {price_line} Check local arrival volume, avoid distress selling, "
                "and split sales across two market days when prices are volatile."
            )
        price_line = (
            f"{price.market} में {price.crop} का अनुमानित मॉडल भाव {price.modal_price} रुपये/क्विंटल है."
            if price
            else "मंडी भाव के लिए फसल और बाजार बताएं."
        )
        return f"त्वरित सलाह: {price_line} स्थानीय आवक देखें, जल्दबाज़ी में बिक्री न करें, और भाव बदलने पर किस्तों में बेचें."
