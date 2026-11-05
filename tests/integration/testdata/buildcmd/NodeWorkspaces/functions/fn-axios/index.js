const axios = require("axios");
const shared = require("@mono/shared");

exports.handler = async () => ({
  statusCode: 200,
  body: JSON.stringify({
    axiosVersion: axios.VERSION,
    sharedLodashVersion: shared.sharedLodashVersion(),
  }),
});
