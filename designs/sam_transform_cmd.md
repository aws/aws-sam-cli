Design Document for sam transform command
====================================

What is the problem?
--------------------
Currently when working with SAM templates and using AWS SAM CLI, getting a transformed version of the file is only able to be done using the command `sam validate --template {name_of_template} --debug`. The validate command also limits some users from working locally or without wifi as AWS credentials are required to run. It also returns more information to assist with debugging the template which is not needed to solve our current situation. To help solve this problem a command named `transform` would need to be implemented so that a developer is able to retrieve the SAM template without using their AWS credentials. Also the command must only return the template and not other information regarding validation or processes. 

What will be changed?
---------------------
No functional changes will be made to SAM, as we are only adding a command to the CLI. This command uses already implemented methods from SAM translator, and all changes to `aws-sam-cli` are additions to current repository and do not interfere with any preexisting commands. 

Success criteria for the change
-------------------------------
If the implementation is successful users will be able to return just the transformed template to the CLI or a text file without affecting the usage of any other commands. 

Out-of-Scope
------------
The command integration takes the functionality from SAM translator and adds its implementation to the transform command. This only gives this command access to the transformed template and any deeper template information will be relayed to the validate command. 

User Experience Walk-Through
---------------------------
##### If you are looking to view the transformed template follow this order: 

1 - Verify that you are in the directory of the template
2 - run the command `sam transform --template {name_of_template}`
3 - This will return the transformed template to the CL

##### If you are looking to retrieve the transformed template follow this order: 

1 - Verify that you are in the directory of the template
2 - run the command `sam transform --template {name_of_template} >> {name_of_file}.json`
3 - This will return the transformed template to the text file


Implementation
==============

CLI Changes
-----------

All changes to the CLI are additions as there is no affected code that exists. It has been added to the `-h` command statement and comes with its own description. Similar to the validate command it requires a `--template` command to be paired with transform for it to run properly. 

### Breaking Change

There are no breaking changes added to the CLI that are known.

Design
------

This feature is implemented as its own command in the sam CLI. That will include addition of a command directory in `samcli/commands/.`, addition of a needed method in `samcli/commands/validate/lib/sam_template_validator.py` to access the SAMtranslator, and added unit and integration tests. Functionality of our command is derived by accessing the `samtranslator.translate()` method. This method will take in a current template and outputs the transformed template to a variable. When this variable is returned we are able to echo it the command line. Added a singular method to the SamTemplateValidator Class and importing the class to our command gives it the ability to perform the transformation. As for bypassing the need to have present AWS credentials, The `managed_policy_map` the reason for the requirement of these credentials, replacing it with a string labeled 'local transformation' will allow you negate the need and perform a transformation.


**SamTemplateValidator Method Below**

 ``` python
def create_template(self):
    sam_translator = Translator(
        managed_policy_map='Local_transformation',
        sam_parser=self.sam_parser,
        plugins=[],
        boto_session=self.boto3_session,
    )
    self._replace_local_codeuri()
    self._replace_local_image()
    try:
        template = sam_translator.translate(sam_template=self.sam_template, parameter_values={})
        return (yaml_dump(template))
    except InvalidDocumentException as e:
        raise InvalidSamDocumentException(
            functools.reduce(lambda message, error: message + " " + str(error), e.causes, str(e))
        ) from e
 ```
`.samrc` Changes
----------------

No changes to samrc are required.

Security
--------

*This addition of this command does not affect security of the aws sam cli, as no new dependencies are added to the repository.*

*No new dependencies are created, no docker images are used, no folders are temporarily created, and no HTTP endpoints or APIs are accessed.* 


What is your Testing Plan (QA)?
===============================

Goal
----
The testing that we have set into place is there to test the usage and accuracy of our `transform` command. This includes two unit tests and 2 integration tests that will touch on various situations that a user might face when running `transform`. 

Pre-requesites
--------------
There are no pre-requesites that are needed for testing as all templates and tests have been added to the repository. 

Test Scenarios/Cases
--------------------
###### Unit Test Scenarios
For our unit tests we will be testing how our command responds to 2 separate scenarios. One being if the template is missing or not in the specified path that the user gives. The other being if the path to the file is valid, it will test that the `_read_sam_file` function returns the expected parsed file. 

**Command to run unit tests**

``` python
python -m unittest tests/integration/transform/test_transform_command.py
```

*code for testing below*
 ``` python
class TestTransformCli(TestCase):
    # Testing if the path to the file is not valid
    @patch("samcli.commands.transform.transform.click")
    @patch("samcli.commands.validate.validate.os.path.exists")
    def test_file_missing(self, path_exists_patch, click_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = False

        with self.assertRaises(SamTemplateNotFoundException):
            _read_sam_file(template_path)

    @patch("samcli.yamlhelper.yaml_parse")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate.os.path.exists")
    def test_file_parsed(self, path_exists_patch, click_patch, yaml_parse_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = True

        yaml_parse_patch.return_value = {"a": "b"}

        actual_template = _read_sam_file(template_path)

        self.assertEqual(actual_template, {"a": "b"})
```

###### Integration Test Scenarios
For our integration tests we will be testing how our command performs when given different templates. The first two templates are identical Cloudformation templates but in two different formats (*.yaml* and *.json*). The first test will run these templates through our `transform` command and check that the expected return file is sent to the command line. If this is properly executed then the unit test will return an `ok.` status to the command line. The next integration test if done using a pre-made flawed template. When ran through our testing it will throw an error which will return the return code of 1. This is the expected behavior and if done properly will also return a status of `ok.` to the command line. 

**Command to run integration tests**
 ``` python
python -m unittest tests/unit/transform/test_cli.py
```
*code for testing below*
 ``` python
    ## test for checking a valid template transformation
    def test_transformed_template_outputs(self, relative_folder: str, expected_file: TemplateFileTypes):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "transform"
        process_dir = test_data_path / relative_folder
        command_result = run_command(self.command_list(), cwd=str(process_dir))
        output = command_result.stdout.decode("utf-8")
        test_output = open("tests/integration/testdata/transform/transformed_template/transformed_yaml", "r")
        checking_output = test_output.read()
        test_output.close()
        self.assertEqual(output, checking_output)
        self.assertEqual(command_result.process.returncode, 0)

    ## test for checking a invalid template transformation
    def test_transformed_template_error(self):
        command_result = run_command([self.base_command(), 'transform', '--template', './testdata/transform/failing_yaml/fail.yaml'])
        self.assertEqual(command_result.process.returncode, 1)
```
Task Breakdown
==============

-   \[x\] Send a Pull Request with this design document
-   \[x\] Build the command line interface
-   \[x\] Build the underlying library
-   \[x\] Unit tests
-   \[ \] Functional Tests
-   \[x\] Integration tests
-   \[ \] Run all tests on Windows
-   \[x\] Update documentation
