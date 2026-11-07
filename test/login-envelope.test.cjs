"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {test} = require("node:test");
const {createDelivery, transformHandshake, SYMBOL} = require("../login-envelope");

const generation = "a".repeat(24);
const ready = "CATALOG_READY ships=9 blueprintTypes=9";
const pack = text => {
  const bytes = Buffer.from(text, "ascii");
  const header = Buffer.alloc(5);
  header[0] = 0x74;
  header.writeUInt32LE(bytes.length, 1);
  return Buffer.concat([header, bytes]);
};

test("catalog receipts still report success and missing output per connection", () => {
  const messages = [];
  const delivery = createDelivery("pass", {nonce: () => generation, log: text => messages.push(text)});
  const headless = {clientId: 1};
  const client = {clientId: 2};
  for (const handshake of [headless, client]) {
    const packet = delivery.compose(handshake, pack("None"));
    assert(packet.subarray(5).includes("<empire-hauler-login>"));
  }
  assert.equal(delivery.receive(headless, [null, "", null]), null);
  assert.equal(delivery.receive(client, [null, "EMPIRE_HAULERS:" + generation + ":" + ready]), ready);
  assert(messages.some(text => text.includes("NO_RESULT")));
  assert(messages.some(text => text.includes("CLIENT_REPORT") && text.endsWith(ready)));
});

// Supply the runtime folder to exercise the exact supported native method:
// node test/login-envelope.test.cjs <EveJS runtime folder>
const runtimeRoot = process.argv[2] || process.env.EVEJS_RUNTIME_ROOT;
test("native login reaches ACK with empty, failed or successful catalog output", {skip: !runtimeRoot}, () => {
  const filename = path.resolve(runtimeRoot, "server/src/network/tcp/handshake.js");
  const native = fs.readFileSync(filename, "utf8");
  const patched = transformHandshake(native, native, {});
  new vm.Script(patched, {filename});
  assert(!patched.includes("Empire Haulers client catalog unavailable"));
  const authentication = source => source.slice(source.indexOf("  _handleAuthentication(decoded) {"), source.indexOf("  _handleFuncResult(decoded) {"));
  assert.equal(authentication(patched).replace('globalThis[Symbol.for("' + SYMBOL + '")].compose(this, buildTidiSignedFunc(this.clientId))', "buildTidiSignedFunc(this.clientId)"), authentication(native));

  const start = patched.indexOf("  _handleFuncResult(decoded) {");
  const end = patched.indexOf("\n  _decrypt(data) {", start);
  assert(start > 0 && end > start);
  const method = patched.slice(start, end);
  for (const stdout of ["", "TIDI_HANDLER:OK\n", "EMPIRE_HAULERS:" + generation + ":BLOCKED resource mount", "EMPIRE_HAULERS:" + generation + ":" + ready]) {
    const delivery = createDelivery("pass", {nonce: () => generation, log() {}});
    const context = {Buffer, console, State: {DONE: "DONE"},
      encodePacket: value => value, createSessionID: () => 1n,
      log: {debug() {}, success() {}, isVerboseDebugEnabled: () => false}};
    context[Symbol.for(SYMBOL)] = delivery;
    const Handler = vm.runInNewContext("(class Handler {\n" + method + "\n})", context);
    const handshake = new Handler();
    Object.assign(handshake, {clientId: 3, userId: 4, role: 0, languageId: "EN", countryCode: "US", sessionId: null});
    const packets = [];
    handshake._sendPacket = packet => packets.push(packet);
    handshake._sendTransportClose = () => assert.fail("Catalog receipt closed native login");
    delivery.compose(handshake, pack("None"));
    assert.equal(handshake._handleFuncResult([null, stdout, null]).done, true);
    assert.equal(handshake.state, "DONE");
    assert.equal(packets.length, 1);
    assert(packets[0].entries.some(([key]) => key === "session_init"));
  }
});
