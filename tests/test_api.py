import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from orchestrator.api import app

client = TestClient(app)

def test_run_pipeline_success():
    """Тест успешного запуска пайплайна"""
    with patch('orchestrator.orchestrator.Orchestrator') as mock_orch_class:
        mock_orch = MagicMock()
        
        # Делаем run_pipeline асинхронной функцией, возвращающей словарь
        async def mock_run_pipeline():
            return {
                "collect_metrics": "Collected",
                "detect_anomaly": "Anomaly detected",
                "send_alert": "Alert sent",
                "auto_recovery": "Recovered"
            }
        
        mock_orch.run_pipeline = mock_run_pipeline
        mock_orch_class.return_value = mock_orch
        
        with patch('orchestrator.api.orchestrator', mock_orch):
            response = client.post("/run-pipeline")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["results"]["collect_metrics"] == "Collected"

def test_run_pipeline_failure():
    """Тест сбоя при запуске пайплайна"""
    with patch('orchestrator.orchestrator.Orchestrator') as mock_orch_class:
        mock_orch = MagicMock()
        
        async def mock_run_pipeline():
            raise Exception("Simulated failure")
        
        mock_orch.run_pipeline = mock_run_pipeline
        mock_orch_class.return_value = mock_orch
        
        with patch('orchestrator.api.orchestrator', mock_orch):
            response = client.post("/run-pipeline")
            assert response.status_code == 500

def test_get_agents():
    """Тест получения списка агентов"""
    with patch('orchestrator.orchestrator.Orchestrator') as mock_orch_class:
        mock_orch = MagicMock()
        
        # Делаем get_agents асинхронной функцией
        async def mock_get_agents():
            return [
                {"agent_id": "agent-1", "type": "collector", "status": "active"},
                {"agent_id": "agent-2", "type": "analyzer", "status": "active"}
            ]
        
        mock_orch.get_agents = mock_get_agents
        mock_orch_class.return_value = mock_orch
        
        with patch('orchestrator.api.orchestrator', mock_orch):
            response = client.get("/agents")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["agents"]) == 2

def test_scale_up_failure():
    """Тест сбоя при масштабировании"""
    with patch('orchestrator.orchestrator.Orchestrator') as mock_orch_class:
        mock_orch = MagicMock()
        
        async def mock_manual_scale_up():
            raise Exception("Scale failed")
        
        mock_orch.manual_scale_up = mock_manual_scale_up
        mock_orch_class.return_value = mock_orch
        
        with patch('orchestrator.api.orchestrator', mock_orch):
            response = client.post("/scale/up")
            assert response.status_code == 500


def test_scale_up_success():
    """Тест успешного масштабирования"""
    with patch('orchestrator.orchestrator.Orchestrator') as mock_orch_class:
        mock_orch = MagicMock()
        
        async def mock_manual_scale_up():
            return "Scaled up to 4 agents"
        
        mock_orch.manual_scale_up = mock_manual_scale_up
        mock_orch_class.return_value = mock_orch
        
        with patch('orchestrator.api.orchestrator', mock_orch):
            response = client.post("/scale/up")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

def test_health_check():
    """Тест health check"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"