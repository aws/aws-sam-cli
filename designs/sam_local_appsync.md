`sam local start-graphql-api` command
====================================

The SAM CLI has had options to test REST APIs locally for quite some time. This is very useful to have combined frontend + backend testing done locally in an environment were fullstack developers are working on complete features at once. 
A similar functionality for GraphQL APIs (backed by AppSync) does not exist but could help developers in a very similar way: to test backend and frontend together, locally. 


What is the problem?
--------------------
Testing a GraphQL/AppSync API locally is not possible.

What will be changed?
---------------------
Add a command that works very similar to `sam local start-api` but instead supports an AppSync-backed architecture. 

Success criteria for the change
-------------------------------
Have a command to simply start a GraphQL API based on a Cloudformation/SAM template.

Out-of-Scope
------------
- Any data source except for Lambda
- Any API that's not using Direct Lambda Resolvers (so no Velocity parsing)
- Any API that has the API setup and Lambdas split over multiple templates

User Experience Walkthrough
---------------------------
1. Run `sam local start-graphql-api`
2. Either open the playground or fire GraphQL queries directly to localhost

Implementation
==============

CLI Changes
-----------
Add an extra command (`sam local start-graphql-api`). This does not interfere with any existing command. 

Design
------
The command should behave similarly to the `sam local start-api` command. 

`.samrc` Changes
----------------
No changes

Security
--------
A new dependency is introduced to be able to dynamically run a GraphQL schema on top of Flask: ariadne.

Documentation Changes
=====================

Some chapter should be added to outline this command and it's use-cases. 

Open Issues
============

Task Breakdown
==============

-   \[x\] Send a Pull Request with this design document
-   \[x\] Build the command line interface
-   \[x\] Build the underlying library
-   \[x\] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Run all tests on Windows
-   \[ \] Update documentation
