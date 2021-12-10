require 'statistics'
require 'json'
require 'layer'

def lambda_handler(event:, context:)
  # Sample pure Lambda function that returns a message and a location

  normal = Statistics::Distribution::Normal.new(2,3)

  {
    statusCode: 200,
    body: {
      message: "#{layer()+1}",
      extra_message: normal.random
    }.to_json
  }
end
