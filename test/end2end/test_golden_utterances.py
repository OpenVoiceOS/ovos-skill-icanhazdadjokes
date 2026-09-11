"""Golden-utterance end-to-end coverage for ovos-skill-icanhazdadjokes
(en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset, keyed by
``skill_id == "ovos-skill-icanhazdadjokes.openvoiceos"``. One shared
``MiniCroft`` (module-scoped fixture) is booted for the whole suite; every
row is its own parametrized test item.

The two grammars overlap on purpose (see ``test_intents_en_us.py``'s module
docstring): a bare "tell me a joke"-style phrasing can legitimately land on
either ``joke.intent`` or ``search_joke.intent``. The corpus's own
``intent_label`` pins one specific handler per row and this suite honors
that pin exactly (no broadened "either" acceptance here) -- every row in
the vendored slice is unambiguous by construction (no bare "tell me a
joke"-style row is present).

Intent match is asserted off the ``ovos.intent.matched`` bus event's
``data.intent_name`` field, which is emitted as ``<skill_id>:<intent_label>``
with the ``.intent`` suffix already stripped. Capture ends at
``mycroft.skill.handler.start`` (right after intent binding fires, before
any handler body runs) so a row never depends on a handler finishing.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
LANG = "en-US"

_PIPELINE = [
    "ovos-adapt-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-adapt-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-adapt-pipeline-plugin-low",
]

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"

# utterances lifted verbatim from OTHER skills' golden-utterance slices,
# picked for lexical overlap with dadjokes' "tell me"/"say"/"laugh"/"joke"
# vocabulary.
NEGATIVE_UTTERANCES = [
    ("what's the weather like today", "ovos-skill-weather.openvoiceos"),
    ("tell me your kernel version", "ovos-skill-diagnostics.openvoiceos"),
    ("who was Joan Fuster", "ovos-skill-fuster-quotes.openvoiceos"),
    ("say the current time", "ovos-skill-time.openvoiceos"),
    ("set a timer for 5 minutes", "ovos-skill-alerts.openvoiceos"),
    ("play some music", "ovos-skill-music.openvoiceos"),
    ("what is my location", "ovos-skill-ip.openvoiceos"),
]


def _expected_names(skill_id: str, intent_label: str) -> set:
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{skill_id}:{base}", f"{skill_id}:{intent_label}"}


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


GOLDEN_ROWS = [pytest.param(r, id=r["utterance"]) for r in _load_golden_rows()]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID], max_wait=300)
    # Real padatious (this repo's `test` extra pins ovos-padatious) trains
    # its neural model in a background thread *after* the skill/service
    # report "ready" -- an utterance fired immediately after boot can race
    # that training and see zero matches even though the same utterance
    # matches correctly moments later. Warm the model up with a
    # known-good utterance and retry until it lands (or give up loudly)
    # before any real test row runs, so flaky training-lag never leaks
    # into a golden-row assertion.
    import time
    deadline = time.monotonic() + 60
    warm = []
    while time.monotonic() < deadline and not warm:
        warm = _matched_intent_names(mc, "tell me a joke", "warmup")
        if not warm:
            time.sleep(1)
    assert warm, "padatious model never finished warming up within 60s"
    yield mc
    mc.stop()


def _matched_intent_names(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(_PIPELINE)
    # blacklisted_intents/skills default to None on a fresh Session, which
    # crashes padatious/padacioso (NoneType membership test).
    session.blacklisted_intents = []
    session.blacklisted_skills = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        eof_msgs=["mycroft.skill.handler.start"],
    )
    capture.capture(utterance, timeout=30)
    msgs = capture.finish()
    return [
        m.data.get("intent_name")
        for m in msgs
        if m.msg_type == "ovos.intent.matched"
    ]


def _golden_id(row):
    return row["utterance"]


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance(minicroft, row):
    expected = _expected_names(SKILL_ID, row["intent_label"])
    matched = _matched_intent_names(minicroft, row["utterance"], f"golden-{_golden_id(row)}")
    assert any(m in expected for m in matched), (
        f"{row['utterance']!r}: expected one of {sorted(expected)!r}, got {matched!r}"
    )


@pytest.mark.timeout(60)
@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_negative_confusable_not_claimed(minicroft, negative):
    text, source_skill = negative
    matched = _matched_intent_names(minicroft, text, f"negative-{text}")
    claimed = any(m.startswith(f"{SKILL_ID}:") for m in matched if m)
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}"
