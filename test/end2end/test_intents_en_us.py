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

``TestJokeEffects`` below goes one step further than routing: it asserts the
handler actually SPEAKS a line drawn from the ``.dialog`` file that its own
category maps to. The expected line sets are read straight off the shipped
``.dialog`` files on disk, never restated from the handler source, and the
suite asserts those sets are pairwise disjoint before trusting membership --
otherwise a handler speaking the wrong category's dialog could still pass by
accident. This skill never calls a network service; every joke line is
shipped locally in ``locale/en-US/*.dialog``, so no stub is needed to keep
the suite offline.

Run: pytest test/end2end/ -v
"""
import time
from pathlib import Path
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
LANG = "en-US"
LOCALE_EN_US = Path(__file__).parent.parent.parent / "locale" / "en-US"

JOKE = "joke.intent"
SEARCH = "search_joke.intent"


def _dialog_lines(name: str) -> set:
    """Read a ``.dialog`` file's own lines, independent of the handler."""
    path = LOCALE_EN_US / f"{name}.dialog"
    with open(path, encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


# Read once, directly from the shipped dialog files -- never restated from
# the skill handler -- so these sets are independent of the code under test.
DAD_LINES = _dialog_lines("dad_jokes")
CHUCK_NORRIS_LINES = _dialog_lines("chuck_norris_jokes")
DEV_LINES = _dialog_lines("dev_jokes")
GENERAL_LINES = _dialog_lines("general_jokes")
NO_JOKE_TEMPLATE = (LOCALE_EN_US / "no_joke.dialog").read_text(encoding="utf-8").strip()

_CATEGORY_LINES = {
    "dad_jokes": DAD_LINES,
    "chuck_norris_jokes": CHUCK_NORRIS_LINES,
    "dev_jokes": DEV_LINES,
    "general_jokes": GENERAL_LINES,
}

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
        # the padatious models for this skill's .intent files take a while
        # to train on CI runners, so allow a generous READY window
        cls.minicroft = get_minicroft([SKILL_ID], max_wait=300)
        # Real padatious trains its neural model in a background thread
        # *after* the skill/service report "ready" -- an utterance fired
        # immediately after boot can race that training and see zero
        # matches even though the same utterance matches correctly moments
        # later. Warm the model up here (outside any per-test deadline) so
        # that lag never leaks into an individual test's assertion.
        deadline = time.monotonic() + 60
        warmed = False
        while time.monotonic() < deadline and not warmed:
            warmed = bool(cls._route_raw(cls.minicroft, "tell me a joke"))
            if not warmed:
                time.sleep(1)
        assert warmed, "padatious model never finished warming up within 60s"

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    @staticmethod
    def _route_raw(minicroft, utterance: str, capture_speech: bool = False):
        """Emit an utterance and return the raw list of intent basenames
        (``.intent`` suffix stripped) the skill's handlers were dispatched
        to. Shared by the warm-up probe, ``_route`` and ``_route_and_speak``
        below. When ``capture_speech`` is set, also returns the list of
        spoken ``(dialog_key, utterance_text)`` pairs the skill emitted."""
        matched = []
        spoken = []
        handlers = {}
        for intent_file in (JOKE, SEARCH):
            base = intent_file[:-len(".intent")]
            handler = lambda msg, name=intent_file: matched.append(name)
            # The dispatched handler message drops the ".intent" filename
            # suffix on current OVOS-INTENT-2 naming; register both forms so
            # this isn't pinned to whichever ovos-workshop version is
            # installed (see ovos-skill-volume's end2end suite).
            for msg_type in (f"{SKILL_ID}:{intent_file}", f"{SKILL_ID}:{base}"):
                handlers[msg_type] = handler
                minicroft.bus.on(msg_type, handler)
        if capture_speech:
            def _on_speak(msg):
                if msg.context.get("skill_id") == SKILL_ID:
                    spoken.append((
                        msg.data.get("meta", {}).get("dialog"),
                        msg.data.get("utterance"),
                    ))
            for msg_type in ("speak", "ovos.utterance.speak"):
                handlers[msg_type] = _on_speak
                minicroft.bus.on(msg_type, _on_speak)
        try:
            session = Session(f"e2e-en_us-{hash(utterance)}")
            session.lang = LANG
            session.pipeline = PIPELINE
            # padatious iterates these directly; they default to None on a
            # freshly built Session, so seed empty lists to keep matching happy
            session.blacklisted_intents = []
            session.blacklisted_skills = []
            minicroft.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            ))
            deadline = time.monotonic() + 15
            while not matched and time.monotonic() < deadline:
                time.sleep(0.2)
            if capture_speech:
                # give the handler body (which runs after intent binding)
                # a little more room to actually call speak_dialog
                speak_deadline = time.monotonic() + 5
                while not spoken and time.monotonic() < speak_deadline:
                    time.sleep(0.2)
        finally:
            for msg_type, handler in handlers.items():
                minicroft.bus.remove(msg_type, handler)
        if capture_speech:
            return matched, spoken
        return matched

    def _route(self, utterance: str, allowed):
        """Emit an utterance and return the skill intent it routed to."""
        matched = self._route_raw(self.minicroft, utterance)
        self.assertTrue(
            matched,
            f"{utterance!r} did not route to the skill",
        )
        self.assertIn(
            matched[0], allowed,
            f"{utterance!r} routed to {matched[0]}, expected one of {allowed}",
        )
        return matched[0]

    def _route_and_speak(self, utterance: str, allowed):
        """Emit an utterance, assert it routes into ``allowed``, and return
        the ``(dialog_key, spoken_text)`` the handler actually spoke."""
        matched, spoken = self._route_raw(self.minicroft, utterance, capture_speech=True)
        self.assertTrue(matched, f"{utterance!r} did not route to the skill")
        self.assertIn(
            matched[0], allowed,
            f"{utterance!r} routed to {matched[0]}, expected one of {allowed}",
        )
        self.assertTrue(spoken, f"{utterance!r} routed but the skill never spoke")
        return spoken[0]


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


class TestDialogSetsAreDisjoint(TestCase):
    """The per-category expected-line sets must not overlap.

    If two dialog files shared a line, a handler speaking the WRONG
    category's dialog would still pass a membership check below, silently
    turning the effect assertions back into routing-only assertions. This
    is checked once, up front, so a membership pass below can be trusted.
    """

    def test_dialog_line_sets_do_not_overlap(self):
        names = list(_CATEGORY_LINES.keys())
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                overlap = _CATEGORY_LINES[left] & _CATEGORY_LINES[right]
                self.assertFalse(
                    overlap,
                    f"{left}.dialog and {right}.dialog share line(s) {overlap!r}; "
                    "a wrong-dialog bug would pass undetected",
                )


class TestJokeEffects(_IntentRoutingMixin, TestCase):
    """The handler must speak a line from the correct category's own
    ``.dialog`` file, not merely emit some ``speak`` message.

    Each expected set below is read straight from the shipped locale file
    (see ``_dialog_lines`` at module scope), never restated from the
    handler, so a handler that speaks the wrong dialog -- or the right
    dialog for the wrong category -- fails here even though intent routing
    and the presence of a ``speak`` message both still succeed.
    """

    def test_dad_joke_speaks_a_dad_jokes_line(self):
        dialog_key, text = self._route_and_speak("tell me a dad joke", {JOKE})
        self.assertEqual(dialog_key, "dad_jokes")
        self.assertIn(text, DAD_LINES, f"spoken line {text!r} is not in dad_jokes.dialog")

    def test_chuck_norris_search_speaks_a_chuck_norris_line(self):
        dialog_key, text = self._route_and_speak("tell me a chuck norris joke", {SEARCH})
        self.assertEqual(dialog_key, "chuck_norris_jokes")
        self.assertIn(
            text, CHUCK_NORRIS_LINES,
            f"spoken line {text!r} is not in chuck_norris_jokes.dialog",
        )

    def test_programmer_search_speaks_a_dev_jokes_line(self):
        dialog_key, text = self._route_and_speak("joke about programmers", {SEARCH})
        self.assertEqual(dialog_key, "dev_jokes")
        self.assertIn(text, DEV_LINES, f"spoken line {text!r} is not in dev_jokes.dialog")

    def test_pun_search_speaks_a_general_jokes_line(self):
        dialog_key, text = self._route_and_speak("joke about pun", {SEARCH})
        self.assertEqual(dialog_key, "general_jokes")
        self.assertIn(text, GENERAL_LINES, f"spoken line {text!r} is not in general_jokes.dialog")

    def test_pun_search_never_speaks_the_bare_dialog_key(self):
        # en-US ships no puns.dialog. An unrendered dialog template renders
        # as its own key (see MustacheDialogRenderer.render's fallback), so
        # a handler that unconditionally speaks "puns" here would make the
        # skill say the literal word "puns" instead of a joke -- this is
        # the defect the puns/general_jokes fallback in _speak_puns exists
        # to prevent. Assert the spoken line is a real dialog line, not that
        # bare key, from a category the skill actually ships a file for.
        dialog_key, text = self._route_and_speak("joke about pun", {SEARCH})
        self.assertNotEqual(text, "puns", "spoke the unrendered dialog key instead of a joke")
        self.assertIn(text, DAD_LINES | CHUCK_NORRIS_LINES | DEV_LINES | GENERAL_LINES)

    def test_unknown_category_speaks_the_no_joke_dialog(self):
        # "xyzzy" matches none of dad/chuck_norris/programmer/pun.voc, so the
        # handler falls back to its error dialog -- the recovery path.
        dialog_key, text = self._route_and_speak("joke about xyzzy", {SEARCH})
        self.assertEqual(dialog_key, "no_joke")
        expected = NO_JOKE_TEMPLATE.format(query="xyzzy")
        self.assertEqual(
            text, expected,
            f"expected the rendered no_joke.dialog error line {expected!r}, got {text!r}",
        )
