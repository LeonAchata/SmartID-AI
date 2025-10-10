import logging
import json
from openai import OpenAI
from models.settings import settings
from models.state import PipelineState
from models.prompts import generate_extraction_prompts

def llm_node(state: PipelineState) -> PipelineState:
    logger = logging.getLogger("Nodo 6")
    
    # Verificar si el estado ya está marcado como FAILED
    if state.processing_control.status == "FAILED":
        logger.error("Estado marcado como FAILED, saltando procesamiento LLM")
        return state
    
    state = state.update_stage("llm_processing")

    try:
        client = OpenAI(api_key=settings.openai_api_key)
    except Exception as e:
        return state.add_error(f"Error inicializando cliente OpenAI: {str(e)}")
    
    try:
        # CORREGIDO: Pasar state en lugar de cleaned_text
        system_prompt, user_prompt = generate_extraction_prompts(state)

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

        # CORREGIDO: Actualizar el estado con los datos extraídos
        state.extracted_data = result
        state.update_metrics(tokens=tokens_used)
        state.processing_control.status = "COMPLETED"
        
        # Actualizar debug info con estadísticas de LLM
        state.logging.debug_info.update({
            "llm_stats": {
                "model_used": settings.llm_model,
                "tokens_used": tokens_used,
                "temperature": settings.llm_temperature,
                "max_tokens": 1500,
                "top_p": 0.9,
                "fields_extracted": len(result),
                "response_length": len(content),
                "extraction_successful": True,
                "prompt_system_length": len(system_prompt),
                "prompt_user_length": len(user_prompt)
            }
        })
        
        logger.info(f"Extracción exitosa: {len(result)} campos, {tokens_used} tokens")
        return state.add_message(f"Extracción completada: {len(result)} campos extraídos")
        
    except Exception as e:
        logger.error(f"Error en extracción LLM: {str(e)}")
        return state.add_error(f"Error en extracción LLM: {str(e)}")