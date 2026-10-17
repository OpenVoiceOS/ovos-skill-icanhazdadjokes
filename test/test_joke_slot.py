"""The joke handler accepts a request that carries no ``{query}`` slot.

The m2v pipeline matches a generic joke request and sends no slot data, so
the handler must speak a joke instead of raising.
"""
from unittest import TestCase
from unittest.mock import MagicMock

from ovos_bus_client.message import Message
from ovos_skill_icanhazdadjokes import JokingSkill


class TestSearchJokeWithoutQuery(TestCase):
    def setUp(self):
        self.skill = MagicMock(spec=JokingSkill)
        self.skill.log = MagicMock()

    def test_missing_query_falls_back_to_a_plain_joke(self):
        message = Message("ovos-skill-icanhazdadjokes.openvoiceos:joke", {})
        JokingSkill.handle_joke(self.skill, message)
        self.skill._speak_default_joke.assert_called_once_with()
        self.skill._handle_category.assert_not_called()

    def test_empty_query_falls_back_to_a_plain_joke(self):
        message = Message("ovos-skill-icanhazdadjokes.openvoiceos:joke", {"query": ""})
        JokingSkill.handle_joke(self.skill, message)
        self.skill._speak_default_joke.assert_called_once_with()

    def test_unknown_category_still_says_no_joke(self):
        self.skill.voc_match.return_value = False
        message = Message("ovos-skill-icanhazdadjokes.openvoiceos:joke", {"query": "Xyzzy"})
        JokingSkill.handle_joke(self.skill, message)
        self.skill._handle_category.assert_called_once_with("xyzzy")
        self.skill._speak_default_joke.assert_not_called()

    def test_unknown_category_says_no_joke(self):
        self.skill.voc_match.return_value = False
        JokingSkill._handle_category(self.skill, "xyzzy")
        self.skill.speak_dialog.assert_called_once_with("no_joke", {"query": "xyzzy"})
