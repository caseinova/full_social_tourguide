from turtlebot_llm_control.models import IntentToken
from turtlebot_llm_control.wake_word import (
    is_alive_request,
    is_emergency_stop_request,
    normalize_text,
)


NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
LOCATION_ALIASES = {
    "pillow": "pillar",
    "below": "pillar",
    "pillar": "pillar",
}
COMMAND_PREFIXES = (
    "pepper ",
    "hey pepper ",
    "ok pepper ",
    "robot ",
    "hey robot ",
    "please ",
    "can you ",
    "could you ",
    "will you ",
    "i want you to ",
    "i need you to ",
)


def is_direct_command(text: str, *phrases: str) -> bool:
    if text in phrases:
        return True
    if any(text.startswith(phrase + " ") for phrase in phrases):
        return True
    for prefix in COMMAND_PREFIXES:
        remainder = text[len(prefix) :] if text.startswith(prefix) else ""
        if not remainder:
            continue
        if remainder in phrases:
            return True
        if any(remainder.startswith(phrase + " ") for phrase in phrases):
            return True
    return False


def parse_utterance(text: str) -> IntentToken:
    raw = text.strip()
    cleaned = normalize_text(raw)

    if not cleaned:
        return IntentToken(intent="unknown", utterance=raw, response="I did not catch that.")

    if is_alive_request(cleaned):
        return IntentToken(
            intent="is_alive",
            utterance=raw,
            response="Yes, I am here, awake, and ready to help.",
        )

    if is_emergency_stop_request(cleaned):
        return IntentToken(
            intent="stop",
            utterance=raw,
            response="Emergency stop. Stopping everything now.",
        )

    if (
        "manual override" in cleaned
        or "manual control" in cleaned
        or "enable teleop" in cleaned
        or "take over" in cleaned
    ):
        return IntentToken(
            intent="manual_override_on",
            utterance=raw,
            response="Manual override enabled. You can teleoperate now.",
        )

    if is_direct_command(cleaned, "stop navigation", "cancel navigation", "stop going", "cancel the navigation"):
        return IntentToken(
            intent="stop_navigation",
            utterance=raw,
            response="Stopping navigation now.",
        )

    if is_direct_command(
        cleaned, "dock", "go to dock", "go dock", "go home", "go charge", "charge",
        "return to base", "go back home", "go plug in", "need to charge", "recharge",
        "go to charging station", "charging station",
    ):
        return IntentToken(
            intent="dock",
            utterance=raw,
            response="Heading to the dock now.",
        )

    if (
        "resume autonomous" in cleaned
        or "disable manual override" in cleaned
        or "return to autonomous" in cleaned
    ):
        return IntentToken(
            intent="manual_override_off",
            utterance=raw,
            response="Manual override cleared. Autonomous behavior can resume.",
        )

    if is_direct_command(cleaned, "stop", "halt", "freeze", "stop stop", "stop now",
                          "abort", "wait", "hold on", "stop that", "never mind",
                          "that's enough", "cancel", "enough"):
        return IntentToken(intent="stop", utterance=raw, response="Stopping the current activity.")

    if is_direct_command(cleaned, "pause"):
        return IntentToken(intent="pause", utterance=raw, response="Pausing for you now.")

    if is_direct_command(cleaned, "resume"):
        return IntentToken(intent="resume", utterance=raw, response="Resuming the previous task.")

    if is_direct_command(cleaned, "start tour", "begin tour", "full tour", "do the tour",
                          "do the whole tour", "show me everything", "tour please",
                          "take me on the tour", "let's start the tour", "start the full tour"):
        return IntentToken(intent="start_tour", utterance=raw, response="Starting the tour.")

    if any(
        phrase in cleaned
        for phrase in (
            "small tour",
            "give a tour",
            "give me a tour",
            "custom tour",
            "short tour",
            "mini tour",
            "pick waypoints",
            "select waypoints",
            "choose waypoints",
            "show me around",
            "take me on a little tour",
            "let me choose",
            "select some spots",
            "pick some places",
            "few stops",
            "my own tour",
            "i want to choose",
            "choose the stops",
            "select the stops",
            "pick the stops",
            "pick some stops",
            "choose some stops",
        )
    ):
        return IntentToken(
            intent="tsp",
            utterance=raw,
            response="Opening waypoint selector. Pick your stops and hit Start.",
        )

    if is_direct_command(cleaned, "record route", "start recording", "start recording now"):
        label = extract_label(cleaned, fallback="new_route")
        return IntentToken(
            intent="start_recording",
            label=label,
            utterance=raw,
            response="Recording route {}.".format(label),
        )

    if is_direct_command(cleaned, "stop recording"):
        return IntentToken(intent="stop_recording", utterance=raw, response="Route recording stopped.")

    if is_direct_command(cleaned, "save route", "save tour", "save the tour"):
        label = extract_label(cleaned, fallback="saved_route")
        return IntentToken(
            intent="save_route",
            label=label,
            utterance=raw,
            response="Saving route as {}.".format(label),
        )

    if is_direct_command(cleaned, "replay", "run route"):
        label = extract_label(cleaned, fallback="saved_route")
        return IntentToken(
            intent="replay_route",
            label=label,
            utterance=raw,
            response="Replaying route {}.".format(label),
        )

    if is_direct_command(cleaned, "go to", "navigate to", "take me to", "lead me to",
                          "bring me to", "show me", "i want to see", "i want to go to",
                          "head to", "i'd like to visit", "let's go to", "let's visit"):
        location = extract_location(cleaned)
        normalized_full_text = normalize_location_name(cleaned)
        if location == "unknown_location" and "pillar" in normalized_full_text:
            return IntentToken(
                intent="no_action",
                utterance=raw,
                response="I need a pillar number. Please say a pillar from 1 to 9.",
            )
        return IntentToken(
            intent="navigate",
            location=location,
            utterance=raw,
            response="Navigating to {}.".format(location),
        )

    if any(phrase in cleaned for phrase in (
        "explain", "tell me about", "what is", "what's here", "describe",
        "tell me more about", "what can i see", "what can i see here",
        "what's in", "what is in", "info about", "information about",
    )):
        location = extract_location(cleaned)
        return IntentToken(
            intent="explain",
            location=location,
            utterance=raw,
            response="Preparing an explanation for {}.".format(location),
        )

    return IntentToken(
        intent="unknown",
        utterance=raw,
        response="I understood speech, but I need a clearer command.",
    )


def extract_label(text: str, fallback: str) -> str:
    markers = ["as ", "route ", "called ", "named "]
    for marker in markers:
        if marker in text:
            candidate = text.split(marker, 1)[1].strip().replace(" ", "_")
            if candidate:
                return candidate
    return fallback


def extract_location(text: str) -> str:
    markers = [
        "go to ", "navigate to ", "take me to ", "lead me to ", "bring me to ",
        "show me ", "i want to see ", "i want to go to ", "head to ",
        "i'd like to visit ", "let's go to ", "let's visit ",
        "tell me about ", "tell me more about ", "explain ",
        "what is ", "describe ", "info about ", "information about ",
    ]
    for marker in markers:
        if marker in text:
            candidate = normalize_location_name(text.split(marker, 1)[1].strip())
            if candidate:
                return candidate
    return "unknown_location"


def normalize_location_name(text: str) -> str:
    words = text.split()
    normalized_words = [
        NUMBER_WORDS.get(LOCATION_ALIASES.get(word, word), LOCATION_ALIASES.get(word, word))
        for word in words
    ]
    if normalized_words in (["pillar"], ["pillar", "number"]):
        return ""
    if len(normalized_words) >= 2 and normalized_words[0] == "pillar" and normalized_words[1].isdigit():
        return "pillar_{}".format(normalized_words[1])
    joined = "_".join(normalized_words)
    if joined.startswith("pillar") and joined[6:].isdigit():
        return "pillar_{}".format(joined[6:])
    return joined
