"""End-to-end intent-routing tests for ovos-skill-icanhazdadjokes (en-US).

Each case feeds an utterance through a MiniCroft stack and asserts it routes
into the skill via one of its two ``.intent`` handlers:

* ``joke.intent``       -> a generic / dad joke request
* ``search_joke.intent`` -> a category-scoped request carrying a ``{query}``

The two grammars overlap on purpose (``tell me a joke`` and ``tell me a chuck
norris joke`` share the ``(tell|say) me a ... joke`` skeleton), so the padatious
scorer legitimately assigns a bare ``tell me a joke`` to either handler
depending on slot greediness. Both outcomes still land inside the skill and
produce a joke, so the assertions accept either intent for the ambiguous
phrasings and pin the unambiguous ones.

Run: pytest test/end2end/ -v
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
LANG = "en-US"

JOKE = "joke.intent"
SEARCH = "search_joke.intent"

# The .intent grammars are optional-heavy; padatious handles the optional
# ``[dad]`` token and open ``{query}`` slot that padacioso cannot.
PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
]


class _IntentRoutingMixin:
    """Shared MiniCroft setup for padatious intent routing."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _route(self, utterance: str, allowed):
        """Emit an utterance and return the skill intent it routed to."""
        matched = []
        handlers = {}
        for intent_file in (JOKE, SEARCH):
            msg_type = f"{SKILL_ID}:{intent_file}"
            handler = lambda msg, name=intent_file: matched.append(name)
            handlers[msg_type] = handler
            self.minicroft.bus.on(msg_type, handler)
        try:
            session = Session(f"e2e-en_us-{hash(utterance)}")
            session.lang = LANG
            session.pipeline = PIPELINE
            # padatious iterates these directly; they default to None on a
            # freshly built Session, so seed empty lists to keep matching happy
            session.blacklisted_intents = []
            session.blacklisted_skills = []
            self.minicroft.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            ))
            deadline = time.monotonic() + 15
            while not matched and time.monotonic() < deadline:
                time.sleep(0.2)
        finally:
            for msg_type, handler in handlers.items():
                self.minicroft.bus.remove(msg_type, handler)
        self.assertTrue(
            matched,
            f"{utterance!r} did not route to the skill",
        )
        self.assertIn(
            matched[0], allowed,
            f"{utterance!r} routed to {matched[0]}, expected one of {allowed}",
        )
        return matched[0]


class TestGenericJokeRouting(_IntentRoutingMixin, TestCase):
    """Generic joke requests land in the skill (either joke handler)."""

    def test_tell_me_a_joke(self):
        self._route("tell me a joke", {JOKE, SEARCH})

    def test_do_you_know_any_jokes(self):
        self._route("do you know any jokes", {JOKE, SEARCH})

    def test_can_you_tell_me_a_joke(self):
        self._route("can you tell me a joke", {JOKE, SEARCH})


class TestDadJokeRouting(_IntentRoutingMixin, TestCase):
    """The explicit ``[dad]`` phrasing pins joke.intent."""

    def test_tell_me_a_dad_joke(self):
        self._route("tell me a dad joke", {JOKE})


class TestSearchJokeRouting(_IntentRoutingMixin, TestCase):
    """Category-scoped requests carry a {query} and hit search_joke.intent."""

    def test_tell_me_a_chuck_norris_joke(self):
        self._route("tell me a chuck norris joke", {SEARCH})

    def test_joke_about_programmers(self):
        self._route("joke about programmers", {SEARCH})
