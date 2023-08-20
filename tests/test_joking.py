# pylint: disable=missing-docstring,import-outside-toplevel,protected-access
import shutil
import unittest
from os import mkdir
from os.path import dirname, exists, join
from unittest.mock import Mock, patch

import requests
from ovos_utils.messagebus import FakeBus, Message
from ovos_workshop.skill_launcher import SkillLoader

bus = FakeBus()


class TestSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bus.run_in_thread()
        skill_loader = SkillLoader(bus, dirname(dirname(__file__)))
        skill_loader.load()
        cls.skill = skill_loader.instance

        # Define a directory to use for testing
        cls.test_fs = join(dirname(__file__), "skill_fs")
        if not exists(cls.test_fs):
            mkdir(cls.test_fs)

        # Override the configuration and fs paths to use the test directory
        cls.skill.settings_write_path = cls.test_fs
        cls.skill.file_system.path = cls.test_fs

        # Override speak and speak_dialog to test passed arguments
        cls.skill.speak = Mock()
        cls.skill.speak_dialog = Mock()

        # Mock exit/shutdown method to prevent interactions with test runner
        cls.skill._do_exit_shutdown = Mock()

    def setUp(self):
        self.skill.speak.reset_mock()
        self.skill.speak_dialog.reset_mock()
        self.skill._do_exit_shutdown.reset_mock()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.test_fs)

    def test_skill_init(self):
        # Test any parameters expected to be set in init or initialize methods
        from ovos_workshop.skills import OVOSSkill

        self.assertIsInstance(self.skill, OVOSSkill)
        self.assertIsNotNone(self.skill.translator)

    def test_fix_encoding(self):
        test_cases = [
            (
                "â\x80\x9cMy Dog has no nose.â\x80\x9d â\x80\x9cHow does he smell?â\x80\x9d â\x80\x9cAwfulâ\x80\x9d",
                '"My Dog has no nose." "How does he smell?" "Awful"',
            ),
            (
                "I was just looking at my ceiling. Not sure if itâ\x80\x99s the best ceiling in the world, but itâ\x80\x99s definitely up there.",
                "I was just looking at my ceiling. Not sure if it's the best ceiling in the world, but it's definitely up there.",
            ),
            (
                "â\x80\x9cDoctor, Iâ\x80\x99ve broken my arm in several placesâ\x80\x9d Doctor â\x80\x9cWell donâ\x80\x99t go to those places.â\x80\x9d",
                '"Doctor, I\'ve broken my arm in several places" Doctor "Well don\'t go to those places."',
            ),
            (
                "I decided to sell my Hooverâ\x80¦ well it was just collecting dust.",
                "I decided to sell my Hoover… well it was just collecting dust.",
            ),
            (
                "Iâ\x80\x99ve just been reading a book about anti-gravity, itâ\x80\x99s impossible to put down!",
                "I've just been reading a book about anti-gravity, it's impossible to put down!",
            ),
            (
                "Whenever the cashier at the grocery store asks my dad if he would like the milk in a bag he replies, â\x80\x98No, just leave it in the carton!'",
                "Whenever the cashier at the grocery store asks my dad if he would like the milk in a bag he replies, 'No, just leave it in the carton!'",
            ),
        ]
        for broken, expected in test_cases:
            with self.subTest(broken=broken, expected=expected):
                result = self.skill._fix_encoding(broken)
                self.assertEqual(result, expected, f"Expected '{expected}', but got '{result}'")

    def test_handle_joke(self):
        # Arrange
        get_joke = self.skill.get_generic_joke = Mock(return_value="joke\r\n")
        fix = self.skill._fix_encoding = Mock(return_value="joke")
        translate = self.skill.translate = Mock(return_value="blague")
        self.skill.speak = Mock()
        # Act
        self.skill.handle_joke(
            Message(
                "skill-icanhazdadjokes.jarbasskills:joke.intent",
                data={
                    "data": {
                        "utterances": ["tell me a joke", "tell me joke"],
                        "lang": "en-us",
                        "utterance": "tell me a joke",
                    }
                },
            )
        )
        # Assert
        get_joke.assert_called_once()
        fix.assert_called_once_with(get_joke.return_value)
        translate.assert_called_once_with(fix.return_value)
        self.skill.speak.assert_called_once_with(translate.return_value)

    @patch("requests.get")
    def test_get_generic_joke(self, mock_get):
        # Mock the response from requests.get
        mock_response = Mock()
        mock_response.text = "Why did the chicken cross the road? To get to the other side."
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the method and check the result
        result = self.skill.get_generic_joke()
        self.assertEqual(result, "Why did the chicken cross the road? To get to the other side.")

    @patch("requests.get")
    def test_get_generic_joke_failure(self, mock_get):
        # Mock the response for a failed request
        mock_get.side_effect = requests.exceptions.HTTPError("Mocked HTTPError")

        # Call the method and expect an exception
        with self.assertRaises(requests.exceptions.HTTPError):
            self.skill.get_generic_joke()

    def test_handle_search_joke(self):
        return  # TODO: Implement stub

    def test_chuck_norris_joke(self):
        return  # TODO: Implement stub

    def test_translate(self):
        return  # TODO: Implement stub
