"""
    Tests cookiecutter baking process and rendered content
"""


def test_project_tree(cookies):
    result = cookies.bake(extra_context={"project_name": "hello sam"})
    assert result.exit_code == 0
    assert result.exception is None
    assert result.project.basename == "hello sam"
    assert result.project.isdir()
    assert result.project.join("template.yaml").isfile()
    assert result.project.join("README.md").isfile()
    assert result.project.join("src").isdir()
    assert result.project.join("src", "main").isdir()
    assert result.project.join("src", "main", "java").isdir()
    assert result.project.join("src", "main", "java", "helloworld").isdir()
    assert result.project.join("src", "main", "java", "helloworld", "App.java").isfile()
    assert result.project.join("src", "main", "java", "helloworld", "GatewayResponse.java").isfile()
    assert result.project.join("src", "test", "java").isdir()
    assert result.project.join("src", "test", "java", "helloworld").isdir()
    assert result.project.join("src", "test", "java", "helloworld", "AppTest.java").isfile()


def test_app_content(cookies):
    result = cookies.bake(extra_context={"project_name": "my_lambda"})
    app_file = result.project.join("src", "main", "java", "helloworld", "App.java")
    app_content = app_file.readlines()
    app_content = "".join(app_content)

    contents = (
        "package helloword",
        "class App implements RequestHandler<Object, Object>",
        "https://checkip.amazonaws.com",
        "return new GatewayResponse",
        "getPageContents",
    )

    for content in contents:
        assert content in app_content
