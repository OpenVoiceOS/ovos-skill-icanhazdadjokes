"""End-to-end coverage for the locale-local joke categories (fr-FR).

fr-FR is the only locale that ships ``beauf_jokes.dialog``,
``blondes_jokes.dialog``, ``dark_jokes.dialog`` and ``edgy_jokes.dialog``.
Before the change these files were unreachable by voice: nothing named the
categories and no handler branch spoke them, so "blague sur les blondes"
answered from ``no_joke.dialog``.

Each test asserts the *effect*, not only the route: the spoken line must be
one of the lines that this category's own dialog file ships. The line sets
are read from disk at test time, never restated here and never read back
from a captured bus message, so they stay independent of the code under
test. ``test_category_line_sets_are_disjoint`` is the control that makes
that membership meaningful: if two collections shared a line, a handler
speaking the wrong file could still pass.

The suite runs on the padacioso pipeline, as ``test_intents_en_us.py``
does, so it needs no trained padatious model.
"""
from pathlib import Path
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft, CaptureSession, PADACIOSO_PIPELINE

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
LANG = "fr-FR"
LOCALE_FR_FR = Path(__file__).parent.parent.parent / "locale" / "fr-FR"

CATEGORIES = ("beauf", "blondes", "dark", "edgy")

# One utterance per category, written the way the shipped
# ``search_joke.intent`` phrases a category request in French.
UTTERANCES = {
    "beauf": "raconte-moi une blague sur les beaufs",
    "blondes": "raconte-moi une blague sur les blondes",
    "dark": "raconte-moi une blague sur l'humour noir",
    "edgy": "raconte-moi une blague sur l'humour trash",
}


def _dialog_lines(name: str) -> set:
    with open(LOCALE_FR_FR / f"{name}.dialog", encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


CATEGORY_LINES = {name: _dialog_lines(f"{name}_jokes") for name in CATEGORIES}


class _FrenchJokeMixin:
    """Shared fr-FR MiniCroft wiring."""

    @classmethod
    def setUpClass(cls):
        # MiniCroft boots en-US unless a language is passed, and an en-US
        # boot loads no fr-FR resource at all, so every assertion below
        # would measure the wrong locale.
        cls.minicroft = get_minicroft([SKILL_ID], lang=LANG)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _spoken(self, utterance: str) -> list:
        session = Session(f"e2e-fr_fr-jokes-{abs(hash(utterance))}")
        session.lang = LANG
        session.pipeline = PADACIOSO_PIPELINE
        session.blacklisted_intents = []
        session.blacklisted_skills = []
        message = Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        capture = CaptureSession(self.minicroft)
        capture.capture(message, timeout=30)
        return [
            m.data.get("utterance", "")
            for m in capture.finish()
            if m.msg_type in ("speak", "ovos.utterance.speak")
        ]


class TestCategoryCorpus(TestCase):
    """Properties of the shipped files, independent of any boot."""

    def test_every_category_ships_a_dialog_and_a_voc(self):
        for name in CATEGORIES:
            self.assertTrue(
                (LOCALE_FR_FR / f"{name}_jokes.dialog").is_file(),
                f"fr-FR must ship {name}_jokes.dialog",
            )
            self.assertTrue(
                (LOCALE_FR_FR / f"{name}.voc").is_file(),
                f"fr-FR must ship {name}.voc to name the {name} category",
            )

    def test_category_line_sets_are_disjoint(self):
        """The control for every membership assertion below. Two categories
        that shared a line would let a handler speaking the wrong file
        pass."""
        for one in CATEGORIES:
            for other in CATEGORIES:
                if one >= other:
                    continue
                overlap = CATEGORY_LINES[one] & CATEGORY_LINES[other]
                self.assertEqual(
                    set(), overlap,
                    f"{one}_jokes.dialog and {other}_jokes.dialog share "
                    f"{len(overlap)} line(s): {sorted(overlap)[:2]}",
                )


class TestLocalCategoriesSpoken(_FrenchJokeMixin, TestCase):
    """Each category answers from its own collection."""

    def _assert_category(self, name: str):
        spoken = self._spoken(UTTERANCES[name])
        self.assertTrue(spoken, f"expected a spoken answer for {name}")
        self.assertTrue(
            any(utt in CATEGORY_LINES[name] for utt in spoken),
            f"expected a line from {name}_jokes.dialog for "
            f"{UTTERANCES[name]!r}, got {spoken!r}",
        )

    def test_beauf(self):
        self._assert_category("beauf")

    def test_blondes(self):
        self._assert_category("blondes")

    def test_dark(self):
        self._assert_category("dark")

    def test_edgy(self):
        self._assert_category("edgy")

    def test_unknown_category_still_falls_back(self):
        """The positive control's negative twin: a category fr-FR does not
        ship must still reach ``no_joke``, not a joke collection."""
        spoken = self._spoken("raconte-moi une blague sur les licornes")
        self.assertTrue(spoken, "expected a spoken answer for an unknown category")
        every_line = set().union(*CATEGORY_LINES.values())
        self.assertFalse(
            any(utt in every_line for utt in spoken),
            f"an unknown category must not answer from a joke collection, "
            f"got {spoken!r}",
        )
        self.assertTrue(
            any("licorne" in utt.lower() for utt in spoken),
            f"expected the no_joke line, which names the query, got {spoken!r}",
        )
