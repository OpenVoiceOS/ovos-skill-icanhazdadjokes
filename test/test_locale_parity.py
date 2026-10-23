"""No locale ships a resource that en-US lacks (OVOS-INTENT-2 §2.3).

A skill's resource set is the same in every locale it ships: a (role, base
name) pair present in any one language directory MUST be present in every
other one. This test reads one direction only, the one a deleted en-US file
breaks: no locale may hold a pair that en-US does not. Resources that a
translated locale still lacks are a separate gap and are not checked here.
`.blacklist` and `.prompt` are exempt from the clause.
"""
from pathlib import Path

LOCALES = Path(__file__).resolve().parents[1] / "locale"
ROLES = {".intent", ".dialog", ".entity", ".voc", ".required"}


def resource_pairs(locale: Path) -> set:
    return {(p.suffix, p.stem) for p in locale.rglob("*")
            if p.is_file() and p.suffix in ROLES}


def test_no_locale_ships_a_resource_en_us_lacks():
    reference = resource_pairs(LOCALES / "en-US")
    assert reference, "en-US ships no resources"
    problems = []
    for locale in sorted(d for d in LOCALES.iterdir() if d.is_dir()):
        for role, name in sorted(resource_pairs(locale) - reference):
            problems.append(f"{locale.name}: {name}{role} has no en-US counterpart")
    assert not problems, "\n  ".join(["resources missing from en-US:"] + problems)
