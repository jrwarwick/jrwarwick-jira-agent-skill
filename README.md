## JIRA
Atlassian JIRA issue inquiry and creation

## Description 
Once configured to connect to your on-premises Atlassian JIRA server with a dedicated service account, Mycroft will be able to answer some simple questions about open issues and allow you to raise a new issue through a dialogue. Your IT service desk will now be staffed even when you are at lunch.

## Examples 
* "Mycroft, how many JIRA issues are open?"
* "Mycroft, raise a new JIRA service request for computer monitor replacement"

## Notes
Initially this will only work with an on-premises, Server edition of JIRA, not the cloud edition. Additional configuration will be necessary, including requisition of a service account and credentials from your JIRA administrator.
Required configuration variables:
* export JIRA_USER=username
* export JIRA_TOKEN=secretpassword
* export JIRA_ORG=


## Credits 
Justin Warwick

