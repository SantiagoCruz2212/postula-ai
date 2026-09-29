"""Fuentes de vacantes remotas con APIs publicas. Cada fuente falla de forma aislada."""
import html, json, re, urllib.parse, urllib.request

UA = {"User-Agent": "auto-cv/1.0 (uso personal)"}
OK_LOC = ("worldwide", "anywhere", "latam", "latin america", "latinoam", "colombia", "americas",
          "south america", "global", "remote", "remoto")
BAD_EMAIL = ("noreply", "no-reply", "example.com", "sentry")


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def _email(t):
    for m in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", t or ""):
        if not any(b in m.lower() for b in BAD_EMAIL):
            return m
    return ""


def _ok_location(loc):
    loc = (loc or "").lower()
    return any(k in loc for k in OK_LOC) if loc else True


def _job(source, title, company, location, url, desc):
    d = _clean(desc)
    return {"source": source, "title": _clean(title), "company": _clean(company),
            "location": _clean(location) or "Remoto", "url": url, "description": d, "email": _email(d)}


def remotive(kw):
    d = _get("https://remotive.com/api/remote-jobs?search=" + urllib.parse.quote(kw))
    return [_job("Remotive", j["title"], j["company_name"], j.get("candidate_required_location"), j["url"], j.get("description"))
            for j in d.get("jobs", [])[:25]]


def jobicy(kw):
    d = _get("https://jobicy.com/api/v2/remote-jobs?count=25&tag=" + urllib.parse.quote(kw))
    return [_job("Jobicy", j["jobTitle"], j["companyName"], j.get("jobGeo"), j["url"], j.get("jobDescription") or j.get("jobExcerpt"))
            for j in d.get("jobs", [])]


_remoteok_cache = None


def remoteok(kw):
    global _remoteok_cache
    if _remoteok_cache is None:
        _remoteok_cache = [j for j in _get("https://remoteok.com/api") if isinstance(j, dict) and j.get("position")]
    words = kw.lower().split()
    out = []
    for j in _remoteok_cache:
        blob = (j["position"] + " " + " ".join(j.get("tags") or [])).lower()
        if any(w in blob for w in words):
            out.append(_job("RemoteOK", j["position"], j.get("company"), j.get("location"), j["url"], j.get("description")))
    return out[:25]


def getonbrd(kw):
    d = _get("https://www.getonbrd.com/api/v0/search/jobs?per_page=25&query=" + urllib.parse.quote(kw))
    out = []
    for j in d.get("data", []):
        a = j.get("attributes", {})
        if a.get("remote_modality") not in (None, "fully_remote", "remote"):
            continue
        countries = a.get("countries") or []
        loc = ", ".join(countries) if isinstance(countries, list) else str(countries)
        out.append(_job("GetOnBoard", a.get("title"), "", loc or "LATAM",
                        j.get("links", {}).get("public_url", ""), (a.get("description") or "") + " " + (a.get("functions") or "")))
    return [o for o in out if o["url"]]


SOURCES = {"Remotive": remotive, "Jobicy": jobicy, "RemoteOK": remoteok, "GetOnBoard": getonbrd}


def search_all(keywords, sources=None, log=print):
    res, seen = [], set()
    for name, fn in SOURCES.items():
        if sources and name not in sources:
            continue
        for kw in keywords:
            try:
                for j in fn(kw):
                    if j["url"] and j["url"] not in seen and _ok_location(j["location"]):
                        seen.add(j["url"])
                        res.append(j)
            except Exception as e:
                log(f"{name} ({kw}): {e}")
    return res


def portal_links(keywords):
    """Enlaces de busqueda pre-filtrados para portales sin API publica (LinkedIn, Indeed, etc.)."""
    links = []
    for kw in keywords[:4]:
        q = urllib.parse.quote(kw)
        links.append((kw, {
            "LinkedIn (remoto, Colombia)": f"https://www.linkedin.com/jobs/search/?keywords={q}&location=Colombia&f_WT=2&f_TPR=r604800",
            "Indeed Colombia": f"https://co.indeed.com/jobs?q={q}+remoto&l=Colombia&fromage=7",
            "Computrabajo": f"https://co.computrabajo.com/trabajo-de-{urllib.parse.quote(kw.replace(' ', '-'))}",
            "Google Jobs": f"https://www.google.com/search?q={q}+remoto+colombia&ibp=htl;jobs",
        }))
    return links
