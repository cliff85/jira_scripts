#!/usr/local/bin/python

from jira.client import JIRA
import base64
import sys

file = open('_jirakey', 'r')
key = file.read()

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

jira_subtask = jira.create_issue(fields={"project":{'key': 'PROPS'}, "summary":summary, "description":description, "issuetype":{"name": "Sub-task Issue"}, 'parent' : { 'id' : key}, "components":[{"name":"PrOps"}],"versions":[{"name":"PrOps"}], "assignee":{"name": assignee}})

print "Jira subtask created %s" % jira_subtask.key
