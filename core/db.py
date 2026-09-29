import hashlib, json, sqlite3
from datetime import datetime, date
from pathlib import Path

DB = Path("data/app.db")


def conn():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT, location TEXT,
        url TEXT, description TEXT, email TEXT, score INTEGER, reason TEXT, gaps TEXT,
        subject TEXT, message TEXT, status TEXT DEFAULT 'nueva', sent_at TEXT, created TEXT);
    """)
    return c


def kv_get(k, default=None):
    c = conn()
    r = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    c.close()
    return json.loads(r["v"]) if r else default


def kv_set(k, v):
    c = conn()
    with c:
        c.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, json.dumps(v, ensure_ascii=False)))
    c.close()


def job_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def add_new_jobs(jobs):
    """Inserta solo vacantes nuevas; devuelve las ids insertadas."""
    nuevas = []
    c = conn()
    with c:
        for j in jobs:
            jid = job_id(j["url"])
            if c.execute("SELECT 1 FROM jobs WHERE id=?", (jid,)).fetchone():
                continue
            c.execute(
                "INSERT INTO jobs (id,source,title,company,location,url,description,email,created) VALUES (?,?,?,?,?,?,?,?,?)",
                (jid, j["source"], j["title"], j["company"], j["location"], j["url"],
                 j["description"], j.get("email", ""), datetime.now().isoformat(timespec="seconds")))
            nuevas.append(jid)
    c.close()
    return nuevas


def get_jobs(ids=None):
    c = conn()
    if ids is None:
        rows = c.execute("SELECT * FROM jobs ORDER BY COALESCE(score,-1) DESC, created DESC").fetchall()
    elif ids:
        q = ",".join("?" * len(ids))
        rows = c.execute(f"SELECT * FROM jobs WHERE id IN ({q})", list(ids)).fetchall()
    else:
        rows = []
    c.close()
    return [dict(r) for r in rows]


def update_job(jid, **fields):
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    c = conn()
    with c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*fields.values(), jid))
    c.close()


def enviados_hoy():
    c = conn()
    n = c.execute("SELECT COUNT(*) n FROM jobs WHERE status='enviada' AND sent_at LIKE ?",
                  (date.today().isoformat() + "%",)).fetchone()["n"]
    c.close()
    return n
