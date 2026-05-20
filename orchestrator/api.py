from fastapi import FastAPI, HTTPException
import asyncio
import logging

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .orchestrator import Orchestrator

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="Monitoring Orchestrator API",
    description="API for orchestrating multi-agent monitoring system",
    version="1.0.0"
)

# Глобальный экземпляр оркестратора
orchestrator = Orchestrator()

# Инструментирование FastAPI для OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

@app.on_event("startup")
async def startup_event():
    """Запуск оркестратора при старте приложения"""
    logger.info("Starting orchestrator...")
    await orchestrator.connect()
    
    # Запуск мониторинга очереди в фоне
    orchestrator.stats_task = asyncio.create_task(orchestrator.monitor_queue_and_scale())
    logger.info("Orchestrator started and monitoring loop running")

@app.on_event("shutdown")
async def shutdown_event():
    """Остановка оркестратора при завершении"""
    logger.info("Shutting down orchestrator...")
    await orchestrator.close()
    logger.info("Orchestrator stopped")

@app.post("/run-pipeline", summary="Запустить полный пайплайн мониторинга")
async def run_pipeline():
    """
    Запускает полный пайплайн:
    collect_metrics → detect_anomaly → send_alert → auto_recovery
    """
    try:
        results = await orchestrator.run_pipeline()
        return {
            "status": "success",
            "results": results,
            "message": "Pipeline completed successfully"
        }
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents", summary="Получить список активных агентов")
async def get_agents():
    """
    Возвращает список всех активных агентов с их характеристиками
    """
    agents = await orchestrator.get_agents()
    return {
        "status": "success",
        "agents": agents,
        "total": len(agents)
    }

@app.post("/scale/up", summary="Ручное масштабирование вверх")
async def scale_up():
    """
    Ручной запуск нового агента
    """
    try:
        result = await orchestrator.manual_scale_up()
        return {
            "status": "success",
            "message": result
        }
    except Exception as e:
        logger.error(f"Manual scale up failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Простой healthcheck эндпоинт
@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)