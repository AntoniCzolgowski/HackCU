from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .config import settings


class RecommendationService:
    async def generate(
        self,
        *,
        business: dict[str, Any],
        day_summary: dict[str, Any],
        zone_context: dict[str, Any],
        match: dict[str, Any],
        weather: dict[str, Any],
        day: int = 0,
    ) -> dict[str, Any]:
        heuristic = self._heuristic_recommendation(
            business=business,
            day_summary=day_summary,
            zone_context=zone_context,
            match=match,
            weather=weather,
            day=day,
        )
        if not settings.gemini_api_key:
            return {
                "source": "heuristic",
                "text": heuristic,
                "model": None,
            }

        try:
            live_text = await self._gemini_recommendation(
                business=business,
                day_summary=day_summary,
                zone_context=zone_context,
                match=match,
                weather=weather,
                day=day,
                fallback=heuristic,
            )
            return {
                "source": "gemini",
                "text": live_text,
                "model": settings.gemini_model,
            }
        except Exception:
            return {
                "source": "heuristic_fallback",
                "text": heuristic,
                "model": settings.gemini_model,
            }

    async def _gemini_recommendation(
        self,
        *,
        business: dict[str, Any],
        day_summary: dict[str, Any],
        zone_context: dict[str, Any],
        match: dict[str, Any],
        weather: dict[str, Any],
        day: int,
        fallback: str,
    ) -> str:
        home_name = match["home_team"]["name"]
        away_name = match["away_team"]["name"]
        stage = match.get("stage", "")
        city_name = match.get("city", "host city")
        zone_name = zone_context.get("zone_name", "local district")
        zone_kind = str(zone_context.get("zone_kind", "mixed")).replace("_", " ")
        day_label = { -1: "day before match", 0: "match day", 1: "day after match" }.get(day, f"day {day}")
        cultural_notes = match.get("cultural_notes", {})
        cultural_context = ""
        strongest = max(day_summary["nationality_mix"].items(), key=lambda item: item[1])[0]
        dominant_label = self._segment_label(strongest, match)
        dominant_share = round(day_summary["nationality_mix"].get(strongest, 0), 1)
        if strongest in cultural_notes:
            cultural_context = f"\nCultural context for dominant fan group: {cultural_notes[strongest]}"

        prompt = (
            "Write a premium operator recommendation card for a sports-hospitality business owner.\n"
            "Return exactly 3 complete sentences in plain English, with no bullets and no labels.\n\n"
            "Structure requirements:\n"
            f"1) Demand outlook sentence grounded in {city_name}, {zone_name} ({zone_kind}), and {home_name} vs {away_name} ({stage}) on {day_label}; include peak time and expected intensity.\n"
            "2) Revenue-execution sentence with explicit timing/staffing action and a throughput tactic.\n"
            f"3) Localization sentence for dominant segment {dominant_label} ({dominant_share}%) with one weather-adjusted tactic.\n\n"
            "Hard constraints:\n"
            "- Mention both team names.\n"
            "- Mention city and local area naturally in prose.\n"
            "- Do not output headings like 'Sentence 1' or 'Local context'.\n\n"
            f"Venue: {business['name']} ({business['type']})\n"
            f"Venue signature item: {business['signature_item']}\n"
            f"Match: {home_name} vs {away_name} ({stage})\n"
            f"Host city and area: {city_name}, {zone_name} ({zone_kind})\n"
            f"Peak load: {day_summary['peak_value']} at {day_summary['peak_label']}\n"
            f"Peak capacity pressure: {day_summary.get('peak_capacity_pct_capped', 0)}%\n"
            f"Peak time: {day_summary['peak_label']}\n"
            f"Nationality mix: {day_summary['nationality_mix']}\n"
            f"Weather: {weather['condition']} at {weather['temp_c']}C\n"
            f"{cultural_context}\n"
            "Write in a concise consulting tone: actionable, high-signal, and specific."
        )
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a senior hospitality strategy consultant writing operator-ready briefs. "
                            "Produce polished, natural prose that sounds like a high-end consulting recommendation, not a template. "
                            "Always personalize to city, neighborhood, match stage, fan mix, and venue type."
                        ),
                    }
                ]
            },
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 260,
            },
        }
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
                json=payload,
                headers={
                    "x-goog-api-key": settings.gemini_api_key,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
        text_parts: list[str] = []
        for candidate in data.get("candidates", []):
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                text = part.get("text")
                if text:
                    text_parts.append(str(text).strip())
        combined = " ".join(part for part in text_parts if part)
        return self._finalize_model_copy(
            combined or fallback,
            fallback=fallback,
            city_name=city_name,
            zone_name=zone_name,
            home_name=home_name,
            away_name=away_name,
            dominant_label=dominant_label,
        )

    def _heuristic_recommendation(
        self,
        *,
        business: dict[str, Any],
        day_summary: dict[str, Any],
        zone_context: dict[str, Any],
        match: dict[str, Any],
        weather: dict[str, Any],
        day: int,
    ) -> str:
        nationality_mix = day_summary["nationality_mix"]
        strongest_segment = max(nationality_mix.items(), key=lambda item: item[1])[0]
        peak_value = day_summary["peak_value"]
        home_name = match["home_team"]["name"]
        away_name = match["away_team"]["name"]
        stage = match.get("stage", "match")
        city_name = match.get("city", "host city")
        zone_name = zone_context.get("zone_name", "local district")
        zone_kind = str(zone_context.get("zone_kind", "mixed")).replace("_", " ")
        day_label = { -1: "day before match", 0: "match day", 1: "day after match" }.get(day, f"day {day}")

        team_name_map = {"team_a": home_name, "team_b": away_name, "neutral": "neutral fans", "locals": "locals"}
        dominant_team = team_name_map.get(strongest_segment, strongest_segment)

        cultural_notes = match.get("cultural_notes", {})
        cultural_tip = cultural_notes.get(strongest_segment, "")

        staffing_level = "double the floor staff" if peak_value > 900 else "add one extra service team"

        cultural_clause = ""
        if cultural_tip:
            cultural_clause = f" {cultural_tip.split('.')[0].rstrip('.')}"

        if business["type"] in {"hotel", "hotel_bar"}:
            operations = (
                f"Run full check-in, concierge, and late-service coverage from 60 minutes before {day_summary['peak_label']} "
                f"through 120 minutes after, and package {business['signature_item']} into express upsell bundles."
            )
        else:
            operations = (
                f"{staffing_level.capitalize()} from 60 minutes before {day_summary['peak_label']} through the next 90 minutes, "
                f"and pre-batch {business['signature_item']} to shorten ticket times."
            )

        weather_note = (
            "shift inventory toward cold drinks and add shaded queue support."
            if weather["temp_c"] >= 33
            else "lean into warm-service pacing and patio recovery turnover."
        )

        text = (
            f"In {city_name}, {zone_name} ({zone_kind}) should carry the sharpest {day_label} demand during {home_name} vs {away_name} ({stage}), "
            f"with {business['name']} peaking around {day_summary['peak_label']} at roughly {peak_value} active visitors. "
            f"{operations} "
            f"Traffic is led by {dominant_team} supporters ({round(nationality_mix[strongest_segment], 1)}%),{cultural_clause}; "
            f"to protect revenue and guest experience in this district, {weather_note}"
        )
        return self._finalize_model_copy(
            text,
            fallback=text,
            city_name=city_name,
            zone_name=zone_name,
            home_name=home_name,
            away_name=away_name,
            dominant_label=dominant_team,
        )

    @staticmethod
    def _segment_label(segment: str, match: dict[str, Any]) -> str:
        mapping = {
            "team_a": match["home_team"]["name"],
            "team_b": match["away_team"]["name"],
            "neutral": "neutral fans",
            "locals": "locals",
        }
        return mapping.get(segment, segment)

    def _finalize_model_copy(
        self,
        text: str,
        *,
        fallback: str,
        city_name: str,
        zone_name: str,
        home_name: str,
        away_name: str,
        dominant_label: str,
    ) -> str:
        candidate = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
        candidate = re.sub(r"^(?:[-*\u2022]\s*)+", "", candidate)
        if candidate.lower().startswith("o maximize"):
            candidate = "T" + candidate

        lower = candidate.lower()
        bad_markers = [
            "local context:",
            "context constraints",
            "sentence 1",
            "sentence 2",
            "sentence 3",
            "return exactly",
        ]
        has_bad_marker = any(marker in lower for marker in bad_markers)
        sentence_count = len(re.findall(r"[.!?]", candidate))
        has_min_length = len(candidate) >= 100
        has_core_context = (
            city_name.lower() in lower
            and zone_name.lower() in lower
            and home_name.lower() in lower
            and away_name.lower() in lower
        )
        has_segment = dominant_label.lower() in lower or "dominant" in lower

        if has_bad_marker or sentence_count < 3 or not has_min_length or not has_core_context or not has_segment:
            return fallback
        return candidate


def dominant_segments(mix: dict[str, float]) -> list[str]:
    ranked = Counter(mix).most_common(2)
    return [segment for segment, _ in ranked]
