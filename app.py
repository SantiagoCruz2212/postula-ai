import os, random, time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core import ai, db, sources, mailer
from core.cv_parser import extract_text

st.set_page_config(page_title="Postula AI", page_icon="📄", layout="wide")
DATA = Path("data")
DATA.mkdir(exist_ok=True)

if not os.getenv("ANTHROPIC_API_KEY"):
    st.error("Falta ANTHROPIC_API_KEY en el archivo .env")
    st.stop()

st.title("📄 Postula AI — vacantes remotas para Colombia")
tab_perfil, tab_vac, tab_hist = st.tabs(["1. Mi CV y perfil", "2. Vacantes", "3. Historial"])

# ---------------------------------------------------------------- Perfil
with tab_perfil:
    up = st.file_uploader("Sube tu CV (PDF, DOCX o TXT)", type=["pdf", "docx", "txt"])
    if up and st.button("Analizar CV con Claude", type="primary"):
        path = DATA / f"cv{Path(up.name).suffix.lower()}"
        path.write_bytes(up.getbuffer())
        with st.spinner("Analizando tu CV..."):
            try:
                texto = extract_text(path)
                if len(texto) < 200:
                    st.error("No pude extraer texto del CV (¿es una imagen escaneada?).")
                else:
                    perfil = ai.extract_profile(texto)
                    db.kv_set("perfil", perfil)
                    db.kv_set("cv_path", str(path))
                    st.success("Perfil extraído. Revísalo y edítalo abajo.")
            except Exception as e:
                st.error(f"Error: {e}")

    perfil = db.kv_get("perfil")
    if perfil:
        c1, c2 = st.columns(2)
        perfil["nombre"] = c1.text_input("Nombre", perfil.get("nombre", ""))
        perfil["titulo"] = c2.text_input("Título profesional", perfil.get("titulo", ""))
        perfil["resumen"] = st.text_area("Resumen", perfil.get("resumen", ""))
        perfil["skills"] = [s.strip() for s in st.text_input("Skills (separadas por coma)", ", ".join(perfil.get("skills", []))).split(",") if s.strip()]
        perfil["roles_objetivo"] = [s.strip() for s in st.text_input("Cargos objetivo", ", ".join(perfil.get("roles_objetivo", []))).split(",") if s.strip()]
        perfil["keywords_busqueda"] = [s.strip() for s in st.text_input("Palabras clave de búsqueda", ", ".join(perfil.get("keywords_busqueda", []))).split(",") if s.strip()]
        st.caption(f"Seniority: {perfil.get('seniority')} · Experiencia: {perfil.get('anos_experiencia')} años · Idiomas: {', '.join(perfil.get('idiomas', []))}")
        if st.button("Guardar cambios"):
            db.kv_set("perfil", perfil)
            st.success("Guardado")

# ---------------------------------------------------------------- Vacantes
with tab_vac:
    perfil = db.kv_get("perfil")
    if not perfil:
        st.info("Primero sube y analiza tu CV en la pestaña 1.")
    else:
        kws = perfil.get("keywords_busqueda", [])
        c1, c2 = st.columns([3, 2])
        fuentes = c2.multiselect("Fuentes", list(sources.SOURCES), default=list(sources.SOURCES))
        c1.write("**Búsqueda:** " + " · ".join(kws))

        if st.button("🔎 Buscar y puntuar vacantes", type="primary"):
            log = st.empty()
            with st.status("Buscando...", expanded=True) as status:
                errores = []
                encontradas = sources.search_all(kws, fuentes, log=errores.append)
                st.write(f"{len(encontradas)} vacantes remotas encontradas")
                nuevas = db.add_new_jobs(encontradas)
                st.write(f"{len(nuevas)} son nuevas. Puntuando con Claude...")
                jobs = db.get_jobs(nuevas)
                bar = st.progress(0.0)
                for i in range(0, len(jobs), 8):
                    lote = jobs[i:i + 8]
                    try:
                        for r in ai.score_jobs(perfil, lote):
                            j = lote[int(r["i"])]
                            db.update_job(j["id"], score=int(r["score"]), reason=r.get("razon", ""), gaps=r.get("faltantes", ""))
                    except Exception as e:
                        errores.append(f"puntuación: {e}")
                    bar.progress(min((i + 8) / max(len(jobs), 1), 1.0))
                if errores:
                    st.warning("Avisos:\n" + "\n".join(f"- {e}" for e in errores[:10]))
                status.update(label="Listo", state="complete")

        with st.expander("Buscar en LinkedIn, Indeed, Computrabajo (abre la búsqueda ya filtrada)"):
            for kw, links in sources.portal_links(kws):
                st.write(f"**{kw}**: " + " · ".join(f"[{n}]({u})" for n, u in links.items()))
            st.caption("Estos portales no permiten consulta automática. Si encuentras una vacante, pega su texto abajo y la evalúo.")

        with st.expander("➕ Evaluar una vacante que encontré manualmente"):
            mt, mc, mu = st.text_input("Cargo"), st.text_input("Empresa"), st.text_input("URL")
            md = st.text_area("Descripción completa de la vacante")
            if st.button("Agregar y puntuar") and mt and mu and md:
                j = sources._job("Manual", mt, mc, "Remoto", mu, md)
                nuevas = db.add_new_jobs([j])
                if nuevas:
                    j = db.get_jobs(nuevas)[0]
                    r = ai.score_jobs(perfil, [j])[0]
                    db.update_job(j["id"], score=int(r["score"]), reason=r.get("razon", ""), gaps=r.get("faltantes", ""))
                    st.success("Agregada")
                else:
                    st.info("Esa URL ya estaba registrada")

        st.divider()
        jobs = db.get_jobs()
        min_score = st.slider("Puntaje mínimo", 0, 100, 60)
        ver = [j for j in jobs if (j["score"] or 0) >= min_score and j["status"] in ("nueva", "lista")]
        st.write(f"**{len(ver)}** vacantes con puntaje ≥ {min_score}")

        if ver:
            df = pd.DataFrame([{
                "Elegir": False, "id": j["id"], "Score": j["score"], "Cargo": j["title"], "Empresa": j["company"],
                "Ubicación": j["location"], "Fuente": j["source"], "Email": j["email"], "Estado": j["status"],
            } for j in ver])
            ed = st.data_editor(df, hide_index=True, width="stretch", disabled=[c for c in df.columns if c != "Elegir"],
                                column_config={"id": None}, key="tabla")
            sel = ed[ed["Elegir"]]["id"].tolist()

            b1, b2 = st.columns(2)
            if b1.button(f"✍️ Generar mensajes ({len(sel)})", disabled=not sel):
                bar = st.progress(0.0)
                for n, jid in enumerate(sel):
                    j = db.get_jobs([jid])[0]
                    try:
                        m = ai.write_message(perfil, j)
                        db.update_job(jid, subject=m["asunto"], message=m["cuerpo"], status="lista")
                    except Exception as e:
                        st.warning(f"{j['title']}: {e}")
                    bar.progress((n + 1) / len(sel))
                st.rerun()

            limite = int(os.getenv("LIMITE_DIARIO", 15))
            restantes = limite - db.enviados_hoy()
            b2.write(f"Envíos hoy: {db.enviados_hoy()}/{limite}")
            listas = [j for j in db.get_jobs(sel) if j["status"] == "lista" and j["email"]]
            if b2.button(f"🚀 Enviar automáticamente ({len(listas)} con email)", disabled=not listas or restantes <= 0):
                if not (os.getenv("SMTP_EMAIL") and os.getenv("SMTP_PASSWORD")):
                    st.error("Configura SMTP_EMAIL y SMTP_PASSWORD en .env")
                else:
                    cv = Path(db.kv_get("cv_path"))
                    prog = st.progress(0.0)
                    for n, j in enumerate(listas[:restantes]):
                        try:
                            mailer.send(j["email"], j["subject"], j["message"], cv, perfil.get("nombre", ""))
                            db.update_job(j["id"], status="enviada", sent_at=datetime.now().isoformat(timespec="seconds"))
                            st.write(f"✅ {j['company'] or j['title']} → {j['email']}")
                            time.sleep(random.uniform(30, 90))
                        except Exception as e:
                            st.error(f"{j['email']}: {e}")
                        prog.progress((n + 1) / min(len(listas), restantes))

            st.subheader("Detalle")
            for j in db.get_jobs(sel):
                with st.expander(f"{j['score']} · {j['title']} — {j['company']}", expanded=len(sel) == 1):
                    st.write(f"**Por qué:** {j['reason']}")
                    if j["gaps"]:
                        st.write(f"**Te falta:** {j['gaps']}")
                    st.markdown(f"[Abrir vacante]({j['url']})" + (f" · contacto: `{j['email']}`" if j["email"] else " · sin email: aplica en el enlace"))
                    st.text_area("Descripción", j["description"][:3000], height=150, key="d" + j["id"], disabled=True)
                    if j["message"]:
                        s = st.text_input("Asunto", j["subject"], key="s" + j["id"])
                        m = st.text_area("Mensaje", j["message"], height=200, key="m" + j["id"])
                        c1, c2 = st.columns(2)
                        if c1.button("Guardar edición", key="g" + j["id"]):
                            db.update_job(j["id"], subject=s, message=m)
                        if not j["email"] and c2.button("Marcar como postulada (portal)", key="p" + j["id"]):
                            db.update_job(j["id"], status="enviada", sent_at=datetime.now().isoformat(timespec="seconds"))
                            st.rerun()

# ---------------------------------------------------------------- Historial
with tab_hist:
    todas = db.get_jobs()
    enviadas = [j for j in todas if j["status"] == "enviada"]
    st.metric("Postulaciones enviadas", len(enviadas))
    if enviadas:
        st.dataframe(pd.DataFrame([{"Fecha": j["sent_at"], "Cargo": j["title"], "Empresa": j["company"],
                                    "Email": j["email"], "URL": j["url"]} for j in enviadas]),
                     hide_index=True, width="stretch")

