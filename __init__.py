# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring,invalid-name
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import random
from typing import Optional

import pyjokes
import requests
from ovos_plugin_manager.language import OVOSLangTranslationFactory
from ovos_utils.messagebus import Message
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill


class JokingSkill(OVOSSkill):
    def __init__(self, *args, **kwargs):
        super(JokingSkill, self).__init__(*args, **kwargs)
        # TODO config from settings
        self.translator = OVOSLangTranslationFactory.create()

    def get_generic_joke(self) -> Optional[str]:
        joke = requests.get("https://icanhazdadjoke.com/", headers={"Accept": "text/plain"}, timeout=10)
        joke.raise_for_status()
        return self._fix_encoding(joke.text)

    def _fix_encoding(self, string: str) -> str:
        replacements = {
            "â\x80\x9c": '"',  # left double quotation mark
            "â\x80\x9d": '"',  # right double quotation mark
            "\r": " ",
            "\n": " ",
            "â\x80\x99": "'",  # right single quotation mark
            "â\x80\x98": "'",  # left single quotation mark
            "â\x80\x93": "–",  # en dash
            "â\x80\x94": "—",  # em dash
            "â\x80¦": "…",  # ellipsis
            "â\x82¬": "€",  # euro sign
            "â\x80\x8b": "‐",  # hyphen (non-breaking)
            "Â\xa0": " ",  # non-breaking space
            "â\x80\x9e": '"',  # double low-9 quotation mark
            "â\x80\x9a": "'",  # single low-9 quotation mark
            "â\x80\xba": "›",  # single right-pointing angle quotation mark
            "â\x80\xb9": "‹",  # single left-pointing angle quotation mark
        }

        for old, new in replacements.items():
            string = string.replace(old, new)
        if "â" in string:
            self.log.warning("Failed to fix encoding, prepare for weird TTS: %s", string)
            self.log.warning("Please report this issue so we can fix it! PRs welcome")
        return string

    @intent_handler("joke.intent")
    def handle_joke(self, message: Message) -> None:
        joke = self.get_generic_joke()
        self._speak_tx(joke)

    @intent_handler("search_joke.intent")
    def handle_search_joke(self, message: Message) -> None:
        category = message.data["search"].lower()
        self.log.debug("joke search: %s", category)

        # special handling for chuck norris jokes
        if "chuck norris" in category:
            self.chuck_norris_joke()
            return

        # search query should be in english, translate if needed
        is_english = self.lang.split("-")[0] == "en"
        if not is_english:
            tx_category = self.translate(utterance=category, lang_tgt="en", lang_src=self.lang)
            # TODO make singular, https://github.com/MycroftAI/lingua-franca/pull/36
            if tx_category.endswith("s"):
                tx_category = tx_category[: len(tx_category) - 1]
            url = "https://icanhazdadjoke.com/search?term=" + tx_category
        else:
            url = "https://icanhazdadjoke.com/search?term=" + category

        headers = {"Accept": "text/plain"}
        result = requests.get(url, headers=headers, timeout=10).text.strip()

        if not result:
            self.speak_dialog("no_joke", {"search": category})
        else:
            joke = random.choice(result.split("\n"))
            self._speak_tx(joke)

    def chuck_norris_joke(self):
        joke = pyjokes.get_joke(category="chuck")
        self._speak_tx(joke)

    def _speak_tx(self, joke):
        # helper to translate jokes to non-english on speak
        is_english = self.lang.split("-")[0] == "en"
        if not is_english:
            translated_utt = self.translate(joke)
            self.speak(translated_utt)
        else:
            self.speak(joke)

    def translate(self, utterance, lang_tgt=None, lang_src="en-us"):
        lang_tgt = lang_tgt or self.lang
        if not lang_tgt.startswith(lang_src.split("-")[0]):
            return self.translator.translate(utterance, lang_tgt, lang_src)
        return utterance.strip()
