"""Automatiza el envío de CV.
Uso:
  python cv_auto.py enviar [--dry-run]     envía a contactos 'pendiente' (respeta límite diario)
  python cv_auto.py seguimiento [--dry-run] reenvía a quienes no respondieron tras N días
  python cv_auto.py portales               abre las vacantes de portales con el mensaje copiado al portapapeles
Contraseña: variable de entorno CV_SMTP_PASSWORD (contraseña de aplicación de Gmail).
"""
import csv, json, os, random, smtplib, sys, time, webbrowser, subprocess
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

CFG = json.loads(Path("config.json").read_text(encoding="utf-8"))
CSV = Path("contactos.csv")
CAMPOS = ["empresa", "contacto", "email", "cargo", "url_portal", "estado", "fecha_envio"]


def leer():
    with CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def guardar(filas):
    with CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)


def render(plantilla, fila):
    datos = {**CFG, **fila, "contacto": fila["contacto"] or "equipo de selección"}
    return Path(plantilla).read_text(encoding="utf-8").format(**datos)


def construir(fila, plantilla, asunto_prefijo=""):
    m = EmailMessage()
    m["From"] = f'{CFG["nombre"]} <{CFG["email"]}>'
    m["To"] = fila["email"]
    m["Subject"] = asunto_prefijo + CFG["asunto"].format(**{**CFG, **fila})
    m.set_content(render(plantilla, fila))
    cv = Path(CFG["cv_pdf"])
    m.add_attachment(cv.read_bytes(), maintype="application", subtype="pdf", filename=cv.name)
    return m


def enviados_hoy(filas):
    hoy = date.today().isoformat()
    return sum(1 for f in filas if f["fecha_envio"].startswith(hoy))


def lote(filas, candidatos, plantilla, nuevo_estado, dry, prefijo=""):
    cupo = CFG["limite_diario"] - enviados_hoy(filas)
    candidatos = candidatos[: max(cupo, 0)]
    if not candidatos:
        print("Nada que enviar (sin pendientes o límite diario alcanzado).")
        return
    srv = None
    if not dry:
        srv = smtplib.SMTP(CFG["smtp_host"], CFG["smtp_port"])
        srv.starttls()
        srv.login(CFG["email"], os.environ["CV_SMTP_PASSWORD"])
    for i, f in enumerate(candidatos):
        try:
            msg = construir(f, plantilla, prefijo)
            if dry:
                print(f"[dry-run] -> {f['email']} | {msg['Subject']}")
            else:
                srv.send_message(msg)
                f["estado"] = nuevo_estado
                f["fecha_envio"] = datetime.now().isoformat(timespec="seconds")
                guardar(filas)
                print(f"Enviado a {f['email']}")
                if i < len(candidatos) - 1:
                    time.sleep(random.uniform(*CFG["pausa_segundos"]))
        except Exception as e:
            f["estado"] = "error"
            print(f"Error con {f['email']}: {e}")
            guardar(filas)
    if srv:
        srv.quit()


def enviar(dry):
    filas = leer()
    cand = [f for f in filas if f["estado"] == "pendiente" and "@" in f["email"]]
    lote(filas, cand, CFG["plantilla"], "enviado", dry)


def seguimiento(dry):
    filas = leer()
    limite = datetime.now() - timedelta(days=CFG["seguimiento_dias"])
    cand = [f for f in filas if f["estado"] == "enviado" and f["fecha_envio"]
            and datetime.fromisoformat(f["fecha_envio"]) < limite]
    lote(filas, cand, "templates/seguimiento.txt", "seguimiento_enviado", dry, "Seguimiento: ")


def portales():
    filas = leer()
    for f in filas:
        if f["estado"] == "portal_pendiente" and f["url_portal"]:
            texto = render(CFG["plantilla"], f)
            subprocess.run("clip", input=texto.encode("utf-16"), shell=True)  # Windows
            print(f"{f['empresa']} - {f['cargo']}: mensaje copiado. Abriendo portal...")
            webbrowser.open(f["url_portal"])
            r = input("¿Postulaste? [s/N/q]: ").lower()
            if r == "s":
                f["estado"] = "postulado"
                f["fecha_envio"] = datetime.now().isoformat(timespec="seconds")
                guardar(filas)
            elif r == "q":
                break


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    dry = "--dry-run" in sys.argv
    {"enviar": lambda: enviar(dry), "seguimiento": lambda: seguimiento(dry),
     "portales": portales}.get(cmd, lambda: print(__doc__))()
