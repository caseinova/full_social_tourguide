import re
from typing import Optional


ROBOT_NAME = "pepper"
WAKE_PHRASES = (
    f"hey {ROBOT_NAME}",
    f"hi {ROBOT_NAME}",
    f"hello {ROBOT_NAME}",
    ROBOT_NAME,
)
IMPLICIT_WAKE_PREFIXES = (
    "hey",
    "hi",
    "hello",
)
ROBOT_ALIASES = {
    ROBOT_NAME,
    "peppa",
}
ALIVE_REQUESTS = {
    "are you alive",
    f"{ROBOT_NAME} are you alive",
    "are you there",
    f"{ROBOT_NAME} are you there",
    "are you awake",
    f"{ROBOT_NAME} are you awake",
    "can you hear me",
    f"{ROBOT_NAME} can you hear me",
}
SLEEP_REQUESTS = {
    "good night pepper",
    "goodnight pepper",
    "sleep pepper",
    "pepper sleep",
    "pepper go to sleep",
    "go to sleep pepper",
    "pepper good night",
}
EMERGENCY_STOP_REQUESTS = {
    "emergency stop",
    "pepper emergency stop",
    "stop stop",
    "pepper stop stop",
    "stop now",
    "pepper stop now",
}


def normalize_text(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return " ".join(normalized.split())


def canonicalize_robot_name(text: str) -> str:
    words = normalize_text(text).split()
    canonical_words = [ROBOT_NAME if word in ROBOT_ALIASES else word for word in words]
    return " ".join(canonical_words)


def strip_wake_phrase(text: str) -> Optional[str]:
    normalized = canonicalize_robot_name(text)
    for phrase in WAKE_PHRASES:
        if normalized == phrase:
            return ""
        if normalized.startswith(f"{phrase} "):
            return normalized[len(phrase) :].strip()
    for prefix in IMPLICIT_WAKE_PREFIXES:
        if normalized == prefix:
            return ""
        if normalized.startswith(f"{prefix} "):
            return normalized[len(prefix) :].strip()
    return None


def is_wake_phrase_only(text: str) -> bool:
    normalized = canonicalize_robot_name(text)
    return normalized in WAKE_PHRASES or normalized in IMPLICIT_WAKE_PREFIXES


def is_alive_request(text: str) -> bool:
    normalized = canonicalize_robot_name(text)
    return normalized in ALIVE_REQUESTS or is_wake_phrase_only(normalized)


def is_sleep_request(text: str) -> bool:
    normalized = canonicalize_robot_name(text)
    return normalized in SLEEP_REQUESTS


def is_emergency_stop_request(text: str) -> bool:
    normalized = canonicalize_robot_name(text)
    return normalized in EMERGENCY_STOP_REQUESTS
