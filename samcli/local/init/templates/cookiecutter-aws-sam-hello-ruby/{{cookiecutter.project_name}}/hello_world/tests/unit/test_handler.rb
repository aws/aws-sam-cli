require 'json'
require 'test/unit'
require 'mocha/test_unit'
require_relative '../../app'

class HelloWorldTest < Test::Unit::TestCase

  def test_lambda_handler
    response = lambda_handler(event:"", context:"")
    json_body = JSON.parse(response[:body])

    assert_equal(200, response[:statusCode])
    assert_equal("hello world", json_body["message"])
  end
end
