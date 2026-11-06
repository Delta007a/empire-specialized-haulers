"use strict";

const fs = require("node:fs");
const path = require("node:path");
const fleet = require("./fleet.json");

const TABLE_KEYS = {
  itemTypes: "types",
  shipTypes: "ships",
  movementAttributes: "attributes",
  typeDogma: "typesByTypeID",
  shipDogmaAttributes: "shipAttributesByTypeID",
  industryBlueprints: "blueprintDefinitions",
  shipInsurancePrices: "byTypeID",
};
const RETIRED_EFFECTS = new Set([529, 727, 728, 5468, 5469, 5471, 5477, 7117, 8275]);
const RETIRED_ATTRIBUTES = [493, 494, 495, 809, 811, 814, 1557, 1573, 2789, 3210];
const ACTIVITIES = ["manufacturing", "copying", "research_material", "research_time"];
const MATERIALS = [80000, 15000, 3750, 2000, 750, 125, 70];
const EMPTY = Object.freeze([]);
const SKILLS = new Map(fleet.ships.map(ship => [ship.typeID, Object.freeze([fleet.races[ship.empire][1]])]));

function requireFleet(ok, label) {
  if (!ok) throw new Error("[empire-specialized-haulers] " + label);
}

function checkIDs(ids, label, valid = id => id > 0 && id <= 0x7fffffff) {
  requireFleet(new Set(ids).size === ids.length &&
    ids.every(id => Number.isInteger(id) && valid(id)), "invalid or duplicate " + label);
}

function replaceOnce(source, anchor, replacement, label) {
  requireFleet(source.split(anchor).length === 2, label + " semantic anchor missing or duplicated");
  return source.replace(anchor, replacement);
}

function rowsByID(rows) {
  return Array.isArray(rows) ? new Map(rows.map(row => [row.typeID, row])) :
    new Map(Object.entries(rows).map(([id, row]) => [Number(id), row]));
}

function ownedIDs() {
  return {
    types: fleet.ships.flatMap(ship => [ship.typeID, ship.blueprintTypeID]),
    graphics: fleet.ships.map(ship => ship.graphicID),
    effects: fleet.ships.map(ship => ship.effectID),
    messages: fleet.ships.flatMap(ship => Array.from({length: 8}, (_, i) => ship.messageBase - i)),
    aliases: fleet.ships.map(ship => ship.alias),
  };
}

function addRow(table, entries, row) {
  const index = Array.isArray(entries) ? entries.length : row.typeID;
  requireFleet(!Object.hasOwn(entries, index), table + " duplicate " + index);
  entries[index] = row;
}

function getStatic(dataDir) {
  return Object.fromEntries(Object.keys(TABLE_KEYS).map(table => [
    table,
    JSON.parse(fs.readFileSync(path.join(dataDir, table, "data.json"), "utf8").replace(/^\uFEFF/, "")),
  ]));
}

function makeCatalog(tables) {
  requireFleet(fleet.ships.length === 9, "fleet size");
  const ids = ownedIDs();
  for (const name of ["types", "graphics", "effects"]) checkIDs(ids[name], name);
  checkIDs(ids.messages, "localization IDs", id => id >= -0x80000000 && id < 0);
  requireFleet(new Set(ids.aliases).size === 9, "duplicate SOF alias");
  const additions = {};
  const indexes = {};
  for (const [table, key] of Object.entries(TABLE_KEYS)) {
    const payload = tables[table];
    const rows = payload?.[key];
    requireFleet(rows && typeof rows === "object", table + " missing " + key);
    if (table !== "shipInsurancePrices") {
      requireFleet(payload.source?.buildNumber === fleet.clientBuild, table + " SDE mismatch");
    }
    additions[table] = Array.isArray(rows) ? [] : {};
    if (table !== "industryBlueprints") {
      indexes[table] = rowsByID(rows);
      requireFleet(ids.types.every(id => !indexes[table].has(id)), table + " private type collision");
    }
  }
  const itemIndex = indexes.itemTypes;
  const sourceDogma = tables.typeDogma;
  requireFleet(ids.graphics.every(id => !tables.itemTypes.types.some(row => row.graphicID === id)),
    "server graphic collision");
  requireFleet(ids.effects.every(id => !Object.hasOwn(sourceDogma.effectTypesByID, id)),
    "server effect collision");
  const existingCaravan = itemIndex.get(10117);
  requireFleet(existingCaravan?.name === "Caravan" && existingCaravan.categoryID === 11 &&
    existingCaravan.groupID === 297, "stock NPC Caravan identity changed");
  const blueprints = tables.industryBlueprints;
  const effects = {};

  for (const ship of fleet.ships) {
    const [raceID, skillID, velocityEffect, velocityCoef, holdCoef, marketGroupID, bpoMarket] =
      fleet.races[ship.empire];
    const [templateID, blueprintID, basePrice, holds, boostedHolds] = fleet.roles[ship.role];
    const stock = itemIndex.get(ship.stockTypeID);
    const template = itemIndex.get(templateID);
    const bpo = itemIndex.get(blueprintID);
    const tDogma = indexes.typeDogma.get(templateID);
    const stockDogma = indexes.typeDogma.get(ship.stockTypeID);
    const bpoDogma = indexes.typeDogma.get(blueprintID);
    const attrs = stockDogma?.attributes;
    const [high, medium, low] = ship.slots;
    requireFleet(high + medium + low === 10, ship.name + " slot matrix");
    requireFleet(stock?.name === ship.stock && stock.published && stock.raceID === raceID &&
      stock.graphicID === ship.stockGraphicID && stock.marketGroupID === marketGroupID &&
      stock.categoryID === 6 && stock.groupID === 28 && attrs?.[182] === skillID &&
      attrs[277] === 1 && attrs[1132] === 400 && attrs[1137] === 3 && attrs[1547] === 2,
    ship.name + " stock source changed");
    requireFleet(template?.capacity === 550 && template.basePrice === 1400000 &&
      tDogma?.attributes?.[1971] === 0.1 &&
      Object.entries(holds).every(([id, value]) => tDogma.attributes[id] === value),
    ship.name + " specialty template drift");
    requireFleet(bpo?.groupID === 108 && bpo.categoryID === 9 && bpo.published &&
      bpo.volume === 0.01 && bpo.basePrice === basePrice && bpoDogma?.attributes?.[1955] === 40,
    ship.name + " BPO template drift");
    requireFleet(!tables.itemTypes.types.some(row =>
      [ship.name, ship.name + " Blueprint"].includes(row.name) && row.categoryID !== 11),
    ship.name + " published identity name already used");

    const shipMeta = {
      typeID: ship.typeID, name: ship.name, description: ship.description,
      capacity: template.capacity, basePrice: template.basePrice, graphicID: ship.graphicID,
    };
    addRow("itemTypes", additions.itemTypes, {...stock, ...shipMeta});
    addRow("shipTypes", additions.shipTypes, {...indexes.shipTypes.get(ship.stockTypeID), ...shipMeta});
    const stockMovement = indexes.movementAttributes.get(ship.stockTypeID);
    requireFleet(stockMovement?.typeName === ship.stock && stockMovement.maxVelocity === attrs[37] &&
      stockMovement.warpSpeedMultiplier === attrs[600], ship.name + " movement authority mismatch");
    addRow("movementAttributes", additions.movementAttributes, {
      ...stockMovement, typeID: ship.typeID, typeName: ship.name,
    });
    const bpoName = ship.name + " Blueprint";
    addRow("itemTypes", additions.itemTypes, {
      ...bpo, typeID: ship.blueprintTypeID, name: bpoName, marketGroupID: bpoMarket,
      graphicID: ship.graphicID,
    });

    const attributes = {...attrs};
    for (const id of RETIRED_ATTRIBUTES) delete attributes[id];
    Object.assign(attributes, holds, {
      12: low, 13: medium, 14: high, 38: template.capacity, 1971: tDogma.attributes[1971],
      [velocityCoef]: 5, [holdCoef]: 10,
    });
    const effect = sourceDogma.effectTypesByID[velocityEffect];
    const skillEffects = indexes.typeDogma.get(skillID)?.effects || [];
    for (const coefficient of [velocityCoef, holdCoef]) {
      requireFleet(skillEffects.some(id => sourceDogma.effectTypesByID[id]?.modifierInfo?.some(mod =>
        mod.domain === "shipID" && mod.func === "ItemModifier" &&
        mod.operation === 0 && mod.modifiedAttributeID === coefficient &&
        mod.modifyingAttributeID === 280)), ship.name + " missing racial skill multiplier");
    }
    requireFleet(effect?.modifierInfo?.length === 1 && effect.effectCategoryID === 0 &&
      effect.modifierInfo[0].modifiedAttributeID === 37 &&
      effect.modifierInfo[0].modifyingAttributeID === velocityCoef &&
      effect.modifierInfo[0].operation === 6, ship.name + " velocity effect changed");
    effects[ship.effectID] = {
      ...effect, effectID: ship.effectID, name: "privateHaulerHold" + ship.name,
      displayName: "", description: "", published: false,
      modifierInfo: boostedHolds.map(id => ({
        ...effect.modifierInfo[0], modifiedAttributeID: id, modifyingAttributeID: holdCoef,
      })),
    };
    const attributeRow = {
      typeID: ship.typeID, typeName: ship.name, attributes, attributeCount: Object.keys(attributes).length,
    };
    const effectIDs = [...new Set([
      ...stockDogma.effects.filter(id => !RETIRED_EFFECTS.has(id)), velocityEffect, ship.effectID,
    ])];
    addRow("shipDogmaAttributes", additions.shipDogmaAttributes, attributeRow);
    addRow("typeDogma", additions.typeDogma, {
      ...attributeRow, effects: effectIDs, effectCount: effectIDs.length,
    });
    addRow("typeDogma", additions.typeDogma, {
      ...bpoDogma, typeID: ship.blueprintTypeID, typeName: bpoName,
    });

    const definition = blueprints.blueprintDefinitionsByTypeID[blueprintID];
    const manufacturing = definition?.activities?.manufacturing;
    requireFleet(definition?.productTypeID === templateID && definition.maxProductionLimit === 10 &&
      manufacturing?.time === 12000 && manufacturing.products.length === 1 &&
      manufacturing.products[0].typeID === templateID && manufacturing.products[0].quantity === 1 &&
      manufacturing.skills.length === 1 && manufacturing.skills[0].typeID === 3380 &&
      manufacturing.skills[0].level === 1 && manufacturing.materials.length === MATERIALS.length &&
      manufacturing.materials.every((material, i) => material.typeID === 34 + i &&
        material.quantity === MATERIALS[i]) &&
      definition.activities.copying.time === 9600 &&
      definition.activities.research_material.time === 4200 && definition.activities.research_time.time === 4200,
    ship.name + " native blueprint recipe changed");
    const activities = Object.fromEntries(ACTIVITIES.map(name => [name, structuredClone(definition.activities[name])]));
    activities.manufacturing.products[0].typeID = ship.typeID;
    additions.industryBlueprints.push({
      ...definition, blueprintTypeID: ship.blueprintTypeID, blueprintName: bpoName,
      productTypeID: ship.typeID, productName: ship.name, activities,
    });
    const insurance = indexes.shipInsurancePrices.get(templateID);
    requireFleet(Number.isSafeInteger(insurance?.fullInsurancePriceCents) &&
      insurance.fullInsurancePriceCents > 0, ship.name + " missing template insurance");
    addRow("shipInsurancePrices", additions.shipInsurancePrices, {...insurance, typeID: ship.typeID});
  }

  function project(table, payload) {
    if (!Object.hasOwn(TABLE_KEYS, table)) return payload;
    const key = TABLE_KEYS[table];
    const before = payload?.[key];
    requireFleet(before && typeof before === "object" &&
      Array.isArray(before) === Array.isArray(additions[table]), table + " runtime shape mismatch");
    if (table !== "shipInsurancePrices") {
      requireFleet(payload.source?.buildNumber === fleet.clientBuild, table + " runtime SDE mismatch");
    }
    if (table === "industryBlueprints") {
      const {blueprintDefinitionsByTypeID: byID, blueprintTypeIDsByProductTypeID: byProduct,
        manufacturingBlueprintTypeIDs: manufacturing} = payload;
      requireFleet(byID && byProduct && Array.isArray(manufacturing), "blueprint indexes missing");
      requireFleet(additions[table].every(row => !Object.hasOwn(byID, row.blueprintTypeID) &&
        !Object.hasOwn(byProduct, row.productTypeID) && !manufacturing.includes(row.blueprintTypeID) &&
        !before.some(old => old.blueprintTypeID === row.blueprintTypeID || old.productTypeID === row.productTypeID)),
      "blueprint index collision");
      return {
        ...payload, [key]: [...before, ...additions[table]],
        blueprintDefinitionsByTypeID: {...byID, ...Object.fromEntries(additions[table].map(row => [row.blueprintTypeID, row]))},
        blueprintTypeIDsByProductTypeID: {...byProduct, ...Object.fromEntries(additions[table].map(row => [row.productTypeID, row.blueprintTypeID]))},
        manufacturingBlueprintTypeIDs: [...manufacturing, ...additions[table].map(row => row.blueprintTypeID)],
      };
    }
    const newRows = Object.values(additions[table]);
    const present = rowsByID(before);
    requireFleet(newRows.every(row => !present.has(row.typeID)), table + " runtime type collision");
    if (Array.isArray(before)) return {...payload, [key]: [...before, ...newRows], count: before.length + newRows.length};
    const result = {...payload, [key]: {...before, ...additions[table]}};
    if (table === "shipDogmaAttributes") {
      result.counts = {
        ...payload.counts, shipTypes: present.size + newRows.length,
        totalAttributes: payload.counts.totalAttributes + newRows.reduce((n, row) => n + row.attributeCount, 0),
      };
    }
    if (table === "typeDogma") {
      requireFleet(ids.effects.every(id => !Object.hasOwn(payload.effectTypesByID, id)),
        "runtime effect collision");
      result.effectTypesByID = {...payload.effectTypesByID, ...effects};
      result.counts = {
        ...payload.counts, types: present.size + newRows.length,
        effectTypes: Object.keys(result.effectTypesByID).length,
        totalAttributes: payload.counts.totalAttributes + newRows.reduce((n, row) => n + row.attributeCount, 0),
        totalEffects: payload.counts.totalEffects + newRows.reduce((n, row) => n + row.effectCount, 0),
      };
    }
    return result;
  }

  for (const table of Object.keys(TABLE_KEYS)) project(table, tables[table]);
  return {project, additions, effects, getHullSkills: id => SKILLS.get(Number(id)) || EMPTY};
}

const SEAMS = {
  "services/_shared/referenceData.js": (src, owner) => replaceOnce(src,
    "normalizePayload(tableName, result.data)",
    "normalizePayload(tableName, " + owner + ".project(tableName, result.data))", "referenceData"),
  "services/industry/industryStaticData.js": (src, owner) => replaceOnce(src,
    "const payload = readTable(INDUSTRY_BLUEPRINT_TABLE);",
    "const payload = " + owner + ".project(INDUSTRY_BLUEPRINT_TABLE, readTable(INDUSTRY_BLUEPRINT_TABLE));", "industry"),
  "services/insurance/insurancePriceAuthority.js": (src, owner) => replaceOnce(src,
    "const result = repo.read(SHIP_INSURANCE_PRICES_TABLE, \"/\");",
    "const result = repo.read(SHIP_INSURANCE_PRICES_TABLE, \"/\");\n" +
    "  if (result.success) result.data = " + owner + ".project(SHIP_INSURANCE_PRICES_TABLE, result.data);", "insurance"),
  "services/fitting/hullBonusSkillAuthority.js": (src, owner) => {
    src = replaceOnce(src, "function getHullBonusSkillTypeIDs(hullTypeID) {",
      "function getHullBonusSkillTypeIDs(hullTypeID) {\n" +
      "  const privateSkills = " + owner + ".getHullSkills(hullTypeID);\n" +
      "  if (privateSkills.length) return privateSkills;", "hull skill getter");
    return replaceOnce(src, "return bonusSkillTypeIDsByHullTypeID.has(Number(hullTypeID));",
      "return " + owner + ".getHullSkills(hullTypeID).length > 0 || " +
      "bonusSkillTypeIDsByHullTypeID.has(Number(hullTypeID));", "hull skill authority");
  },
};

module.exports = { fleet, ownedIDs, getStatic, makeCatalog, SEAMS, TABLE_KEYS };
