from __future__ import annotations

import re

from app.shared.schemas import ClaimObject


class ClaimParser:
    def parse(self, text: str) -> ClaimObject:
        entities = re.findall(r"\b[A-Z][a-z]{2,}\b", text)
        places = re.findall(r"\b(?:in|at|near)\s+([A-Z][a-zA-Z]+)\b", text)
        dates = re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|today|yesterday)\b", text, flags=re.IGNORECASE)
        events = re.findall(r"\b(protest|earthquake|flood|fire|attack|election|festival|war)\b", text, flags=re.IGNORECASE)
        actions = re.findall(r"\b(arrested|announced|claimed|confirmed|happened|occurred|shows)\b", text, flags=re.IGNORECASE)
        return ClaimObject(
            original_text=text,
            entities=list(dict.fromkeys(entities))[:15],
            places=list(dict.fromkeys(places))[:10],
            dates=list(dict.fromkeys(dates))[:10],
            events=list(dict.fromkeys(events))[:10],
            actions=list(dict.fromkeys(actions))[:15],
        )
