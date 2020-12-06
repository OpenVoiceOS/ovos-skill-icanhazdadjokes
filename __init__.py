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
from mycroft.messagebus.message import Message
from mycroft.configuration import LocalConf, USER_CONFIG
from mycroft.skills.core import MycroftSkill, intent_handler
from google_trans_new import google_translator
import pyjokes


class JokingSkill(MycroftSkill):
    def __init__(self):
        super(JokingSkill, self).__init__(name="JokingSkill")
        self.translator = google_translator()
        self.tx_cache = {}  # avoid translating twice

    def initialize(self):
        self.blacklist_default_skill()

    def blacklist_default_skill(self):
        # load the current list of already blacklisted skills
        blacklist = self.config_core["skills"]["blacklisted_skills"]

        # check the folder name (skill_id) of the skill you want to replace
        skill_id = "mycroft-joke.mycroftai"

        # add the skill to the blacklist
        if skill_id not in blacklist:
            self.log.debug("Blacklisting official mycroft skill")
            blacklist.append(skill_id)

            # load the user config file (~/.mycroft/mycroft.conf)
            conf = LocalConf(USER_CONFIG)
            if "skills" not in conf:
                conf["skills"] = {}

            # update the blacklist field
            conf["skills"]["blacklisted_skills"] = blacklist

            # save the user config file
            conf.store()

        # tell the intent service to unload the skill in case it was loaded already
        # this should avoid the need to restart
        self.bus.emit(Message("detach_skill", {"skill_id": skill_id}))

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

    def translate(self, utterance, lang_tgt=None, lang_src="en"):
        lang_tgt = lang_tgt or self.lang
        if not lang_tgt.startswith(lang_src):
            if lang_tgt not in self.tx_cache:
                self.tx_cache[lang_tgt] = {}
            if utterance in self.tx_cache[lang_tgt]:
                translated_utt = self.tx_cache[lang_tgt][utterance]
            else:
                translated_utt = self.translator.translate(
                    utterance, lang_tgt=lang_tgt, lang_src=lang_src).strip()
                self.tx_cache[lang_tgt][utterance] = translated_utt
            self.log.debug("translated {src} -- {tgt}".format(
                src=utterance, tgt=translated_utt))
        else:
            translated_utt = utterance.strip()
        return translated_utt


def create_skill():
    return JokingSkill()
