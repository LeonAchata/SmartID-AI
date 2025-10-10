import logging
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import os

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MainApp")

# Importar pipeline y configuraciones
from pipeline import Pipeline
from models.settings import settings
from utils.api_utils import validate_document, save_temp_file

# Crear app FastAPI
app = FastAPI(
    title="Procesador de Documentos de Identidad",
    description="API escalable para procesar PDFs e imágenes de documentos de identidad (DNI, licencias)",
    version="2.0.0"
)

# Configurar CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios exactos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# ALMACENAMIENTO EN MEMORIA (Para desarrollo)
# En producción usar Redis, PostgreSQL, etc.
# ================================

job_storage = {}  # {job_id: job_data}
pipeline = Pipeline()

class JobStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# ================================
# FUNCIONES AUXILIARES
# ================================

def create_job_id() -> str:
    """Genera un ID único para el trabajo."""
    return str(uuid.uuid4())

async def process_file_background(job_id: str, file_path: str, filename: str):
    """Procesa el archivo en background y actualiza el estado."""
    try:
        logger.info(f"[{job_id}] Iniciando procesamiento de: {filename}")
        
        # Actualizar estado a PROCESSING
        job_storage[job_id].update({
            "status": JobStatus.PROCESSING,
            "started_at": datetime.now().isoformat()
        })

        # Procesar archivo con el pipeline
        result = await pipeline.process(file_path=file_path, filename=filename)
        
        # Verificar si el procesamiento falló según el resultado
        if result and result.get("processing_control", {}).get("status") == "FAILED":
            # El pipeline falló, marcar job como FAILED
            error_details = result.get("error_details", {})
            error_msg = "; ".join(error_details.get("errors", ["Error desconocido en pipeline"]))
            
            job_storage[job_id].update({
                "status": JobStatus.FAILED,
                "completed_at": datetime.now().isoformat(),
                "error": error_msg,
                "error_details": error_details
            })
            
            logger.error(f"[{job_id}] Pipeline falló: {error_msg}")
            return
        
        # Verificar si el resultado es None (error crítico)
        if result is None:
            job_storage[job_id].update({
                "status": JobStatus.FAILED,
                "completed_at": datetime.now().isoformat(),
                "error": "Error crítico en pipeline - resultado nulo"
            })
            
            logger.error(f"[{job_id}] Error crítico: resultado nulo")
            return
        
        # Procesamiento exitoso
        # Extraer métricas de procesamiento para el frontend
        extracted_data = result.get("extracted_data", {})
        debug_info = result.get("debug_info", {})
        ocr_stats = debug_info.get("ocr_stats", {})
        processing_metrics = result.get("processing_control", {}).get("time_metrics", {})
        processing_data = result.get("processing_data", {})
        
        # Crear estructura mejorada para el frontend
        enhanced_result = {
            "extracted_data": {
                **extracted_data,
                "texto_extraido": processing_data.get("raw_text", "")
            },
            "processing_metrics": {
                "ocr_confidence": round(ocr_stats.get("ocr_confidence", 0), 1),
                "processing_time": round(processing_metrics.get("total_time", 0), 1),
                "text_length": len(processing_data.get("raw_text", "")),
                "ocr_method": ocr_stats.get("ocr_method", "Google Vision API")
            },
            "raw_result": result  # Mantener resultado completo para debugging
        }
        
        job_storage[job_id].update({
            "status": JobStatus.COMPLETED,
            "completed_at": datetime.now().isoformat(),
            "result": enhanced_result
        })
        
        logger.info(f"[{job_id}] Procesamiento completado exitosamente")
        
    except Exception as e:
        logger.error(f"[{job_id}] Error en procesamiento: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Actualizar con error
        job_storage[job_id].update({
            "status": JobStatus.FAILED,
            "completed_at": datetime.now().isoformat(),
            "error": str(e)
        })
    
    finally:
        # Limpiar archivo temporal
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"[{job_id}] Archivo temporal eliminado: {file_path}")
        except Exception as e:
            logger.error(f"[{job_id}] Error eliminando archivo: {e}")

# ================================
# ENDPOINTS
# ================================

@app.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Endpoint para subir documentos (PDF o imágenes) y iniciar procesamiento asíncrono.
    
    Formatos soportados:
    - PDFs: .pdf
    - Imágenes: .jpg, .jpeg, .png, .tiff, .tif, .bmp
    
    Args:
        file: Archivo PDF o imagen del documento de identidad (DNI, licencia, etc.)
        
    Returns:
        Dict con job_id y estado inicial
    """
    try:
        # Validar archivo (PDF o imagen)
        file_content = validate_document(file)

        # Crear job ID único
        job_id = create_job_id()
        
        # Guardar archivo temporal
        temp_file_path = save_temp_file(file_content, file.filename, Path(settings.temp_dir))
        logger.info(f"[{job_id}] Archivo guardado: {temp_file_path}")

        # Validar que el archivo existe
        if not temp_file_path.exists():
            raise HTTPException(status_code=400, detail="El archivo no se pudo guardar correctamente.")

        # Crear entrada en job_storage
        job_storage[job_id] = {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "filename": file.filename,
            "file_size_mb": round(len(file_content) / (1024 * 1024), 2),
            "created_at": datetime.now().isoformat(),
            "file_path": str(temp_file_path)
        }

        # Iniciar procesamiento en background
        background_tasks.add_task(
            process_file_background,
            job_id,
            str(temp_file_path),
            file.filename
        )
        
        logger.info(f"[{job_id}] Job creado para: {file.filename}")

        return {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "message": "Documento subido exitosamente. Procesamiento iniciado.",
            "filename": file.filename,
            "file_type": "PDF" if file.filename.lower().endswith('.pdf') else "Imagen",
            "estimated_time_seconds": 30  # Estimación
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/status/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Consulta el estado de un trabajo de procesamiento.
    
    Args:
        job_id: ID del trabajo
        
    Returns:
        Dict con estado actual del trabajo
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job ID no encontrado")
    
    job_data = job_storage[job_id]
    
    response = {
        "job_id": job_id,
        "status": job_data["status"],
        "filename": job_data["filename"],
        "created_at": job_data["created_at"]
    }
    
    # Agregar campos específicos según el estado
    if job_data["status"] == JobStatus.PROCESSING and "started_at" in job_data:
        response["started_at"] = job_data["started_at"]
    
    elif job_data["status"] == JobStatus.COMPLETED:
        response.update({
            "completed_at": job_data["completed_at"],
            "result_available": True
        })
    
    elif job_data["status"] == JobStatus.FAILED:
        response.update({
            "completed_at": job_data["completed_at"],
            "error": job_data["error"]
        })
    
    return response


@app.get("/result/{job_id}")
async def get_job_result(job_id: str) -> Dict[str, Any]:
    """
    Obtiene el resultado completo de un trabajo completado.
    
    Args:
        job_id: ID del trabajo
        
    Returns:
        Dict con resultado completo del procesamiento
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job ID no encontrado")
    
    job_data = job_storage[job_id]
    
    if job_data["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"El trabajo está en estado '{job_data['status']}'. Solo trabajos COMPLETED tienen resultados."
        )
    
    result = job_data["result"].copy()
    
    # Agregar metadata del job
    result["job_metadata"] = {
        "job_id": job_id,
        "filename": job_data["filename"],
        "file_size_mb": job_data["file_size_mb"],
        "created_at": job_data["created_at"],
        "completed_at": job_data["completed_at"]
    }
    
    return result


@app.get("/jobs")
async def list_jobs(limit: int = 10) -> Dict[str, Any]:
    """
    Lista los trabajos recientes (útil para debugging).
    
    Args:
        limit: Número máximo de trabajos a retornar
        
    Returns:
        Lista de trabajos con información básica
    """
    jobs = list(job_storage.values())
    
    # Ordenar por fecha de creación (más recientes primero)
    jobs.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Limitar cantidad
    jobs = jobs[:limit]
    
    # Simplificar información para la lista
    simplified_jobs = []
    for job in jobs:
        simplified = {
            "job_id": job["job_id"],
            "status": job["status"],
            "filename": job["filename"],
            "created_at": job["created_at"]
        }
        
        if job["status"] == JobStatus.COMPLETED:
            simplified["completed_at"] = job["completed_at"]
        elif job["status"] == JobStatus.FAILED:
            simplified["error"] = job.get("error", "Unknown error")
            
        simplified_jobs.append(simplified)
    
    return {
        "total_jobs": len(job_storage),
        "jobs": simplified_jobs
    }


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> Dict[str, Any]:
    """
    Elimina un trabajo del almacenamiento.
    
    Args:
        job_id: ID del trabajo a eliminar
        
    Returns:
        Confirmación de eliminación
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job ID no encontrado")
    
    job_data = job_storage.pop(job_id)
    
    # Limpiar archivo si aún existe
    if "file_path" in job_data and os.path.exists(job_data["file_path"]):
        try:
            os.unlink(job_data["file_path"])
            logger.info(f"Archivo eliminado: {job_data['file_path']}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo: {e}")
    
    return {
        "message": f"Job {job_id} eliminado exitosamente",
        "deleted_job": {
            "job_id": job_id,
            "filename": job_data["filename"],
            "status": job_data["status"]
        }
    }


# ================================
# ENDPOINT DE SALUD
# ================================

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Endpoint de salud para monitoreo."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_jobs": len([j for j in job_storage.values() if j["status"] in [JobStatus.PENDING, JobStatus.PROCESSING]]),
        "total_jobs": len(job_storage),
        "version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    # Configuración para desarrollo
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )