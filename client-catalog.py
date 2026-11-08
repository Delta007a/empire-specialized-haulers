# ASCII source for EVE build 3396210's Python 2.7.
# Additive data and rollback mechanics shared by the native ABI verifier and loader.
class CatalogError(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise CatalogError(reason)


class View(object):
    def __init__(self, base, added, replacements=None):
        require(not any(key in base for key in added), "private ID collides with native catalog")
        self.base = base
        self.added = added
        self.replacements = replacements or {}
        require(all(key in base for key in self.replacements), "reverse index source missing")
        self.active = True

    def __len__(self):
        return len(self.base) + (len(self.added) if self.active else 0)

    def __contains__(self, key):
        return (self.active and key in self.added) or key in self.base

    def __getitem__(self, key):
        if self.active:
            if key in self.added:
                return self.added[key]
            if key in self.replacements:
                return self.replacements[key]
        return self.base[key]

    def get(self, key, default=None):
        return self[key] if key in self else default

    def has_key(self, key):
        return key in self

    def iterkeys(self):
        for key in self.base.iterkeys():
            yield key
        if self.active:
            for key in self.added:
                yield key

    __iter__ = iterkeys

    def iteritems(self):
        for key in self.iterkeys():
            yield key, self[key]

    def itervalues(self):
        for _, row in self.iteritems():
            yield row

    def keys(self):
        return list(self.iterkeys())

    def items(self):
        return list(self.iteritems())

    def values(self):
        return list(self.itervalues())


class CertificateCatalogView(object):
    # The FSD root is an ObjectLoader, not a dictionary. Only its masteries
    # dictionary is extended; native certificate definitions stay untouched.
    def __init__(self, base, masteries):
        self.base = base
        self._masteries = masteries

    @property
    def active(self):
        return self._masteries.active

    @active.setter
    def active(self, value):
        self._masteries.active = value

    def __getitem__(self, key):
        if key == "masteries" and self.active:
            return self._masteries
        return self.base[key]

    def __getattr__(self, name):
        if name == "masteries":
            return self["masteries"]
        return getattr(self.base, name)


def build_masteries(base, ships):
    masteries = base["masteries"]
    certificates = base["certificates"]
    added = {}
    for ship in ships:
        type_id, stock_id = ship["typeID"], ship["stockTypeID"]
        require(type_id not in added and type_id not in masteries,
                "mastery type collision: %s" % type_id)
        require(stock_id in masteries, "native mastery source missing: %s" % stock_id)
        profile = masteries[stock_id]
        for level in range(5):
            require(level in profile and len(profile[level]) > 0,
                    "native mastery level missing: %s/%s" % (stock_id, level + 1))
            require(all(cert_id in certificates for cert_id in profile[level]),
                    "native mastery certificate missing: %s/%s" % (stock_id, level + 1))
        # Reuse the immutable native profile. Certificate service calculates
        # character mastery and handles skill-change invalidation itself.
        added[type_id] = profile
    return CertificateCatalogView(base, View(masteries, added))


class Row(object):
    def __init__(self, base, **fields):
        self.base = base
        self.fields = fields

    def __getattr__(self, field):
        if field in self.fields:
            return self.fields[field]
        return getattr(self.base, field)


class LocaleView(object):
    def __init__(self, base, added):
        self.base = base
        self.added = added
        self.active = True

    def __getattr__(self, name):
        return getattr(self.base, name)

    def GetByMessageID(self, messageID, *args, **kwargs):
        if self.active and messageID in self.added:
            return self.added[messageID]
        return self.base.GetByMessageID(messageID, *args, **kwargs)

    def GetImportantByMessageID(self, messageID, *args, **kwargs):
        if self.active and messageID in self.added:
            return self.added[messageID]
        return self.base.GetImportantByMessageID(messageID, *args, **kwargs)


class BlueprintView(View):
    def __init__(self, base, added, byProduct):
        View.__init__(self, base, added)
        require(len(byProduct) == len(added), "missing blueprint product index")
        require(callable(getattr(base, "index", None)) and callable(getattr(base, "filter", None)) and
                callable(getattr(base, "filter_keys", None)), "unexpected blueprint storage API")
        for key in byProduct:
            require(not list(base.filter_keys("productTypeID", key)), "blueprint product collision")
        self.byProduct = byProduct

    def iterkeys(self):
        for key in self.base:
            yield key
        if self.active:
            for key in self.added:
                yield key

    __iter__ = iterkeys
    Get = View.get

    def filter_keys(self, name, key):
        if self.active and name == "productTypeID" and key in self.byProduct:
            return [self.byProduct[key]]
        return self.base.filter_keys(name, key)

    def filter(self, name, key):
        if self.active and name == "productTypeID" and key in self.byProduct:
            return [self.added[self.byProduct[key]]]
        return self.base.filter(name, key)

    def index(self, name, key):
        if self.active and name == "productTypeID" and key in self.byProduct:
            return self.added[self.byProduct[key]]
        return self.base.index(name, key)

    def __getattr__(self, name):
        return getattr(self.base, name)


class Transaction(object):
    def __init__(self, generation):
        require(len(generation) == 24 and all(c in "0123456789abcdef" for c in generation), "invalid generation")
        self.generation = generation
        self.active = True
        self.replacements = []

    def replace(self, obj, name, previous, view):
        require(self.active and getattr(obj, name) is previous, "catalog ownership changed at " + name)
        setattr(obj, name, view)
        self.replacements.append((obj, name, previous, view))

    def restore(self, generation):
        require(generation == self.generation, "stale catalog generation")
        self.active = False
        conflicts = []
        for obj, name, previous, view in reversed(self.replacements):
            view.active = False
            if getattr(obj, name) is view:
                setattr(obj, name, previous)
            else:
                conflicts.append(name)
        self.replacements = []
        require(not conflicts, "foreign ownership during rollback: " + ", ".join(conflicts))


HOLD_TEXT = {
    1556: "to Mining Hold capacity",
    1557: "to Gas Hold capacity",
    1558: "to Mineral Hold capacity",
    3136: "to Ice Hold capacity",
    1653: "to Planetary Commodities Hold capacity",
}


def build_catalog(payload, native, attribute, effect_ref):
    fleet = payload["fleet"]
    assert fleet["clientBuild"] == 3396210
    additions = payload["additions"]
    server_types = dict((row["typeID"], row) for row in additions["itemTypes"])
    owned = dict((key, {}) for key in ("types", "typedogma", "requiredskillsfortypes", "dogmaeffects", "graphicids"))
    locale, traits = {}, {}
    for ship in fleet["ships"]:
        ship_id, bpo_id, graphic_id, effect_id = (ship[k] for k in ("typeID", "blueprintTypeID", "graphicID", "effectID"))
        stock = ship["stockTypeID"]
        race, skill, velocity_effect = fleet["races"][ship["empire"]][:3]
        _, stock_bpo, _, _, boosted = fleet["roles"][ship["role"]]
        name_id = ship["messageBase"]
        description_id, bpo_name_id = name_id - 1, name_id - 2
        native_type = native["types"][stock]
        require(native_type.groupID == 28 and native_type.raceID == race and
                native_type.graphicID == ship["stockGraphicID"], "native hull source mismatch")
        require(dict(native["requiredskillsfortypes"][stock].iteritems()) == {skill: 1},
                "native racial skill source mismatch")
        for type_id, source_id, message_id, description in (
            (ship_id, stock, name_id, description_id),
            (bpo_id, stock_bpo, bpo_name_id, None),
        ):
            server_type = server_types[type_id]
            base_type = native["types"][source_id]
            require(type_id not in owned["types"] and type_id not in native["types"], "duplicate private type")
            require(base_type.groupID == server_type["groupID"] and base_type.published,
                    "type source group or publication changed")
            owned["types"][type_id] = Row(
                base_type, typeID=type_id, typeNameID=message_id, descriptionID=description,
                capacity=server_type["capacity"], basePrice=server_type["basePrice"],
                graphicID=graphic_id, marketGroupID=server_type["marketGroupID"], published=True,
            )
            locale[message_id] = server_type["name"]
            if description is not None:
                locale[description] = server_type["description"]
            dogma = additions["typeDogma"][str(type_id)]
            base_dogma = native["typedogma"][source_id]
            stock_effects = dict((row.effectID, row) for row in base_dogma.dogmaEffects)
            velocity_ref = next((row for row in native["typedogma"][stock].dogmaEffects
                                 if row.effectID == velocity_effect), None)
            if velocity_ref is None:
                # The fast haulers do not have the approved velocity effect;
                # use the same faction's heavy hauler's native effect row.
                reference = {1: 649, 4: 1944, 2: 652, 8: 657}[race]
                velocity_ref = next(row for row in native["typedogma"][reference].dogmaEffects
                                    if row.effectID == velocity_effect)
            effect_rows = []
            for effect in dogma["effects"]:
                if effect == effect_id:
                    effect_rows.append(effect_ref(velocity_ref, effect))
                elif effect == velocity_effect:
                    effect_rows.append(velocity_ref)
                else:
                    effect_rows.append(stock_effects[effect])
            # Mass/volume/capacity/radius are owned by evetypes. The native
            # identity helper merges those fields into the Dogma surface.
            values = tuple(attribute(int(k), float(v)) for k, v in sorted(
                dogma["attributes"].iteritems(), key=lambda row: int(row[0])) if int(k) not in (4,38,161,162))
            owned["typedogma"][type_id] = Row(base_dogma, dogmaAttributes=values, dogmaEffects=tuple(effect_rows))
        owned["requiredskillsfortypes"][ship_id] = native["requiredskillsfortypes"][stock]
        graphic = native["graphicids"][ship["stockGraphicID"]]
        require(graphic.sofHullName == ship["stockAlias"], "native hull alias mismatch")
        owned["graphicids"][graphic_id] = Row(graphic, sofHullName=str(ship["alias"]))
        effect = payload["effects"][str(effect_id)]
        effect_base = native["dogmaeffects"][velocity_effect]
        modifier = effect_base.modifierInfo[0]
        info = tuple(Row(modifier, **row) for row in effect["modifierInfo"])
        owned["dogmaeffects"][effect_id] = Row(effect_base, effectID=effect_id,
                                               effectName=effect["name"], modifierInfo=info, published=False)

        labels = [(5, 2, "to ship maximum velocity")]
        labels.extend((10, 1, HOLD_TEXT[id_]) for id_ in boosted)
        labels.append((90, 1, "reduction in effective distance traveled for jump fatigue"))
        bonuses = []
        for i, (percent, importance, label) in enumerate(labels):
            key = name_id - 3 - i
            locale[key] = label
            bonuses.append(dict(bonus=percent, importance=importance, nameID=key, unitID=105))
        traits[ship_id] = dict(types={str(skill): bonuses[:-1]}, roleBonuses=[bonuses[-1]], miscBonuses=[])

    require(len(owned["types"]) == 2 * len(fleet["ships"]) and len(owned["graphicids"]) == len(fleet["ships"]) and
            len(owned["dogmaeffects"]) == len(fleet["ships"]), "incomplete fleet")
    require(not any(getattr(row, "typeNameID", None) in locale or
                    getattr(row, "descriptionID", None) in locale for row in native["types"].itervalues()),
            "native type localization collision")
    aliases = set(row.sofHullName for row in owned["graphicids"].itervalues())
    require(len(aliases) == len(fleet["ships"]) and not any(getattr(row, "sofHullName", None) in aliases
                                         for row in native["graphicids"].itervalues()), "native SOF collision")
    views = dict((k, View(native[k], rows)) for k, rows in owned.iteritems())
    return views, locale, traits


def build_blueprints(native, definitions, decode):
    private, products = {}, {}
    for item in definitions:
        id_, product = item["blueprintTypeID"], item["productTypeID"]
        require(id_ not in private and product not in products, "duplicate blueprint")
        require(set(item["activities"]) == {"manufacturing", "copying", "research_material", "research_time"},
                "unexpected blueprint activity set")
        row = decode(dict(blueprintTypeID=id_, maxProductionLimit=item["maxProductionLimit"],
                          activities=item["activities"]))
        require(row.blueprintTypeID == id_ and row.productTypeID == product and row.original,
                "native blueprint decode mismatch")
        require(set(row.all_activities) == {1, 3, 4, 5}, "native blueprint activity mismatch")
        private[id_] = row
        products[product] = id_
    return BlueprintView(native, private, products)

