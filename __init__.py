# Copyright 2018 Justin Warwick and Mycroft AI, Inc.
#
# This file is an extension to Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.


# Visit https://docs.mycroft.ai/skill.creation for more detailed information
# on the structure of this skill and its containing folder, as well as
# instructions for designing your own skill based on this template.


# Import statements: the list of outside modules you'll be using in your
# skills, whether from other files in mycroft-core or from external libraries
from os.path import dirname

from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger
import mycroft.audio
import mycroft.util

from jira import JIRA
import os
import re
import time

__author__ = 'jrwarwick'

# Logger: used for debug lines, like "LOGGER.debug(xyz)". These
# statements will show up in the command line when running Mycroft.
LOGGER = getLogger(__name__)

# The logic of each skill is contained within its own class, which inherits
# base methods from the MycroftSkill class with the syntax you can see below:
# "class ____Skill(MycroftSkill)"


class JIRASkill(MycroftSkill):
    # Constants from the core IP skill
    SEC_PER_LETTER = 0.65  # timing based on Mark 1 screen
    LETTERS_PER_SCREEN = 9.0

    # The constructor of the skill, which calls MycroftSkill's constructor
    def __init__(self):
        super(JIRASkill, self).__init__(name="JIRASkill")
        self.jira = None
        self.project_key = None

    # Establish basic login via jira package interface (RESTful API)
    # RETURN the connection object.
    def server_login(self):
        new_jira_connection = None
        try:
            # TODO: revisit this. null/none/"" ?
            if self.settings.get("url", "") or \
                self.settings.get("username", "") or \
                self.settings.get("password", ""):
                    self._is_setup = True
            else:
                # There appears to be a planned, but so far only stub for this
                # get_intro_message(self)   in docs. So, TODO-one-day?
                self.speak("Please navigate to home.mycroft.ai to establish or "
                           "complete JIRA Service Desk server access configuration.")
        except Exception as e:
            LOGGER.error(e)
        try:
            # Would a config fallback be appropriate?
            #   jira = JIRA(server=os.environ['JIRA_SERVER_URL'],
            #      basic_auth=(os.environ['JIRA_USER'],os.environ['JIRA_PASSWORD']))
            #  http://bakjira01.int.bry.com:8080/rest/api/2/
            # TODO: improve check for rest/api/2 suffix
            # or instruction user to remove.
            # Or actually, is it smarter to require user to give fullpath
            # to rest endpoint? If backwards compatible this makes the skill
            # less brittle.
            server_url = self.settings.get("url", "").strip()
            if server_url[-11:] == 'rest/api/2/':
                self.speak("It seems that you have included the rest api two suffix "
                           "to the server URL. This will probably fail. "
                           "Just the base URL is required.")
                self.speak("Please navigate to home.mycroft.ai to amend "
                           "the JIRA Service Desk server access configuration.")

            new_jira_connection = JIRA(server=self.settings.get("url", ""),
                                    basic_auth=(self.settings.get("username", ""),
                                                self.settings.get("password", ""))
                                    )
        except Exception as e:
            LOGGER.error('JIRA Server connection failure!')
            LOGGER.error(e)

        return new_jira_connection

    # Determine project key (prefix to issue IDs)
    # RETURN string which is project key
    def get_jira_project(self):
            # Probably a bit sloppy to just take the first project from a list
            # but this skill is oriented around a single-project Servie Desk
            # only type install. Caveat Emptor or something.
            # LOGGER.debug("--SELF reveal: " + str(type(self)) + " | " +
            #             str(id(self)) + "  |  " + str(self.__dict__.keys()) )
            return self.jira.projects()[0].key

    # This method loads the files needed for the skill's functioning, and
    # creates and registers each intent that the skill uses
    def initialize(self):
        self.load_data_files(dirname(__file__))

        status_report_intent = IntentBuilder("StatusReportIntent").\
            require("StatusReportKeyword").build()
        self.register_intent(status_report_intent, 
                             self.handle_status_report_intent)

        thank_you_intent = IntentBuilder("ThankYouIntent").\
            require("ThankYouKeyword").build()
        self.register_intent(thank_you_intent, 
                             self.handle_thank_you_intent)

        issue_status_intent = IntentBuilder("IssueStatusIntent").\
            require("IssueStatusKeyword").build()
        self.register_intent(issue_status_intent,
                             self.handle_issue_status_intent)

        raise_issue_intent = IntentBuilder("RaiseIssueIntent").\
            require("RaiseIssueKeyword").build()
        self.register_intent(raise_issue_intent,
                             self.handle_raise_issue_intent)

        contact_info_intent = IntentBuilder("ContactInfoIntent").\
            require("ContactInfoKeyword").build()
        self.register_intent(contact_info_intent,
                             self.handle_contact_info_intent)

        self.jira = self.server_login()
        self.project_key = self.get_jira_project()
        LOGGER.info("JIRA project key set to '" + self.project_key + "'.")


    # The "handle_xxxx_intent" functions define Mycroft's behavior when
    # each of the skill's intents is triggered: in this case, he simply
    # speaks a response. Note that the "speak_dialog" method doesn't
    # actually speak the text it's passed--instead, that text is the filename
    # of a file in the dialog folder, and Mycroft speaks its contents when
    # the method is called.
    def handle_status_report_intent(self, message):
        if self.jira is None:
            LOGGER.info('____' + str(type(self)) + ' :: ' + str(id(self)))
            self.jira = self.server_login()
        else:
            LOGGER.info('JIRA Server login appears to have succeded already.')

        self.speak("JIRA Service Desk status report:")
        inquiry = self.jira.search_issues('assignee is EMPTY AND '
                                          'status != Resolved '
                                          'ORDER BY createdDate DESC')
        if inquiry.total < 1:
            self.speak("No JIRA issues found in the unassigned queue.")
        else:
            self.speak(str(inquiry.total) + " issue" + ('', 's')[inquiry.total > 1] +
                       " found in the unassigned queue.")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Latest issue is regarding: " +
                       re.sub('([fF][wW]:)+', '', thissue.fields.summary))

        inquiry = self.jira.search_issues('status != Resolved AND '
                                          'duedate < now() '
                                          'ORDER BY duedate')
        if inquiry.total < 1:
            self.speak("No overdue issues.")
        else:
            self.speak(str(inquiry.total) + " issue" + ('', 's')[inquiry.total > 1] +
                       " overdue!")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Most overdue issue is regarding: " +
                       re.sub('([fF][wW]:)+', '', thissue.fields.summary))

        inquiry = self.jira.search_issues('resolution = Unresolved '
                                          'AND priority > Medium '
                                          'ORDER BY priority DESC')
        if inquiry.total < 1:
            self.speak("No HIGH priority JIRA issues remain open.")
        else:
            self.speak(str(inquiry.total) + " high priority issue" + ('', 's')[inquiry.total > 1] +
                       " remain" + ('s', '')[inquiry.total > 1] + " open!")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Highest priority issue is regarding: " +
                       re.sub('([fF][wW]:)+', '', thissue.fields.summary))
        # TODO: of these open issues, X are overdue!
        # TODO: SLAs breached or nearly so, if you have that sort of thing.


    # TODO: def handle_how_many_open_issues(self, message):
    # TODO: def handle_how_many_overdue_issues(self, message):
    # TODO: def handle_how_many_open_high_priority_issues(self, message):
    # TODO: def handle_how_many_vip_issues(self, message):
    # TODO: def handle_most_urgent_issue(self, message):

    def handle_thank_you_intent(self, message):
        self.speak_dialog("welcome")

    def handle_issue_status_intent(self, message):
        # TODO: flexibly, and somewhat reliably  detect if user
        # uttered the project name abbrev. prefix and just deal with it.

        #issue_id = re.sub(r'\s+', '', self.get_response('specify.issue'))

        def issue_id_validator(utterance):
            #Confesion: "20 characters" is an arbitrary max in this re
            return re.match(r'^[\s0-9]{1,20}$', utterance)

        def valid_issue_id_desc(utterance):
            return ('A valid issue ID is an integer number, '
                    'I will prefix it with project name abbreviation.'
                    'Let me try again.')

        issue_id = self.get_response(dialog='specify.issue', validator=issue_id_validator, 
                                     on_fail=valid_issue_id_desc, num_retries=3 )
        issue_id = re.sub(r'\s+', '', issue_id)
        LOGGER.info('Attempted issue_id understanding:  "' + issue_id + '"')
        # TODO dialog, gain ID 
        if isinstance(int(issue_id), int):
            self.speak("Hmmm... ok... issue " + 
                       self.project_key + '-' + str(issue_id))
            self.speak("Examining records for latest status on this issue.")
            # TODO lookup issue and report
            try:
                issue = self.jira.issue(self.project_key + '-' + str(issue_id))
                self.speak(issue.fields.summary)
                self.speak(issue.fields.resolution)
                # last update ...
            except Exception as e:
                LOGGER.error('JIRA issue retrieval error!')
                LOGGER.error(e)
        else:
            self.speak('I am afraid that is not a valid issue id number '
                       'or perhaps I misunderstood.')

    def handle_raise_issue_intent(self, message):
        # TODO: pull from settings, but also have some kind of fallback, else.
        self.speak('Unfortunately, I do not yet have the ability to file ' +
                   'an issue record by myself.')
        telephone_number = self.settings.get("support_telephone", "")
        # TODO check and fallback on telephone number
        data = {'telephone_number': telephone_number, 
                'email_address': self.settings.get("support_email", "")}
        self.speak_dialog("human.contact.info", data)

        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(telephone_number)
        time.sleep((self.LETTERS_PER_SCREEN + len(telephone_number)) *
                   self.SEC_PER_LETTER)
        mycroft.audio.wait_while_speaking()
        self.enclosure.activate_mouth_events()
        self.enclosure.mouth_reset()

        # Establish requestor identity
        # Get brief general description
        # Get priority
        # Make a quick search through open 
        # (and perhaps very recently closed) issues,
        #    is this a duplicate issue?
        # Create Issue, read out ticket key/ID (also print it out, 
        # if printer attached;
        #    also IM tech staff, if high priority)

    def handle_contact_info_intent(self, message):
        telephone_number = self.settings.get("support_telephone", "")
        # TODO check and fallback on telephone number
        data = {'telephone_number': telephone_number, 
                'email_address': self.settings.get("support_email", "")}
        self.speak_dialog("human.contact.info", data)

        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(telephone_number)
        time.sleep((self.LETTERS_PER_SCREEN + len(telephone_number)) *
                   self.SEC_PER_LETTER)
        mycroft.audio.wait_while_speaking()
        self.enclosure.activate_mouth_events()
        self.enclosure.mouth_reset()
        
    # The "stop" method defines what Mycroft does when told to stop during
    # the skill's execution. In this case, since the skill's functionality
    # is extremely simple, the method just contains the keyword "pass", which
    # does nothing.
    def stop(self):
        pass


# The "create_skill()" method is used to create an instance of the skill.
# Note that it's outside the class itself.
def create_skill():
    return JIRASkill()
