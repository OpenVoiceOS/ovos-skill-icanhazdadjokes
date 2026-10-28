"""End-to-end intent-routing tests for ovos-skill-icanhazdadjokes (en-US).

Each case feeds an utterance through a MiniCroft stack and asserts it routes
into the skill via ``joke.intent``. That one intent covers a generic / dad
joke request and a category-scoped request carrying a ``{query}``; the
handler speaks the category's dialog when the slot is bound and a default
joke when it is not.

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
import re
from pathlib import Path
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
LANG = "en-US"
LOCALE_EN_US = Path(__file__).parent.parent.parent / "locale" / "en-US"

JOKE = f"{SKILL_ID}:joke"


def _dialog_lines(name: str) -> set:
    """Read a ``.dialog`` file's own lines, independent of the handler.

    Collapses interior whitespace runs the same way
    ``ovos_spec_tools.expansion.expand`` does when the renderer speaks a
    line, so a raw file line with a double space (several of these jokes
    carry one after the punctuation) still matches the normalized text the
    skill actually speaks.
    """
    path = LOCALE_EN_US / f"{name}.dialog"
    with open(path, encoding="utf-8") as handle:
        return {
            re.sub(r"\s+", " ", line.strip())
            for line in handle if line.strip()
        }


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

class _IntentRoutingMixin:
    """Shared MiniCroft setup for intent routing."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft([SKILL_ID], lang=LANG, max_wait=300)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _route_raw(self, utterance: str):
        """Emit an utterance and return the bus message types it fired and
        the ``(dialog_key, utterance_text)`` pairs the skill spoke."""
        session = Session(f"e2e-en_us-{hash(utterance)}")
        session.lang = LANG
        session.pipeline = PIPELINE
        session.blacklisted_intents = []
        session.blacklisted_skills = []
        capture = CaptureSession(self.minicroft,
                                 eof_msgs=["ovos.utterance.handled"])
        capture.capture(Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG},
            {"session": session.serialize()},
        ), timeout=30)
        messages = capture.finish()
        spoken = [(m.data.get("meta", {}).get("dialog"), m.data.get("utterance"))
                  for m in messages
                  if m.msg_type in ("speak", "ovos.utterance.speak")
                  and m.context.get("skill_id") == SKILL_ID]
        return [m.msg_type for m in messages], spoken

    def _route(self, utterance: str, intent: str):
        """Emit an utterance and check it routed to ``intent``."""
        types, _ = self._route_raw(utterance)
        TALLY.assert_routed(utterance, intent, types)

    def _route_and_speak(self, utterance: str, intent: str):
        """Emit an utterance, check it routed to ``intent``, and return the
        ``(dialog_key, spoken_text)`` the handler actually spoke."""
        types, spoken = self._route_raw(utterance)
        TALLY.assert_routed(utterance, intent, types)
        self.assertTrue(spoken, f"{utterance!r} routed but the skill never spoke")
        return spoken[0]


class TestGenericJokeRouting(_IntentRoutingMixin, TestCase):
    """Generic joke requests land in the skill (either joke handler)."""

    def test_tell_me_a_joke(self):
        self._route("tell me a joke", JOKE)

    def test_do_you_know_any_jokes(self):
        self._route("do you know any jokes", JOKE)

    def test_can_you_tell_me_a_joke(self):
        self._route("can you tell me a joke", JOKE)


class TestDadJokeRouting(_IntentRoutingMixin, TestCase):
    """The explicit ``[dad]`` phrasing pins joke.intent."""

    def test_tell_me_a_dad_joke(self):
        self._route("tell me a dad joke", JOKE)


class TestSearchJokeRouting(_IntentRoutingMixin, TestCase):
    """Category-scoped requests carry a {query} and hit joke.intent."""

    def test_tell_me_a_chuck_norris_joke(self):
        self._route("tell me a chuck norris joke", JOKE)

    def test_joke_about_programmers(self):
        self._route("joke about programmers", JOKE)


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
        dialog_key, text = self._route_and_speak("tell me a dad joke", JOKE)
        self.assertEqual(dialog_key, "dad_jokes")
        self.assertIn(text, DAD_LINES, f"spoken line {text!r} is not in dad_jokes.dialog")

    def test_chuck_norris_search_speaks_a_chuck_norris_line(self):
        dialog_key, text = self._route_and_speak("tell me a chuck norris joke", JOKE)
        self.assertEqual(dialog_key, "chuck_norris_jokes")
        self.assertIn(
            text, CHUCK_NORRIS_LINES,
            f"spoken line {text!r} is not in chuck_norris_jokes.dialog",
        )

    def test_programmer_search_speaks_a_dev_jokes_line(self):
        dialog_key, text = self._route_and_speak("joke about programmers", JOKE)
        self.assertEqual(dialog_key, "dev_jokes")
        self.assertIn(text, DEV_LINES, f"spoken line {text!r} is not in dev_jokes.dialog")

    def test_pun_search_speaks_a_general_jokes_line(self):
        dialog_key, text = self._route_and_speak("joke about pun", JOKE)
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
        dialog_key, text = self._route_and_speak("joke about pun", JOKE)
        self.assertNotEqual(text, "puns", "spoke the unrendered dialog key instead of a joke")
        self.assertIn(text, DAD_LINES | CHUCK_NORRIS_LINES | DEV_LINES | GENERAL_LINES)

    def test_unknown_category_speaks_the_no_joke_dialog(self):
        # "xyzzy" matches none of dad/chuck_norris/programmer/pun.voc, so the
        # handler falls back to its error dialog -- the recovery path.
        dialog_key, text = self._route_and_speak("joke about xyzzy", JOKE)
        self.assertEqual(dialog_key, "no_joke")
        expected = NO_JOKE_TEMPLATE.format(query="xyzzy")
        self.assertEqual(
            text, expected,
            f"expected the rendered no_joke.dialog error line {expected!r}, got {text!r}",
        )
