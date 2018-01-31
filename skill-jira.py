#import pyjira
from jira import JIRA
import os
import re


# Essential initialization and connection establishment.
# TODO: wrap into a try block and have fancy analysis of failure (auth? ping, dns resolve, etc)
#  http://bakjira01.int.bry.com:8080/rest/api/2/
jira = JIRA(server=os.environ['JIRA_SERVER_URL'],basic_auth=(os.environ['JIRA_USER'],os.environ['JIRA_PASSWORD'])) 


inquiry = jira.search_issues('assignee is EMPTY AND status != Resolved ORDER BY createdDate DESC')
if inquiry.total < 1:
    print "No JIRA issues found in the unassigned queue."
else:
    print str( inquiry.total ) + " issues found in the unassigned queue."
    thissue = jira.issue(inquiry[0].key,fields='summary,comment')
    print "Latest issue is regarding: " + re.sub('([fF][wW]:)+','',thissue.fields.summary)


inquiry = jira.search_issues('resolution = Unresolved AND priority > Medium ORDER BY priority DESC')
if inquiry.total < 1:
    print "No HIGH priority JIRA issues remain open."
else:
    print str( inquiry.total ) + " high priority issue" + ('','s')[inquiry.total > 1] + " remain" + ('s','')[inquiry.total > 1] + " open!"
    thissue = jira.issue(inquiry[0].key,fields='summary,comment')
    print "Highest priority issue is regarding: " + re.sub('([fF][wW]:)+','',thissue.fields.summary)

##inquiry = jira.search_issues('assignee=jrw')
##print str( inquiry ) + "__ \n"


##inquiry = jira.issue("BPITS-1796",fields='summary,comment')
##print inquiry.fields
##for comment in inquiry.fields.comment.comments:
##    print comment
#
