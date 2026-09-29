import json, os, re
import anthropic

_client = None


def model():
    return os.getenv("CLAUDE_MODEL", "claude-opus-5-5")


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY
    return _client


def _ask(user: str, max_tokens=8000, effort="medium") -> str:
    r = client().messages.create(
        model=model(), max_tokens=max_tokens,
        system="Eres un reclutador senior. Respondes SOLO con JSON valido, sin texto adicional ni bloques de codigo.",
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user}],
    )
    if r.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazo la solicitud")
    return "".join(b.text for b in r.content if b.type == "text")


def _json(text: str):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if not m:
            raise
        return json.loads(m.group(1))


PERFIL_PROMPT = """Analiza este CV y devuelve un JSON con exactamente estas claves:
- nombre (string)
- email (string, vacio si no aparece)
- titulo (string: titulo profesional actual)
- seniority (junior|semi-senior|senior|lead)
- anos_experiencia (numero)
- resumen (2-3 frases)
- skills (lista de las 15 tecnologias/habilidades mas relevantes)
- idiomas (lista, ej. "Espanol nativo", "Ingles B2")
- roles_objetivo (lista de 3-5 cargos a los que deberia aplicar)
- keywords_busqueda (lista de 6-8 terminos de busqueda de empleo, mezclando ingles y espanol, cortos)

CV:
{cv}"""


def extract_profile(cv_text: str) -> dict:
    return _json(_ask(PERFIL_PROMPT.format(cv=cv_text[:30000])))


SCORE_PROMPT = """Perfil del candidato (JSON):
{perfil}

Restricciones: el candidato vive en Colombia y solo quiere trabajo 100% remoto al que pueda aplicar desde Colombia.

Evalua cada vacante. Devuelve un JSON: lista de objetos {{"i": <indice>, "score": 0-100, "razon": "1 frase", "faltantes": "skills que le faltan o vacio"}}.
Pon score 0 si la vacante exige residir/trabajar en otro pais o no es remota.

Vacantes:
{vacantes}"""


def score_jobs(profile: dict, jobs: list) -> list:
    vac = "\n\n".join(
        f"[{i}] {j['title']} | {j['company']} | {j['location']}\n{j['description'][:1500]}"
        for i, j in enumerate(jobs))
    return _json(_ask(SCORE_PROMPT.format(perfil=json.dumps(profile, ensure_ascii=False), vacantes=vac), effort="low"))


MSG_PROMPT = """Escribe un correo de postulacion breve (max 130 palabras), sincero y concreto, para esta vacante.
- Idioma: el mismo de la descripcion de la vacante.
- Menciona 2-3 puntos reales del perfil que encajen. No inventes experiencia.
- Sin frases de relleno ni formulas rebuscadas. Cierra invitando a conversar. Firma con el nombre.
Devuelve JSON: {{"asunto": "...", "cuerpo": "..."}}

Perfil: {perfil}

Vacante: {title} en {company}
{descripcion}"""


def write_message(profile: dict, job: dict) -> dict:
    return _json(_ask(MSG_PROMPT.format(
        perfil=json.dumps(profile, ensure_ascii=False), title=job["title"], company=job["company"],
        descripcion=job["description"][:3000]), effort="low"))
