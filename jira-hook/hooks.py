import web
import json
import logging
import datetime
import dateutil.parser
from jira.client import JIRA
import sys
import time
from daemon import runner
import base64
import re
import requests
import threading

#Script to update and create tickets using Pagerduty's webhook feature.
#web.py, jira-python, python-dateutil, python-daemon required.

####################################################
####################################################
#
# PagerDuty Client section
# id_dict layout is id_dict[Jira Project][List of alerts associated with them]
id_dict={'BPRO': ['P9S0KPI','PKPSM9M','PA6CJ46','PI4I1Y1', 'PVRLZMA', 'PVRLZMA', 'PDF91WV', 'P725LSF'], 'CQPRO': ['PA7DH49', 'PZYKY3M', 'PKTHA82', 'PL2AJ8P', 'P7X1XIX', 'PICFKO9', 'PO00A10'], 'CVPRO': ['P1EJEMQ', 'PE0EFQO'], 'FMPRO': ['P1UJCJ3', 'PSRRILL', 'P4WUGHI', 'PPPGF06', 'PJ7BWE1', 'P053XJK'], 'HAL': ['P4SCXWR', 'P4SI8MK', 'PSNFO40', 'PSNZZAU', 'PYPEUZL', 'PLAYELX', 'P053XJK'], 'HANESPRO': ['PV8SUNF', 'PK46LLO', 'POJ8U5K', 'PG3PWRI', 'PM5URRP', 'PPKEADR', 'PTIZPOZ'], 'LCTPRO': ['PJ15R26', 'PCWDSEN', 'P0J3TIG', 'P7QVS6C', 'PBNXPN9', 'P22HYZO', 'P8LV4HH'], 'LNDT': ['PNOO9H0', 'PPTA8TT', 'P8HP7E3', 'PY68OL3', 'PQSAN66', 'PSIXVQC', 'POJNMV5'], 'PROPS': ['PNFQGVH'], 'HDPT': ['PB416YR', 'PXV2CKJ', 'PB4QDA9', 'PLLL8CU', 'P2XD823', 'P50AT9Z', 'PUEJBFE'], 'TRAC': ['PE1H18C', 'P5X4AUU', 'PARE16C', 'P2R72Q8', 'PE8Q6KX', 'PGBNS53', 'PKHUCTR', 'P9HFUOM'], 'TUMIPRO': ['PLA05VE', 'PAF33RB', 'PEZ6NW4', 'PBBQSIG', 'PTE98S1', 'PQGTQED', 'PEJH7J4', 'PM2785X', 'PDGAHTE', 'PDYO8DB', 'PL8R7AY', 'POKC6BZ', 'PQ8VSOP'], 'SAVPRO': ['PVXNAWR', 'P7CQYSO', 'PJQ0XNF', 'PYV3V6C', 'PNA6T2Z', 'PMNGRL3', 'PCC0J9W', 'P1ILR7S'], 'SBSPRO': ['P3B1AI3', 'PUTEXZU', 'PI9UUQI', 'P9WAQ5C', 'P1ZW5BK', 'PSS92TO']}
#
#
####################################################


#Credentials to auth with Jira
jira_password = base64.b64decode("")
jira = JIRA(basic_auth=('', jira_password), options = { 'server': '', 'verify': False } )
apikey= ""

#Log API URL
log_url = "https://crossview.pagerduty.com/api/v1/log_entries/"

#Map / to class hooks
urls = ('/.*', 'hooks')
app = web.application(urls, globals())

#Logging information
logger = logging.getLogger('hooks')
hdlr = logging.FileHandler('/home/CROSSVIEW/cfrasure/jira-hook/hook.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.DEBUG)

#We sometimes get multiple posts for the same issue. Unsure if this is a pd bug, but a quick fix is creating a list and checking against past 2 minutes
recent_incidents = []

#Items not currently in use
"""Set labels with issue.update(labels=['AAA', 'BBB'])
def check_service(service, labels):
	if ("Alertsite" in service) and ("Alertsite" not in labels) :
		issue.update(labels=["Alertsite"])
        elif ("Dispatch" in service) and ("Dispatch" not in labels) :
                issue.update(labels=["Dispatch"])
        elif ("Quickbuild" in service) and ("Quickbuild" not in labels) :
                issue.update(labels=["Quickbuild"])
	else:
		print "check_service else error"
"""

#Main Class
class hooks:
	def clean_recent_incidents(self):
		global recent_incidents
		if len(recent_incidents) > 0:
			for sub in recent_incidents:
				if sub[2] < datetime.datetime.now()-datetime.timedelta(minutes=2):
					logger.debug('Removing %s from recent_incidents' % sub)
					recent_incidents.remove(sub)

	def request_email(self,log_url, apikey, log_id, version):
		#Grab E-mail from pagerduty based on log id
		logger.debug('Using %s%s' % (log_url,log_id))
		r = requests.get(log_url + log_id, headers={'Authorization': 'Token token=%s' % apikey, 'Content-type': 'application/json'}, params= {"include[]": "channel"},verify=False,)
		#Make it easier to handle
		data = json.loads(r.text)['log_entry']['channel']['body']
		logger.debug('version = %s' % version)
		if version == "Hyperic":
                	#Click the link to go to alert currently firing
                	al_firing = re.search(r'https://monitoring.crossview.com/alerts(.+?)*\n', data).group(0)
                	#Direct link to resource firing alert
        		al_direct = re.search(r'https://monitoring.crossview.com/ResourceCurrentHealth(.+?)*\n', data).group(0)
			#Grab all of the addional info
                	if "Additional Information:" in data:
				ad_info = re.search(r'Additional Information(.+?)\n\n\n', data, re.DOTALL).group(0)
			else:
				ad_info = re.search(r'ALERT DETAIL(.+?)\n\n\n', data, re.DOTALL).group(0)
                	return al_firing, al_direct, ad_info
		else:
			return data
	def check_recent_incidents(self, incident, type):
		self.clean_recent_incidents()
		global recent_incidents
		if len(recent_incidents) > 0:
			for sub in recent_incidents:
				if sub[0] == incident and sub[1] == type:
					logger.debug('IGNORING since there has already been this even in the past 2 minutes : %s' % sub)
					return True
			logger.debug('No recent incidents for %s' % incident)
                	logger.debug('Adding current incident')
			recent_incidents.append([incident, type, datetime.datetime.now()])
			return False
		logger.debug('No recent incidents for %s' % incident)
		logger.debug('Adding current incident')
		recent_incidents.append([incident, type, datetime.datetime.now()])
		return False
	def jira_search(self, pager_id):
		logger.info('Searching for %s' % pager_id)
		search_result = jira.search_issues('summary~"\\" %s\\"" and reporter = currentUser() order by created' % pager_id)
		return search_result
	def create_issue(self, project, summary, description, version, priority, log_id):
		logger.debug('@ create_issue before try')
		try:
			if version == 'Hyperic':
				al_firing, al_direct, ad_info = self.request_email(log_url, apikey, log_id, version)
				description = description + " \nAlert currently firing : %s\n Link to resource firing: %s\n Resources  %s" % (al_firing, al_direct, ad_info) 
			elif version == 'AlertSite':
				data = self.request_email(log_url, apikey, log_id, version)
				description = description + "\n%s" % data
			logger.info('Creating issue for project: %s summary: %s version: %s priority: %s' % (project, summary, version, priority))
			jira_issue = jira.create_issue(fields={"project":{'key': project}, "summary":summary, "description":description, "priority": {"id": priority},"customfield_11931": {"value": version}, "issuetype":{"id": "59"}})
			d = datetime.datetime.now().isoformat()
			now = d[:-4] + "-0400"
			logger.info('Updating %s to %s' % (jira_issue, now))
			jira_issue.update(customfield_12131=now)
			return
		except:
			logger.exception('')
		return
	def HDPT_issue(self, project, summary, description, version, priority, log_id):
                logger.info('DEBUG: @ HDPT_issue before try')
		try:
			if version == 'Hyperic':
                                al_firing, al_direct, ad_info = self.request_email(log_url, apikey, log_id, version)
                                description = description + " '\nAlert currently firing : %s\n Link to resource firing: %s\n Resources  %s" % (al_firing, al_direct, ad_info)
                        elif version == "AlertSite":
				data = self.request_email(log_url, apikey, log_id, version)
				description = description + "\n%s" % data	
                        logger.info('Creating issue for project: %s summary: %s version: %s priority: %s' % (project, summary, version, priority))
                        return jira.create_issue(fields={"project":{'key': project}, "summary":summary, "description":description, "priority": {"id": priority},"customfield_10290": version, "issuetype":{"name": "Task"}, "versions": [{"name": "Production Support"}], "components":[{"name": "Monitoring-Alerting"}]})
                except:
                        return logger.exception('')
	def update_issue(self, issue_id, comment):
		logger.info('Commenting on issue: %s, %s' % (issue_id, comment))
		jira.add_comment(issue_id, comment)
	def check_linked(self, project, summary):
		search_open = jira.search_issues('type = Incident AND project = %s AND status not in (Resolved, Closed) AND updated >= "-120m"' % project)
		#logger.info('search_open: %s' % search_open)
		if search_open:
			for i in search_open:
				search_linked = jira.search_issues('issue in linkedIssues(%s)' % i.key)
				#logger.info('search_linked %s' % search_linked)
				if search_linked:
					for s in search_linked:
						if s.fields.summary.startswith(summary):
							logger.info('Updating %s linked issue %s' % (i, s))
							self.update_issue(i, "%s : %s alert is still firing" % (s.key, summary))
							logger.info('%s is updating main key %s' % (s, s.key))
							self.update_issue(s,  "%s : alert is still firing" % i.key)
							return True
		logger.debug('Returned False')
		return False 
			
	def check_service(self, service):
		sev1 = "1 - Blocker"
		sev2 = "2 - Critical"
		sev3 = "3 - Major"
		sev4 = "4 - Minor"
		sev5 = "5 - Trivial"
        	if "Alertsite" in service:
                	return "AlertSite", sev3
        	elif "Dispatch" in service:
               		return "Dispatch", sev3
                elif "Hyperic Site Down" in service:
                        return "Hyperic", sev1
        	elif "Quickbuild" in service:
                	return "Quickbuild", sev3
		elif "Hyperic" in service:
			return "Hyperic", sev3
		elif "Test" in service:
			return "Quickbuild", sev3
		elif " Prod" in service:
			return "Hyperic", sev4
		elif "Non-Prod" in service:
			return "Hyperic", sev5
		elif "Hybris Cronjobs Ticket" in service:
			return "Quickbuild", sev4
		elif "Hybris Cronjobs Callout" in service:
			return "Quickbuild", sev3
                elif "Hybris Cronjobs Critical" in service:
                        return "Quickbuild", sev2
                elif "Log Event Critical" in service:
                        return "Hyperic", sev2
		elif "Log Event" in service:
			return "Hyperic", sev3
        	else:
                	logger.error("check_service else error: %s" % service)
			logger.error(data)
# When page is loaded, check this issue. (Used for Hyperic Alerting)
	def GET(self):
		issue = jira.issue('TIME-654')
                return issue.fields.assignee
# Handles POST's then creates or updates issues. 
	def POST(self):
		global app
		data = web.data()
		data1 = json.loads(data)["messages"]
		#Tell pagerduty 'OK' that we received their post then send it to HANDLE to process
		#if wait_var > datetime.datetime.now()-datetime.timedelta(seconds=3):
		#thread = threading.Thread(target=self.MANAGE_POST, args=(data1,))
		app.add_processor(self.MANAGE_POST(data1))
		return web.ok 
			 
	def MANAGE_POST(self, data1):
		#Handle information from post
		#Pagerduty at times will send two api posts at once. Therefore we need to go through each of them.
		for d in data1:
			#Variables
			logger.info('Checking incident: %s' % d["data"]["incident"]["id"])
			type = d["type"]
			incident = d["data"]["incident"]["id"]
			pagerduty_url = d["data"]["incident"]["html_url"]
			service_summary = d["data"]["incident"]["trigger_summary_data"]["subject"]
			escalation_policy = d["data"]["incident"]["escalation_policy"]["name"]
			service_name = d["data"]["incident"]["service"]["name"]
			trigger_details_html_url = d["data"]["incident"]["trigger_details_html_url"]
			log_id = trigger_details_html_url.split('/')[-1]
			service_id = d["data"]["incident"]["service"]["id"]
			version, priority_s = self.check_service(service_name)
			priority = priority_s.split(' ')[0]
			service_s = ""
			if self.check_recent_incidents(incident, type) == True:
				return 'OK'
			if service_summary.startswith("[HQ]"):
				for n in service_summary.split("- ")[2:]:
					service_s += n
			else:
				service_s = service_summary
			description ="PagerDuty has created an alert for %s. \nPagerDuty Incident Log : %s" % (service_summary, pagerduty_url)
			project = None
			# Check if it is a project we want to monitor
			for key, value in id_dict.iteritems():
				if service_id in value:
					project = key
			#Create ticket when Pagerduty receives an alert
			#we create Tasks for HDPT and Incidents for everyone else
			jira_type = 'Task' if project == 'HDPT' else 'Incident'
			#HDPT uses grouping vs everyone else using Incident Source
			search_version = 'Grouping ~' if project == 'HDPT' else '"Incident Source" ='
			#
			# Non-Prod and Prod Alerts - Sev 4 and 5
			#
			if type == "incident.trigger" and priority in ("2", "4", "5"):
				if self.check_linked(project, service_s):
					return 'Linked Issue'
				now = datetime.datetime.now().strftime('%m-%d-%Y %H:%M:%S')
				logger.info('Searching project : %s description: %s type: %s status not in (closed, resolved) and priority in (2,4,5)' % (project, service_s, jira_type))
				jira_issue = jira.search_issues('project = %s AND description ~ "\\"%s\\"" AND type = %s AND status not in (Closed, Resolved) AND priority in (4,5) ORDER BY created' % (project, service_summary, jira_type))
				if jira_issue and project != 'HDPT' and ("Log Event" or "CronJob") not in service_s :
					logger.info('Already an open incident %s. Marking as still firing.' % jira_issue[0])
					#jira uses time format YYYY-MM-DDThh:mm:ss.sTZD. Therefore take the iso format, gives us YYYY-MM-DDThh:mm:ss.ssssss. Cut back 4 microseconds 
					#and add -0400(EST) time 
					d = datetime.datetime.now().isoformat()
					now = d[:-4] + "-0400"
					logger.info('Updating %s to %s' % (jira_issue[0], now))
					jira_issue[0].update(customfield_12131=now)
				elif jira_issue and project == 'HDPT':
					logger.info('Already an open incident %s. Marking as still firing.' % jira_issue[0])
					self.update_issue(jira_issue[0], "Hyperic alert still firing via PagerDuty")
				else:
					logger.info('Creating new issue')
					if project == "HDPT":
						return self.HDPT_issue(project, "%s - %s : %s" % (service_s, time.strftime("%X"), incident), description, version, priority, log_id)
					else:
						return self.create_issue(project, "%s - %s : %s" % (service_s, time.strftime("%X"), incident), description, version, priority, log_id)
			#
			#  On-Call production alerts. Sev 3
			#
			elif type == "incident.trigger" and priority in ("1", "3"):
				if self.check_linked(project, service_s):
                                        return 'Linked Issue'
				logger.debug('Searching project: %s version: %s priority_s: %s jira_type: %s' % (project,version, priority_s, jira_type))
				jira_issue = jira.search_issues('project = %s and type = %s and reporter = pagerduty and %s %s and priority = "%s" order by created' % (project, jira_type, search_version, version, priority_s))
				#logger.debug('jira_issue returned %s' % jira_issue[0])
				now = datetime.datetime.now().strftime('%m-%d-%Y %H:%M:%S')
                                FMT = '%m-%d-%Y %H:%M:%S'
				check_list = ["Action Needed", "In Progress", "Resolved"]
				if jira_issue:
					if project == 'HDPT':
                                        	incident_created = dateutil.parser.parse(jira_issue[0].fields.created).strftime('%m-%d-%Y %H:%M:%S')
                                	else:
                                        	logger.info('Parsing %s' % jira_issue[0].key)
						if jira_issue[0].fields.customfield_12131:
							incident_created = dateutil.parser.parse(jira_issue[0].fields.customfield_12131).strftime('%m-%d-%Y %H:%M:%S')
						else:
							logger.info('%s returned false, parsing by created date instead' % jira_issue[0].key)
							incident_created = dateutil.parser.parse(jira_issue[0].fields.created).strftime('%m-%d-%Y %H:%M:%S')
					#get difference now and last ticket created
                                	jira_diff = (datetime.datetime.strptime(now, FMT) - datetime.datetime.strptime(incident_created, FMT))
                                	jira_status = jira_issue[0].fields.status.name

				else:
					logger.info('Unable find date of previous ticket, probably first ticket created')
                                        jira_diff = datetime.timedelta(5, 25) # No ticket found, force to else
                                        jira_status = "None"
				#If the difference is less than 2 hours and still set to Open
				if (jira_diff <= datetime.timedelta(hours=1)) and (jira_status in check_list):
					logger.info('Less than 1 hour update current %s' % jira_issue[0])
					if incident not in jira_issue[0].fields.summary:
						if jira_issue[0].fields.status.name == "Resolved":
							jira.transition_issue(jira_issue[0], 121)
						jira_issue[0].update(summary=jira_issue[0].fields.summary + " " + incident, description=jira_issue[0].fields.description + "\n\nLinked escalation because it was within 1 hour\n\n" + description)
					else:
						logger.info('This incident %s has already been added, ignoring!' % incident )
				elif jira_diff > datetime.timedelta(hours=2) or (jira_status not in check_list):
					logger.info('Greater than 2 hours create new ticket')
					if project == "HDPT":
						return self.HDPT_issue(project, "%s - %s : %s" % (service_s, time.strftime("%X"), incident), description, version, priority, log_id)
					else:
						return self.create_issue(project, "%s : %s - %s" % (service_s, time.strftime("%X"), incident), description, version, priority, log_id)
				else:
					logger.error("Error firing in Incident Trigger")
					logger.error(data1) 
			#	Search and update ticket when acknowledged
			elif type == "incident.acknowledge":
				try:
					jira_user = d["data"]["incident"]["assigned_to_user"]["name"]
					result = self.jira_search(incident)
					jira_email = d["data"]["incident"]["assigned_to_user"]["email"]
					jira_username = jira_email.split('@')[0]  #split at @ and take the first part
					if project == "HDPT":
                                                if result[0].fields.status.name == "Open":
                                                        jira.transition_issue(result[0], 871) #Start progress
                                        else:   
                                                if result[0].fields.status.name == "Action Needed":
                                                        jira.transition_issue(result[0], 11)
					jira.assign_issue(result[0], jira_username)
					self.update_issue(result[0], "Issue acknowledged via PagerDuty by: %s" % jira_user)
				except:
					logger.exception('')
					logger.error(data1)
			#Search and update ticket when resolved
			elif (type == "incident.resolve") and ("Prod" not in service_name):
				try:
					jira_email = d["data"]["incident"]["resolved_by_user"]["email"]
					jira_username = jira_email.split('@')[0]  #split at @ and take the first part
					jira_user = d["data"]["incident"]["resolved_by_user"]["name"]
					result = self.jira_search(incident)
					if project == "HDPT":
						if result[0].fields.status.name == "Open":
							jira.transition_issue(result[0], 5) #Resolve 
						if result[0].fields.status.name == "Assigned":
							jira.transition_issue(result[0], 851) #Stop progress
							jira.transition_issue(result[0], 5) #Resolve
					else:
						if result[0].fields.status.name == "Action Needed": 
                                			jira.transition_issue(result[0], 11)
							jira.transition_issue(result[0], 21)
						else:
							jira.transition_issue(result[0], 21)
						jira.assign_issue(result[0], jira_username)
					self.update_issue(result[0], "Issue resolved via PagerDuty by: %s" % jira_user)
				except:
					logger.exception('')
					logger.error(data1)
			elif type == "incident.unacknowledge":
				try:
					jira_user = d["data"]["incident"]["assigned_to_user"]["name"]
					result = self.jira_search(incident)
					self.update_issue(result[0], "Issue unacknowledged via PagerDuty : %s" % jira_user)
				except:
                                        logger.exception('')
                                        logger.error(data1)
			elif type == "incident.assign":
				try:
                                        jira_user = d["data"]["incident"]["assigned_to_user"]["name"]
					jira_email = d["data"]["incident"]["assigned_to_user"]["email"]
					jira_username = jira_email.split('@')[0]  #split at @ and take the first part
                                        result = self.jira_search(incident)
                                        if result[0].fields.status.name == "Action Needed":
                                                jira.transition_issue(result[0], 11)
                                        jira.assign_issue(result[0], jira_username)
                                        self.update_issue(result[0], "Issue assigned to %s via PagerDuty" % jira_user)
                                except:
                                        logger.exception('')
                                        logger.error(data1)	
			elif type == "incident.escalate":
				jira_user = d["data"]["incident"]["assigned_to_user"]["name"]
				jira_esc = d["data"]["incident"]["number_of_escalations"]
				result = self.jira_search(incident)
				self.update_issue(result[0], "Issue escalated via PagerDuty to: %s. %s Escalation" % (jira_user, jira_esc))
			elif type == "incident.delegate":
				result = self.jira_search(incident)
			elif (type == "incident.resolve") and ("Prod" in service_name):
				logger.debug('incident resolve: %s is being ignored' % incident)
				pass #do nothing with resolved issues from Prod tickets
			else : 
				logger.error("Error at end of POST: %s" % data1)
		return 'OK'
#Class to run as daemon
class app_daemon():

    def __init__(self):
	#Ignore stdout. Set to /dev/tty to debug
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/null'
        self.stderr_path = '/dev/null'
        self.pidfile_path =  '/var/run/jira-hook/hooks.pid'
        self.pidfile_timeout = 5

    def run(self):
	urls = ('/.*', 'hooks')
	app = web.application(urls, globals())
        while True:
                if __name__ == '__main__':
			#run on ip 10.251.0.41 and port 444
                        web.httpserver.runsimple(app.wsgifunc(), ("10.251.0.41", 444))
                        app.run()
                time.sleep(10)
appdaemon = app_daemon()
daemon_runner = runner.DaemonRunner(appdaemon)
#keep steam open for log file
daemon_runner.daemon_context.files_preserve=[hdlr.stream]
daemon_runner.do_action()

