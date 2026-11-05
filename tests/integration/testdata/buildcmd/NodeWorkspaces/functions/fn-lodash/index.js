const _ = require("lodash");
const shared = require("@mono/shared");

exports.handler = async () => ({
  statusCode: 200,
  body: JSON.stringify({
    ownLodashVersion: _.VERSION,
    sharedLodashVersion: shared.sharedLodashVersion(),
  }),
});
