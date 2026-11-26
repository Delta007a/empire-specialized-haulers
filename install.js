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
const canonical = name => path.resolve(name).toLowerCase();
const hash = data => createHash("sha256").update(data).digest("hex");

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
  const serverVersion = read(path.join(root,"server/package.json")).version;
  const {evejsVersions} = read(path.join(modRoot,"evejs-launcher.mod.json")).compatibility;
  requireReady(evejsVersions.includes(serverVersion), "unsupported server version " + serverVersion);
  const runtimeSrc = path.join(root,"server/src");
  const {CLIENT_COMPATIBILITY_PROFILE} = require(path.join(runtimeSrc,"network/protocolProfile"));
  const clientBuild = CLIENT_COMPATIBILITY_PROFILE.clientBuild;
  requireReady(clientBuild === (serverVersion === "261125.3" ? fleet.clientBuild : 3396210),
    "unexpected client build " + clientBuild + " for EveJS " + serverVersion);
  const handshakeFile = canonical(path.join(runtimeSrc,HANDSHAKE));
  const codec = require(path.join(runtimeSrc,"network/tcp/utils/marshal"));
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

