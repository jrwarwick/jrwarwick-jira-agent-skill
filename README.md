## JIRA Agent
Atlassian JIRA issue inquiry and creation

## Description 
Once configured to connect to your on-premises Atlassian JIRA server with Service Desk installed and with a dedicated service agent account (i.e., an ordinary JIRA user login with membership in the jira-servicedesk-users group, dedicated to the device), Mycroft will be able to answer some simple questions about open issues and allow you to raise a new issue through a dialogue. Your IT service desk will now be staffed even when you are at lunch. Or service desk technicians can send Mycroft to department status meetings on their behalf. Mycroft can be a part of your technical support team.

## Examples 
* "Mycroft, how many JIRA issues are open?"
* "Mycroft, how many open JIRA issues are overdue?"
* "Mycroft, JIRA status report!"
* _planned for future:  "Mycroft, raise a new JIRA service request for computer monitor replacement"_
* "Mycroft, what is the most urgent service desk issue?"
* "Mycroft, what is the status for issue 22333?"
* "Mycroft, how can I contact help desk staff?"

## Notes
Initially this will only work with an on-premises, Server edition of JIRA, not the cloud edition. Additional configuration will be necessary, including requisition of a [service agent user account](https://confluence.atlassian.com/servicedeskserver/working-on-service-desk-projects-939926440.html) and credentials from your JIRA administrator. 

This skill is oriented around JIRA Service Desk rather than plain old development-oriented JIRA (though it might work with both). Please also note that it assumes a single JIRA Project is active in the server instance.

As of yet, no plans to integrate with the knowledgebase feature of JIRA (which depends upon an Atlassian Confluence installation). However, that would certainly be cool if some kind of reasonably effective chaining or querying could be achieved to have Mycroft diagnose some simple problems via dialog backed by JIRA Service Desk knowledgebase.

Required configuration variables (from settings interface on home.mycroft.ai):
* JIRA Server REST API URL  (just the base URL, do not include the rest/api/2 path suffix)
* Username
* Password 


## Credits 
Justin Warwick

https://github.com/MycroftAI		https://mycroft.ai/

https://github.com/pycontribs/jira	https://pypi.python.org/pypi/jira/

https://www.atlassian.com/software/jira
