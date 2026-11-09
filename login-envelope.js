"use strict";

const {createHash, randomBytes} = require("node:crypto");

const SYMBOL = "evejs.empireSpecializedHaulers.login";
const OWNER = 'globalThis[Symbol.for("' + SYMBOL + '")]';
const NATIVE_CALL = "buildTidiSignedFunc(this.clientId)";
const SEND = /^([ \t]*)\[(.*buildTidiSignedFunc\(this\.clientId\).*), (?:false|0)\],(?: \/\/ func tuple: \[marshaled_code, verification\])?(\r?)$/m;
const CALL_PREFIXES = [
  '((packet) => globalThis[Symbol.for("evejs.ourMods.privateFittingRuntime")]?.compose(packet) ?? packet)(',
  '((packet) => globalThis[Symbol.for("evejs.moonOreAnomalies.transientNames")]?.compose(this.socket, packet) ?? packet)(',
];
const RESULT = "  _handleFuncResult(decoded) {";
const MAX = 256 * 1024;
const FLEET_SIZE = require("./fleet.json").ships.length;
const READY = `CATALOG_READY ships=${FLEET_SIZE} blueprintTypes=${FLEET_SIZE}`;
const CORE_HASHES = new Set([
  "c84cffe20c00cf075a97daa31ca53c435af4f14c814e46d828760dbbb55fb566", // 261028.1
  "5e6d7445213c89c8ad58d58ace38ac1f08d6ebfb40f7ef7c4a2491626a8dab15", // 261108.1
]);
const normal = value => value.replaceAll("\r\n", "\n");
const sha = value => createHash("sha256").update(value).digest("hex");

// These are source-shape boundaries, not module IDs or an enabled-mod list.
// Dynamic data is allowed only in the one reviewed base64 literal.
const HEADS = [
  ["signed-rebinder", ';buildTidiSignedFunc = globalThis[Symbol.for("evejs.cpi.wrapSignedFunc")]'],
  ["fitting-builder", ";const __fscOriginalLogin = buildTidiSignedFunc;"],
  ["localization-builder", "const __moonPreviousLogin = buildTidiSignedFunc;"],
  ["menu-builder", "// Launcher owns only this local builder wrapper."],
];
const HEAD_MATCHES = new Map(HEADS.map(([name, text]) => [text, name]));
const START = new RegExp("^(?:" + HEADS.map(([,text]) =>
  text.replace(/[.*+?^$(){}|[\]\\]/g, "\\$&")).join("|") + ")", "gm");
const PAYLOAD = /b64decode\((['"])([A-Za-z0-9+/]+={0,2})\1\)/g;
const KNOWN_DYNAMIC = new Set(["localization-builder","menu-builder"]);

function demand(value, problem) {
  if (!value) throw new Error("[EmpireHaulers] " + problem);
}

function inspectCall(source) {
  const match = SEND.exec(source);
  demand(match && source.split(NATIVE_CALL).length === 2, "ambiguous login send ownership");
  let call = match[2];
  const wrappers = new Set();
  while (call !== NATIVE_CALL) {
    const prefix = CALL_PREFIXES.find(candidate => call.startsWith(candidate));
    demand(prefix && !wrappers.has(prefix) && call.endsWith(")"), "unknown signed-function call wrapper");
    wrappers.add(prefix);
    call = call.slice(prefix.length,-1);
  }
  return {match, wrappers};
}

function inspectTails(baseline, incoming) {
  baseline = normal(baseline);
  incoming = normal(incoming);
  demand(CORE_HASHES.has(sha(baseline)), "native login source changed");
  const {match} = inspectCall(incoming);
  incoming = incoming.replace(match[0], match[0].replace(match[2], NATIVE_CALL));
  demand(incoming.startsWith(baseline), "native login body or insertion seam changed");
  const suffix = incoming.slice(baseline.length);
  if (!suffix.trim()) return [];
  const boundaries = [...suffix.matchAll(START)];
  demand(boundaries.length > 0 && !suffix.slice(0, boundaries[0].index).trim(),
    "unknown prelude around login wrapper");
  return boundaries.map((match, i) => {
    const name = HEAD_MATCHES.get(match[0]);
    const tail = suffix.slice(match.index, boundaries[i+1]?.index ?? suffix.length).trim();
    const payloads = [...tail.matchAll(PAYLOAD)];
    demand(payloads.length === Number(KNOWN_DYNAMIC.has(name)), name + " payload shape changed");
    let normalized = tail;
    if (payloads.length) {
      const encoded = payloads[0][2];
      demand(encoded.length < MAX && Buffer.from(encoded,"base64").toString("base64") === encoded,
        name + " invalid embedded data");
      normalized = tail.replace(PAYLOAD, (_,quote) => "b64decode(" + quote + "@PAYLOAD@" + quote + ")");
    }
    return {name, fingerprint: sha(normalized)};
  });
}

function transformHandshake(baseline, incoming, expected) {
  const tails = inspectTails(baseline,incoming);
  demand(new Set(tails.map(tail => tail.name)).size === tails.length, "duplicate login wrapper");
  for (const {name,fingerprint} of tails) {
    demand(expected[name] === fingerprint, "unknown " + name + " source shape");
  }
  const {match} = inspectCall(incoming);
  demand(incoming.split(RESULT).length === 2 && !incoming.includes(OWNER), "ambiguous login reply ownership");
  // The receipt diagnoses client data loading. Native authentication owns login.
  return incoming.replace(match[0], match[0].replace(match[2], OWNER+".compose(this, "+match[2]+")"))
    .replace(RESULT, RESULT+"\n    "+OWNER+".receive(this, decoded);");
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
        const payload = Buffer.from(program + "\nrun_family(_family_context,'" + generation + "')\n","ascii");
        const expression = "(lambda _result: (eval(compile(__import__('base64').b64decode('" +
          payload.toString("base64") + "'), '<empire-hauler-login>', 'exec'), " +
          "{'__builtins__': __builtins__, '_family_context': globals()}), _result)[1])(";
        const data = Buffer.concat([Buffer.from(expression,"ascii"), original.subarray(5), Buffer.from(")")]);
        demand(data.length <= MAX, "composed payload exceeds size limit");
        const header = Buffer.alloc(5);
        header[0] = 0x74;
        header.writeUInt32LE(data.length,1);
        pending.set(handshake, {generation, clientId: handshake.clientId});
        log("[EmpireHaulers] SENT generation=" + generation);
        return Buffer.concat([header,data]);
      } catch (error) {
        log("[EmpireHaulers] BLOCKED " + error.message);
        return original;
      }
    },
    receive(handshake, decoded) {
      const state = pending.get(handshake);
      if (!state) return null;
      pending.delete(handshake);
      const raw = Array.isArray(decoded) ? decoded[1] : null;
      const stdout = Buffer.isBuffer(raw) ? raw.toString("utf8") : raw;
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

module.exports = {SYMBOL, inspectTails, transformHandshake, createDelivery};

