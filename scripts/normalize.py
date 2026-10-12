import json, re, unicodedata, os
HERE = os.path.dirname(os.path.abspath(__file__))

def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("’", "'").replace("`", "'")
    s = re.sub(r"\b(al|el|ul|ur|bin|ibn|abu|abd|mullah|maulana|maulvi|sheikh|shaykh|haji|hajji|dr|mr|general|gen|lt|lieutenant|mufti|qari|khalifa)[.\s'-]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(the|of|province|city|district|network|group)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

class Resolver:
    def __init__(self, path=os.path.join(HERE, "aliases.json")):
        self.canon = {}  # kind -> fold(alias) -> canonical
        d = json.load(open(path))
        for kind in ("persons", "organizations", "places"):
            self.canon[kind] = {}
            for canonical, aliases in d[kind].items():
                for a in [canonical] + aliases:
                    self.canon[kind][fold(a)] = canonical
                    self.canon[kind][a.lower().strip()] = canonical
    def resolve(self, kind, name):
        if not name: return None
        k = name.lower().strip()
        if k in self.canon[kind]: return self.canon[kind][k]
        f = fold(name)
        if f in self.canon[kind]: return self.canon[kind][f]
        return name.strip()
    def resolve_any(self, name):
        for kind in ("persons", "organizations", "places"):
            r = self.resolve(kind, name)
            if r != name.strip(): return kind, r
        return None, name.strip()
