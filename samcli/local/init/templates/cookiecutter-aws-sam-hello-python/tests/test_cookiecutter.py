"""
    Tests cookiecutter baking process and rendered content
"""


def test_project_tree(cookies):
    result = cookies.bake(extra_context={
        'project_name': 'hello sam'
    })
    assert result.exit_code == 0
    assert result.exception is None
    assert result.project.basename == 'hello sam'    
    assert result.project.isdir()
    assert result.project.join('requirements.txt').isfile()
    assert result.project.join('.gitignore').isfile()
    assert result.project.join('template.yaml').isfile()    
    assert result.project.join('README.md').isfile()
    assert result.project.join('hello_world').isdir()
    assert result.project.join('hello_world', 'app.py').isfile()
    assert result.project.join('hello_world', '__init__.py').isfile()
    assert result.project.join('tests').isdir()
    assert result.project.join('tests', 'unit', '__init__.py').isfile()
    assert result.project.join('tests', 'unit', 'test_handler.py').isfile()


def test_app_content(cookies):
    result = cookies.bake(extra_context={'project_name': 'my_lambda'})
    app_file = result.project.join('hello_world', 'app.py')
    app_content = app_file.readlines()
    app_content = ''.join(app_content)

    contents = (
        "import requests",
        "Sample pure Lambda function",
        "location",
        "message",
        "hello world",
        "statusCode"
    )

    for content in contents:
        assert content in app_content
