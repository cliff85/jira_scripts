#!/usr/bin/python

from jira.client import JIRA
import base64


#Credentials to auth with Jira
jira_password = base64.b64decode("")
jira = JIRA(basic_auth=('', jira_password), options = { 'server': '', 'verify': False } )

#############
#
# Clients to search for. Did not include HDPT for now
#
clients = ['BPRO', 'CQPRO', 'CVPRO', 'FMPRO', 'HAL', 'HANESPRO', 'LCTPRO', 'LNDT', 'PROPS', 'TRAC', 'TUMIPRO', 'SAVPRO']
clients_print = ', '.join(clients) #Make pretty (remove brackets)
#
#Comment to close the issue with
comment = 'Alert has not fired in the past 2 hrs, issue is being auto closed'
#
##############

def jira_search():
	search_result = jira.search_issues('type = Incident AND project in (%s) AND status = "Action Needed" AND Assignee = Unassigned AND "Incident Source" != Quickbuild  AND reporter = pagerduty AND priority in ("4 - Minor", "5 - Trivial") AND updated <= "-2h" ORDER BY createdDate DESC' %clients_print)
	return search_result
def check_incident(issue):
	check_list = ["HTTPS Certificate", "CronJob"]
	for check in check_list:
                if check in issue.fields.summary:
                        return False 
	return True
for i in jira_search():
	if check_incident(i):
		print i.key, i.fields.summary
		jira.transition_issue(i, 11) #Acknowledge issue
		jira.transition_issue(i, 21) #Resolve issue
		jira.transition_issue(i, 71, comment=comment,customfield_11930={'id': '11250'}) #Close
	else:
		print i.key, "Not closing"
