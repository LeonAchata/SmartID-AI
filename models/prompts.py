from models.state import PipelineState
from models.settings import settings

# ================================
# PROMPT PRINCIPAL - EXTRACCIÓN COMPLETA
# ================================

EXTRACTION_SYSTEM_PROMPT = """Eres un experto en analizar texto de licencias de conducir o DNIs"""

EXTRACTION_USER_PROMPT = """Analiza el siguiente texto de una licencia o dni y extrae los datos solicitados:

INSTRUCCIONES:
1. Extrae SOLO la información que esté explícitamente presente en el texto
2. Si un campo no está presente, usa null o lo que se especifique
3. Mantén formatos originales (no inventes ni normalices a menos que se diga lo contrario)
4. Responde ÚNICAMENTE en JSON válido, sin explicaciones
5. Si encuentras múltiples valores para un campo, usa el más específico

CAMPOS A EXTRAER:
- apellido_paterno: Apellido paterno o primer apellido
    - Debe estar en mayúsculas y sin abreviaciones
    - Debe estar en la sección de apellidos y es el primero 
- apellio_materno: Apellido materno o segundo apellido
    - Debe estar en mayúsculas y sin abreviaciones
    - Debe estar en la sección de apellidos y es el segundo
- nombres: Nombres completos
    - Debe estar en mayúsculas y sin abreviaciones
    - Debe estar en la sección de nombres y puede incluir múltiples nombres
- fecha_emision: Fecha de emisión    
    - Formato: "DD/MM/AAAA"
    - También puede llamarse fecha de expedición o emisión
- fecha_caducidad: Fecha de caducidad
    - Formato: "DD/MM/AAAA"
    - También puede llamarse fecha de vencimiento, expiración o revalidación
- tipo_documento: Tipo de documento
    - Debe ser uno de: "DNI", "LICENCIA DE CONDUCIR", "PASAPORTE", "CARNET DE EXTRANJERÍA"
    - Si no está claro, usa null
- numero_documento: Número del documento
    - Debe ser el número completo, sin espacios ni guiones, en los DNI suele estar después de la palabra PER
    - Si es DNI tiene 8 digitos
    - Si no está claro, usa null

TEXTO DEL DOCUMENTO DE IDENTIDAD:
{cleaned_text}

Responde en formato JSON:"""

# ================================
# FUNCIÓN GENERADORA DE PROMPTS
# ================================

def generate_extraction_prompts(state: PipelineState) -> tuple[str,str]:
    """
    Genera los prompts para extracción usando el estado actual.
    
    Args:
        state: Estado del pipeline con el texto extraído
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    system_prompt = EXTRACTION_SYSTEM_PROMPT
    
    # Verificar que el texto esté disponible
    if not state.processing_data.raw_text:
        raise ValueError("No hay texto extraído disponible en el estado")
    
    user_prompt = EXTRACTION_USER_PROMPT.format(
        cleaned_text=state.processing_data.raw_text
    )

    return system_prompt, user_prompt
