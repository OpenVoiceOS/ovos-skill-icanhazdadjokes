"""End-to-end intent-routing tests for ovos-skill-icanhazdadjokes (en-US).

Each case feeds an utterance through a MiniCroft stack and asserts it routes
to the expected ``.intent`` handler. Coverage spans the generic joke request
(``tell me a joke``), the ``[dad]`` optional-slot phrasing, and the
category-search variant that carries a ``{query}`` slot.

Run: pytest test/end2end/ -v
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
LANG = "en-US"

# Exact expansions score conf 1.0 (the -high band); the {query} slot variant
# lands lower, so register all three padacioso bands.
PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]


class _IntentRoutingMixin:
    """Shared MiniCroft setup for padacioso intent routing."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _assert_intent(self, utterance: str, intent_file: str):
        intent_msg_type = f"{SKILL_ID}:{intent_file}"
        matched = []
        handler = lambda msg: matched.append(msg)
        self.minicroft.bus.on(intent_msg_type, handler)
        try:
            session = Session(f"e2e-en_us-{intent_file}-{hash(utterance)}")
            session.lang = LANG
            session.pipeline = PIPELINE
            self.minicroft.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            ))
            deadline = time.monotonic() + 15
            while not matched and time.monotonic() < deadline:
                time.sleep(0.2)
        finally:
            self.minicroft.bus.remove(intent_msg_type, handler)
        self.assertTrue(
            matched,
            f"{utterance!r} did not route to {intent_file}",
        )


class TestJokeRouting(_IntentRoutingMixin, TestCase):
    """joke.intent"""

    def test_tell_me_a_joke(self):
        self._assert_intent("tell me a joke", "joke.intent")

    def test_tell_me_a_dad_joke(self):
        self._assert_intent("tell me a dad joke", "joke.intent")

    def test_can_you_tell_me_a_joke(self):
        self._assert_intent("can you tell me a joke", "joke.intent")

    def test_do_you_know_any_jokes(self):
        self._assert_intent("do you know any jokes", "joke.intent")


class TestSearchJokeRouting(_IntentRoutingMixin, TestCase):
    """search_joke.intent"""

    def test_tell_me_a_chuck_norris_joke(self):
        self._assert_intent("tell me a chuck norris joke", "search_joke.intent")

    def test_joke_about_programmers(self):
        self._assert_intent("joke about programmers", "search_joke.intent")
