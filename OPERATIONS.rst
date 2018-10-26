PROJECT OPERATIONS
==================


What is AWS SAM CLI
-------------------
``sam`` is the AWS CLI tool for managing Serverless applications written with AWS Serverless Application Model (SAM). 
SAM CLI can be used to test functions locally, start a local API Gateway from a SAM template, validate a SAM 
template, fetch logs, generate sample payloads for various event sources, and generate a SAM project in your 
favorite Lambda Runtime.

Contributors
------------




Communication
=============

* All communications about AWS SAM CLI Development go on slack channel #samdev


Slack
-----

Meetings
--------

Structure

* Every week the sam cli team (a fixed time slot every week) engages in a slack meeting that discusses the following
    * What features are currently being worked on? What is the progress?
    * How are we tracking against next release?
    * Discuss action items from previous meetings
    * Capture minutes of the current meeting and store in the repo.

Logistics

* A sam slack bot starts and stops the meeting in another slack channel #sammeeting and puts out a message on #samdev that a meeting is currently taking place.
* A different member of the sam cli core orchestrates the meeting every week on a rotation basis.

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

Releases
--------
- Release cadence: Every 2 weeks
- Tests should be automatically run for each release
- Changelog should be generated
- Use Milestones to capture what will be included in each release

Development
===========

Design Docs
------------

* All design docs for major features are setup as pull requests that follow below spec:
    * Breakdown of design tasks into separately tagged github isssues that are then referenced in the design doc directly.
    * These issues should be in an ordered checklist, that can be ticked off as when a pull request addressing a particular github issue in the design doc is merged.
    * Issues should be granular enough in isolation to be picked up and worked on in parallel.