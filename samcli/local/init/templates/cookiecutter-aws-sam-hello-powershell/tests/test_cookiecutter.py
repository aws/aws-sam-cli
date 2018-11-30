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
    assert result.project.join('src').isdir()
    assert result.project.join('test').isdir()
    assert result.project.join('src').isdir()
    assert result.project.join(
        'src', 'Function.ps1').isfile()
    assert result.project.join('src', 'Build.ps1').isfile()
    assert result.project.join(
        'test', 'Function.tests.ps1').isfile()


def test_app_content(cookies):
    result = cookies.bake(extra_context={'project_name': 'my_lambda'})
    app_file = result.project.join('src', 'Function.ps1')
    app_content = app_file.readlines()
    app_content = ''.join(app_content)

    contents = (
        "AWSPowerShell.NetCore",
        "$LambdaInput",
        "Write-Host"
    )

    for content in contents:
        assert content in app_content
