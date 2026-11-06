"use strict";

const path = require("node:path");
const {isMainThread} = require("node:worker_threads");

if (isMainThread) {
  module.exports = require("./install").install(path.resolve(__dirname,"../.."),__dirname);
}
