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


# Joke collections that a locale ships as its own `<name>_jokes.dialog`. A
# locale reaches one by voice when it ships both `<name>.voc`, to name the
# category, and `<name>_jokes.dialog`, to hold the jokes.
LOCAL_CATEGORIES = ("beauf", "blondes", "dark", "edgy")


class JokingSkill(OVOSSkill):

    def _speak_local_category(self, name: str) -> bool:
        """Speak a line of ``<name>_jokes.dialog``, or return False when this
        locale ships no such dialog.

        A locale that names the category in a ``.voc`` file but ships no
        dialog would otherwise speak the bare dialog key aloud; every locale
        but fr-FR names ``dark`` and ships no ``dark_jokes.dialog``."""
        if f"{name}_jokes" not in self.dialog_renderer.templates:
            return False
        self.speak_dialog(f"{name}_jokes")
        return True

    def _speak_puns(self) -> None:
        """Speak from ``puns.dialog`` when this locale ships one, else fall
        back to ``general_jokes``. Checked against the skill's own
        lang-scoped dialog renderer -- the same object ``speak_dialog``
        renders from -- rather than a filesystem path we test ourselves, so
        a locale with no puns file never speaks the bare key "puns" (which
        is what an unrendered dialog name falls back to) and one that does
        keeps its own pun category rather than losing it to the general
        one."""
        if "puns" in self.dialog_renderer.templates:
            self.speak_dialog("puns")
        else:
            self.speak_dialog("general_jokes")

    @intent_handler("joke.intent")
    def handle_joke(self, message: Optional[Message] = None) -> None:
        category = ((message.data.get("query") if message else None) or "").lower()
        if category:
            self._handle_category(category)
        else:
            self._speak_default_joke()

    def _speak_default_joke(self) -> None:
        # TODO - refactor this once lang support is more uniform
        if self.lang.startswith("pt"):
            self._speak_puns()
        elif self.lang.split("-")[0] in ["cs", "es", "eu", "gl", "hu", "it", "pl", "sv"]:
            self.speak_dialog("dev_jokes")
        else:
            self.speak_dialog("dad_jokes")

    def _handle_category(self, category: str) -> None:
        self.log.debug("joke search: %s", category)

        # TODO self.voc_match more joke types
        # TODO allow blacklisting some categories in settings.json (kid friendly setting by default)
        if self.voc_match(voc_filename="chuck_norris", utt=category, lang=self.lang):
            self.speak_dialog("chuck_norris_jokes")
        elif self.voc_match(voc_filename="dad", utt=category, lang=self.lang):
            self.speak_dialog("dad_jokes")
        elif self.voc_match(voc_filename="programmer", utt=category, lang=self.lang):
            self.speak_dialog("dev_jokes")
        elif self.voc_match(voc_filename="pun", utt=category, lang=self.lang):
            self._speak_puns()
        else:
            for name in LOCAL_CATEGORIES:
                if self.voc_match(voc_filename=name, utt=category, lang=self.lang):
                    if self._speak_local_category(name):
                        return
                    break
            self.speak_dialog("no_joke", {"query": category})
