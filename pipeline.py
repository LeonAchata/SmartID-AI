# Pipeline principal de procesamiento - Simplificado para solo imágenes
import logging
import traceback
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models.state import PipelineState, DocumentInfo
from nodes.image_processing import image_processing_node
from nodes.llm import llm_node

logger = logging.getLogger("Pipeline")


class Pipeline:
    
    def __init__(self):
        self.graph = None
        self.app = None
        self.initialize_pipeline()
    
    def initialize_pipeline(self):
        """Inicializar pipeline simplificado: Image Processing → LLM"""
        try:
            workflow = StateGraph(PipelineState)
            
            # === SOLO 2 NODOS ===
            workflow.add_node("image_processing", image_processing_node)
            workflow.add_node("llm", llm_node)

            # Flujo lineal simple
            workflow.set_entry_point("image_processing")
            workflow.add_edge("image_processing", "llm")
            workflow.add_edge("llm", END)

            # Compilar grafo con memoria
            memory = MemorySaver()
            self.app = workflow.compile(checkpointer=memory)
            
            logger.info("Pipeline inicializado correctamente")
        
        except Exception as e:
            logger.error(f"Error inicializando pipeline: {e}")
            logger.error(traceback.format_exc())
            raise

    async def process(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Procesa una imagen a través del pipeline.

        Args:
            file_path (str): Ruta del archivo de imagen a procesar.
            filename (str): Nombre del archivo de imagen.

        Returns:
            Dict[str, Any]: Resultado del procesamiento del pipeline.
        """
        try:
            logger.info(f"Iniciando procesamiento de: {filename}")
            
            # === CREAR ESTADO INICIAL ===
            initial_state = self.create_initial_state(file_path, filename)
            logger.info("Ejecutando pipeline")
            
            # Usar un thread_id único para el checkpointer
            import uuid
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            
            # Ejecutar el grafo
            final_state = await self.app.ainvoke(initial_state, config=config)

            # Verificar si el procesamiento falló
            # Manejar tanto objetos Pydantic como diccionarios de manera robusta
            processing_control = final_state.get("processing_control")
            
            # Extraer status de manera segura
            if hasattr(processing_control, 'status'):
                # Es un objeto Pydantic ProcessingControl
                status = processing_control.status
                stage = processing_control.processing_stage
            elif isinstance(processing_control, dict):
                # Es un diccionario
                status = processing_control.get("status")
                stage = processing_control.get("processing_stage", "unknown")
            else:
                # Fallback
                status = None
                stage = "unknown"
            
            if status == "FAILED":
                logger.error("Pipeline falló durante el procesamiento")
                # Retornar información del error para el usuario
                logging_data = final_state.get("logging")
                
                # Extraer errors y warnings de manera segura
                if hasattr(logging_data, 'errors'):
                    # Es un objeto Pydantic LoggingData
                    errors = logging_data.errors
                    warnings = logging_data.warnings
                elif isinstance(logging_data, dict):
                    # Es un diccionario
                    errors = logging_data.get("errors", [])
                    warnings = logging_data.get("warnings", [])
                else:
                    # Fallback
                    errors = []
                    warnings = []
                
                result = {
                    "processing_control": {
                        "status": status,
                        "processing_stage": stage
                    },
                    "error_details": {
                        "errors": errors,
                        "warnings": warnings,
                        "last_stage": stage
                    },
                    "metrics": final_state.get("metrics", {}),
                }
                return result

            # Procesamiento exitoso - extraer metrics de manera segura
            metrics = final_state.get("metrics")
            if hasattr(metrics, 'model_dump'):
                # Es un objeto Pydantic
                metrics_dict = metrics.model_dump()
            elif isinstance(metrics, dict):
                metrics_dict = metrics
            else:
                metrics_dict = {}

            result = {
                "processing_control": {
                    "status": status or "COMPLETED",
                    "processing_stage": stage
                },
                "extracted_data": final_state.get("extracted_data", {}),
                "metrics": metrics_dict,
            }

            logger.info(f"Procesamiento completado exitosamente.")
            return result
            
        except Exception as e:
            logger.error(f"Error en pipeline: {e}")
            logger.error(traceback.format_exc())
            return None

    def create_initial_state(self, file_path: str, filename: str) -> PipelineState:
        """Crear estado inicial simplificado para imágenes."""
        
        document_info = DocumentInfo(
            file_path=file_path,
            filename=filename
        )
        
        return PipelineState(document_info=document_info)

