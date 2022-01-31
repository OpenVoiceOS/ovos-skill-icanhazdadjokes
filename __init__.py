#
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
import requests
import random
from mycroft.skills.core import MycroftSkill, intent_handler
from ovos_plugin_manager.language import OVOSLangTranslationFactory
import pyjokes


class JokingSkill(MycroftSkill):
    def __init__(self):
        super(JokingSkill, self).__init__(name="JokingSkill")
        # TODO config form settings
        self.translator = OVOSLangTranslationFactory.create()

    @intent_handler("joke.intent")
    def handle_joke(self, message):
        joke = requests.get("https://icanhazdadjoke.com/",
                            headers={"Accept": "text/plain"}).text
        translated_utt = self.translate(joke)
        self.speak(translated_utt)

    @intent_handler("search_joke.intent")
    def handle_search_joke(self, message):
        category = message.data["search"].lower()
        self.log.debug("joke search: " + category)

        # special handling for chuck norris jokes
        if "chuck norris" in category:
            self.chuck_norris_joke()
            return

        # search query should be in english
        tx_category = self.translate(category, "en", self.lang)

        # TODO make singular, https://github.com/MycroftAI/lingua-franca/pull/36
        if tx_category.endswith("s"):
            tx_category = tx_category[:len(tx_category) - 1]

        url = "https://icanhazdadjoke.com/search?term=" + tx_category
        headers = {'Accept': 'text/plain'}
        result = requests.get(url, headers=headers).text.strip()

        if not result:
            self.speak_dialog("no_joke", {"search": category})
        else:
            joke = random.choice(result.split("\n"))
            translated_utt = self.translate(joke)
            self.speak(translated_utt)

    def chuck_norris_joke(self):
        joke = pyjokes.get_joke(category="chuck")
        translated_utt = self.translate(joke)
        self.speak(translated_utt)

    def translate(self, utterance, lang_tgt=None, lang_src="en-us"):
        lang_tgt = lang_tgt or self.lang
        if not lang_tgt.startswith(lang_src.split("-")[0]):
            return self.translator.translate(utterance, lang_tgt, lang_src)
        return utterance.strip()


def create_skill():
    return JokingSkill()
