"""m2v-multilingual candidate-default gate for ovos-skill-icanhazdadjokes.

Boots the skill through the candidate default intent engine -- the
model2vec multilingual classifier (``OpenVoiceOS/ovos-m2v-intents-multi-128M-v5``)
-- via ovoscope's ``get_m2v_minicroft`` and asserts, for a representative slice
of the skill's own golden utterances, the whole round trip: the correct
intent routed AND real spoken content came out.

``joke.intent`` and a recognized ``search_joke.intent`` category both render
a random line from a locale dialog file, so those cases assert non-empty
spoken text that is not the raw dialog file name (real effect, not routing
alone). An unrecognized category falls through to ``no_joke``, whose
``{query}`` slot is deterministic, so that case asserts the exact rendered
text.

FINDING: the model confuses ``search_joke`` for the bare ``joke`` intent on
every "joke about X" phrasing tried here -- ``joke about chuck norris``
(0.51, ``ovos-m2v-pipeline-medium``), ``do you know any programmer jokes``
(0.88, ``-high``), and ``joke about xyzzyfrobnicate`` (0.72, ``-high``) all
route to ``ovos-skill-icanhazdadjokes.openvoiceos:joke`` instead of
``:search_joke``, so the category is dropped and a generic dad joke is
spoken instead of the requested (or "not found") category. Recorded as
``xfail(strict=True)`` rather than loosened or skipped -- a corpus/model fix
should flip these back into real gates.
"""
import os
import shutil
import tempfile
import unittest

import pytest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session

from ovoscope import get_m2v_minicroft, M2V_PIPELINE

SKILL_ID = "ovos-skill-icanhazdadjokes.openvoiceos"
LANG = "en-US"

_MC = None
_PIPE = None
_XDG = None
_ORIG_XDG = None


def setUpModule():
    global _MC, _PIPE, _XDG, _ORIG_XDG
    _ORIG_XDG = os.environ.get("XDG_DATA_HOME")
    _XDG = tempfile.mkdtemp(prefix="ovoscope-m2v-icanhazdadjokes-xdg-")
    os.environ["XDG_DATA_HOME"] = _XDG

    _MC = get_m2v_minicroft(skill_ids=[SKILL_ID], lang=LANG)
    _PIPE = _MC.intents.pipeline_plugins["ovos-m2v-pipeline"]
    _PIPE._ensure_model(background_ok=False)


def tearDownModule():
    global _MC, _XDG, _ORIG_XDG
    if _MC is not None:
        _MC.stop()
        _MC = None
    if _ORIG_XDG is None:
        os.environ.pop("XDG_DATA_HOME", None)
    else:
        os.environ["XDG_DATA_HOME"] = _ORIG_XDG
    if _XDG is not None:
        shutil.rmtree(_XDG, ignore_errors=True)
        _XDG = None


class TestM2VJokesGoldenEffect(unittest.TestCase):
    """Effect assertions: golden utterance in -> correct intent -> real spoken joke out."""

    def _run(self, utterance: str, lang: str = LANG, timeout: float = 15.0):
        speaks = []
        failures = []

        def _on_speak(msg):
            speaks.append(msg)

        def _on_fail(msg):
            failures.append(msg)

        _MC.bus.on("speak", _on_speak)
        _MC.bus.on("complete_intent_failure", _on_fail)
        sess = Session(session_id=f"m2v-golden-{hash(utterance)}", pipeline=M2V_PIPELINE)
        sess.lang = lang
        try:
            _MC.bus.emit(Message(
                "recognizer_loop:utterance",
                data={"utterances": [utterance], "lang": lang},
                context={"session": sess.serialize(), "lang": lang},
            ))
            import time as _t
            deadline = _t.time() + timeout
            while _t.time() < deadline and not speaks and not failures:
                _t.sleep(0.05)
        finally:
            _MC.bus.remove("speak", _on_speak)
            _MC.bus.remove("complete_intent_failure", _on_fail)

        if not speaks:
            return None, None, bool(failures)
        data = speaks[0].data
        meta = data.get("meta", {}) or {}
        return meta.get("dialog"), (data.get("utterance") or ""), False

    def _assert_random_joke(self, utterance, expected_dialog):
        dialog, text, failed = self._run(utterance)
        self.assertFalse(failed, f"{utterance!r} did not route: complete_intent_failure")
        self.assertEqual(
            dialog, expected_dialog,
            f"{utterance!r} routed to dialog {dialog!r}, expected {expected_dialog!r}")
        self.assertTrue(text, f"{utterance!r} produced no spoken output")
        self.assertNotIn(
            expected_dialog, text.lower(),
            f"{utterance!r} spoke the dialog NAME, not rendered text: {text!r}")

    def test_tell_me_a_joke(self):
        self._assert_random_joke("tell me a joke", "dad_jokes")

    def test_make_me_laugh(self):
        self._assert_random_joke("make me laugh", "dad_jokes")

    @pytest.mark.xfail(
        reason="model misclassifies as 'joke' (0.51 medium) instead of "
               "'search_joke'; category dropped, generic dad joke spoken "
               "instead (see module docstring)",
        strict=True)
    def test_joke_about_chuck_norris(self):
        self._assert_random_joke("joke about chuck norris", "chuck_norris_jokes")

    @pytest.mark.xfail(
        reason="model misclassifies as 'joke' (0.88 high) instead of "
               "'search_joke'; category dropped, generic dad joke spoken "
               "instead (see module docstring)",
        strict=True)
    def test_joke_about_programmers(self):
        self._assert_random_joke("do you know any programmer jokes", "dev_jokes")

    @pytest.mark.xfail(
        reason="model misclassifies as 'joke' (0.72 high) instead of "
               "'search_joke'; category dropped, generic dad joke spoken "
               "instead of no_joke (see module docstring)",
        strict=True)
    def test_joke_about_unknown_category(self):
        # The {query} slot on no_joke is deterministic -- assert the exact text.
        dialog, text, failed = self._run("joke about xyzzyfrobnicate")
        self.assertFalse(failed, "joke about xyzzyfrobnicate did not route")
        self.assertEqual(dialog, "no_joke")
        self.assertIn("xyzzyfrobnicate", text.lower())
        self.assertNotIn("no_joke", text.lower())


class TestM2VRegisteredLabelRouting(unittest.TestCase):
    """The model's labels carry the skill's real runtime id and route it."""

    def test_registered_skill_id_labels_route(self):
        classes = {str(c) for c in _PIPE.model.classes_}
        registered = set(_PIPE.intents)
        self.assertIn(f"{SKILL_ID}:joke", registered)
        self.assertTrue(
            registered & classes,
            "registered intent labels do not intersect the model's classes; "
            f"{SKILL_ID} would route nothing through this model")


if __name__ == "__main__":
    unittest.main()
