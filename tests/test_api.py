import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Импортируем приложение из orchestrator.api
from orchestrator.api import app, orchestrator

class TestOrchestratorMock:
    """Мок для оркестратора"""
    async def run_pipeline(self):
        return {
            "status": "success",
            "results": {
                "collect_metrics": "Collected",
                "detect_anomaly": "No anomaly",
                "send_alert": "Skipped",
                "auto_recovery": "Skipped",
                "llm_analysis": "No analysis needed"
            }
        }
    
    async def get_agents(self):
        return [
            {"agent_id": "agent-1", "skill": 0.8, "load": 0.3},
            {"agent_id": "agent-2", "skill": 0.7, "load": 0.4}
        ]
    
    async def manual_scale_up(self):
        return "Scaling up initiated, current agents: 3"

# Заменяем реальный оркестратор на мок
orchestrator = TestOrchestratorMock()
client = TestClient(app)

def test_run_pipeline_success():
    """Тест успешного запуска пайплайна"""
    response = client.post("/run-pipeline")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert "Pipeline completed successfully" in data["message"]
    assert "results" in data
    assert data["results"]["collect_metrics"] == "Collected"

def test_run_pipeline_failure():
    """Тест сбоя при запуске пайплайна"""
    # Меняем мок, чтобы он бросал исключение
    with patch.object(TestOrchestratorMock, 'run_pipeline') as mock_run:
        mock_run.side_effect = Exception("Simulated failure")
        
        response = client.post("/run-pipeline")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

def test_get_agents():
    """Тест получения списка агентов"""
    response = client.get("/agents")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert data["total"] == 2
    assert len(data["agents"]) == 2
    assert data["agents"][0]["agent_id"] == "agent-1"

def test_scale_up():
    """Тест ручного масштабирования"""
    response = client.post("/scale/up")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert "Scaling up initiated" in data["message"]

def test_scale_up_failure():
    """Тест сбоя при масштабировании"""
    with patch.object(TestOrchestratorMock, 'manual_scale_up') as mock_scale:
        mock_scale.side_effect = Exception("Scale failed")
        
        response = client.post("/scale/up")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

def test_health_check():
    """Тест healthcheck эндпоинта"""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"