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
    assert result.project.join('.gitignore').isfile()
    assert result.project.join('template.yaml').isfile()    
    assert result.project.join('README.md').isfile()
    assert result.project.join('hello_world').isdir()
    assert result.project.join('hello_world', 'app.js').isfile()
    assert result.project.join('hello_world', 'package.json').isfile()
    assert result.project.join('hello_world', 'yarn.lock').isfile()
    assert result.project.join('hello_world', 'tests').isdir()
    assert result.project.join('hello_world', 'tests', 'unit', 'test.spec.js').isfile()


def test_app_content(cookies):
    result = cookies.bake(extra_context={'project_name': 'my_lambda'})
    app_file = result.project.join('hello_world', 'app.js')
    app_content = app_file.readlines()
    app_content = ''.join(app_content)

    contents = (
        "const axios",
        "JSON.stringify",
        "location",
        "message",
        "hello world",
        "statusCode"
    )

    for content in contents:
        assert content in app_content
