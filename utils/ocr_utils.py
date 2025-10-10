import logging
import os
from typing import Tuple, Dict, List, Optional

logger = logging.getLogger(__name__)

# Intentar importar cliente de Google Vision
try:
    from google.cloud import vision
    from google.api_core.retry import Retry
    from google.api_core.exceptions import GoogleAPIError, RetryError
    VISION_AVAILABLE = True
except Exception as e:
    logger.warning(f"google-cloud-vision no disponible: {e}")
    VISION_AVAILABLE = False


def validate_tesseract_installation() -> Tuple[bool, str]:
    """
    Validar que Google Vision API esté disponible.
    Asume que las credenciales ya están configuradas por entrypoint.sh.
    
    Returns:
        Tuple[bool, str]: (disponible, mensaje)
    """
    if not VISION_AVAILABLE:
        return False, "Google Vision API no disponible. Instalar: pip install google-cloud-vision"
    
    # Verificar que la variable de entorno esté configurada
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not credentials_path:
        return False, "Variable GOOGLE_APPLICATION_CREDENTIALS no configurada"
    
    # No validamos que el archivo exista (puede estar en /tmp creado por entrypoint)
    # Si falla al crear el cliente, lo sabremos en tiempo de ejecución
    return True, f"Google Vision API disponible"


def extract_text_with_google_vision(image_path: str, language: str = 'es') -> str:
    """
    Extraer texto de una imagen usando Google Vision API (versión simple).

    Args:
        image_path: Ruta a la imagen
        language: Código de idioma (es para español)
        
    Returns:
        str: Texto extraído
        
    Raises:
        Exception: Si hay error en la extracción
    """
    logger.info(f"Extrayendo texto con Google Vision: {image_path}")
    
    # Leer bytes de imagen
    image_bytes = _read_image_bytes(image_path)

    # Llamar a Vision API
    response = _call_vision_text_detection(
        image_bytes,
        document=True,
        language_hints=[language] if language else None
    )

    # Extraer texto completo
    full_text_annotation = response.full_text_annotation
    text = full_text_annotation.text if full_text_annotation else ""
    logger.info(f"Texto extraído: {text} ")
    logger.info(f"Texto extraído: {len(text)} caracteres")
    return text

def _ensure_vision_available():
    """Verificar que Google Vision esté disponible."""
    if not VISION_AVAILABLE:
        raise ImportError("google-cloud-vision no está instalado. Instalar con: pip install google-cloud-vision")


def _read_image_bytes(image_path: str) -> bytes:
    """Leer bytes de archivo de imagen."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Imagen no encontrada: {image_path}")
    with open(image_path, 'rb') as f:
        return f.read()


def _call_vision_text_detection(
    image_bytes: bytes, 
    document: bool = True, 
    language_hints: Optional[List[str]] = None, 
    max_retries: int = 3
) -> dict:
    """
    Llamar a Google Vision API para detección de texto.
    
    Args:
        image_bytes: Bytes de la imagen
        document: Si usar Document Text Detection (mejor para documentos)
        language_hints: Sugerencias de idioma
        max_retries: Máximo reintentos
        
    Returns:
        Respuesta de Vision API
    """
    _ensure_vision_available()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)

    # Configurar retry
    retry = Retry(
        initial=0.1, 
        maximum=2.0, 
        multiplier=2.0, 
        deadline=30.0,
        predicate=lambda exc: isinstance(exc, (GoogleAPIError, RetryError))
    )

    try:
        if document:
            # Preferir Document Text Detection para documentos
            response = client.document_text_detection(image=image, retry=retry)
        else:
            # Text Detection simple
            response = client.text_detection(image=image, retry=retry)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        return response
    
    except Exception as e:
        logger.error(f"Error en Google Vision API: {e}")
        raise


def extract_text_with_tesseract(
    image_path: str,
    language: str = 'es',
    config: str = '',
    confidence_threshold: float = 60.0
) -> Tuple[str, float, Dict]:
    """
    Extraer texto usando Google Vision API (mantiene firma de compatibilidad).

    Args:
        image_path: Ruta a la imagen
        language: Código de idioma (es para español)
        config: Ignorado (compatibilidad)
        confidence_threshold: Umbral de confianza
        
    Returns:
        Tuple[str, float, Dict]: (texto, confianza_promedio, métricas)
    """
    logger.info(f"Extrayendo texto con Google Vision: {image_path}")
    
    # Leer bytes de imagen
    image_bytes = _read_image_bytes(image_path)

    # Llamar a Vision API
    try:
        response = _call_vision_text_detection(
            image_bytes,
            document=True,
            language_hints=[language] if language else None
        )

        # Extraer texto completo
        full_text_annotation = response.full_text_annotation
        text = full_text_annotation.text if full_text_annotation else ""

        # Calcular confianza promedio a partir de las palabras
        confidences = []
        total_words = 0
        low_confidence_words = 0
        high_confidence_words = 0
        
        for page in full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        # Google Vision da confianza de 0.0 a 1.0, convertir a porcentaje
                        word_confidence = getattr(word, 'confidence', 0.0) * 100.0
                        confidences.append(word_confidence)
                        total_words += 1
                        
                        if word_confidence < confidence_threshold:
                            low_confidence_words += 1
                        elif word_confidence >= 80:
                            high_confidence_words += 1

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Métricas detalladas
        metrics = {
            "total_words": total_words,
            "avg_confidence": round(avg_confidence, 2),
            "low_confidence_words": low_confidence_words,
            "high_confidence_words": high_confidence_words,
            "text_length": len(text),
            "engine": "google_vision",
            "language": language,
            "confidence_distribution": {
                "high": high_confidence_words,
                "medium": total_words - low_confidence_words - high_confidence_words,
                "low": low_confidence_words
            }
        }

        logger.info(f"Texto extraído: {len(text)} caracteres, confianza: {avg_confidence:.1f}%")
        return text, avg_confidence, metrics

    except Exception as e:
        logger.error(f"Error en OCR con Google Vision: {e}")
        raise RuntimeError(f"Error en Google Vision OCR: {str(e)}")


def extract_text_from_multiple_images(
    image_paths: List[str],
    language: str = 'es',
    config: str = ''
) -> Tuple[str, float, Dict]:
    """
    Extraer texto de múltiples imágenes usando Google Vision.
    
    Args:
        image_paths: Lista de rutas de imágenes
        language: Código de idioma
        config: Ignorado (compatibilidad)
        
    Returns:
        Tuple[str, float, Dict]: (texto_combinado, confianza_promedio, métricas)
    """
    if not image_paths:
        return "", 0.0, {"error": "No hay imágenes para procesar"}

    logger.info(f"Procesando {len(image_paths)} imágenes con Google Vision")
    
    all_texts = []
    all_confidences = []
    combined_metrics = {
        "total_pages": len(image_paths),
        "successful_pages": 0,
        "failed_pages": 0,
        "page_results": [],
        "engine": "google_vision"
    }

    for i, image_path in enumerate(image_paths):
        try:
            logger.debug(f"Procesando página {i+1}/{len(image_paths)}: {image_path}")
            
            text, confidence, metrics = extract_text_with_tesseract(
                image_path, 
                language=language, 
                config=config
            )

            if text.strip():
                all_texts.append(f"--- PÁGINA {i+1} ---\n{text}")
                all_confidences.append(confidence)
                combined_metrics["successful_pages"] += 1
                combined_metrics["page_results"].append({
                    "page": i+1,
                    "text_length": len(text),
                    "confidence": round(confidence, 2),
                    "status": "success",
                    "words": metrics.get("total_words", 0)
                })
            else:
                combined_metrics["failed_pages"] += 1
                combined_metrics["page_results"].append({
                    "page": i+1,
                    "status": "no_text",
                    "error": "No se extrajo texto"
                })
                logger.warning(f"Página {i+1}: No se extrajo texto")

        except Exception as e:
            logger.error(f"Error procesando página {i+1}: {e}")
            combined_metrics["failed_pages"] += 1
            combined_metrics["page_results"].append({
                "page": i+1,
                "error": str(e),
                "status": "error"
            })

    # Combinar resultados
    combined_text = "\n\n".join(all_texts)
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    combined_metrics.update({
        "total_text_length": len(combined_text),
        "avg_confidence": round(avg_confidence, 2),
        "pages_with_text": len(all_texts),
        "total_words": sum(result.get("words", 0) for result in combined_metrics["page_results"] if result.get("words"))
    })

    logger.info(f"OCR multi-página completado: {len(all_texts)}/{len(image_paths)} páginas exitosas")

    return combined_text, avg_confidence, combined_metrics


def clean_ocr_text_for_licenses(text: str) -> str:
    """
    Limpia texto OCR específicamente para documentos de identidad.
    
    Args:
        text: Texto crudo del OCR
        
    Returns:
        str: Texto limpio
    """
    if not text:
        return ""

    # Normalizar espacios y saltos de línea
    cleaned_text = ' '.join(text.split())
    
    # Remover caracteres especiales comunes del OCR que interfieren
    import re
    
    # Remover caracteres de control
    cleaned_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', cleaned_text)
    
    # Normalizar espacios múltiples
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    
    return cleaned_text.strip()


def optimize_tesseract_config_for_document(image_path: str) -> str:
    """
    Función de compatibilidad: ya no se usa configuración específica.
    
    Args:
        image_path: Ruta de la imagen
        
    Returns:
        str: Cadena vacía (no se usa con Google Vision)
    """
    # Con Google Vision no necesitamos configuración específica
    return 'google_vision_optimized'