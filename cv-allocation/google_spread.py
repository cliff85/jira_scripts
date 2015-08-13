#!/usr/bin/env python
from sqlalchemy import *
import gspread
from time import strftime, sleep
from datetime import datetime, timedelta
import re
import sys
import base64
 
##############################
#
#         Not currently in use

"""
def google_create_spreadsheet(name):
        sprd_edit.add_worksheet(name, rows="200", cols="10")
        current_sprd = sprd.worksheet(name)
        current_sprd.update_cell(1, 1, "Work Week")
        current_sprd.update_cell(1, 2, "User")
        current_sprd.update_cell(1, 3, "Time Project")
        current_sprd.update_cell(1, 4, "Actual")

if sys.argv[1] == "allocation":
        if len(sys.argv) == 3:
                date = mod_date(sys.argv[2])
                allocation(date)
                print "allocation works"
        elif len(sys.argv) == 2:
                allocation(False)
        else:
                sys.exit('Please use google_spread.py allocation <date>')

def allocation(date=False):
        if date == False:
                #week = datetime.now().strftime("%m/%d/%Y") #Assuming run on day of
                week = datetime.now()
        else:
                #week = date
                week = datetime.strptime(date, "%m/%d/%Y")
        week_num = week.isocalendar()[1]
        search = '{d.month}/{d.day}/{d.year}'.format(d=week)
        week_col = main_sheet.find(search).col #get the week column
        sprd_edit = gc.open("TMS Week %s" % week_num)
        week_sprdsheet = sprd_edit.worksheet("Allocation")
        row = 2
        attempts =0
        while attempts < 3:
                try:
                        for s in main_sheet.col_values(5)[2:]:
                                week_sprdsheet.update_cell(row, 1, s)
                                print "added %s" % s
                                row +=1
                        break
                except:
                        attempts +=1
        row =2
        attempts =0
        while attempts < 3:
                try:
                        for s in main_sheet.col_values(6)[2:]:
                                week_sprdsheet.update_cell(row, 2, s)
                                print "added %s" % s
                                row +=1
                        break
                except:
                        attempts +=1
        row =2
        for s in main_sheet.col_values(week_col)[2:]:
                try:
                        if '%' in s:
                                s = ((float(s[:-1]) / 100.0)*40)
                except:
                        pass
                week_sprdsheet.update_cell(row, 3, s)
                print "added %s" % s
                row +=1
"""
####################################################################


#####################################################################
#               Credentials
# 
db_password = base64.b64decode("")
gspread_password = base64.b64decode('') 
db = create_engine('mysql://<user>:%s@<host>/<db>' % db_password)
gc = gspread.login('', gspread_password)

#Raw SQL query
searchdata = """
SELECT
     worklog.`AUTHOR` as User,
     concat(project.pkey,'-',jiraissue.issuenum) AS jiraissue_pkey,
     SUM(worklog.timeworked)/3600 AS Actual,
     issuetype.pname as Type,
     jiraissue.summary AS Project_Description
FROM
		     issuetype,
                     `jiraissue` jiraissue LEFT JOIN `worklog` worklog ON jiraissue.`ID` = worklog.`issueid`
                     INNER JOIN `project` project ON jiraissue.`project` = project.`ID`
     WHERE project.`pkey` LIKE 'TIME%%' and worklog.`AUTHOR` = :user and worklog.startdate > :past and worklog.startdate < :current 
     and issuetype.id = jiraissue.issuetype
     Group by jiraissue_pkey
"""

gather_all_time = """
SELECT

     worklog.`AUTHOR` as User, 
     concat(p.pkey,'-',ji.issuenum) AS jiraissue_pkey, 
     SUM(worklog.timeworked)/3600 AS Actual,
     issuetype.pname as Type,
     ji.summary AS Project_Description
FROM
     issuetype,
     `jiraissue` ji INNER JOIN `nodeassociation` na ON ji.`id` = na.`source_node_id`
     INNER JOIN `component` c ON na.`sink_node_id` = c.`id`
     INNER JOIN `project` p ON ji.`PROJECT` = p.`ID`
     LEFT JOIN `worklog` worklog ON ji.`ID` = worklog.`issueid` 
WHERE
     ji.PROJECT = '10270'
     and cname = 'ProAAMS'
     and worklog.startdate > :past 
     and worklog.startdate < :current
     and issuetype.id = ji.issuetype 
Group by Author,jiraissue_pkey
"""
#Open google spreadsheet
sprd_main = gc.open("ProAAMS Team Allocation & Dashboard")
main_sheet = sprd_main.worksheet("Resource Summary")

def query_google():
	users = []
	print "Getting users from main sheet...."
	for s in main_sheet.col_values(4):
        	if (s != None) and (s != "JIRA ID") and (s != "#N/A") and (s not in users):
                	users.append(s) 
	return users

def query_db(past, current):
	users = query_google()
	results = []
	for u in users:
        	db_line = db.engine.execute(text(searchdata), user=u, past=past, current=current)
        	results.append(db_line)
        	db.engine.dispose()

	results1 = db.engine.execute(text(gather_all_time), past=past, current=current)
	searchdata_list=[]
	for r in results:
        	for i in r:
			#SQL objects dont allow item assignment. Assigned to f instead
			f = i[4]
			f = unicode(f, errors='ignore')
                	searchdata_list.append([i[0], i[1], i[2], 'TMS', i[3], f])
	gather_all_time_list = []
	for i in results1:
        	gather_all_time_list.append([i[0], i[1], i[2], 'TMS', i[3], i[4]])

	final_list = [] 
	for i in gather_all_time_list:
		i[5] = unicode(i[5], errors='ignore')
        	if i not in searchdata_list:
			#print "%s not in TMS" % i 
                	i[3] = 'Non-TMS'
			final_list.append(i)
	return searchdata_list + final_list

def get_week(time="None"):
	if time == "None":
		d = datetime.now().toordinal()
		last = d - 6
		sunday = last - (last % 7)
		saturday = sunday + 6
		return datetime.fromordinal(sunday).strftime('%Y-%m-%d 00:00:00'), datetime.fromordinal(saturday).strftime('%Y-%m-%d 23:59:59'), datetime.fromordinal(saturday).isocalendar()[1]
	else:
		time = datetime.strptime(time, '%m/%d/%Y')
                d = time.toordinal() #Input will have to be date(Y, m, d)
                #last = d - 6
                sunday = d - (d % 7)
                saturday = sunday + 6
                return datetime.fromordinal(sunday).strftime('%Y-%m-%d 00:00:00'), datetime.fromordinal(saturday).strftime('%Y-%m-%d 23:59:59'), datetime.fromordinal(saturday).isocalendar()[1]


def jira_search(date="None", TMS_workbook='TMS Actuals'):
	if date != "None":
		past, current, week_num = get_week(date)
	else:
		past, current, week_num = get_week()
	
	sprd_edit = gc.open(TMS_workbook)
        week_sprdsheet = sprd_edit.worksheet("Actuals")
	values_list = week_sprdsheet.col_values(3)
	week_print = 'Week %s' % week_num
	if week_print in values_list:
		sys.exit('ERROR : There is already a %s. Please remove %s entries before running' % (week_print, week_print))
	#We write about 200 rows each week. Check to see if we have enough rows, if not create 200 more
	rows_in_use = len(values_list)
	if (week_sprdsheet.row_count - rows_in_use) < 200:
		print "Adding 200 more rows"
		week_sprdsheet.add_rows(200)
	#Start from last row
	row=(rows_in_use + 1)
	print "Looking up users and adding it to spreadsheet..."
	rows = query_db(past, current)
	attempts = 0
	for item in rows:
		while attempts < 5:
			try:
        			week_sprdsheet.update_cell(row, 1, item[0])
       				week_sprdsheet.update_cell(row, 2, item[1])
				week_sprdsheet.update_cell(row, 3, week_print)
        			week_sprdsheet.update_cell(row, 4, item[2])
				week_sprdsheet.update_cell(row, 5, item[3])
				week_sprdsheet.update_cell(row, 6, item[4])
				week_sprdsheet.update_cell(row, 7, item[5])
				print "added %s" % item[0]
        			row+=1
				attempts=0
				break
			except:
				attempts +=1
				print "There was an error writing to the spreadsheet. We will try a maximum of 5 times"
				if attempts == 5:
					sys.exit('ERROR : Retry failed 5 times')
	return "Complete"
#Put the date into a workable format
def mod_date(date):
	r = re.compile('.*-.*-.*')
	if r.match(sys.argv[2]) is not None:
		n = sys.argv[2].split('-')
		return n[1] + "/" +  n[2] + "/" +  n[0]
	else:
		sys.exit('ERROR : Proper date format: 2014-02-20')

if sys.argv[1] == "actuals":
	if len(sys.argv) == 4:
		date = mod_date(sys.argv[2])
		jira_search(date=date, TMS_workbook=sys.argv[3])
	elif len(sys.argv) == 3:
		date = mod_date(sys.argv[2])
		#print get_week(date)
		jira_search(date=date)
	elif len(sys.argv) == 2:
		jira_search()
		#print get_week("None")
	else:
		sys.exit('ERROR : Please use google_spread actuals <date> <spreadsheet>')
else:
	sys.exit('ERROR : Please use google_spread.py actuals')
