SYSTEM_TRIAGE = (
  "Tu es un assistant de triage vétérinaire NON clinique. "
  "Tu n’émets PAS de diagnostic médical. "
  "Tu proposes un TRIAGE (low/medium/high), 2-3 hypothèses et des red flags, "
  "avec des conseils prudents et incitation à consulter un vétérinaire si nécessaire."
)

SYSTEM_JSON_EXTRACTOR = (
  "Tu es un extracteur d'entités vétérinaires. "
  "Ta sortie doit être STRICTEMENT un JSON valide, sans texte autour, sans ```."
)

def build_parse_prompt(user_text: str) -> str:
    schema = (
      "{\n"
      '  "species": "dog|cat|unknown",\n'
      '  "breed": "string",\n'
      '  "symptoms": [\n'
      '    { "code": "vomiting|fever|...",\n'
      '      "duration_days": 0,\n'
      '      "severity": "mild|moderate|severe"\n'
      '    }\n'
      '  ]\n'
      "}\n"
    )
    example_ok = (
      '{\n'
      '  "species": "dog",\n'
      '  "breed": "Labrador Retriever",\n'
      '  "symptoms": [\n'
      '    {"code":"vomiting","duration_days":2,"severity":"moderate"},\n'
      '    {"code":"fever"},\n'
      '    {"code":"lethargy"}\n'
      '  ]\n'
      '}'
    )
    rules = (
      "- Tous les champs racine sont obligatoires.\n"
      "- Si inconnu: species=\"unknown\", breed=\"\".\n"
      "- Rends un seul objet JSON avec exactement ces 3 clés racine.\n"
      "- Ne rends pas juste un objet symptôme.\n"
    )
    return (
      "TÂCHE: Extraire espèce, race et symptômes depuis un texte utilisateur.\n"
      f"TEXTE: {user_text}\n\n"
      "SCHÉMA EXACT À RESPECTER:\n" + schema + "\n"
      "EXEMPLE DE SORTIE VALIDE:\n" + example_ok + "\n\n"
      "RÈGLES:\n" + rules
    )

def build_explain_prompt(species: str, breed: str, differential, red_flags, advice) -> str:
    return (
      "Contexte: un scoring déterministe interne a déjà été effectué.\n"
      f"Espèce: {species} | Race: {breed or '-'}\n"
      f"Hypothèses (avec probabilités et raisons): {differential}\n"
      f"Red flags: {red_flags}\n"
      f"Conseils: {advice}\n"
      "Formule une réponse courte, claire, en français simple, rappelant que ce n'est pas un diagnostic.\n"
    )
