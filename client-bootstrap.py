# Python 2.7 signed-login bootstrap for EVE 3396210.
OWNER_KEY = "_empire_haulers_session_v040"
MOUNT_KEY = "_empire_haulers_mount_v040"
PASS = "CATALOG_READY ships=12 blueprintTypes=12"


class SessionCatalog(object):
    __notifyevents__ = ["OnDisconnect", "OnSessionChanged"]

    def __init__(self, builtins, manager, session, generation, catalog, dogma):
        self.builtins, self.manager, self.session = builtins, manager, session
        self.catalog, self.dogma = catalog, dogma
        self.tx = Transaction(generation)
        self.events = []
        self.ids = set()
        self.effect_entries = []
        self.blueprints = None
        self.active = True

    def subscribe(self):
        for event in self.__notifyevents__:
            self.manager.RegisterForNotifyEvent(self, event)
            self.events.append(event)

    def check_current(self):
        require(self.active and getattr(self.builtins, OWNER_KEY, None) is self,
                "client generation no longer owns this catalog")
        require(not self.session.charid, "catalog bootstrap after character selection")

    def invalidate(self):
        self.catalog._OnReloadTypes()
        self.catalog.ClearMemoized()
        self.dogma.refresh_dogma()
        godma = self.manager.GetServiceIfRunning("godma")
        state = getattr(godma, "stateManager", None)
        static = self.manager.GetServiceIfRunning("clientDogmaStaticSvc")
        for obj, attributes in ((state, ("typeWrappers", "effectsByType")),
                                (static, ("attributesByTypeAttribute", "effectsByType",
                                          "passiveFilteredEffectsByType", "defaultEffectByType"))):
            for name in attributes:
                cache = getattr(obj, name, None)
                if isinstance(cache, dict):
                    for type_id in self.ids:
                        cache.pop(type_id, None)
        types_by_effect = getattr(static, "typesByEffect", None)
        if isinstance(types_by_effect, dict):
            for entries in types_by_effect.itervalues():
                if isinstance(entries, dict):
                    for type_id in self.ids:
                        entries.pop(type_id, None)
        fn = getattr(godma, "GetFlagsWithValidCapacity", None)
        clear = getattr(getattr(fn, "im_func", fn), "clear_memoized", None)
        if callable(clear):
            clear()

    def put_effects(self, target, compiled):
        require(isinstance(target, dict), "unexpected native effect compiler cache")
        require(not any(id_ in target for id_ in compiled), "private compiled effect collision")
        for id_, effect in compiled.iteritems():
            target[id_] = effect
            self.effect_entries.append((target,id_,effect))

    def restore(self):
        if not self.active:
            return
        self.active = False
        failures = []
        for target, id_, effect in reversed(self.effect_entries):
            if target.get(id_) is effect:
                del target[id_]
            else:
                failures.append("effect ownership")
        self.effect_entries = []
        actions = [lambda: self.tx.restore(self.tx.generation), self.invalidate]
        if self.blueprints is not None:
            actions.insert(0, self.blueprints.restore)
        for action in actions:
            try:
                action()
            except Exception as error:
                failures.append(str(error) or type(error).__name__)
        for event in reversed(self.events):
            try:
                self.manager.UnregisterForNotifyEvent(self,event)
            except Exception:
                failures.append(event)
        self.events = []
        if getattr(self.builtins,OWNER_KEY,None) is self:
            delattr(self.builtins,OWNER_KEY)
        require(not failures, "catalog rollback " + ", ".join(failures))

    def finish(self, reason):
        if not self.active or getattr(self.builtins,OWNER_KEY,None) is not self:
            return
        try:
            self.restore()
            print("EMPIRE_HAULERS:%s:REMOVED %s" % (self.tx.generation,reason))
        except Exception:
            print("EMPIRE_HAULERS:%s:ROLLBACK_FAILED close-client" % self.tx.generation)

    def OnDisconnect(self, *args):
        self.finish("disconnect")

    def OnSessionChanged(self, _remote, session, change):
        user = change.get("userid")
        if session is self.session and user and user[0] and user[0]!=user[1]:
            self.finish("account-change")


class ReverseMaterials(View):
    def __init__(self, base, definitions):
        self.base = base
        self.active = True
        self.added = {}
        for bp in definitions:
            for activity in bp["activities"].itervalues():
                for material in activity.get("materials", []):
                    self.added.setdefault(material["typeID"],set()).add(bp["blueprintTypeID"])
        self.replacements = {}
        for key in list(self.added):
            if key in base:
                old = base[key]
                require(isinstance(old,(tuple,list,set,frozenset)), "unexpected reverse blueprint index rows")
                combined = list(old)+sorted(self.added.pop(key)-set(old))
                self.replacements[key] = type(old)(combined)


class BlueprintRegistration(object):
    def __init__(self, cfg, generation, definitions, decode, ships):
        self.cfg = cfg
        self.generation = generation
        self.definitions = definitions
        self.decode = decode
        self.ships = ships
        self.tx = None
        self.mastery_tx = None
        self.active = True
        self.original = cfg.LoadCfgData
        self.previous_attribute = cfg.__dict__.get("LoadCfgData")
        self.hook = self.load_cfg
        cfg.LoadCfgData = self.hook

    def clear_views(self):
        failures = []
        for name in ("mastery_tx", "tx"):
            tx = getattr(self, name)
            setattr(self, name, None)
            if tx is not None:
                try:
                    tx.restore(self.generation)
                except Exception as error:
                    failures.append(str(error))
        require(not failures, "; ".join(failures))

    def restore(self):
        self.active = False
        if self.cfg.__dict__.get("LoadCfgData") is self.hook:
            if self.previous_attribute is None:
                del self.cfg.LoadCfgData
            else:
                self.cfg.LoadCfgData = self.previous_attribute
        self.clear_views()

    def load_cfg(self, *args, **kwargs):
        self.clear_views()
        result = self.original(*args, **kwargs)
        if self.active:
            try:
                self.add_views()
            except Exception as error:
                self.clear_views()
                self.cfg.LogError("[EmpireHaulers] BLUEPRINTS_BLOCKED %s" % error)
            try:
                self.add_masteries()
            except Exception as error:
                if self.mastery_tx is not None:
                    tx, self.mastery_tx = self.mastery_tx, None
                    tx.restore(self.generation)
                self.cfg.LogError("[EmpireHaulers] MASTERIES_BLOCKED %s" % error)
        return result

    def add_masteries(self):
        # LoadCfgData owns certificates.static and loads it after login ACK.
        # Extend that freshly loaded root before Show Info / Ship Tree use it.
        stock = self.cfg.certificates
        view = build_masteries(stock, self.ships)
        self.mastery_tx = Transaction(self.generation)
        self.mastery_tx.replace(self.cfg, "certificates", stock, view)
        self.cfg.LogNotice("[EmpireHaulers] MASTERIES_READY ships=%d levels=5 source=native-stock" % len(self.ships))

    def add_views(self):
        # DataConfig calls this native loader after the handshake ACK. The
        # stock storage and material index belong to that load, even on relog.
        stock = self.cfg.blueprints
        materials = self.cfg.blueprintsByMaterialTypeIDs
        blueprints = build_blueprints(stock,self.definitions,lambda row:self.decode(row,stock.mapping))
        reverse = ReverseMaterials(materials,self.definitions)
        self.tx = Transaction(self.generation)
        self.tx.replace(self.cfg,"blueprints",stock,blueprints)
        self.tx.replace(self.cfg,"blueprintsByMaterialTypeIDs",materials,reverse)
        for item in self.definitions:
            id_ = item["blueprintTypeID"]
            product = item["productTypeID"]
            require(self.cfg.blueprints.index("productTypeID",product).blueprintTypeID==id_ and
                    8 not in self.cfg.blueprints[id_].all_activities, "native Industry index failed")
        self.cfg.LogNotice("[EmpireHaulers] BLUEPRINTS_READY count=%d" % len(self.definitions))


def normalized_path(value):
    import os
    return os.path.normcase(os.path.normpath(value)) if value else ""


def bind_subset(fn, helpers):
    # The installed Dogma helpers use caching.memoize.Memoize. Work with the
    # underlying function so the subset never hits or populates the stock cache.
    if fn.func_code.co_name == "inner_deco" and fn.func_code.co_freevars == ("_cache", "fn"):
        fn = fn.func_closure[1].cell_contents
    env=fn.func_globals.copy()
    env.update(helpers)
    return type(fn)(fn.func_code,env,fn.func_name,fn.func_defaults)


def install_static_dogma(owner, static, d, views):
    if static is None:
        return
    subset=tuple((id_,row.dogmaEffects) for id_,row in views["typedogma"].added.iteritems())
    scope={"get_all_type_ids_and_effects":lambda:subset}
    effects=views["dogmaeffects"].added
    # Run the native index builder against only the owned rows. In particular,
    # do not scan or replace the stock static dictionaries after login.
    loader=static.LoadTypeEffects.im_func
    get_by_type=bind_subset(loader.func_globals["get_effects_indexed_by_type_id_and_effect_id"],scope)
    get_by_effect=bind_subset(loader.func_globals["get_effects_indexed_by_effect_id_and_type_id"],scope)
    receiver=Row(None,effects=View(static.effects,effects),unwantedEffects=static.unwantedEffects)
    load=bind_subset(loader,{
        "get_effects_indexed_by_type_id_and_effect_id":get_by_type,
        "get_effects_indexed_by_effect_id_and_type_id":get_by_effect,
        "dogma_data":Row(d,**scope),
    })
    load(receiver,False)
    owner.put_effects(static.effects,effects)
    owner.put_effects(static.effectsByName,dict((r.effectName,r) for r in effects.itervalues()))
    for name in ("effectsByType","passiveFilteredEffectsByType","defaultEffectByType"):
        owner.put_effects(getattr(static,name),getattr(receiver,name))
    for effect_id, rows in receiver.typesByEffect.iteritems():
        if effect_id in static.typesByEffect:
            owner.put_effects(static.typesByEffect[effect_id],rows)
        else:
            owner.put_effects(static.typesByEffect,{effect_id:rows})


def mount_visuals(owner, blue, visuals):
    # SOF has no remove-hull ABI. The private mounts and metadata are owned by
    # this client process. Login views are independently unwound on disconnect.
    path_service = blue.paths
    paths = path_service.GetAllSearchPaths()
    previous = getattr(owner.builtins,MOUNT_KEY,None)
    signature = visuals["signature"]
    # JSON yields unicode in Python 2. Native resource keys are byte strings,
    # while SetSearchPath takes a wide filesystem path as its second argument.
    roots = dict((str(scheme), root) for scheme, root in visuals["roots"].iteritems())
    if previous is None:
        require(not set(roots).intersection(paths), "private resource scheme already registered")
        previous = dict(signature=signature,roots=roots,installed=set(),hulls={})
        setattr(owner.builtins,MOUNT_KEY,previous)
    require(previous["signature"]==signature and previous["roots"]==roots,
            "previous family resource version loaded close client")
    factory = owner.manager.GetService("sofService").spaceObjectFactory
    factory._LoadOrYield()
    owner.check_current()
    manager = factory._sof.dataMgr
    require(factory._loaded, "native SOF data manager not loaded")
    for scheme, root in roots.iteritems():
        if scheme not in previous["installed"]:
            require(scheme not in paths, "foreign private mount")
            path_service.SetSearchPath(scheme,unicode(root))
            previous["installed"].add(scheme)
        require(normalized_path(path_service.GetAllSearchPaths().get(scheme))==normalized_path(root),
                "private resource mount ownership changed")
    import os
    for uri in visuals["files"]:
        uri = str(uri)
        scheme, relative = uri.split(":/",1)
        local = os.path.join(roots[scheme],*relative.split("/"))
        require(path_service.FileExistsLocally(uri) and
                normalized_path(path_service.ResolvePath(uri))==normalized_path(local), "private resource unavailable")
    for row in visuals["hulls"]:
        alias = str(row["alias"])
        stock_alias = str(row["stockAlias"])
        require(manager.HasHullData(stock_alias), "stock SOF hull unavailable " + stock_alias)
        if alias in previous["hulls"]:
            require(previous["hulls"][alias]==row["geometryUri"] and manager.HasHullData(alias),
                    "private SOF hull ownership changed " + alias)
            continue
        require(not manager.HasHullData(alias), "foreign SOF hull already loaded close client " + alias)
        hull = blue.resMan.LoadObject(str(row["blackUri"]))
        owner.check_current()
        require(hull is not None and hull.name==alias and hull.geometryResFilePath==row["geometryUri"],
                "native BLACK decode failed " + alias)
        require(manager.UpdateHull(alias,hull) and manager.HasHullData(alias), "native hull registration failed " + alias)
        previous["hulls"][alias] = row["geometryUri"]


def activate_catalog(owner, payload, cfg, d, e, skills, gfx, loc, traits_data,
                     trait_ui, fsd_decode, create_effect, effect_tables, icon_folder):
    holders = {
        "types": e.Types,
        "typedogma": d.TypeDogma,
        "requiredskillsfortypes": skills.RequiredSkillsForTypes,
        "dogmaeffects": d.DogmaEffects,
        "graphicids": gfx.fsdGraphicIDs.GraphicIDs,
    }
    native = dict((key,holder.GetData()) for key,holder in holders.iteritems())
    for key, table in native.iteritems():
        require(type(table).__module__=="cfsd" and holders[key].__dict__.get("__binary__") is table,
                "foreign native catalog owner " + key)
    views, locale, traits = build_catalog(payload,native,d.DogmaTypeAttribute,
                                          lambda ref, id_: Row(ref,effectID=id_))
    for graphic in views["graphicids"].added.itervalues():
        graphic.fields["iconInfo"] = Row(getattr(graphic.base,"iconInfo",None),folder=icon_folder)
    trait_base = traits_data.get_info_bubble_type_bonuses()
    require(traits_data.INFO_BUBBLE_TYPE_BONUSES is trait_base, "native trait cache changed")
    compiled = dict((id_,create_effect(row)) for id_,row in views["dogmaeffects"].added.iteritems())
    require(all(getattr(effect,"__modifies_ship__",False) for effect in compiled.itervalues()),
            "native effect compile did not bind ship")
    owner.check_current()
    owner.ids.update(views["types"].added)
    tx = owner.tx
    for key, view in views.iteritems():
        tx.replace(holders[key],"__binary__",native[key],view)
    tx.replace(traits_data,"INFO_BUBBLE_TYPE_BONUSES",trait_base,View(trait_base,traits))
    for module in (loc,trait_ui):
        localization = module.localization
        tx.replace(module,"localization",localization,LocaleView(localization,locale))
    for table in effect_tables:
        owner.put_effects(table,compiled)
    owner.invalidate()
    install_static_dogma(owner,owner.manager.GetServiceIfRunning("clientDogmaStaticSvc"),d,views)
    owner.check_current()
    for ship in payload["fleet"]["ships"]:
        type_id,bpo = ship["typeID"],ship["blueprintTypeID"]
        require(e.Exists(type_id) and e.Exists(bpo) and e.GetName(type_id)==ship["name"] and
                e.GetCategoryID(type_id)==6 and e.GetCategoryID(bpo)==9 and
                e.GetCapacity(type_id)==(500 if ship["role"]=="gas" else 550) and e.GetGraphicID(type_id)==ship["graphicID"],
                "native type readback failed " + ship["name"])
        require(gfx.BuildSOFDNAFromTypeID(type_id).split(":")[0]==ship["alias"],
                "native SOF DNA readback failed " + ship["name"])
        require(d.get_effect(ship["effectID"]).effectID==ship["effectID"],"native Dogma effect lookup failed")
    require(e.GetGraphicID(649)==52 and e.GetCategoryID(10117)==11 and
            e.GetName(2000000001)=="Wolverine","Wolverine or stock identity readback failed")
    owner.blueprints = BlueprintRegistration(cfg,tx.generation,
        payload["additions"]["industryBlueprints"],fsd_decode,payload["fleet"]["ships"])


def run_family(context,generation):
    import __builtin__ as builtins
    owner = None
    phase = "login context"
    try:
        import base64
        import json
        import zlib
        import blue
        import dogma.data as dogma
        from dogma.effects.util import CreateEffect
        import evetypes
        import evetypes.localizationUtils as loc
        import evetypes.skills as skills
        import evegraphics.utils as gfx
        import fsdlite
        import infobubbles
        from eve.client.script.ui.shared import traits as trait_ui
        boot = context.get("boot",getattr(builtins,"boot",None))
        manager = context.get("sm",getattr(builtins,"sm",None))
        session = context.get("session",getattr(builtins,"session",None))
        cfg = context.get("cfg",getattr(builtins,"cfg",None))
        require(int(getattr(boot,"build",0))==3396210,"unsupported client build")
        require(manager is not None and session is not None and cfg is not None and not session.charid,
                "login context missing or character already active")
        require(not hasattr(builtins,"_evejs_tayra_canary_owner_v1"),"legacy Wolverine session still active close client")
        previous = getattr(builtins,OWNER_KEY,None)
        if previous is not None:
            previous.restore()
        owner = SessionCatalog(builtins,manager,session,generation,evetypes,dogma)
        setattr(builtins,OWNER_KEY,owner)
        owner.subscribe()
        bundle=json.loads(zlib.decompress(base64.b64decode(_family_bundle)))
        phase = "resource mount"
        mount_visuals(owner,blue,bundle["visuals"])
        phase = "effect compiler"
        effect_tables=[]
        # Warmed compilers need an owned additive entry. Later-starting
        # client/ghost compilers see the native DogmaEffects view when run.
        compiler=manager.GetService("clientEffectCompiler")
        effect_tables.append(compiler.GetEffects())
        ghost=manager.GetServiceIfRunning("ghostFittingEffectCompiler")
        if ghost is not None and ghost.GetEffects() is not effect_tables[0]:
            effect_tables.append(ghost.GetEffects())
        phase = "catalog activation"
        activate_catalog(owner,bundle["catalog"],cfg,dogma,evetypes,skills,gfx,loc,infobubbles,
            trait_ui,lambda row,mapping: fsdlite.decode(json.dumps(row),mapping=mapping,json=True),
            CreateEffect,effect_tables,str(bundle["visuals"]["iconFolder"]))
        status=PASS
    except Exception as error:
        reason=phase + " - " + (str(error) or type(error).__name__)
        status="BLOCKED "+"".join(c if c.isalnum() or c in "_. -" else " " for c in reason)[:150]
        if owner is not None:
            try:
                owner.restore()
            except Exception:
                status="ROLLBACK_FAILED close-client"
    print("EMPIRE_HAULERS:%s:%s" % (generation,status))

