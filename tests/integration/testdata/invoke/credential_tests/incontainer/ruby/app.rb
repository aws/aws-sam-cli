require 'json'
require 'aws-sdk-core'

def lambda_handler(event:, context:)
  begin
    client = Aws::STS::Client.new()
    resp = client.get_caller_identity({})
  end

  {
    statusCode: 200,
    body: {
      message: "Hello World!",
      account: resp.account
    }.to_json
  }
end