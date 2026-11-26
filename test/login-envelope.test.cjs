"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {test} = require("node:test");
const {attachDelivery, createDelivery} = require("../login-envelope");

const generation = "a".repeat(24);
const ready = "CATALOG_READY ships=12 blueprintTypes=12";
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

// Supply a runtime folder to exercise its codec and native acknowledgement:
// node test/login-envelope.test.cjs <EveJS runtime folder>
const runtimeRoot = process.argv[2] || process.env.EVEJS_RUNTIME_ROOT;
test("assembled challenge preserves native fields, other payloads and acknowledgement", {skip: !runtimeRoot}, () => {
  const tcp = path.resolve(runtimeRoot, "server/src/network/tcp");
  const codec = require(path.join(tcp, "utils/marshal"));
  const native = fs.readFileSync(path.join(tcp, "handshake.js"), "utf8");
  const tuple = native.match(/^[ \t]*\[buildTidiSignedFunc\(.*\), (false|0)\],/m);
  assert(tuple);
  const verification = tuple[1] === "false" ? false : 0;
  const start = native.indexOf("  _handleFuncResult(decoded) {");
  const end = native.indexOf("\n  _decrypt(data) {", start);
  assert(start > 0 && end > start);
  const context = {Buffer, State: {DONE: "DONE"}, encodePacket: codec.encodePacket,
    createSessionID: () => 1n, log: {debug() {}, success() {}, isVerboseDebugEnabled: () => false}};
  const Handler = vm.runInNewContext("(class Handler {\n_sendPacket(packet) { this.packets.push(packet); }\n" +
    native.slice(start, end) + "\n})", context);
  const messages = [];
  const delivery = createDelivery("pass", {nonce: () => generation, log: message => messages.push(message)});
  attachDelivery(Handler, codec, delivery);
  const otherExpression = "('existing-payload-result', None)[0]";
  const original = ["", [pack(otherExpression), verification], {type: "dict", entries: []},
    {type: "dict", entries: [["challenge_responsehash", "55087"]]}];
  const challenge = codec.encodePacket(original);
  const decode = packet => codec.marshalDecodeExact(packet.subarray(4));
  const success = "EMPIRE_HAULERS:" + generation + ":" + ready;
  for (const stdout of ["", "TIDI_HANDLER:OK\n", "EMPIRE_HAULERS:" + generation + ":BLOCKED resource mount",
    Buffer.from(success), {type: "wstring", value: success}]) {
    const handshake = new Handler();
    Object.assign(handshake, {packets: [], clientId: 3, userId: 4, role: 0, languageId: "EN",
      countryCode: "US", sessionId: null, address: "127.0.0.1"});
    handshake._sendTransportClose = () => assert.fail("Catalog receipt closed native login");
    const unrelated = codec.encodePacket(2);
    handshake._sendPacket(unrelated);
    assert.equal(handshake.packets[0], unrelated);
    handshake._sendPacket(challenge);
    const decoded = decode(handshake.packets[1]);
    const expression = decoded[1][0].subarray(5).toString("ascii");
    assert(expression.includes("<empire-hauler-login>") && expression.endsWith("(" + otherExpression + ")"));
    decoded[1][0] = original[1][0];
    assert.deepEqual(decoded, decode(challenge));
    assert.equal(handshake._handleFuncResult([null, stdout, null]).done, true);
    assert.equal(handshake.state, "DONE");
    assert.equal(handshake.packets.length, 3);
    assert(codec.dictGet(decode(handshake.packets[2]), "session_init"));
  }
  assert.equal(messages.filter(message => message.endsWith(ready)).length, 2);
});
