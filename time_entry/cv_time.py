#!/usr/bin/env python

from sqlalchemy import *
from jira.client import JIRA
import base64
import gspread
import sys
import re
from datetime import datetime
import calendar

#####
# Script to Automate time entry
#
###### 

#Passwords
db_password = base64.b64decode("")
db = create_engine('mysql://<user>:%s@<host>/<db>' % db_password)
gspread_password = base64.b64decode('')
gc = gspread.login('', gspread_password)


##########################################
#SQL Queries
#Shared Hours
shared_hours = """
SELECT 
     worklog.`AUTHOR` as User,
     concat(project.pkey,'-',jiraissue.issuenum) AS jiraissue_pkey,
     worklog.timeworked/3600 AS Actual
FROM
     `jiraissue` jiraissue LEFT JOIN `worklog` worklog ON jiraissue.`ID` = worklog.`issueid`
      INNER JOIN `project` project ON jiraissue.`project` = project.`ID`
      INNER JOIN `label` label ON jiraissue.`ID` = label.`ISSUE`
      WHERE
      worklog.`AUTHOR` = :user
      AND worklog.startdate >= :start ' 00:00:00' and worklog.startdate <= :current ' 23:59:59'
      AND((project.`pkey` LIKE 'CVPRO%%') and (LOWER('Shared') IN (SELECT LOWER(LABEL) FROM label WHERE ISSUE = jiraissue.`ID`)))
"""
shared_projects = """
Select 
                group_concat(distinct(jiranumber) separator ', ')
from
                (select
                        concat(project.pkey,'-',issuenum) as jiranumber
                FROM
                     `jiraissue` jiraissue INNER JOIN `worklog` worklog ON jiraissue.`ID` = worklog.`issueid`
                     INNER JOIN `project` project ON jiraissue.`project` = project.`ID`
                     INNER JOIN `label` label ON jiraissue.`ID` = label.`ISSUE`
                WHERE
                     worklog.`author` = :user
                     and (project.`pkey` LIKE 'CVPRO%%')
                     and LOWER(label.`LABEL`) = LOWER('Shared')
                     and worklog.startdate >= :start ' 00:00:00'
                     and worklog.startdate <= :current ' 23:59:59' )JIRA
"""
#Non-Shared Hours
nonshared_hours= """
SELECT
     worklog.`AUTHOR` as User,
     concat(project.pkey,'-',jiraissue.issuenum) AS jiraissue_pkey,
     worklog.timeworked/3600 AS Actual
FROM
                     `jiraissue` jiraissue LEFT JOIN `worklog` worklog ON jiraissue.`ID` = worklog.`issueid`
                     INNER JOIN `project` project ON jiraissue.`project` = project.`ID`
                     LEFT JOIN `label` label ON jiraissue.`ID` = label.`ISSUE`      
WHERE
      worklog.`AUTHOR` = :user
      AND worklog.startdate >= :start ' 00:00:00' and worklog.startdate <= :current ' 23:59:59' 
      AND((project.`pkey` LIKE 'TIME%%' or project.`pkey` LIKE 'PERF%%')
      OR (project.`pkey` LIKE 'CVPRO%%') and (LOWER('Shared') NOT IN (SELECT LOWER(LABEL) FROM label WHERE ISSUE = jiraissue.`ID`) OR label.`LABEL` IS NULL))
"""
#Project Hours
project_hours = """
SELECT
     worklog.`AUTHOR` as User,
     concat(project.pkey,'-',jiraissue.issuenum) AS jiraissue_pkey,
     worklog.timeworked/3600 AS Actual
FROM
                     `jiraissue` jiraissue LEFT JOIN `worklog` worklog ON jiraissue.`ID` = worklog.`issueid`
                     INNER JOIN `project` project ON jiraissue.`project` = project.`ID`
WHERE
      worklog.`AUTHOR` = :user
      AND worklog.startdate >= :start ' 00:00:00' and worklog.startdate <= :current ' 23:59:59'
      and (project.`pkey` NOT LIKE 'TIME%%' and project.`pkey` NOT LIKE 'CVPRO%%' and project.`pkey` NOT LIKE 'PERF%%')
"""
#######################################################################################

#Open google doc and load into a list

"""def query_google():
	sprd_main = gc.open("TMS - JIRA TIME Sync")
	main_sheet = sprd_main.sheet1
	time_entry = {}
	print "Getting data from google spreadsheet...."
	for s,i in zip(main_sheet.col_values(1), main_sheet.col_values(2)):
		if (s != None):
			#print "adding time_entry[%s] = %s" % (s, i)
			time_entry[s] = i
	return time_entry
"""
####Get time entries
#time_entry = query_google()
time_entry = {'FMPRO': 'TIME-11','BPRO': 'TIME-215','TRAC': 'TIME-492','LCTPRO': 'TIME-193','CQPRO': 'TIME-481','SAV': 'TIME-754','LNDT': 'TIME-646'
,'HANESPRO': 'TIME-270','PERF-177': 'TIME-31','PERF-179': 'TIME-51','PERF-180': 'TIME-444','CVPRO': 'TIME-445','TUMIPRO': 'TIME-786','DSG': 'TIME-623'
,'HDPT': 'TIME-674','VFPRO': 'TIME-505','HAL': 'TIME-746','SAVPRO': 'TIME-754','TUMI': 'TIME-696','SBSPRO': 'TIME-801','BPROUP': 'TIME-215','TPC': 'TIME-825'
,'TCP': 'TIME-833','PERF': 'TIME-445'}
def total_hours(*args):
        total = 0
        for i in args:
                if type(i) == list:
                        for v in i:
                                total += v[2]
                else:
                        total += i
        return total


def query_db(user, start, current):
	user_shared_time = []
	user_shared_projects = []
	user_internal_time = []
	user_project_time = []
	db_line=[]
	#print "#####Querying shared hours######"
	db_line = db.engine.execute(text(shared_hours), user=user, start=start, current=current)
	for i in db_line:
		user_shared_time.append(i)
	#print "#####Querying internal time#####"
	db_line=[]
        db_line = db.engine.execute(text(nonshared_hours), user=user, start=start, current=current)
        for i in db_line:
                user_internal_time.append(i)
	#print "#####Querying project time######"
	db_line = []
	db_line = db.engine.execute(text(project_hours), user=user, start=start, current=current)
	for i in db_line:
		user_project_time.append(i)
	#print '####Query shared jiras######'
	db_line = []
        db_line = db.engine.execute(text(shared_projects), user=user, start=start, current=current)
        for i in db_line:
                user_shared_projects.append(i)
	#print user_shared_projects
	#print "####Returning output#########"
#	print user_shared_time
#	print user_internal_time
#	print user_project_time
	total = total_hours(user_shared_time, user_internal_time, user_project_time)
	return user_shared_time, user_internal_time, user_project_time, user_shared_projects, total
def print_time(user, user_shared_time, user_internal_time, user_project_time, total):
	print "'\t\t\t %s \t\t\t'" % user
	print "'\n'\n' Shared \t\t\t\t\t\t' \n' "
	print "'\t Project # \tTime Spent \t\t'"
	print_pretty(user_shared_time) 
	print "'\n' Internal \t\t\t\t\t\t' \n' "
	print_pretty(user_internal_time)
	print "'\n' Project \t\t\t\t\t\t' \n' "
	print_pretty(user_project_time)
	print "'\n'\t\t   TOTAL\t\t%s \t\t'" % total
	if total < 40:
		print "'\n'\t **WARNING YOU ARE UNDER 40 HOURS**"
def insert_time(**kwargs):
	pass
def check_val(val):
        if val in time_entry:
                return time_entry[val]
def check_time(shared, internal, project):
	enter_time = {}
	for i in shared:
		if enter_time.get('TIME-654') is None:
			enter_time['TIME-654'] = i[2]
		else:
			enter_time['TIME-654'] += i[2]
	for i in project:
		check = check_val(i[1])
		check_mod = check_val(i[1].split('-')[0])
		if check:
			if enter_time.get(check) is None:
                        	enter_time[check] = i[2]
			else:
				enter_time[check] += i[2]
		elif check_mod:
                        if enter_time.get(check_mod) is None:
                                enter_time[check_mod] = i[2]
                        else:
                                enter_time[check_mod] += i[2]
	for i in internal:
		check = check_val(i[1])
		check_mod = check_val(i[1].split('-')[0])
		if i[1].split('-')[0] == 'TIME':
			if enter_time.get(i[1]) is None:
                        	enter_time[i[1]] = i[2]
                	else:
                        	enter_time[i[1]] += i[2]
		elif check:
			if enter_time.get(check) is None:
                                enter_time[check] = i[2]
                        else:
                                enter_time[check] += i[2]
		elif check_mod:
			if enter_time.get(check_mod) is None:
				enter_time[check_mod] = i[2]
                        else:   
                                enter_time[check_mod] += i[2] 	
	return enter_time
def print_pretty(list_var):
	for i in list_var:
                tab = "\t" if len(i[1]) > 6 else "\t\t"
                print "' \t  ", i[1],"\t", i[2], tab, "\t\t'"
	
#query_db('cfrasure', '2014-07-20', '2014-07-26')
def pretty_time_var(_dict):
	print 'Time to be entered.....'
	for key, value in _dict.iteritems():
		print "%s : %s" % (key, value)

def jira_enter(user, password, start, end):
	shared, internal, project, project_jiras, total = query_db(user, start, end)
	time_entry = check_time(shared, internal, project)
	jira_password = password
	jira = JIRA(basic_auth=(user, jira_password), options = { 'server': 'https://jira.crossview.inc', 'verify': False } )
	end_s = end.split('-')
	#print end_s
	if_cal = calendar.monthrange(int(end_s[0]), int(end_s[1]))
	if_cal = int(if_cal[1])
	if int(end_s[2]) == if_cal or int(end_s[2]) == (if_cal - 1):
		#If it is the either last day or one more day until last of the month, input previous Sunday. Just taking one day off start date.
		new_date = end
		new_date = datetime.strptime(new_date, '%Y-%m-%d').toordinal()
		sunday = new_date - (new_date % 7)
		new_date = datetime.fromordinal(sunday)
		print new_date
		new_date = new_date.isoformat()
		new_date = new_date + ".937-0500"
		print "Entering on date %s" % new_date
	else:
		#If it is NOT he last day of the month, input on Saturday. Taking 1 day from end date
		day = int(end_s[2]) - 1
		new_date = "%s-%s-%s" % (end_s[0], end_s[1], day)
		new_date = datetime.strptime(new_date, "%Y-%m-%d").isoformat()
		new_date = new_date + ".937-0500"
		print "Entering on date %s" % new_date
	ignoretimes = ['TIME-3', 'TIME-7', 'TIME-9', 'TIME-45', 'TIME-590', 'TIME-720', 'TIME-820', 'TIME-821']
	for key, value in time_entry.iteritems():
		if key == 'TIME-654':
			list_jiras = []
			for i in project_jiras[0]:
				list_jiras.append(i)
			project_jiras = ', '.join(list_jiras)
			print 'adding worklog for %s timespent %sh and comment %s, on %s' % (key,value, project_jiras, new_date)
			jira.add_worklog(issue=key, timeSpent='%sh' % value, started=new_date, comment=project_jiras)
		elif key in ignoretimes:
			print 'ignoring %s entry' % key
		else:
			print 'adding worklog for %s timespent %sh on %s' % (key, value, new_date)
			jira.add_worklog(issue=key, timeSpent='%sh' % value, started=new_date)

def time_return(user, start, end):
	shared, internal, project, project_jiras, total = query_db(user, start, end)
	check_time_var = check_time(shared, internal, project)
	print_time(user, shared, internal, project, total)
	pretty_time_var(check_time_var)
	

#user (for jira) date_start/date_end
if sys.argv[1] == "list":
        if len(sys.argv) == 5:
		r = re.compile('.*-.*-.*')
		if r.match(sys.argv[3]) or r.match(sys.argv[4]):
			time_return(sys.argv[2], sys.argv[3], sys.argv[4])
		else:
			sys.exit('ERROR : Proper date format: 2014-02-20')
        else:
                sys.exit('ERROR : Please use ./time.py list <user> <start> <end>')
elif sys.argv[1] == "post":
	if len(sys.argv) == 6:
                r = re.compile('.*-.*-.*')
                if r.match(sys.argv[4]) or r.match(sys.argv[5]):
                        jira_enter(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
                else:
                        sys.exit('ERROR : Proper date format: 2014-02-20')
        else:
                sys.exit('ERROR : Please use ./time.py list <user> <pass> <start> <end>')
	
else:
        sys.exit('ERROR : Please use ./time.py list or post')
