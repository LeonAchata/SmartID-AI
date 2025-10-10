import logging
import json
from typing import Dict, Tuple, Any
from models.settings import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

def perform_openai_extraction(client: OpenAI, text: str, current_data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """
    Extracción usando OpenAI con sistema de prompts.
    Retorna (campos extraídos, tokens usados)
    """
    from models.prompts import build_extraction_prompt

    prompt_config = build_extraction_prompt(text[:2500], "first_pass")
    

    system_prompt = prompt_config["system"]
    user_prompt = prompt_config["user"]

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=1500,
        temperature=settings.llm_temperature,
        top_p=0.9
    )

    tokens_used = response.usage.total_tokens if response.usage else 0
    content = response.choices[0].message.content.strip()

    # Limpiar formato JSON
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]

    result = json.loads(content.strip())

    if not isinstance(result, dict):
        raise ValueError("Respuesta de OpenAI no es un objeto JSON válido")

    logger.debug(f"Extracción exitosa: {len(result)} campos, {tokens_used} tokens")
    return result, tokens_used