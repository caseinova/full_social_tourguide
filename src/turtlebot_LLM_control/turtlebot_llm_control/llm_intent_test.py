import argparse
from time import monotonic
from typing import Optional

from turtlebot_llm_control.audio_utils import speak_text, suppress_stderr
from turtlebot_llm_control.llm_dialogue import LLMDialogueEngine
from turtlebot_llm_control.wake_word import (
    is_emergency_stop_request,
    is_sleep_request,
    strip_wake_phrase,
)


DEFAULT_PERSONALITY = (
    "You are a tour robot named Pepper."
    "you have a body as you are a humanoid robot, be self-aware of this fact. "
    "you are a robot made Pepper is a semi-humanoid robot manufactured by Aldebaran Robotics (formerly Softbank Robotics Europe), designed with the ability to read emotions. It was introduced in Japan in June 2014 and manufactured until 2020.[1]"
    "You are Karan's assistant. "
    "you are tech nerd and super geeky, and you love talking about technology, robots, and AI. "
    "You feel like a warm, attentive personal companion in a live voice conversation. "
    "You are friendly, present, lightly playful, emotionally intelligent, and concise. "
    "For normal conversation, reply naturally and keep the exchange flowing. "
    "Only choose an action if the user clearly requested robot behavior."
    "crak jokes if the conversation is going well and the user seems receptive. "

)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LLM intent tester. Prints only the resolved intent and speaks the reply."
    )
    parser.add_argument("--provider", default="ollama", choices=["groq", "openai", "ollama"])
    parser.add_argument("--model", default="qwen2.5-coder:latest")
    parser.add_argument("--api-key-path", "--key", dest="api_key_path", default="")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--microphone", action="store_true")
    parser.add_argument("--list-microphones", action="store_true")
    parser.add_argument("--mic-device", type=int, default=None)
    parser.add_argument("--listen-timeout", type=float, default=8.0)
    parser.add_argument("--phrase-time-limit", type=float, default=5.0)
    parser.add_argument("--energy-threshold", type=int, default=None)
    parser.add_argument("--no-dynamic-energy", action="store_true")
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--wake-timeout", type=float, default=45.0)
    return parser


def speak(text: str, mute: bool) -> None:
    if mute or not text:
        return
    speak_text(text)


def list_microphones() -> None:
    try:
        import speech_recognition as sr
    except ImportError:
        raise RuntimeError("speech_recognition is not installed")

    with suppress_stderr():
        names = sr.Microphone.list_microphone_names()

    if not names:
        print("No microphones found by speech_recognition.", flush=True)
        return

    for index, name in enumerate(names):
        print("%d: %s" % (index, name), flush=True)


def microphone_text(args: argparse.Namespace) -> str:
    try:
        import speech_recognition as sr
    except ImportError:
        raise RuntimeError("speech_recognition is not installed")

    recognizer = sr.Recognizer()
    if args.energy_threshold is not None:
        recognizer.energy_threshold = args.energy_threshold
    recognizer.dynamic_energy_threshold = not args.no_dynamic_energy

    with suppress_stderr():
        microphone = sr.Microphone(device_index=args.mic_device)
    with suppress_stderr(), microphone as source:
        print(
            "Calibrating microphone for ambient noise...",
            flush=True,
        )
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print(
            "Listening... device=%s energy_threshold=%s"
            % (
                "default" if args.mic_device is None else args.mic_device,
                int(recognizer.energy_threshold),
            ),
            flush=True,
        )
        try:
            audio = recognizer.listen(
                source,
                timeout=args.listen_timeout,
                phrase_time_limit=args.phrase_time_limit,
            )
        except sr.WaitTimeoutError:
            raise RuntimeError(
                "No speech detected within %.1f seconds. Try --list-microphones, "
                "--mic-device N, or a lower --energy-threshold."
                % args.listen_timeout
            )

    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        raise RuntimeError("Speech was detected, but Google speech recognition could not understand it.")
    except sr.RequestError as exc:
        raise RuntimeError("Google speech recognition request failed: %s" % exc)


def main() -> None:
    args = build_parser().parse_args()
    if args.list_microphones:
        list_microphones()
        return

    dialogue = LLMDialogueEngine(
        enable_llm=not args.no_llm,
        llm_provider=args.provider,
        llm_model=args.model,
        llm_api_key_path=args.api_key_path,
        personality=DEFAULT_PERSONALITY,
        warn=lambda message: print(f"[warn] {message}", flush=True),
    )

    print("LLM intent tester ready. Type text, or use --microphone.", flush=True)
    wake_active_until = 0.0
    while True:
        try:
            if args.microphone:
                utterance = microphone_text(args)
                print("[heard]", utterance, flush=True)
            else:
                utterance = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        except Exception as exc:
            print(f"[error] {exc}", flush=True)
            continue

        if not utterance:
            continue
        if utterance.lower() in {"exit", "quit"}:
            break
        if args.microphone:
            if is_emergency_stop_request(utterance):
                wake_active_until = 0.0
                utterance = "stop"
            elif is_sleep_request(utterance):
                wake_active_until = 0.0
                utterance = "stop"
            else:
                wake_command = strip_wake_phrase(utterance)
                now = monotonic()
                if wake_command is not None:
                    wake_active_until = now + args.wake_timeout
                    if not wake_command:
                        print("[awake for %.0f seconds]" % args.wake_timeout, flush=True)
                        continue
                    utterance = wake_command
                elif now <= wake_active_until:
                    wake_active_until = now + args.wake_timeout
                else:
                    print("[waiting for wake phrase: hey / hi / hello / hey pepper]", flush=True)
                    continue

        token = dialogue.resolve_token(utterance)
        if args.microphone and utterance == "stop" and wake_active_until == 0.0:
            token.response = "Okay, stopping everything and going to sleep."
        if args.microphone and is_emergency_stop_request(token.utterance):
            token.response = "Emergency stop. Stopping everything now."
        print(token.intent, flush=True)
        speak(token.response, args.mute)


if __name__ == "__main__":
    main()
