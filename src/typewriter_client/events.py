import json
from dataclasses import dataclass
from urllib.request import Request, urlopen


DEFAULT_EVENTS_URL = "http://127.0.0.1:8000/events"


@dataclass(frozen=True)
class Event:
    id: str
    text: str


def validate_text(text: object) -> str:
    if not isinstance(text, str) or not text.strip() or "\0" in text:
        raise ValueError("text must be a non-blank string without NUL characters")
    text.encode("utf-8")
    return text


def fetch_latest(url: str) -> Event | None:
    request = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise ValueError(f"expected HTTP 200, got {response.status}")
        payload = json.load(response)

    if not isinstance(payload, dict) or not isinstance(events := payload.get("events"), list):
        raise ValueError("expected an object containing an events array")
    if not events:
        return None

    latest = events[-1]
    if not isinstance(latest, dict):
        raise ValueError("expected an event object")
    event_id = latest.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("expected an event with a non-empty string id")
    return Event(id=event_id, text=validate_text(latest.get("text")))
