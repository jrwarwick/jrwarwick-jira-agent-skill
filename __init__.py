# Copyright 2018 Justin Warwick
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

# Import statements: the list of outside modules you'll be using in your
# skills, whether from other files in mycroft-core or from external libraries
from os.path import dirname

from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger
import mycroft.audio
import mycroft.util

from jira import JIRA, JIRAError
import os
import re
import time
import datetime
import dateutil.parser

__author__ = 'jrwarwick'

# Some general TODO items:
#  - have some more issue key context setting. test it some.
#  - new intent: RequestEscalation/increaseUrgency 
#  - identity guessing utility function. Try some fuzzy matching methods 
#  to see if we can determine if an arbitrary string is probably 
#  "this person" in the directory. could be useful for raising an issue,
#  but possibly also some day some kind of comprehension of issue comments.

# Logger: used for debug lines, like "LOGGER.debug(xyz)". These
# statements will show up in the command line when running Mycroft.
LOGGER = getLogger(__name__)

# The logic of each skill is contained within its own class, which inherits
# base methods from the MycroftSkill class with the syntax you can see below:
# "class ____Skill(MycroftSkill)"


class JIRAagentSkill(MycroftSkill):
    # Constants from the core IP skill
    SEC_PER_LETTER = 0.65  # timing based on Mark 1 screen
    LETTERS_PER_SCREEN = 9.0
    # Special Constants discoverd from Atlassian product documentation
    # omit leading slash, but include trailing slash
    JIRA_REST_API_PATH = 'rest/api/2/'

    class ServerConnectionError(Exception):
        """Simple, basic exception for any incomplete connection to the JIRA
        server. There is no point in trying anything further without an active
        and valid connection.
        """
        def __init__(self, msg):
            self.msg = msg

    # The constructor of the skill, which calls MycroftSkill's constructor
    def __init__(self):
        super(JIRAagentSkill, self).__init__(name="JIRAagentSkill")
        self.jira = None
        self.project_key = None


    def server_login(self):
        """Establish basic login via jira package interface (RESTful API)

        RETURN the connection object.
        """
        new_jira_connection = None
        if self.jira is not None:
            LOGGER.debug("self.jira is not already None, FYI. "
                         "So this is a 're-login'.")
        try:
            # TODO: revisit this to confirm possible initial null/none/"" ?
            if (self.settings.get("url", "") or
               self.settings.get("username", "") or
               self.settings.get("password", "")):
                    self._is_setup = True
            else:
                # There appears to be a planned, but so far only stub for this
                # get_intro_message(self)  in docs. So, TODO-one-day?
                self.speak("Please navigate to home.mycroft.ai to establish "
                           "or complete JIRA Service Desk server access "
                           "configuration.")
                # phrase is slightly different than home.configuration.prompt
                LOGGER.debug("Probably missing part of the critical 3 settings.")
                return None
        except Exception:
            LOGGER.exception("Error while trying to retrieve skill critical settings.")
            return None
        try:
            # Would a config fallback be appropriate?
            #   jira = JIRA(server=os.environ['JIRA_SERVER_URL'],
            #      basic_auth=(os.environ['JIRA_USER'],os.environ['JIRA_PASSWORD']))
            # http://jira01.corpintra.com:8080/rest/api/2/
            # Is there some kind of magical or clever way to
            # discover the current available API revision?
            # Maybe let user know if we are not using it?
            server_url = self.settings.get("url", "").strip()
            if (server_url[0:7].lower() != 'http://' and
               server_url[0:8].lower() != 'https://'):
                self.speak("It seems that you have specified an invalid "
                           "server U-R-L. A valid server U-R-L must include "
                           "the h t t p colon slash slash prefix.")
                self.speak_dialog("home.configuration.prompt")
                raise ValueError("server_url contained invalid URL, missing "
                                 "correct prefix: {server_url}"
                                 .format(server_url=repr(server_url)))
            if server_url.endswith(self.JIRA_REST_API_PATH):
                self.speak("It seems that you have included the rest api 2 "
                           "path in the server URL. This should work fine. "
                           "However, if the API is upgraded, you may need to "
                           "update my record of the endpoint URL.")
                self.speak_dialog("home.configuration.prompt")
                self.speak("If deemed necessary.")
            else:
                if server_url[-1:] != '/':
                    server_url = server_url + '/'
                server_url = server_url + self.JIRA_REST_API_PATH
            LOGGER.debug("Determined server_url is: " + server_url)
            new_jira_connection = JIRA(server=self.settings.get("url", ""),
                                       basic_auth=(self.settings.get("username", ""),
                                                   self.settings.get("password", ""))
                                       )
        except JIRAError as jerr:
            LOGGER.exception("JIRA Server connection failure! ",
                             jerr.text, jerr.status_code)
            LOGGER.info("JIRA Server connection failure! ",
                        jerr.text, jerr.status_code)
            if jerr.status_code == 403 and jerr.text.strip().startswith("CAPTCHA_CHALLENGE"):
                msg = ("JIRA server Login was denied and a captcha requirement "
                       "has been activated. Either login manually via web browser "
                       "to clear it, or request an admin use the 'Reset failed "
                       "login count' control in the User Management Module of "
                       "the Administration console in JIRA.")
                LOGGER.info(msg)
                self.speak(msg)
            else:
                # TODO: examine and detect login failiure due to credentials
                #       (but no captcha barrier installed, yet)
                msg = ("Unexpected connection error, consult tech support." +
                       jerr.text.strip()[0:100])
                LOGGER.debug(msg)
                self.speak(msg)
        except:
            LOGGER.exception("JIRA Server connection failure! (url=" + server_url)
            # TODO: consider: reraise and handle in calling function
            #       instead of return None.
            #
            return None

        return new_jira_connection


    def get_jira_project(self):
        """Determine JIRA project key (for autoamtic prefix to issue IDs)

        RETURN string which is project key
        """
        # Probably a bit sloppy to just take the first project from a list
        # but this skill is oriented around a single-project Servie Desk
        # only type install. Caveat Emptor or something.
        # LOGGER.debug("--SELF reveal: " + str(type(self)) + " | " +
        #             str(id(self)) + "  |  " + str(self.__dict__.keys()) )
        # Another concern: what is the Most Right thing to do here:
        #  check for connection, return None if not connected? or allow
        #  the exception? or check for connection but /throw/ a logical
        #  exception?
        target_project_key = self.settings.get("project_key").strip().upper()
        #TODO: string validation, maybe some validation rules from Atlassian, too?
        #TODO: redo this to throw an exception if not found, refactor calls to this
        #      function to make a little note of that ,then default to 0
        # start with the default...
        project_index = 0
        if target_project_key:
            for pindex, proj in enumerate(self.jira.projects()):
                if proj.key == target_project_key:
                    project_index = pindex
        else:
            LOGGER.info("No JIRA project specified, defaulting to project at index " + project_index)
        return self.jira.projects()[project_index].key


    def establish_server_connection(self):
        """Series of standard actions including login, but a few things
        beyond that any connect or reconnect should try to do. E.g.,
        determine the project short-name/prefix. Thus this should appar
        at the top of almost every intent handler.
        """
        # which is server login, checking for auth failures, sort of
        # handling those and then after that, check for project prefix
        # and fill in or update via get_jira_project then use that at
        # top of the handlers as well as initialize.
        if self.jira is None:  # actually /do/ we want this to be conditional?
            self.jira = self.server_login()
            if self.jira is None:
                LOGGER.debug("self.jira server connection is None after call "
                             "to server_login(). "
                             "Cannot proceed without server connection.")
                self.speak_dialog("server.connection.failure")
                raise self.ServerConnectionError("Call to server_login returned None.")
            else:
                self.project_key = self.get_jira_project()
                LOGGER.info("JIRA project key set to '" + self.project_key + "'.")
                # Maybe an optional announcement of same. 
                # or maybe only announce on init case?
        else:
            # TODO: deeper investigation like maybe header check
            # or a simple issues list call with exception handling
            LOGGER.debug("Although self.jira is not None, strictly speaking"
                         "it could still be pointing to invalid/expired "
                         "connection object.")


    def clean_summary(self, summary_text):
        """Accept a string which is a typical issue record summary text
        which, if coming from a mail thread subject line, needs cleaning.

        RETURN string that is cleaned up of cruft and maybe even a few
        common mispronunciations/abbreviations expanded.
        """
        # since people are sometimes careless and lazy with email subject lines
        # and sending an email in to an automated handler is a common way of
        # raising JIRA issues, we see lots of cruft in the summary lines
        # such as FW: and RE:
        # just have a single standard, flexible inline-string-cleaner.
        # but be careful not to have false positives like:
        #    Require: diagrams and software
        return re.sub("^(([Ff][Ww]:|[Rr][Ee]:) *)*", " ", summary_text.strip())


    def descriptive_past(self, then):
        """Accept a datetime (or parsable string representation of same) as "then"
        to compare with an evaluated now.

        RETURN string which is a speakable, natural clause of form "X days ago"
        """
        # is this "overloading" method pythonic? and/or "GoodProgramming(R)TM"?
        if isinstance(then, basestring):
            then = dateutil.parser.parse(then)
        if then.tzinfo is None:
            then = datetime.datetime(then.year, then.month, then.day, tzinfo=tzlocal())
        ago = datetime.datetime.now(then.tzinfo) - then
        cronproximate = ""
        # TODO: a bit about crossing day boundaries if 22 hours etc ago
        if ago.seconds < 0 or ago.days < 0:
            # TODO: better handle negatives, i.e., when then is in the future.
            if ago.seconds > -14400:
                cronproximate = "in the future, very soon."
            cronproximate = "in the future."
        elif ago.days == 0:
            if ago.seconds < 1500:
                cronproximate = "just minutes ago."
            elif ago.seconds < 7200:
                cronproximate = "today, very recently."
            # TODO: add a elif "late last night" subcase
            else:
                cronproximate = "today."
        else:
            cronproximate = str(ago.days) + " days ago."
        return cronproximate


    def initialize(self):
        """This method loads the files needed for the skill's functioning, and
        creates and registers each intent that the skill uses
        """
        self.load_data_files(dirname(__file__))

        status_report_intent = IntentBuilder("StatusReportIntent").\
            require("StatusReportKeyword").build()
        self.register_intent(status_report_intent,
                             self.handle_status_report_intent)

        issues_open_intent = IntentBuilder("IssuesOpenIntent").\
            require("IssueRecordsKeyword").require("OpenKeyword").build()
            # optional("HowManyKeyword").require("IssueRecordsKeyword").require("OpenKeyword").build()
        self.register_intent(issues_open_intent,
                             self.handle_issues_open_intent)

        issues_overdue_intent = IntentBuilder("IssuesOverdueIntent").\
            require("IssueRecordsKeyword").require("OverdueKeyword").build()
        self.register_intent(issues_overdue_intent,
                             self.handle_issues_overdue_intent)

        most_urgent_issue_intent = IntentBuilder("MostUrgentIssueIntent").\
            require("MostUrgentKeyword").require("IssueRecordKeyword").build()
        self.register_intent(most_urgent_issue_intent,
                             self.handle_most_urgent_issue)

        due_date_for_issue = IntentBuilder("DueDateForIssueIntent").\
            require("DueDate").require("IssueID").build()
            # optional("IssueRecordKeyword").require("DueDate").require("IssueID").build()
        self.register_intent(due_date_for_issue,
                             self.handle_due_date_for_issue)

        issue_status_intent = IntentBuilder("IssueStatusIntent").\
            require("IssueStatusKeyword").build()
        self.register_intent(issue_status_intent,
                             self.handle_issue_status_intent)

        raise_issue_intent = IntentBuilder("RaiseIssueIntent").\
            require("RaiseKeyword").require("IssueRecordKeyword").\
            build()
        self.register_intent(raise_issue_intent,
                             self.handle_raise_issue_intent)

        contact_info_intent = IntentBuilder("ContactInfoIntent").\
            require("ContactKeyword").require("ServiceDeskStaffKeyword").\
            build()
        self.register_intent(contact_info_intent,
                             self.handle_contact_info_intent)

        # self.jira = self.server_login()
        # self.project_key = self.get_jira_project()
        # LOGGER.info("JIRA project key set to '" + self.project_key + "'.")
        try:
            self.establish_server_connection()
        except self.ServerConnectionError:
            LOGGER.info("JIRA project key could not be set, because connection "
                        "was not established. Even if skill loaded, it will "
                        "be NON-functional until configuration is corrected "
                        "and/or service restored.")


    def handle_status_report_intent(self, message):
        """Handle intent for a general, overall service desk status report.
        """
        if self.jira is None:
            try:
                self.establish_server_connection()
            except self.ServerConnectionError:
                LOGGER.debug("Caught connection error exception, "
                             "bailing out of intent.")
                return None
        else:
            LOGGER.info("JIRA Server login appears to have succeded already.")

        self.speak("JIRA Service Desk status report:")
        inquiry = self.jira.search_issues('assignee is EMPTY AND '
                                          'status != Resolved '
                                          'ORDER BY createdDate DESC')
        if inquiry.total < 1:
            self.speak("No JIRA issues found in the unassigned queue.")
        else:
            self.speak(str(inquiry.total) + " issue" + ("", "s")[inquiry.total > 1] +
                       " found in the unassigned queue.")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Latest issue is regarding: " +
                       self.clean_summary(thissue.fields.summary))

        inquiry = self.jira.search_issues('status != Resolved AND '
                                          'duedate < now() '
                                          'ORDER BY duedate')
        if inquiry.total < 1:
            self.speak("No overdue issues.")
        else:
            self.speak(str(inquiry.total) + " issue" + ("", "s")[inquiry.total > 1] +
                       " overdue!")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Most overdue issue is regarding: " +
                       self.clean_summary(thissue.fields.summary))

        inquiry = self.jira.search_issues('resolution = Unresolved '
                                          'AND priority > Medium '
                                          'ORDER BY priority DESC')
        if inquiry.total < 1:
            self.speak("No HIGH priority JIRA issues remain open.")
        else:
            self.speak(str(inquiry.total) + " high priority "
                       "issue" + ("", "s")[inquiry.total > 1] +
                       " remain" + ("s", "")[inquiry.total > 1] + " open!")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Highest priority issue is regarding: " +
                       self.clean_summary(thissue.fields.summary))
        # TODO: SLAs breached or nearly so, if you have that sort of thing.


    def handle_issues_open_intent(self, message):
        if self.jira is None:
            try:
                self.establish_server_connection()
            except self.ServerConnectionError:
                LOGGER.debug("Caught connection error exception, "
                             "bailing out of intent.")
                return None
        else:
            LOGGER.info("JIRA Server login appears to have succeded already.")

        inquiry = self.jira.search_issues('status != Resolved '
                                          'ORDER BY priority DESC, duedate ASC')
        if inquiry.total < 1:
            self.speak("No unresolved issues.")
        else:
            self.speak(str(inquiry.total) + " issue" + ("", "s")[inquiry.total > 1] +
                       " remain unresolved.")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Highest priority unresolved issue is regarding: " +
                       self.clean_summary(thissue.fields.summary))


    def handle_issues_overdue_intent(self, message):
        if self.jira is None:
            try:
                self.establish_server_connection()
            except self.ServerConnectionError:
                LOGGER.debug("Caught connection error exception, "
                             "bailing out of intent.")
                return None
        else:
            LOGGER.info("JIRA Server login appears to have succeded already.")

        inquiry = self.jira.search_issues('status != Resolved AND '
                                          'duedate < now() '
                                          'ORDER BY duedate')
        if inquiry.total < 1:
            self.speak("No overdue issues.")
        else:
            self.speak(str(inquiry.total) + " issue" + ("", "s")[inquiry.total > 1] +
                       " overdue!")
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("Most overdue issue is regarding: " +
                       self.clean_summary(thissue.fields.summary))


    # TODO: def handle_how_many_open_high_priority_issues(self, message):
    # TODO: def handle_how_many_vip_issues(self, message):
    # TODO: def handle_how_many_queue_issues(self, message):
        # stats on named queues. JIRA comes seeded with a few,
        # but maybe make it a param/context/entity
    # TODO: def handle_to_whom_issue_is_assigned(self, message):
    #       or less pedantically : handle_issue_assignee()


    def handle_most_urgent_issue(self, message):
        # this one might need a little more special sauce to it.
        # does something overdue at medium priority exceed
        # explicit high priority? Do we account for VIP factor?
        if self.jira is None:
            try:
                self.establish_server_connection()
            except self.ServerConnectionError:
                LOGGER.debug("Caught connection error exception, "
                             "bailing out of intent.")
                return None
        else:
            LOGGER.info("JIRA Server login appears to have succeded already.")

        inquiry = self.jira.search_issues('status != Resolved '
                                          'ORDER BY priority desc, duedate asc,'
                                          'createdDate asc')
        if inquiry.total < 1:
            self.speak("No unresolved issues found!")
        else:
            thissue = self.jira.issue(inquiry[0].key, fields='summary,comment')
            self.speak("The highest priority issue is " + str(thissue.key) +
                       " regarding: " + self.clean_summary(thissue.fields.summary))
            LOGGER.info("Issue type:  " + ",".join(thissue.__dict__.keys()) )
            LOGGER.info("Issue type:  " + ",".join(thissue.fields.__dict__.keys()) )
            # TODO: strip the proj key prefix, if skill prefs
            #     indicate to do so
            #     str(thissue.key).replace(self.project_key + '-', '')
            self.set_context('IssueID', str(thissue.key))
            # TODO: now establish Context so that if user follows up with:
            #  "when is that issue due?" or "who reported this issue?"  or
            #  "how long ago was this reported?!"
            #  we can give real, useful, accurate, pertinent answers.


    def handle_due_date_for_issue(self, message):
        if self.jira is None:
            try:
                self.establish_server_connection()
            except self.ServerConnectionError:
                LOGGER.debug("Caught connection error exception, "
                             "bailing out of intent.")
                return None
        else:
            LOGGER.info("JIRA Server login appears to have succeded already.")

        issue_id = message.data.get('IssueID')
        if re.match(self.project_key + '-[0-9]+', issue_id):
            pass
        elif isinstance(int(issue_id), int):
            issue_id = self.project_key + '-' + str(issue_id)
        else:
            self.speak("Sorry, I do not seem to have a valid issue I D "
                       "to look for.")
            LOGGER.debug("Will not try to search for issue " + issue_id)
            return None

        LOGGER.debug("Searching for issue " +
                     self.project_key + '-' + str(issue_id))
        try:
            issue = self.jira.issue(issue_id)
            if issue.fields.resolution is not None:
                self.speak("Issue is already yet resolved.")
            if issue.fields.duedate is None:
                self.speak("Issue has no specified due date.")
                # TODO: consult default SLA? heuristics based on report time?
            else:    
                then = dateutil.parser.parse(issue.fields.duedate)
                if then.tzinfo is None:
                    then = datetime.datetime(then.year, then.month,
                                             then.day, tzinfo=tzlocal())
                ago = datetime.datetime.now(then.tzinfo) - then
                cronproximate = ''
                if ago.days < 0:
                    if ago.days > -3:
                        self.speak("This issue is due very soon.")
                elif ago.days == 0:
                    self.speak("This issue is due today!")
                elif ago.days > 0:
                    cronproximate = str(ago.days) + " days."
                    self.speak("This issue is overdue by " + cronproximate)
                self.speak("On " + then)
        except Exception:
            self.speak("Search for further details on the issue record "
                       "failed. Sorry.")
            LOGGER.exception("JIRA issue API error!")


    def handle_issue_status_intent(self, message):
        """Accept additional specification in the form of a JIRA
        Issue ID number to lookup and report highlights of status
        for that particular issue.
        """
        if self.jira is None:
            try:
                self.establish_server_connection()
            except self.ServerConnectionError:
                LOGGER.debug("Caught connection error exception, "
                             "bailing out of intent.")
                return None
        else:
            LOGGER.info("JIRA Server login appears to have succeded already.")

        def issue_id_validator(utterance):
            # Confesion: "20 characters" is an arbitrary max in this re
            return re.match(r'^[\s0-9]{1,20}$', utterance)

        def valid_issue_id_desc(utterance):
            return ("A valid issue I D is an integer number. "
                    "No prefix, if you please. "
                    "I will prefix the issue I D with a predetermined "
                    "JIRA project name abbreviation. "
                    "Let us try again. ")

        # TODO: flexibly/fuzzily, and somewhat reliably detect if user
        # uttered the project name abbrev. prefix and just deal with it.
        issue_id = self.get_response(dialog='specify.issue',
                                     validator=issue_id_validator,
                                     on_fail=valid_issue_id_desc,
                                     num_retries=3)
        if not isinstance(issue_id, basestring):
            LOGGER.debug("issue_id is " + str(type(issue_id)))
        if issue_id is None:
            LOGGER.exception("No valid issue_id from get_response. "
                             "Better to bail out now.")
        issue_id = re.sub(r'\s+', '', issue_id)
        LOGGER.info("Attempted issue_id understanding:  '" + issue_id + "'")
        # TODO if this issue has/had a blocking issue: then examine that issue
        #   for recent resolution. If so, then mention it, and then
        #   offer to "tickle/remind/refresh" this issue
        if isinstance(int(issue_id), int):
            self.speak("Searching for issue " +
                       self.project_key + '-' + str(issue_id))
            try:
                issue = self.jira.issue(self.project_key + '-' + str(issue_id))
                self.speak(self.clean_summary(issue.fields.summary))
                if issue.fields.resolution is None:
                    self.speak(" is not yet resolved.")
                    if issue.fields.duedate is not None:
                        then = dateutil.parser.parse(issue.fields.duedate)
                        if then.tzinfo is None:
                            then = datetime.datetime(then.year, then.month,
                                                     then.day, tzinfo=tzlocal())
                        ago = datetime.datetime.now(then.tzinfo) - then
                        cronproximate = ''
                        if ago.days < 0:
                            if ago.days > -3:
                                self.speak("This issue is due very soon.")
                        elif ago.days == 0:
                            self.speak("This issue is due today!")
                        elif ago.days > 0:
                            cronproximate = str(ago.days) + " days."
                            self.speak("This issue is overdue by " + cronproximate)
                    if issue.fields.updated is None:
                        self.speak("No recorded progress on this issue, yet.")
                    else:
                        cronproximate = self.descriptive_past(issue.fields.updated)
                        self.speak("Record last updated " + cronproximate)
                    self.speak("Issue is at " + issue.fields.priority.name +
                               " priority.")
                    if issue.fields.assignee is None:
                        self.speak("And the issue has not yet been assigned "
                                   "to a staff person.")
                    # linked/related issues check. At least 'duplicates' and
                    # "blocks" although there is a little start here, making
                    # the bad assumption of only one link. a lot TODO here.
                    if (len(issue.fields.issuelinks) and
                        issue.fields.issuelinks[0].type.name.lower() == "blocks"):
                        blocker = issue.fields.issuelinks[0].inwardIssue
                        if blocker.fields.status.name.lower() != "resolved":
                            # TODO: consider dialog file for this one
                            self.speak("Also note that this issue is currently "
                                       "blocked by outstanding issue " +
                                       blocker.key + " " +
                                       self.clean_summary(blocker.fields.summary))
                else:
                    self.speak("This issue is already resolved. ")
                    self.speak(issue.fields.resolution.description)
                    # TODO: "about" should be conditional, 
                    #     descript-past might be "Today". In that case
                    #     the specific date below would also be unneeded.
                    self.speak(" about " +
                               self.descriptive_past(issue.fields.resolutiondate))
                    # give nice, short form of specific date if within
                    # current year, or "January 21st, 2018" if outside
                    # of current year.
                    then = issue.fields.resolutiondate
                    if isinstance(then, basestring):
                        then = dateutil.parser.parse(then)
                    if then.tzinfo is None:
                        then = datetime.datetime(then.year, then.month,
                                                 then.day, tzinfo=tzlocal())
                    if then.year == datetime.datetime.now(then.tzinfo).year:
                        ago = datetime.datetime.now(then.tzinfo) - then
                        if ago.days < 7:
                            self.speak(" just last " + then.strftime('%A'))
                        self.speak(" on " + then.strftime('%B %d'))
                    else:
                        self.speak(" on " + then.strftime('%B %d %Y'))
            except Exception:
                self.speak("Search for further details on the issue record "
                           "failed. Sorry.")
                LOGGER.exception("JIRA issue API error!")
        else:
            self.speak("I am afraid that is not a valid issue id number "
                       "or perhaps I misunderstood.")


    def handle_raise_issue_intent(self, message):
        """Collect enough information to create an issue record,
        then use the JIRA web API to create the issue record.
        """
        if self.settings.get("enable_issue_creation"):
            self.speak("Unfortunately, I do not yet have the ability to file " +
                       "an issue record by myself.")
            # Should interim contact info lines just below just be
            # a call to the function handle_contact_info_intent?
            telephone_number = self.settings.get("support_telephone", "")
            # TODO: pull from settings, but also have some kind of fallback.
            # check and fallback on telephone number
    
            email_address = ' '.join(list(self.settings.get("support_email", "")))
            email_address = email_address.replace('.', 'dot')
            # TODO: once the core pronounce_email method is available,
            # replace this naive spell-out approach
            data = {'telephone_number': telephone_number,
                    'email_address': email_address}
            self.speak_dialog("human.contact.info", data)
    
            self.enclosure.deactivate_mouth_events()
            self.enclosure.mouth_text(telephone_number)
            time.sleep((self.LETTERS_PER_SCREEN + len(telephone_number)) *
                       self.SEC_PER_LETTER)
            mycroft.audio.wait_while_speaking()
            self.enclosure.activate_mouth_events()
            self.enclosure.mouth_reset()
        else:
            # TODO: real raise issue implementation steps:
            # Establish requestor identity
            # Get brief general description
    	# Get error messages, computernames, account names, symptom observation datetimes
            # Get priority  (duedate?)
            # Make a quick search through open
            # (and perhaps very recently closed) issues,
            #   is this a duplicate issue?
            # Create Issue, display and read out ticket key/ID
            #   (also print it out, if printer attached);
            #   set_context() on issue id so if user immediately
            #     afterward want to adjust or get warm fuzzy about it
            #     they can just use pronouns and stuff.
            #   also IM tech staff, if high priority {and IM capability})
            self.speak("Very good. Let us begin by gathering some information.")
            #TODO: make a choice here: we could ask a yes/no question: is this a problem report? vs. is this a requisition?
            #    or we could try fancy intent analysis on the responses... or even assume problems, redirecting requisitions to a working email
            reporter_name = self.get_response(dialog='specify.newissue.reporter_name',
                                         #validator=issue_id_validator,
                                         #on_fail=valid_issue_id_desc,
                                         num_retries=3)
            reporter_name = reporter_name.title()
            #TODO: make a college try to normalize, validate, and lookup this name
            self.set_context('ReporterName', reporter_name)
            issue_summary = self.get_response(dialog='specify.newissue.summary',
                                         #validator=issue_id_validator,
                                         #on_fail=valid_issue_id_desc,
                                         num_retries=3)
            self.set_context('IssueSummary', issue_summary)
            issue_description = self.get_response(dialog='specify.newissue.description',
                                         #validator=issue_id_validator,
                                         #on_fail=valid_issue_id_desc,
                                         num_retries=3)
            self.set_context('IssueDescription', issue_description)
            self.speak("Very good, thank you. I understand that " + reporter_name + " is having a problem with " + issue_summary)
            self.speak("One moment please...")
            LOGGER.debug("--issue types listing in " + self.project_key + "--")
            for x in self.jira.issue_types():
                LOGGER.debug(str(x))
            #LOGGER.debug("createmeta:" + self.jira.createmeta(projectKeys=self.project_key)) ##, projectIds=['TestCase'],expand=None)
            #TODO try the create_customer_request method, right now getting a not valid request type with plain create issue
            #new_issue = self.jira.create_customer_request(project=self.project_key, summary=issue_summary,
            #                       description=reporter_name + ' reports ' + issue_description , issuetype={'name': "Service Request"}) #Remember, this is JSD oriented, and this is the OotB type. Maybe parameterize this default later?
            new_issue = self.jira.create_issue(project=self.project_key, summary=issue_summary,
                                   description=reporter_name + ' reports ' + issue_description , issuetype={'name': "Service Request"}) #Remember, this is JSD oriented, and this is the OotB type. Maybe parameterize this default later?
            LOGGER.info("JIRA issue creation: ", new_issue.key)
            self.set_context('IssueKey', new_issue.key)
            self.speak("Alright, I have created the issue record for you.")
            self.speak("Refer to issue key " + new_issue.key + " for status and updates.")
            #TODO: maybe afix a jira tag for origin (ai voice assistant, instead of collector)? or if not specified, optional description appendix
            #TODO: set the context with the new key, and/or cache it as most recently created key for one hour so that user can say "what was that issue id again?"
            #TODO: followup with one more get_response("would you like to add some contact information in case the service desk staff need to ask some diagnostic questions?") and then append as comment if they would like to.
            #      IFF a successful id on the user, repeat back what the directory says. Optional check for presence of an LDAP skill/setting as well? (one day)
            #TODO: followup with one more get_response("would you like to add any other notes to the issue?") and then append as comment if they thought of one more thing 
            #      (or user noticed that mycroft did /not/ catch the whole final sentence of dictation
            self.enclosure.mouth_text(new_issue.key)


    def handle_contact_info_intent(self, message):
        """Just reply with a summary of key contact information for
        traditional human-to-human voice or text communications.
        """
        telephone_number = self.settings.get('support_telephone', "")
        # TODO check and fallback on telephone number
        data = {'telephone_number': telephone_number,
                'email_address': self.settings.get('support_email', "")}
        self.speak_dialog("human.contact.info", data)

        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(telephone_number)
        time.sleep((self.LETTERS_PER_SCREEN + len(telephone_number)) *
                   self.SEC_PER_LETTER)
        mycroft.audio.wait_while_speaking()
        self.enclosure.activate_mouth_events()
        self.enclosure.mouth_reset()


    def stop(self):
        """The "stop" method defines what Mycroft does when told to stop during
        the skill's execution. In this case, since the skill's functionality
        is extremely simple, the method just contains the keyword "pass", which
        does nothing.
        """
        pass


def create_skill():
    """The "create_skill()" method is used to create an instance of the skill.
    Note that it's outside the class itself.
    """
    return JIRAagentSkill()

