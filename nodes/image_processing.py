import logging
import time
from pathlib import Path

from models.state import PipelineState
from models.settings import settings
from utils.image_utils import is_image_file, validate_image_dependencies
from utils.ocr_utils import validate_tesseract_installation, extract_text_with_google_vision

logger = logging.getLogger("ImageProcessing")


def image_processing_node(state: PipelineState) -> PipelineState:
    """
    Nodo único de procesamiento de imágenes.
    
    Funciones:
    1. Valida que sea una imagen y tamaño correcto
    2. Extrae texto usando Google Vision API
    3. Retorna texto crudo para el nodo LLM
    
    Args:
        state: Estado del pipeline con información del documento
        
    Returns:
        Estado actualizado con texto extraído
    """
    
    logger.info("Iniciando procesamiento de imagen")
    state = state.update_stage('ImageProcessing')
    
    start_time = time.time()
    
    try:
        # === VALIDACIÓN DE GOOGLE VISION ===
        vision_ok, vision_msg = validate_tesseract_installation()
        if not vision_ok:
            return state.add_error(f"Google Vision API no disponible: {vision_msg}")
        
        logger.info(f"Google Vision API validado: {vision_msg}")
        
        # Verificar dependencias de imagen (Pillow)
        try:
            validate_image_dependencies()
        except ImportError as e:
            return state.add_error(f"Dependencias de imagen faltantes: {str(e)}")
        
        # === VALIDACIÓN DEL ARCHIVO ===
        file_path = Path(state.document_info.file_path)
        
        if not file_path.exists():
            return state.add_error(f"Archivo no encontrado: {file_path}")
        
        if not is_image_file(file_path):
            return state.add_error(f"El archivo no es una imagen válida: {file_path.suffix}")
        
        # Verificar tamaño
        file_size_bytes = file_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)
        max_size = getattr(settings, 'max_image_size_mb', 10)
        
        if file_size_mb > max_size:
            return state.add_error(f"Imagen demasiado grande: {file_size_mb:.1f}MB > {max_size}MB")
        
        logger.info(f"Imagen válida: {file_path.name} ({file_size_mb:.2f}MB)")
        state = state.add_message(f"Imagen válida: {file_size_mb:.2f}MB")
        
        # === EXTRACCIÓN DE TEXTO CON GOOGLE VISION ===
        logger.info("Extrayendo texto con Google Vision API...")
        
        try:
            raw_text = extract_text_with_google_vision(str(file_path))
            
            if not raw_text or not raw_text.strip():
                logger.warning("Google Vision no detectó texto en la imagen")
                return state.add_error("No se detectó texto en la imagen")
            
            # Guardar texto crudo en el estado
            state.processing_data.raw_text = raw_text.strip()
            
            elapsed_time = time.time() - start_time
            char_count = len(raw_text)
            
            logger.info(f"Texto extraído: {char_count} caracteres en {elapsed_time:.2f}s")
            state = state.add_message(f"Texto extraído: {char_count} caracteres")
            
            # Actualizar debug info
            state.logging.debug_info.update({
                "image_processing_stats": {
                    "file_size_mb": file_size_mb,
                    "processing_time_seconds": elapsed_time,
                    "characters_extracted": char_count,
                    "ocr_engine": "google_vision",
                    "file_extension": file_path.suffix.lower()
                }
            })
            
            return state
            
        except Exception as e:
            error_msg = f"Error en Google Vision API: {str(e)}"
            logger.error(error_msg)
            return state.add_error(error_msg)
    
    except Exception as e:
        error_msg = f"Error crítico en procesamiento de imagen: {str(e)}"
        logger.error(error_msg)
        return state.add_error(error_msg)
