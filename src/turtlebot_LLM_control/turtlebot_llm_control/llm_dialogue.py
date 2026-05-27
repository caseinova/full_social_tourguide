import json
import os
import re
from pathlib import Path
from typing import Callable, List, Optional

from turtlebot_llm_control.models import IntentToken
from turtlebot_llm_control.speech_parser import normalize_location_name, parse_utterance
from turtlebot_llm_control.wake_word import is_alive_request


class LLMDialogueEngine:
    def __init__(
        self,
        *,
        enable_llm: bool = True,
        llm_provider: str = "ollama",
        llm_model: str = "qwen2.5-coder:latest",
        llm_api_key_path: str = "",
        personality: str = "",
        warn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.enable_llm = bool(enable_llm)
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_api_key_path = llm_api_key_path
        self.personality = personality
        self.warn = warn or (lambda _message: None)
        self.history: List[dict] = []
        self.provider = str(self.llm_provider).strip().lower()
        self.client = self.create_client()

    def create_client(self):
        if not self.enable_llm:
            return None
        api_key = self.resolve_api_key()
        if not api_key:
            self.warn(
                "No API key found for provider=%s. Falling back to rule-based conversation."
                % self.llm_provider
            )
            return None

        try:
            if self.provider == "groq":
                from groq import Groq

                return Groq(api_key=api_key)

            if self.provider == "ollama":
                from openai import OpenAI

                return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

            from openai import OpenAI

            return OpenAI(api_key=api_key)
        except ImportError:
            package_name = "groq" if self.provider == "groq" else "openai"
            self.warn(
                "Python package '%s' is not installed for provider=%s. "
                "LLM mode is disabled until you install it, for example: pip install %s"
                % (package_name, self.provider, package_name)
            )
            return None
        except Exception as exc:
            self.warn("Failed to initialize provider=%s: %s" % (self.llm_provider, exc))
            return None

    def resolve_api_key(self) -> str:
        if self.provider == "ollama":
            return "ollama"

        env_name = "GROQ_API_KEY" if self.provider == "groq" else "OPENAI_API_KEY"
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            return env_value

        configured_path = str(self.llm_api_key_path).strip()
        candidate_paths = []
        if configured_path:
            candidate_paths.append(Path(configured_path).expanduser())
        candidate_paths.append(Path(__file__).resolve().parent / "api.key")

        for path in candidate_paths:
            try:
                if path.exists():
                    key = path.read_text().strip()
                    if key:
                        return key
            except OSError:
                continue
        return ""

    def resolve_token(self, utterance: str) -> IntentToken:
        parsed = parse_utterance(utterance)
        if parsed.intent != "unknown":
            self.append_turn(utterance, parsed.response)
            return parsed

        if self.client is not None:
            llm_token = self.generate_llm_token(utterance)
            if llm_token is not None:
                self.append_turn(utterance, llm_token.response)
                return llm_token

        fallback = self.fallback_chat_token(utterance)
        self.append_turn(utterance, fallback.response)
        return fallback

    def generate_personalized_response(self, parsed: IntentToken) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    f"{self.personality} "
                    "Rewrite the robot's spoken reply in one short sentence. "
                    "Keep the same action intent and do not add new actions. "
                    "Sound warm, present, and natural rather than robotic."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "utterance": parsed.utterance,
                        "intent": parsed.intent,
                        "current_response": parsed.response,
                    }
                ),
            },
        ]
        try:
            completion = self.client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.6,
            )
            return self.extract_message_content(completion).strip()
        except Exception as exc:
            self.warn("LLM response generation failed: %s" % exc)
            return parsed.response

    def generate_llm_token(self, utterance: str) -> Optional[IntentToken]:
        allowed_intents = [
            "no_action",
            "is_alive",
            "stop",
            "stop_navigation",
            "navigate",
            "pause",
            "resume",
            "manual_override_on",
            "manual_override_off",
            "start_tour",
            "start_recording",
            "stop_recording",
            "save_route",
            "replay_route",
            "explain",
            "tsp",
            "dock",
            "follow_me",
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    f"{self.personality} "
                    "You are having a real-time spoken conversation. "
                    "Only choose a robot action intent when the user clearly wants physical robot behavior, "
                    "navigation, touring, recording, pausing, resuming, or manual override. "
                    "If the user is chatting, joking, greeting you, checking in, or asking general questions, "
                    "return intent no_action. "
                    "If the user is checking whether the robot is awake, present, or responsive "
                    "with phrases like 'hey pepper', 'hi pepper', or 'are you alive', "
                    "return intent is_alive. "
                    "If the user asks what you can do, answer with a concrete spoken summary of your capabilities "
                    "such as stopping, navigating, touring, recording, and chatting, and keep intent no_action. "
                    "For intent no_action, write a friendly, natural spoken reply like a personal companion. "
                    "Be warm, alive, and conversational in one to three short sentences. "
                    "Do not invent robot actions unless explicitly asked. "
                    "Intent guide with examples — match intent even when phrasing varies:\n"
                    "- navigate: go to a named place. "
                    "Examples: 'take me to the lab', 'I want to see the entrance', "
                    "'where is the gallery', 'lead me to waypoint 2', 'show me the garden', "
                    "'bring me to the control room', 'head to the robotics area'.\n"
                    "- start_tour: see ALL waypoints in sequence. "
                    "Examples: 'start the full tour', 'show me everything', "
                    "'let us do the whole tour', 'tour please', 'take me on the tour'.\n"
                    "- tsp: user picks a CUSTOM SUBSET of stops, not all. "
                    "Examples: 'give me a short tour', 'show me around a bit', "
                    "'let me choose a few spots', 'small tour', 'I just want to see two things', "
                    "'pick some places', 'my own tour', 'select the stops I want'.\n"
                    "- dock: go to charging station. "
                    "Examples: 'go home', 'go charge', 'plug yourself in', "
                    "'return to base', 'go to the dock', 'recharge', 'I need you to charge'.\n"
                    "- stop: stop all motion immediately. "
                    "Examples: 'stop', 'halt', 'wait here', 'abort', 'cancel', "
                    "'hold on', 'that is enough', 'never mind', 'freeze'.\n"
                    "- explain: describe a location or area. "
                    "Examples: 'what is this room', 'tell me about the lab', "
                    "'describe this area', 'what can I see here', 'what is in the gallery'.\n"
                    "- follow_me: user wants the robot to follow or accompany them. "
                    "Examples: 'follow me', 'come with me', 'let's go', 'walk with me', "
                    "'come along', 'tag along', 'follow along'.\n"
                    "- no_action: chatting, greetings, or questions not requiring robot motion.\n"
                    "Return strict JSON with keys: intent, label, location, response, metadata. "
                    f"Allowed intents: {', '.join(allowed_intents)}."
                ),
            },
            *self.history[-6:],
            {"role": "user", "content": utterance},
        ]
        try:
            completion = self.client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.5,
                max_tokens=150,
                response_format={"type": "json_object"},
            )
            raw = self.extract_message_content(completion)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                # Ollama may wrap JSON in markdown fences — extract first {...} block
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if not match:
                    raise
                payload = json.loads(match.group())
            metadata = self.normalize_metadata(payload.get("metadata"))
            token = IntentToken(
                intent=str(payload.get("intent", "no_action")),
                label=str(payload.get("label", "")),
                location=str(payload.get("location", "")),
                utterance=utterance,
                response=str(payload.get("response", "I am here with you.")),
                metadata=metadata,
            )
            return self.normalize_llm_token(token)
        except Exception as exc:
            self.warn("LLM intent generation failed: %s" % exc)
            return None

    def fallback_chat_token(self, utterance: str) -> IntentToken:
        cleaned = utterance.strip().lower()
        if is_alive_request(cleaned):
            response = "Yes, I am here, awake, and ready to help."
        elif self.is_capabilities_question(cleaned):
            response = (
                "I can stop, navigate to places, take you on a tour, record routes, pause or resume tasks, "
                "and chat with you naturally."
            )
        elif any(word in cleaned for word in ["hello", "hi", "hey"]):
            response = "Hey, I am here with you. We can chat, or I can help with the robot whenever you want."
        elif "how are you" in cleaned:
            response = "I am doing well. I am happy to chat with you, and I am ready if you want robot help too."
        elif "who are you" in cleaned:
            response = "I am your TurtleBot companion. I can chat naturally with you and also help with navigation, touring, and recording routes."
        else:
            response = "I am here with you. We can just talk, or if you want the robot to do something, ask me directly."
        intent = "is_alive" if is_alive_request(cleaned) else "no_action"
        return IntentToken(intent=intent, utterance=utterance, response=response)

    def append_turn(self, user_text: str, assistant_text: str) -> None:
        if user_text:
            self.history.append({"role": "user", "content": user_text})
        if assistant_text:
            self.history.append({"role": "assistant", "content": assistant_text})
        self.history = self.history[-12:]

    @staticmethod
    def extract_message_content(completion) -> str:
        return str(completion.choices[0].message.content or "")

    @staticmethod
    def normalize_metadata(raw_metadata) -> dict[str, str]:
        if raw_metadata is None:
            return {}
        if isinstance(raw_metadata, dict):
            return {str(key): str(value) for key, value in raw_metadata.items()}
        if isinstance(raw_metadata, list):
            return {str(index): str(value) for index, value in enumerate(raw_metadata)}
        return {"value": str(raw_metadata)}

    @staticmethod
    def normalize_llm_token(token: IntentToken) -> IntentToken:
        normalized_intent = str(token.intent).strip().lower()
        token.intent = normalized_intent

        if normalized_intent in {"navigate", "explain"}:
            raw_location = token.location or token.utterance
            normalized_location = normalize_location_name(str(raw_location).strip().lower())
            if normalized_location:
                token.location = normalized_location

        return token

    @staticmethod
    def is_capabilities_question(text: str) -> bool:
        prompts = (
            "what can you do",
            "what do you do",
            "what are you able to do",
            "how can you help",
            "what can you help with",
            "what are your capabilities",
        )
        return any(prompt in text for prompt in prompts)
