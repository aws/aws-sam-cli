const express = require("express");
const app = express();
app.get("/", (req, res, next) => {
  return res.send({ Output: "hello from get" });
});
app.options("/", (req, res, next) => {
  res.status(204).send({ Output: "hello from options" });
});

module.exports = app;
