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
from typing import Optional

from ovos_utils.messagebus import Message
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill


class JokingSkill(OVOSSkill):

    @intent_handler("joke.intent")
    def handle_joke(self, message: Optional[Message] = None) -> None:
        self.speak_dialog("general_jokes")

    @intent_handler("search_joke.intent")
    def handle_search_joke(self, message: Message) -> None:
        category = message.data["search"].lower()
        self.log.debug("joke search: %s", category)

        # TODO self.voc_match more joke types
        # special handling for chuck norris jokes
        if self.voc_match(voc_filename="ChuckNorris", utt=category, lang=self.lang):
            self.speak_dialog("chuck_norris_jokes")
        elif self.voc_match(voc_filename="Dad", utt=category, lang=self.lang):
            self.speak_dialog("dad_jokes")
        elif self.voc_match(voc_filename="Programmer", utt=category, lang=self.lang):
            self.speak_dialog("dev_jokes")
        else:
            self.speak_dialog("no_joke", {"search": category})
