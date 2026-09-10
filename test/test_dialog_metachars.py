"""OVOS-INTENT-2 §4.2 compliance for en-US dialog content.

A ``.dialog`` phrase uses the metacharacters ``( ) [ ] { } |`` structurally
(wording-variety groups and named slots) and therefore cannot contain any of
them as literal spoken text; this is an accepted constraint, not an omission.
A line that carries one of these characters outside a ``{name}`` /
``{{name}}`` named slot is malformed by that clause, whether or not the
current renderer happens to raise on it.

Run: pytest test/test_dialog_metachars.py -v
"""
import re
from pathlib import Path
from unittest import TestCase

LOCALE_DIR = Path(__file__).parent.parent / "locale" / "en-US"

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
