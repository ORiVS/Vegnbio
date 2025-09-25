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
    # Schéma contractuel + champs obligatoires
    schema = (
      "{\n"
      '  "species": "dog|cat|unknown",              # OBLIGATOIRE\n'
      '  "breed": "string",                          # OBLIGATOIRE (mettre "" si inconnu)\n'
      '  "symptoms": [                               # OBLIGATOIRE, tableau d’objets\n'
      '    { "code": "vomiting|fever|...",           # OBLIGATOIRE\n'
      '      "duration_days": 0,                     # Facultatif (0 si non précisé)\n'
      '      "severity": "mild|moderate|severe"      # Facultatif\n'
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

    # très explicite pour éviter les sorties partielles
    rules = (
      "- Tous les champs au niveau racine sont OBLIGATOIRES (species, breed, symptoms).\n"
      "- Si une information est absente, mets: species=\"unknown\", breed=\"\".\n"
      "- RENDS UNIQUEMENT un objet JSON avec exactement ces 3 clés au niveau racine.\n"
      "- NE rends pas juste un objet symptôme; rends l'objet complet.\n"
    )

    return (
      "TÂCHE: Extraire espèce, race et symptômes depuis un texte utilisateur.\n"
      f"TEXTE: {user_text}\n\n"
      "SCHÉMA EXACT À RESPECTER:\n" + schema + "\n"
      "EXEMPLE DE SORTIE VALIDE:\n" + example_ok + "\n\n"
      "RÈGLES:\n" + rules
    )

# Pour /triage : reformulation (après ton scoring déterministe)
def build_explain_prompt(species: str, breed: str, differential, red_flags, advice) -> str:
    """
    differential: list[ { 'disease': str, 'prob': float, 'why': str } ]
    red_flags: list[str]
    advice: str
    """
    return (
      "Contexte: on a déjà effectué un scoring déterministe interne.\n"
      f"Espèce: {species} | Race: {breed or '-'}\n"
      f"Hypothèses (avec probabilités et raisons): {differential}\n"
      f"Red flags: {red_flags}\n"
      f"Conseils: {advice}\n"
      "Formule une réponse courte, claire, en français simple, rappelant que ce n'est pas un diagnostic.\n"
    )
