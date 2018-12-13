function echo_request () {
  EVENT_DATA=$1

  RESPONSE="{\"body\": \"hello 曰有冥 world 🐿\", \"statusCode\": 200, \"headers\": {}}"

  echo $RESPONSE
}