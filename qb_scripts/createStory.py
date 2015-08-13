#!/usr/local/bin/python

from jira.client import JIRA
import base64
import sys
import os

#Input Variables
summary = sys.argv[1]
priority = sys.argv[2]
assignee = sys.argv[3]
description = sys.argv[4]
user = sys.argv[5]
password = sys.argv[6]

if len(sys.argv) != 7:
	print "We got %s variables. We need 6" % len(sys.argv)-1
	sys.exit('ERROR : We require 6 variables please use ./createstory.py user pass summary priority assignee description')

#Credentials to auth with Jira
jira = JIRA(basic_auth=(user, password), options = { 'server': '', 'verify': False } )


jira_story = jira.create_issue(fields={"project":{'key': 'PROPS'}, "summary":summary, "description":description, "priority": {"id": priority}, "issuetype":{"name": "Story"}, "components":[{"name":"PrOps"}],"versions":[{"name":"PrOps"}], "assignee":{"name": assignee}})

print "%s has been created" % jira_story.key
try:
	os.remove('_jirakey')
except OSError:
	pass

f = open('_jirakey', 'w+')
f.write(jira_story.key)
f.close()
