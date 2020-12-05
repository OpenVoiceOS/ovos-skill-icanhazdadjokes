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
from mycroft.messagebus.message import Message
from mycroft.configuration import LocalConf, USER_CONFIG
from mycroft.skills.core import MycroftSkill, intent_handler
from google_trans_new import google_translator


class JokingSkill(MycroftSkill):
    def __init__(self):
        super(JokingSkill, self).__init__(name="JokingSkill")
        self.translator = google_translator()

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
        if not self.lang.startswith("en"):
            joke = self.translator.translate(joke, lang_tgt=self.lang,
                                             lang_src="en")
        self.speak(joke)


def create_skill():
    return JokingSkill()
