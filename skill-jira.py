#import pyjira
from jira import JIRA
import os


jira = JIRA(server=os.environ['PYJIRA_URL'],basic_auth=(os.environ['PYJIRA_USER'],os.environ['PYJIRA_TOKEN'])) #  http://bakjira01.int.bry.com:8080/rest/api/2/


inquiry = jira.search_issues('assignee=jrw')
print "search count: " + str( inquiry )


inquiry = jira.issue("BPITS-1796",fields='summary,comment')

print inquiry.fields

for comment in inquiry.fields.comment.comments:
    print comment

