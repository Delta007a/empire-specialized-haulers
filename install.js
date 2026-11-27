"use strict";

const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const {createHash} = require("node:crypto");
const {deflateSync} = require("node:zlib");
const {fleet, getStatic, makeCatalog, SEAMS} = require("./catalog");
const {SYMBOL, attachDelivery, createDelivery} = require("./login-envelope");

const OWNER = 'globalThis[Symbol.for("' + SYMBOL + '")]';
const KEY = Symbol.for(SYMBOL);
const HANDSHAKE = "network/tcp/handshake.js";
const MARSHAL = "network/tcp/utils/marshal.js";
const canonical = name => path.resolve(name).toLowerCase();
const hash = data => createHash("sha256").update(data).digest("hex");
const sourceHash = file => hash(fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n"));

// The catalog wraps the encoded native challenge, so both its producer and
// the marshal codec must match a reviewed contract for the selected client.
const CURRENT_HANDSHAKE = "7aaa72247049b38d3f656f3b2c602877a8bcf0d9ff0af68f1795ff1327565ba7";
const CURRENT_MARSHAL = "1386060fc712b3a23b7968da51c51955f76341b42e2e162502e03a050f267df3";
const LOGIN_CONTRACTS = new Map([
  [3396210, new Map([
    ["c84cffe20c00cf075a97daa31ca53c435af4f14c814e46d828760dbbb55fb566",
      "d78d3c7738b24ffa1315e1cc025b227a551fbeab251e36b0a25e70320c899092"],
    ["5e6d7445213c89c8ad58d58ace38ac1f08d6ebfb40f7ef7c4a2491626a8dab15", CURRENT_MARSHAL],
    [CURRENT_HANDSHAKE, CURRENT_MARSHAL],
  ])],
  [fleet.clientBuild, new Map([[CURRENT_HANDSHAKE, CURRENT_MARSHAL]])],
]);

function requireReady(condition, message) {
  if (!condition) throw new Error("[EmpireHaulers] " + message);
}

function read(file) {
  return JSON.parse(fs.readFileSync(file,"utf8").replace(/^\uFEFF/,""));
}

function verifiedVisuals(modRoot, manifest) {
  requireReady(manifest.version === fleet.version && manifest.build === fleet.clientBuild,
    "visual resource version mismatch");
  const roots = Object.fromEntries(Object.entries(manifest.roots).map(([key,value]) => [
    key,path.resolve(modRoot,value),
  ]));
  const files = Object.keys(manifest.files);
  const native = manifest.hulls;
  requireReady(native.length === fleet.ships.length && native.every((row,i) =>
    row.alias === fleet.ships[i].alias && row.stockAlias === fleet.ships[i].stockAlias &&
    files.includes(row.blackUri) && files.includes(row.geometryUri) &&
    Object.values(row.textureUris||{}).every(uri=>files.includes(uri))),
  "incomplete visual hull list");
  for (const [uri,entry] of Object.entries(manifest.files)) {
    const match = /^([a-z0-9]+):\/([a-zA-Z0-9_.\/-]+)$/.exec(uri);
    requireReady(match && Object.hasOwn(roots,match[1]) &&
      match[2].split("/").every(part=>part && ![".",".."].includes(part)), "invalid private resource URI");
    const file = path.join(roots[match[1]],match[2]);
    requireReady(fs.existsSync(file) && fs.statSync(file).size===entry.bytes,
      "missing or changed private resource " + uri);
    requireReady(hash(fs.readFileSync(file))===entry.sha256, "private resource hash mismatch " + uri);
  }
  for (const ship of fleet.ships) {
    for (const size of [64,128]) {
      for (const style of ["","_BP","_BPC"]) {
        requireReady(files.includes("ehico:/"+ship.graphicID+"_"+size+style+".png"), "missing native icon variant");
      }
    }
  }
  return {roots,hulls:native,files,signature:hash(JSON.stringify(manifest)),iconFolder:"ehico:"};
}

function buildProgram(modRoot,catalog,visuals,clientBuild=fleet.clientBuild) {
  const payload = {
    fleet:{clientBuild,ships:fleet.ships,races:fleet.races,roles:fleet.roles},
    additions:Object.fromEntries(["itemTypes","typeDogma","industryBlueprints"].map(table=>[table,catalog.additions[table]])),
    effects:catalog.effects,
  };
  const encoded=deflateSync(Buffer.from(JSON.stringify({catalog:payload,visuals}),"utf8"),{level:9}).toString("base64");
  return "_family_bundle = "+JSON.stringify(encoded)+"\n" +
    fs.readFileSync(path.join(modRoot,"client-catalog.py"),"ascii")+"\n"+
    fs.readFileSync(path.join(modRoot,"client-bootstrap.py"),"ascii");
}

function install(root,modRoot,moduleHost=Module) {
  requireReady(!globalThis[KEY],"duplicate catalog owner");
  const runtimeSrc = path.join(root,"server/src");
  const {CLIENT_COMPATIBILITY_PROFILE} = require(path.join(runtimeSrc,"network/protocolProfile"));
  const clientBuild = CLIENT_COMPATIBILITY_PROFILE?.clientBuild;
  const login = LOGIN_CONTRACTS.get(clientBuild);
  requireReady(login, "unsupported client build " + clientBuild);
  const nativeHandshake = sourceHash(path.join(runtimeSrc,HANDSHAKE));
  const nativeMarshal = login.get(nativeHandshake);
  requireReady(nativeMarshal, "unreviewed login handshake for client build " + clientBuild);
  requireReady(nativeMarshal === sourceHash(path.join(runtimeSrc,MARSHAL)), "unreviewed login marshal codec");
  const handshakeFile = canonical(path.join(runtimeSrc,HANDSHAKE));
  const codec = require(path.join(runtimeSrc,MARSHAL));
  const seams = new Map();
  for (const [name,transform] of Object.entries(SEAMS)) {
    const file = path.join(runtimeSrc,name);
    const input = fs.readFileSync(file,"utf8");
    transform(input,OWNER);
    seams.set(canonical(file),transform);
  }
  const ownedFiles = new Set([handshakeFile,...seams.keys()]);
  requireReady(!Object.keys(moduleHost._cache).some(file=>ownedFiles.has(canonical(file))),
    "catalog or handshake already compiled");
  const visuals = verifiedVisuals(modRoot,read(path.join(modRoot,"visual-resources.json")));
  const {resolveDataDir} = require(path.join(runtimeSrc,"gameStore/storeRoot"));
  const catalog = makeCatalog(getStatic(resolveDataDir()),clientBuild);
  const delivery=createDelivery(buildProgram(modRoot,catalog,visuals,clientBuild));
  const state={...catalog,active:true,handshakeReady:false};
  const previous=moduleHost.prototype._compile;
  moduleHost.prototype._compile=function compileFamily(source,filename) {
    const file=canonical(filename);
    if (seams.has(file)) source=seams.get(file)(source,OWNER);
    const result=previous.call(this,source,filename);
    if (file===handshakeFile) {
      requireReady(!state.handshakeReady,"duplicate handshake compilation");
      attachDelivery(this.exports,codec,delivery);
      state.handshakeReady=true;
      console.log("[EmpireHaulers] LOGIN_READY build=" + clientBuild + " types=" + fleet.ships.length * 2);
    }
    return result;
  };
  globalThis[KEY]=state;
  return state;
}

module.exports={install,verifiedVisuals,buildProgram};

