# Auto CV

App local (Streamlit) que analiza tu CV con Claude, busca vacantes remotas aplicables desde Colombia,
las puntúa contra tu perfil, redacta el correo de postulación y lo envía.

## Uso
1. Instala Python 3.10+ (marca "Add to PATH").
2. Doble clic en `run.bat` (la primera vez crea el entorno e instala dependencias y genera `.env`).
3. Completa `.env`: `ANTHROPIC_API_KEY` y, para enviar, `SMTP_EMAIL` / `SMTP_PASSWORD` (contraseña de aplicación de Gmail).
4. En el navegador (localhost:8501): sube tu CV → revisa el perfil → busca vacantes → elige → genera mensajes → envía.

## Fuentes
- Automáticas (APIs públicas): Remotive, Jobicy, RemoteOK, GetOnBoard.
- LinkedIn, Indeed, Computrabajo: la app genera las búsquedas ya filtradas (remoto/Colombia) y puedes pegar
  cualquier vacante para que la evalúe. No se automatiza login ni aplicación allí (va contra sus términos).
- El envío automático por email solo aplica a vacantes cuya descripción incluye un correo de contacto;
  para el resto, abre el enlace y usa el mensaje generado.

`legacy/` contiene la versión inicial por CSV.
