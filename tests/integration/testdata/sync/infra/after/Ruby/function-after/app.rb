require 'httparty'
require 'json'
require 'layer_test'

def lambda_handler(event:, context:)
  # Sample pure Lambda function that returns a message and a location

  begin
    response = HTTParty.get('http://checkip.amazonaws.com/')
  rescue HTTParty::Error => error
    puts error.inspect
    raise error
  end

  {
    statusCode: 200,
    body: {
      message: "#{layer_test()+2}",
      location: response.body
    }.to_json
  }
end
