import json, os, requests
from django.conf import settings

try:
    if settings.LLM_PROVIDER == "transformers":
        import torch, transformers
        _pipe = transformers.pipeline(
            "text-generation",
            model=settings.HF_MODEL,
            model_kwargs={"torch_dtype": torch.bfloat16},
            device_map="auto",
        )
        _eos = None
except Exception:
    _pipe = None
    _eos = None

class LLMClient:
    @staticmethod
    def _format_llama_chat(system: str, user: str) -> str:
        if _pipe is None:
            return f"{system}\n\n{user}"
        tok = _pipe.tokenizer
        msg = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        prompt = tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        return prompt

    @staticmethod
    def _gen_transformers(system: str, user: str, max_tokens=256, temperature=0.0) -> str:
        prompt = LLMClient._format_llama_chat(system, user)
        out = _pipe(prompt, max_new_tokens=max_tokens, temperature=temperature)
        gen = out[0]["generated_text"][len(prompt):]
        return gen.strip()

    @staticmethod
    def _gen_ollama(system: str, user: str, max_tokens=256, temperature=0.0) -> str:
        base = (settings.OLLAMA_BASE_URL or "http://127.0.0.1:11434").strip().rstrip("/")
        prompt = (
            f"SYSTEM:\n{system}\n\n"
            f"USER:\n{user}\n\n"
            "CONTRAINTE DE SORTIE: Réponds UNIQUEMENT avec un JSON valide conforme au schéma demandé, "
            "sans texte autour, sans balises ``` ni commentaires."
        )
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "options": {"temperature": temperature, "num_predict": max_tokens, "top_k": 40, "top_p": 0.9},
            "format": "json",
            "stream": False
        }
        r = requests.post(f"{base}/api/generate", json=payload, timeout=180, proxies={"http": None, "https": None})
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()

    @staticmethod
    def generate(system: str, user: str, max_tokens=256, temperature=0.0) -> str:
        if settings.LLM_PROVIDER == "transformers":
            return LLMClient._gen_transformers(system, user, max_tokens, temperature)
        return LLMClient._gen_ollama(system, user, max_tokens, temperature)

    @staticmethod
    def generate_json(system: str, user: str, max_tokens=256) -> dict:
        txt = LLMClient.generate(system, user, max_tokens=max_tokens, temperature=0.0).strip()
        if not txt:
            raise RuntimeError("Réponse vide du modèle.")
        try:
            return json.loads(txt)
        except Exception:
            pass

        def _extract_json_block(s: str) -> str | None:
            start = s.find("{")
            if start == -1:
                return None
            depth = 0
            for i in range(start, len(s)):
                if s[i] == "{":
                    depth += 1
                elif s[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return s[start:i+1]
            return None

        blob = _extract_json_block(txt)
        if blob:
            try:
                return json.loads(blob)
            except Exception:
                pass

        cleaned = txt.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
