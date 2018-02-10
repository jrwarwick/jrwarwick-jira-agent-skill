## JIRA
Atlassian JIRA issue inquiry and creation

## Description 
Once configured to connect to your on-premises Atlassian JIRA server with a dedicated service account, Mycroft will be able to answer some simple questions about open issues and allow you to raise a new issue through a dialogue. Your IT service desk will now be staffed even when you are at lunch.

## Examples 
* "Mycroft, how many JIRA issues are open?"
* "Mycroft, how many open JIRA issues are overdue?"
* "Mycroft, JIRA status report!"
* "Mycroft, raise a new JIRA service request for computer monitor replacement"
* "Mycroft, what is the status for issue 22333?"
* "Mycroft, how can I contact help desk staff?"

## Notes
Initially this will only work with an on-premises, Server edition of JIRA, not the cloud edition. Additional configuration will be necessary, including requisition of a service account and credentials from your JIRA administrator. 

Required configuration variables (from settings interface on home.mycroft.ai):
* JIRA Server REST API URL  (just the base URL, do not include the rest/api/2 path suffix)
* Username
* Password 

--alternative/fallback environment variables:--
* export JIRA_USER=username
* export JIRA_PASSWORD=secretpassword
* export JIRA_SERVER_URL=

This skill is oriented around JIRA Service Desk rather than plain old development-oriented JIRA. Please also note that it assumes a single JIRA Project is active in the server instance.

## Credits 
Justin Warwick

