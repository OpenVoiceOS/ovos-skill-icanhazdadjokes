"""A locale resource that exists but is empty is worse than one that is
missing: a parity check that only looks for the file's presence reports no
gap, and the skill silently speaks nothing for a key that looks covered.

de-DE shipped dad_jokes.dialog and dev_jokes.dialog as 0-byte files for a
period (T-3038, T-3166); this guards against that regression recurring, for
any locale and any .dialog/.voc/.intent/.entity/.blacklist/.value file this
skill ships.

Run: pytest test/test_locale_nonempty.py -v
"""
from pathlib import Path
from unittest import TestCase

LOCALE_DIR = Path(__file__).parent.parent / "locale"
RESOURCE_EXTS = (".dialog", ".voc", ".intent", ".entity", ".blacklist", ".value")


class TestLocaleResourcesAreNotEmpty(TestCase):
    def test_no_shipped_resource_file_is_empty(self):
        offenders = []
        for path in sorted(LOCALE_DIR.rglob("*")):
            if not path.is_file() or path.suffix not in RESOURCE_EXTS:
                continue
            if path.stat().st_size == 0:
                offenders.append(str(path.relative_to(LOCALE_DIR)))

        self.assertEqual(
            offenders, [],
            "a shipped locale resource file is empty (0 bytes), which speaks "
            "nothing and hides the gap from a presence-only parity check:\n"
            + "\n".join(offenders)
        )
