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

from jira import JIRA
import os
import re

__author__ = 'jrwarwick'

# Logger: used for debug lines, like "LOGGER.debug(xyz)". These
# statements will show up in the command line when running Mycroft.
LOGGER = getLogger(__name__)



# The logic of each skill is contained within its own class, which inherits
# base methods from the MycroftSkill class with the syntax you can see below:
# "class ____Skill(MycroftSkill)"
class JIRASkill(MycroftSkill):

    # The constructor of the skill, which calls MycroftSkill's constructor
    def __init__(self):
        super(JIRASkill, self).__init__(name="JIRASkill")
        self.jira = None

    # Establish basic login via jira package interface (RESTful API)
    def server_login(self):
        try:
            if self.settings.get("url", "") or \
                self.settings.get("username", "") or \
                self.settings.get("password", ""):
                    self._is_setup = True
            else:
                self.speak("Please navigate to home.mycroft.ai to establish or complete JIRA Service Desk server access configuration.")
        except Exception as e:
            LOGGER.error(e)
        try:
            #(fallback?)#jira = JIRA(server=os.environ['JIRA_SERVER_URL'],basic_auth=(os.environ['JIRA_USER'],os.environ['JIRA_PASSWORD'])) #  http://bakjira01.int.bry.com:8080/rest/api/2/        
            #TODO: check for rest/api/2 suffix and remove or instruct user to do so.
            self.jira = JIRA(server=self.settings.get("url", ""),basic_auth=(self.settings.get("username", ""),self.settings.get("password", "")) )
            LOGGER.info(self.jira.__dict__)
            LOGGER.info(self.jira)
            #  http://bakjira01.int.bry.com:8080/rest/api/2/
        except Exception as e:
            LOGGER.error('JIRA Server connection failure!')
            LOGGER.error(e)        

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

        self.server_login()


    # The "handle_xxxx_intent" functions define Mycroft's behavior when
    # each of the skill's intents is triggered: in this case, he simply
    # speaks a response. Note that the "speak_dialog" method doesn't
    # actually speak the text it's passed--instead, that text is the filename
    # of a file in the dialog folder, and Mycroft speaks its contents when
    # the method is called.
    def handle_status_report_intent(self, message):
        if self.jira == None:
            server_login()
        else:
            LOGGER.info('JIRA Server login appears to have succeded already.')

        self.speak("JIRA Service Desk status report:")
        inquiry = self.jira.search_issues('assignee is EMPTY AND status != Resolved ORDER BY createdDate DESC')
        if inquiry.total < 1:
            self.speak( "No JIRA issues found in the unassigned queue." )
        else:
            self.speak( str( inquiry.total ) + " issues found in the unassigned queue." )
            thissue = self.jira.issue(inquiry[0].key,fields='summary,comment')
            self.speak( "Latest issue is regarding: " + re.sub('([fF][wW]:)+','',thissue.fields.summary) )

        inquiry = self.jira.search_issues('resolution = Unresolved AND priority > Medium ORDER BY priority DESC')
        if inquiry.total < 1:
            self.speak( "No HIGH priority JIRA issues remain open." )
        else:
            self.speak( str( inquiry.total ) + " high priority issue" + ('','s')[inquiry.total > 1] + " remain" + ('s','')[inquiry.total > 1] + " open!" )
            thissue = self.jira.issue(inquiry[0].key,fields='summary,comment')
            self.speak( "Highest priority issue is regarding: " + re.sub('([fF][wW]:)+','',thissue.fields.summary) )

        #TODO: call external python script instead? 

    def handle_thank_you_intent(self, message):
        self.speak_dialog("welcome")

    def handle_issue_status_intent(self, message):
        self.speak("Please identify the issue by issue ID number.")
        #TODO dialog, gain ID 
        self.speak("Examining records for latest status on this issue.")
        #TODO lookup issue and report

    def handle_raise_issue_intent(self, message):
        self.speak_dialog("human.contact.info")

        

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
