"use strict";

const {randomBytes} = require("node:crypto");

const SYMBOL = "evejs.empireSpecializedHaulers.login";
const MAX_EXPRESSION_BYTES = 256 * 1024;
const MAX_PACKET_BYTES = 2 * 1024 * 1024;
const FRAME_HEADER_BYTES = 4;
const MARSHAL_HEADER_BYTES = 5;
const FLEET_SIZE = require("./fleet.json").ships.length;
const READY = "CATALOG_READY ships=" + FLEET_SIZE + " blueprintTypes=" + FLEET_SIZE;

function demand(value, problem) {
  if (!value) throw new Error("[EmpireHaulers] " + problem);
}

function composePacket(handshake, packet, codec, delivery) {
  const fieldStart = FRAME_HEADER_BYTES + MARSHAL_HEADER_BYTES;
  if (!(handshake.userId > 0) || !Buffer.isBuffer(packet) || packet.length < fieldStart ||
      packet.length > MAX_PACKET_BYTES || packet.readUInt32LE(0) !== packet.length - FRAME_HEADER_BYTES ||
      packet[FRAME_HEADER_BYTES] !== codec.MARSHAL_HEADER || packet.readUInt32LE(FRAME_HEADER_BYTES + 1) !== 0) {
    return packet;
  }
  try {
    const decoded = codec.marshalDecodeExact(packet.subarray(FRAME_HEADER_BYTES));
    if (!Array.isArray(decoded) || decoded.length !== 4 || codec.strVal(decoded[0]) !== "" ||
        decoded[2]?.type !== "dict" || codec.dictGet(decoded[3], "challenge_responsehash") === undefined) {
      return packet;
    }
    const signed = decoded[1];
    if (!Array.isArray(signed) || signed.length !== 2 || (signed[1] !== 0 && signed[1] !== false) ||
        !Buffer.isBuffer(signed[0])) {
      return packet;
    }
    // Replace only the encoded signed function. Keep native verification,
    // the context and every other part of the assembled challenge intact.
    const original = codec.marshalEncode(signed[0]).subarray(MARSHAL_HEADER_BYTES);
    const offset = packet.indexOf(original, fieldStart);
    if (offset === -1 || packet.indexOf(original, offset + 1) !== -1) return packet;
    const next = delivery.compose(handshake, signed[0]);
    if (next === signed[0]) return packet;
    const encoded = codec.marshalEncode(next).subarray(MARSHAL_HEADER_BYTES);
    return codec.wrapPacket(Buffer.concat([
      packet.subarray(FRAME_HEADER_BYTES, offset), encoded, packet.subarray(offset + original.length),
    ]));
  } catch (_) {
    return packet;
  }
}

function attachDelivery(Handshake, codec, delivery) {
  const prototype = Handshake?.prototype;
  const send = prototype?._sendPacket;
  const reply = prototype?._handleFuncResult;
  demand(typeof send === "function" && typeof reply === "function", "native handshake methods unavailable");
  prototype._sendPacket = function sendWithCatalog(packet) {
    return send.call(this, composePacket(this, packet, codec, delivery));
  };
  prototype._handleFuncResult = function reportCatalog(decoded) {
    delivery.receive(this, decoded);
    return reply.call(this, decoded);
  };
}

function receiptText(raw) {
  if (Buffer.isBuffer(raw)) return raw.toString("utf8");
  if (["wstring", "token", "rawstr"].includes(raw?.type)) return raw.value;
  return raw;
}

function createDelivery(program, {nonce = () => randomBytes(12).toString("hex"), log = console.log} = {}) {
  demand(typeof program === "string" && /^[\x00-\x7f]+$/.test(program), "invalid client program");
  const pending = new WeakMap();
  return {
    compose(handshake, original) {
      if (pending.has(handshake)) return original;
      try {
        demand(Buffer.isBuffer(original) && original.length > 5 && original[0] === 0x74 &&
          original.readUInt32LE(1) === original.length - 5, "unexpected signed-function envelope");
        demand(Number.isSafeInteger(handshake.clientId) && handshake.clientId > 0, "invalid connection ID");
        const generation = nonce();
        demand(/^[a-f0-9]{24}$/.test(generation), "invalid session generation");
        const payload = Buffer.from(program + "\nrun_family(_family_context,'" + generation + "')\n", "ascii");
        const expression = "(lambda _result: (eval(compile(__import__('base64').b64decode('" +
          payload.toString("base64") + "'), '<empire-hauler-login>', 'exec'), " +
          "{'__builtins__': __builtins__, '_family_context': globals()}), _result)[1])(";
        const data = Buffer.concat([Buffer.from(expression, "ascii"), original.subarray(5), Buffer.from(")")]);
        demand(data.length <= MAX_EXPRESSION_BYTES, "composed payload exceeds size limit");
        const header = Buffer.alloc(5);
        header[0] = 0x74;
        header.writeUInt32LE(data.length, 1);
        pending.set(handshake, {generation, clientId: handshake.clientId});
        log("[EmpireHaulers] SENT generation=" + generation);
        return Buffer.concat([header, data]);
      } catch (error) {
        log("[EmpireHaulers] BLOCKED " + error.message);
        return original;
      }
    },
    receive(handshake, decoded) {
      const state = pending.get(handshake);
      if (!state) return null;
      pending.delete(handshake);
      const stdout = receiptText(Array.isArray(decoded) ? decoded[1] : null);
      const prefix = "EMPIRE_HAULERS:" + state.generation + ":";
      const hits = typeof stdout === "string" && stdout.length < 65536 ?
        stdout.split(/\r?\n/).filter(line => line.startsWith(prefix)) : [];
      const message = hits.length === 1 ? hits[0].slice(prefix.length) : "";
      if (state.clientId !== handshake.clientId || (message !== READY &&
          !/^(BLOCKED [A-Za-z0-9_. -]{1,160}|ROLLBACK_FAILED close-client)$/.test(message))) {
        log("[EmpireHaulers] NO_RESULT generation=" + state.generation);
        return null;
      }
      log("[EmpireHaulers] CLIENT_REPORT generation=" + state.generation + " " + message);
      return message;
    },
  };
}

module.exports = {SYMBOL, attachDelivery, createDelivery};
