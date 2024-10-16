require 'ruby-statistics/distribution/normal'
require 'json'
require 'layer'

def lambda_handler(event:, context:)
  # Sample pure Lambda function that returns a message and a location

  normal = RubyStatistics::Distribution::Normal.new(2,3)

  {
    statusCode: 200,
    body: {
      message: "#{layer()+2}",
      extra_message: normal.random
    }.to_json
  }
end
