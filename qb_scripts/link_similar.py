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
#
##############
#Make dict to check against
check_dict = {}
#Ignore items in the following check list
check_list = ["HTTPS Certificate", "CronJob"]

for i in clients:
	check_dict[i] = []

def prep_issue(issue):
	sev = 6
	main_issue = ''
	to_link = []
	for i in issue:
		if int(i.fields.priority.name.split(' ')[0]) < sev:
			main_issue, sev  = i.key, int(i.fields.priority.name.split(' ')[0])
	link_issue(main_issue, issue)
 	
def link_issue(main_issue, issue):
        for i in issue:
                if i.key != main_issue:
                        print "Linking %s to %s" % (i.key, main_issue)
			jira.transition_issue(i.key, 11) #Acknowledge issue
			jira.create_issue_link("Reference", i.key,main_issue) #link issue
			jira.transition_issue(i.key, 21, comment="Fired within 15 minutes from %s. Linking and closing this issue" % main_issue,customfield_11930={'id': '11253'})
			#jira.transition_issue(i.key, 71) #close issue


jira_dict = []
def jira_search():
	search_result = jira.search_issues('type = Incident AND project in (%s) AND status not in (Resolved, Closed) AND reporter = pagerduty AND created >= "-15m" ORDER BY createdDate DESC' % clients_print)
	for i in search_result:
		if check_incident(i):
			check_dict[i.key.split('-')[0]].append(i)
		else:
			print "Ignoring", i.key		
	for key, i in check_dict.iteritems():
		if len(check_dict[key]) >= 2:
			prep_issue(check_dict[key])
        return True
def check_incident(issue):
        check_list = ["HTTPS Certificate", "CronJob"]
        for check in check_list:
                if check in issue.fields.summary:
                        return False
        return True

jira_search()
