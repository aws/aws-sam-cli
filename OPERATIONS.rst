PROJECT OPERATIONS
==================


What is AWS SAM CLI
-------------------
``sam`` is the AWS CLI tool for managing Serverless applications. SAM CLI supports you through your entire 
workflow of developing a serverless app. It allows you to quickly getting started, develop, test, and debug 
your application locally, build, package, deploy to the cloud, and monitor and troubleshoot a deployed 
application. It supports applications defined using AWS Serverless Application Model (SAM). 


Core Team
---------
SAM CLI project is still small enough that we don't have a official team structure or governance. Therefore "Core Team" simply consists of developers who have commit access to the this Github Repository. They know most about the source code and work on it every day. 


Contributors
------------
We are actively looking for contributors to join the project. You could help us fix bugs, write features, improve documentation or even do Marketing/PR activities. Read the DEVELOPMENT_GUIDE.rst file for information on how to get started. 


Communication
=============


Slack
-----
All communications about AWS SAM CLI Development go on slack channel #samdev. `Join the SAM developers channel (#samdev) on Slack <https://awssamopensource.splashthat.com/>`__ to collaborate with us.

Meetings
--------

Structure
~~~~~~~~~
Every week the core team (a fixed time slot every week) engages in a slack meeting that discusses the following

* What features are currently being worked on? What is the progress?
* How are we tracking against next release?
* Discuss action items from previous meetings
* Capture minutes of the current meeting and store in the repo.

Logistics
~~~~~~~~~

* A Slack bot starts and stops the meeting in another slack channel #sammeeting and puts out a message on #samdev that a meeting is currently taking place.
* A different member of the core team orchestrates the meeting every week on a rotation basis.

Process
=======

Issues Management
-----------------
- Assign Issues to you
- Tag issues with relevant labels


Pull Request Management
-----------------------
- Assign PR to you
- 2 Commiters must approve
- Squash and merge into develop branch
- Merge commit into master branch
- Follow conventional commits for commit messages
- Contributors must complete the PR Checklist before a PR can be merged


Releases
--------
- Release cadence: Every 2 weeks
- Tests should be automatically run for each release
- Changelog should be generated automatically
- Use Milestones to capture what will be included in each release


Development
===========

Design Docs
------------

* All design docs for major features are setup as pull requests that follow below spec:
* Breakdown of design tasks into separately tagged github isssues that are then referenced in the design doc directly.
* These issues should be in an ordered checklist, that can be ticked off as when a pull request addressing a particular github issue in the design doc is merged.
* Issues should be granular enough in isolation to be picked up and worked on in parallel.

Task Breakdown
--------------
Final section of a design document must be breakdown of tasks necessary to implement the design. Once the design document is accepted, create a Github Issue for each task, assign a feature label to the issue, and update the design document with a link to the Issue. This will help any contributor discover and pick up remaining work necessary to complete the feature.


Action Items
============

- [ ] Add a PR Checklist to Pull Request Template (owner?)
- [ ] Add a PR Reviewer checklist to DEVELOPMENT_GUIDE.rst (owner?)
- [ ] Create a Design Document teamplate (owner?)
