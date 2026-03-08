from __future__ import annotations

from collections import Counter
from typing import Any

from .config import settings


class RecommendationService:
    async def generate(
        self,
        *,
        business: dict[str, Any],
        day_summary: dict[str, Any],
        match: dict[str, Any],
        weather: dict[str, Any],
    ) -> dict[str, Any]:
        heuristic = self._heuristic_recommendation(
            business=business,
            day_summary=day_summary,
            match=match,
            weather=weather,
        )
        if not settings.anthropic_api_key:
            return {
                "source": "heuristic",
                "text": heuristic,
                "model": None,
            }

        try:
            live_text = await self._anthropic_recommendation(
                business=business,
                day_summary=day_summary,
                match=match,
                weather=weather,
                fallback=heuristic,
            )
            return {
                "source": "anthropic",
                "text": live_text,
                "model": settings.anthropic_model,
            }
        except Exception:
            return {
                "source": "heuristic_fallback",
                "text": heuristic,
                "model": settings.anthropic_model,
            }

    async def _anthropic_recommendation(
        self,
        *,
        business: dict[str, Any],
        day_summary: dict[str, Any],
        match: dict[str, Any],
        weather: dict[str, Any],
        fallback: str,
    ) -> str:
        home_name = match["home_team"]["name"]
        away_name = match["away_team"]["name"]
        stage = match.get("stage", "")
        cultural_notes = match.get("cultural_notes", {})
        cultural_context = ""
        strongest = max(day_summary["nationality_mix"].items(), key=lambda item: item[1])[0]
        if strongest in cultural_notes:
            cultural_context = f"\nCultural context for dominant fan group: {cultural_notes[strongest]}"

        prompt = (
            "You are writing one concise recommendation card for a sports-hospitality venue owner.\n"
            "Return 3 short actionable sentences. Reference the specific teams and their fan culture.\n\n"
            f"Venue: {business['name']} ({business['type']})\n"
            f"Match: {home_name} vs {away_name} ({stage})\n"
            f"Peak footfall: {day_summary['peak_value']}\n"
            f"Peak time: {day_summary['peak_label']}\n"
            f"Nationality mix: {day_summary['nationality_mix']}\n"
            f"Weather: {weather['condition']} at {weather['temp_c']}C\n"
            f"Signature item: {business['signature_item']}\n"
            f"{cultural_context}\n"
            "Make the advice operational, specific, and culturally aware."
        )
        payload = {
            "model": settings.anthropic_model,
            "max_tokens": 220,
            "messages": [{"role": "user", "content": prompt}],
            "system": "Respond with plain English only. No bullets. Reference team names and fan cultures.",
        }
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        text_parts = [item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"]
        combined = " ".join(part.strip() for part in text_parts if part.strip())
        return combined or fallback

    def _heuristic_recommendation(
        self,
        *,
        business: dict[str, Any],
        day_summary: dict[str, Any],
        match: dict[str, Any],
        weather: dict[str, Any],
    ) -> str:
        nationality_mix = day_summary["nationality_mix"]
        strongest_segment = max(nationality_mix.items(), key=lambda item: item[1])[0]
        peak_value = day_summary["peak_value"]
        home_name = match["home_team"]["name"]
        away_name = match["away_team"]["name"]
        stage = match.get("stage", "match")

        team_name_map = {"team_a": home_name, "team_b": away_name, "neutral": "neutral fans", "locals": "locals"}
        dominant_team = team_name_map.get(strongest_segment, strongest_segment)

        cultural_notes = match.get("cultural_notes", {})
        cultural_tip = cultural_notes.get(strongest_segment, "")

        staffing_level = "double the floor staff" if peak_value > 900 else "add one extra service team"

        if business["type"] in {"hotel", "hotel_bar"}:
            operations = "Keep the lobby, valet, and late check-in desk staffed through the post-match spike."
        else:
            operations = f"{staffing_level.capitalize()} from 60 minutes before {day_summary['peak_label']} through the next hour."

        weather_note = "Plan cold-drink stations and shaded queue management." if weather["temp_c"] >= 33 else "Shift some staff to patio recovery service."

        cultural_sentence = ""
        if cultural_tip:
            cultural_sentence = f" {cultural_tip.split('.')[0]}."

        return (
            f"For {home_name} vs {away_name} ({stage}), expect the sharpest demand around {day_summary['peak_label']} "
            f"at roughly {peak_value} match-linked visitors. "
            f"{operations} "
            f"Primary fan segment is {dominant_team} at {round(nationality_mix[strongest_segment], 1)}%.{cultural_sentence} "
            f"{weather_note}"
        )


def dominant_segments(mix: dict[str, float]) -> list[str]:
    ranked = Counter(mix).most_common(2)
    return [segment for segment, _ in ranked]
