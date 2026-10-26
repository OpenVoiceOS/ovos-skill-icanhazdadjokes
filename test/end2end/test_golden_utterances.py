"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row's utterance goes through that pipeline's high, medium and low tiers in
order, and the row passes when the first tier to match names its
``intent_label``. The engine embeds the utterance, so a row that no template
spells out word for word still matches when it means the same thing.

Each ``negative_utterances_<lang>.jsonl`` holds requests for other skills.
They run on the same pipeline and must not match any intent of this skill.

Each locale must match at least ``MIN_MATCH_RATE`` of its golden rows, and at
least ``MIN_MATCHED_ROWS_PER_INTENT`` rows of each intent. A negative row that
matches this skill fails the locale, unless ``NEGATIVE_KNOWN_CLAIMS`` lists
that claim. All rows run, including rows marked ``needs_manual`` or
``machine_generated``, and the test prints every row that misses with the
intent that matched instead, and a count per expected and matched intent.
"""
import json
from collections import Counter
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
TIERS = ("high", "medium", "low")
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row.
MIN_MATCH_RATE = 0.8
# A locale also fails when any of its intents has fewer matched rows than this.
MIN_MATCHED_ROWS_PER_INTENT = 1
END2END_DIR = Path(__file__).parent
LOCALE_DIR = END2END_DIR.parents[1] / "locale"
# Locales whose golden rows the published m2v model does not separate at
# MIN_MATCH_RATE with the shipped templates, as (rate measured in two runs,
# reason). Such a locale is an expected failure only for the 80% gate: it
# still fails when an intent has no matched row, when its rate falls more
# than GAP_RATE_SLACK below the stored rate, or when it reaches the gate.
GAP_RATE_SLACK = 0.10
GOLDEN_LOCALE_GAPS = {
    "es-ES": (0.5, "m2v matches 50% of the es-ES rows with the shipped templates"),
    "eu-ES": (0.4, (
        'm2v matches 40% of the 10 eu-ES rows with the shipped templates '
        "and names no intent for the rest: 'ba al dakizu txiste onik?'; "
        "'barre eragin iezadazu, mesedez'; 'aitei buruzko txiste bat entzun "
        "nahi dut'; 'esan zerbait barregarria'; 'medikuei buruzko txisteren "
        "bat?'; 'irakasleei buruzko txiste bat nahi dut'. The published m2v "
        'model predates these templates; remove after retrain.')),
    "fa-IR": (0.5, (
        'm2v matches 50% of the 10 fa-IR rows with the shipped templates '
        "and names no intent for the rest: 'جوک خوب سراغ داری؟'; 'میخوام یه "
        "جوک درباره باباها بشنوم'; 'حوصلم سر رفته، یه جوک بگو'; 'از دکترها "
        "جوک داری؟'; 'میخوام یه جوک درباره معلم ها بشنوم'. The published "
        'm2v model predates these templates; remove after retrain.')),
    "gl-ES": (0.4, (
        'm2v matches 40% of the 10 gl-ES rows with the shipped templates '
        "and names no intent for the rest: 'conta algo gracioso'; 'coñeces "
        "chistes de programadores?'; 'dime algo que me faga rir'; 'conta "
        "algo gracioso sobre gatos'; 'tes chistes de médicos?'; 'quero un "
        "chiste sobre mestres'. The published m2v model predates these "
        'templates; remove after retrain.')),
    "hu-HU": (0.7, "m2v matches 70% of the hu-HU rows with the shipped templates"),
    "pl-PL": (0.6, "m2v matches 60% of the pl-PL rows with the shipped templates"),
    "pt-BR": (0.6, (
        'm2v matches 60% of the 10 pt-BR rows with the shipped templates '
        "and names no intent for the rest: 'fala alguma coisa engraçada'; "
        "'me conta algo engraçado sobre gatos'; 'sabe alguma piada de "
        "médico'; 'manda uma piada sobre professores'. The published m2v "
        'model predates these templates; remove after retrain.')),
    "sv-SE": (0.6, "m2v matches 60% of the sv-SE rows with the shipped templates"),
}
# Locales whose negative rows the published m2v model cannot separate from
# this skill's intents when this skill is the only one loaded, with the
# measured reason.
NEGATIVE_ENGINE_GAPS = {}
# Negative rows that m2v claimed for this skill on origin/dev as well, with the
# intents it named across runs. A listed claim is allowed, not required. Any
# other claim fails the locale.
NEGATIVE_KNOWN_CLAIMS = {
    "pl-PL": {"ścisz muzykę": ("joke",)},
}


def _rows_by_lang(prefix):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}_*.jsonl")):
        lang = path.stem.removeprefix(f"{prefix}_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang("golden_utterances")
NEGATIVE_ROWS = _rows_by_lang("negative_utterances")


def _matched_intent(engine, utterance, lang):
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    match = next(filter(None, (getattr(engine, f"match_{tier}")([utterance], lang, message)
                               for tier in TIERS)), None)
    return match.match_type if match else None


def _match_all(lang, rows):
    """Boot the skill on m2v in ``lang`` and return the intent each row matches."""
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    try:
        warm_m2v_models(minicroft)
        engine = minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]
        return [_matched_intent(engine, row["utterance"], lang) for row in rows]
    finally:
        minicroft.stop()


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    rows = ROWS[lang]
    matched = _match_all(lang, rows)
    misses = []
    confusion = Counter()
    hits = {row["intent_label"]: 0 for row in rows}
    for row, got in zip(rows, matched):
        if got == f"{SKILL_ID}:{row['intent_label']}":
            hits[row["intent_label"]] += 1
        else:
            got_label = got.removeprefix(f"{SKILL_ID}:") if got else None
            confusion[(row["intent_label"], got_label)] += 1
            misses.append(f"{row['utterance']!r}: expected {row['intent_label']}, got {got}")
    starved = sorted(label for label, count in hits.items()
                     if count < MIN_MATCHED_ROWS_PER_INTENT)
    rate = 1 - len(misses) / len(rows)
    print(f"[{lang}] {rate:.1%} of {len(rows)} rows match", *misses, sep="\n  ")
    for (expected, got), count in sorted(confusion.items(), key=str):
        print(f"[{lang}] CONFUSION {expected} -> {got}: {count}")
    if starved:
        print(f"[{lang}] intents below {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}")
    assert not starved, (
        f"[{lang}] intents below {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    )
    if lang in GOLDEN_LOCALE_GAPS:
        stored, reason = GOLDEN_LOCALE_GAPS[lang]
        assert rate >= stored - GAP_RATE_SLACK, (
            f"[{lang}] {rate:.1%} of rows match, more than {GAP_RATE_SLACK:.0%} below "
            f"the stored gap rate {stored:.0%}:\n  " + "\n  ".join(misses)
        )
        assert rate < MIN_MATCH_RATE, (
            f"[{lang}] {rate:.1%} of rows match, remove it from GOLDEN_LOCALE_GAPS"
        )
        pytest.xfail(f"[{lang}] {rate:.1%} of rows match: {reason}")
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of rows match, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", [
    pytest.param(lang, marks=pytest.mark.xfail(reason=NEGATIVE_ENGINE_GAPS[lang], strict=True))
    if lang in NEGATIVE_ENGINE_GAPS else lang
    for lang in sorted(NEGATIVE_ROWS)
])
def test_negative_rows_match_no_skill_intent(lang):
    rows = NEGATIVE_ROWS[lang]
    known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
    matched = _match_all(lang, rows)
    claims = [(row["utterance"], got.removeprefix(f"{SKILL_ID}:"))
              for row, got in zip(rows, matched)
              if got and got.startswith(f"{SKILL_ID}:")]
    unknown = [f"{utterance!r}: matched {intent}" for utterance, intent in claims
               if intent not in known.get(utterance, ())]
    print(f"[{lang}] {len(claims)} of {len(rows)} negative rows claimed, "
          f"{len(unknown)} not in NEGATIVE_KNOWN_CLAIMS", *unknown, sep="\n  ")
    assert not unknown, f"[{lang}] negative rows matched this skill:\n  " + "\n  ".join(unknown)


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    shipping = {d.name for d in LOCALE_DIR.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"


def test_every_locale_ships_every_reference_intent():
    reference = {p.name for p in (LOCALE_DIR / "en-US").rglob("*.intent")}
    missing = {d.name: sorted(reference - {p.name for p in d.rglob("*.intent")})
               for d in LOCALE_DIR.iterdir() if d.is_dir()}
    missing = {lang: names for lang, names in missing.items() if names}
    assert not missing, f"locales missing en-US intent files: {missing}"


@pytest.mark.parametrize("lang", sorted(ROWS))
def test_every_intent_has_golden_rows(lang):
    intents = {p.stem for p in (LOCALE_DIR / lang).rglob("*.intent")}
    labelled = {row["intent_label"] for row in ROWS[lang]}
    assert intents <= labelled, f"[{lang}] intents without golden rows: {sorted(intents - labelled)}"
