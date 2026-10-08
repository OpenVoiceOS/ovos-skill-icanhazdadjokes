"""OVOS-INTENT-2 §4.2 compliance and speakability for dialog content.

A ``.dialog`` phrase uses the metacharacters ``( ) [ ] { } |`` structurally
(wording-variety groups and named slots) and therefore cannot contain any of
them as literal spoken text; this is an accepted constraint, not an omission.
A line that carries one of these characters outside a ``{name}`` /
``{{name}}`` named slot is malformed by that clause, whether or not the
current renderer happens to raise on it.

The literal-metacharacter rule above reads en-US only, because a locale
line that carries a bracket is a translation decision and needs its own
native reader. What every locale must pass is weaker and harder: each line
has to be speakable at all. The renderer expands a line before the skill
speaks it, and it RAISES on a line it cannot parse, so the skill says
nothing and the handler fails on the draw. ``TestDialogIsSpeakable`` reads
every shipped locale with the renderer's own expansion and names any line
that cannot be spoken.

Run: pytest test/test_dialog_metachars.py -v
"""
import re
from pathlib import Path
from unittest import TestCase

from ovos_spec_tools.expansion import expand

LOCALE_ROOT = Path(__file__).parent.parent / "locale"
LOCALE_DIR = LOCALE_ROOT / "en-US"

# named slots: {name} and {{name}} are structural, not literal text
SLOT_RE = re.compile(r"\{\{?\s*[\w.]+\s*\}?\}")
METACHAR_RE = re.compile(r"[(){}\[\]|]")


class TestDialogMetacharacters(TestCase):
    def test_no_literal_metacharacters_in_en_us_dialogs(self):
        offenders = []
        for path in sorted(LOCALE_DIR.glob("*.dialog")):
            for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                stripped = SLOT_RE.sub("", line)
                if METACHAR_RE.search(stripped):
                    offenders.append(f"{path.name}:{lineno}: {raw!r}")

        self.assertEqual(
            offenders, [],
            "OVOS-INTENT-2 §4.2: literal ( ) [ ] { } | found as spoken text "
            "outside a named slot:\n" + "\n".join(offenders)
        )


class TestDialogIsSpeakable(TestCase):
    """Every shipped line, in every locale, can be spoken.

    A line the expansion refuses raises when the renderer draws it. The
    skill then speaks nothing and the handler fails, about once every N
    draws for a collection of N lines, which reads as a flaky skill rather
    than as the content defect it is.
    """

    def test_every_dialog_line_can_be_spoken(self):
        refused = []
        for path in sorted(LOCALE_ROOT.glob("*/*.dialog")):
            lines = [line for line in path.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.strip().startswith("#")]
            for number, line in enumerate(lines, start=1):
                try:
                    expand(line)
                except Exception as error:  # noqa: BLE001 - reported below
                    refused.append(
                        f"{path.parent.name}/{path.name}:{number}: "
                        f"{type(error).__name__}: {line!r}"
                    )
        self.assertEqual(
            [], refused,
            "these lines raise when the renderer draws them, so the skill "
            "speaks nothing:\n" + "\n".join(refused),
        )

    def test_the_sweep_reads_every_locale(self):
        """The control: a sweep that read one directory would pass for the
        wrong reason."""
        locales = {path.parent.name for path in LOCALE_ROOT.glob("*/*.dialog")}
        self.assertIn("en-US", locales)
        self.assertGreater(len(locales), 10, f"only {sorted(locales)} were read")
