"""End-to-end coverage for the locale-local joke categories.

All 19 locales ship ``beauf.voc``, ``blondes.voc``, ``dark.voc`` and
``edgy.voc``, and all 19 ship ``beauf_jokes.dialog``,
``blondes_jokes.dialog`` and ``edgy_jokes.dialog``. Only fr-FR ships
``dark_jokes.dialog``. So this change makes three collections reachable in
19 locales and ``dark`` reachable in fr-FR alone -- it is not an fr-FR-only
change, and an earlier version of this docstring said it was.

Before the change all of them were unreachable by voice: nothing named the
categories and no handler branch spoke them, so "blague sur les blondes"
answered from ``no_joke.dialog``.

The fr-FR tests below cover the four collections where all four exist. The
da-DK class at the end covers what fr-FR structurally cannot: the guard in
``_speak_local_category`` that returns False when a locale names a category
in a ``.voc`` but ships no ``<name>_jokes.dialog``. Because 18 locales ship
``dark.voc`` and none of them ships ``dark_jokes.dialog``, that guard is not
defensive -- it is the path every non-fr-FR "dark humour" request takes, and
without a row here, deleting it would leave this suite green while 18
locales began speaking ``dark_jokes`` as a bare resource name.

Each test asserts the *effect*, not only the route: the spoken line must be
one of the lines that this category's own dialog file ships. The line sets
are read from disk at test time, never restated here and never read back
from a captured bus message, so they stay independent of the code under
test. ``test_category_line_sets_are_disjoint`` is the control that makes
that membership meaningful: if two collections shared a line, a handler
speaking the wrong file could still pass.

A line is not always spoken as it is written: the renderer collapses every
run of whitespace and expands a ``(a|b)`` group. Eleven lines across the
four collections carry a double space and three carry a group, which is
about 5% of the picks, so a verbatim comparison failed about one
whole-suite run in twenty. The expected set therefore holds every form the
renderer can speak a line as, and the spoken line is collapsed before it is
looked up.
``TestRendererCollapsesWhitespace`` is the deterministic control: it renders
every line of every collection through the renderer the skill itself loads,
so the eleven lines are measured on every run rather than drawn at random.

The suite runs on the padacioso pipeline, as ``test_intents_en_us.py``
does, so it needs no trained padatious model.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_spec_tools.expansion import expand
from ovos_workshop.resource_files import MustacheDialogRenderer
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


def _collapse(text: str) -> str:
    """Return ``text`` with every run of whitespace reduced to one space.

    This is what the dialog renderer does to a template before the skill
    speaks it, so a comparison against a shipped line must do it too.
    """
    return " ".join(text.split())


def _spoken_forms(line: str) -> set:
    """Return every form the renderer can speak a template line as.

    A line is not always spoken as written: the renderer expands a
    ``(a|b)`` group and collapses every run of whitespace. The expansion
    comes from the same library the renderer uses, never from the skill
    under test. A line the expansion refuses can never be spoken at all,
    and returns an empty set, which
    ``test_every_line_can_be_spoken_at_all`` reports by name.
    """
    try:
        return {_collapse(form) for form in expand(line)}
    except Exception:  # noqa: BLE001 - reported by the corpus test
        return set()


def _raw_lines(name: str) -> list:
    with open(LOCALE_FR_FR / f"{name}.dialog", encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if line.strip()]


def _dialog_lines(name: str) -> set:
    return set().union(*(_spoken_forms(line) for line in _raw_lines(name)))


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

    def test_every_line_can_be_spoken_at_all(self):
        """A line the template expansion refuses raises when the renderer
        picks it, so the skill says nothing and the handler fails. One
        stray ``>`` in a joke is enough."""
        refused = []
        for name in CATEGORIES:
            for number, line in enumerate(_raw_lines(f"{name}_jokes"), start=1):
                if not _spoken_forms(line):
                    refused.append(f"{name}_jokes.dialog:{number}: {line!r}")
        self.assertEqual(
            [], refused,
            "these lines cannot be spoken; the renderer raises on them:\n"
            + "\n".join(refused),
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


class TestRendererCollapsesWhitespace(TestCase):
    """Every shipped line, as the renderer speaks it, is in the expected set.

    The spoken tests below draw one line at random, so a line the
    comparison cannot match fails about one run in twenty. This case
    renders every line of every collection through the renderer the skill
    itself loads, so the same defect fails every run instead.
    """

    def test_every_rendered_line_is_in_its_category_set(self):
        for name in CATEGORIES:
            path = LOCALE_FR_FR / f"{name}_jokes.dialog"
            raw = _raw_lines(f"{name}_jokes")
            renderer = MustacheDialogRenderer()
            renderer.load_template_file(f"{name}_jokes", str(path))
            for index in range(len(raw)):
                rendered = renderer.render(f"{name}_jokes", index=index)
                self.assertIn(
                    rendered, CATEGORY_LINES[name],
                    f"{name}_jokes.dialog line {index + 1} is spoken as "
                    f"{rendered!r}, which is not in the expected set",
                )

    def test_the_renderer_really_collapses_a_double_space(self):
        """The control for the control: a comparison that needed no
        collapsing would make the case above pass for the wrong reason."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.dialog"
            path.write_text("deux  espaces\tet une tabulation\n", encoding="utf-8")
            renderer = MustacheDialogRenderer()
            renderer.load_template_file("probe", str(path))
            rendered = renderer.render("probe", index=0)
        self.assertEqual("deux espaces et une tabulation", rendered)
        self.assertNotEqual("deux  espaces\tet une tabulation", rendered)


class TestLocalCategoriesSpoken(_FrenchJokeMixin, TestCase):
    """Each category answers from its own collection."""

    def _assert_category(self, name: str):
        spoken = self._spoken(UTTERANCES[name])
        self.assertTrue(spoken, f"expected a spoken answer for {name}")
        self.assertTrue(
            any(_collapse(utt) in CATEGORY_LINES[name] for utt in spoken),
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
            any(_collapse(utt) in every_line for utt in spoken),
            f"an unknown category must not answer from a joke collection, "
            f"got {spoken!r}",
        )
        self.assertTrue(
            any("licorne" in utt.lower() for utt in spoken),
            f"expected the no_joke line, which names the query, got {spoken!r}",
        )


LANG_DA = "da-DK"
LOCALE_DA_DK = Path(__file__).parent.parent.parent / "locale" / LANG_DA


def _da_lines(name: str) -> set:
    """Every form the renderer can speak a da-DK collection's lines as."""
    path = LOCALE_DA_DK / f"{name}.dialog"
    with open(path, encoding="utf-8") as handle:
        raw = [line.rstrip("\n") for line in handle if line.strip()]
    return set().union(*(_spoken_forms(line) for line in raw))


class TestMissingDialogGuard(TestCase):
    """The guard path, which fr-FR cannot exercise for any category.

    ``_speak_local_category`` returns False when ``"<name>_jokes"`` is absent
    from ``self.dialog_renderer.templates``, and the caller falls through to
    ``no_joke``. 18 locales name ``dark`` in a ``.voc`` and none of them ships
    ``dark_jokes.dialog``, so this is the live path for every non-fr-FR "dark
    humour" request, not a defensive branch.

    da-DK is the locale under test because it names the category in its own
    words (``sort humor``) and ships ``beauf_jokes.dialog``, which gives the
    positive control below a real answer from the same boot.
    """

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID], lang=LANG_DA)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _spoken(self, utterance: str) -> list:
        session = Session(f"e2e-da_dk-jokes-{abs(hash(utterance))}")
        session.lang = LANG_DA
        session.pipeline = PADACIOSO_PIPELINE
        session.blacklisted_intents = []
        session.blacklisted_skills = []
        message = Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG_DA},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        capture = CaptureSession(self.minicroft)
        capture.capture(message, timeout=30)
        return [
            m.data.get("utterance", "")
            for m in capture.finish()
            if m.msg_type in ("speak", "ovos.utterance.speak")
        ]

    def test_da_dk_ships_dark_voc_and_no_dark_dialog(self):
        """The precondition. If either half stops holding, the two rows below
        stop testing what they are named for, so it is asserted and not
        assumed."""
        self.assertTrue((LOCALE_DA_DK / "dark.voc").is_file(),
                        "da-DK must name the dark category for the guard to be reached")
        self.assertFalse((LOCALE_DA_DK / "dark_jokes.dialog").is_file(),
                         "da-DK must NOT ship dark_jokes.dialog; if it now does, "
                         "pick another locale that names dark and ships no dialog")

    def test_a_named_category_with_no_dialog_falls_back(self):
        """"sort humor" is in da-DK's dark.voc, so the handler matches the
        category and then finds no dialog to speak.

        The answer must be the no_joke line. The failure this guards against is
        speaking the bare resource name "dark_jokes" aloud, which is worse than
        the fallback it replaces.
        """
        spoken = self._spoken("fortæl mig en vittighed om sort humor")
        self.assertTrue(spoken, "expected a spoken answer, got silence")
        joined = " ".join(spoken)
        self.assertNotIn("dark_jokes", joined,
                         f"the bare dialog key was spoken aloud: {spoken!r}")
        self.assertTrue(
            any("sort humor" in utt.lower() for utt in spoken),
            f"expected the no_joke line, which names the query, got {spoken!r}",
        )

    def test_a_named_category_with_a_dialog_still_answers(self):
        """The positive control, on the same boot: without it, a handler that
        answered no_joke for everything in da-DK would pass the row above."""
        spoken = self._spoken("fortæl mig en vittighed om plat")
        self.assertTrue(spoken, "expected a spoken answer, got silence")
        beauf = _da_lines("beauf_jokes")
        self.assertTrue(
            any(_collapse(utt) in beauf for utt in spoken),
            f"expected a line from da-DK/beauf_jokes.dialog, got {spoken!r}",
        )
