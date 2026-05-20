import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json

# Имитируем окружение, так как мы не можем запустить настоящий NATS в тестах
from orchestrator.orchestrator import Orchestrator

@pytest.fixture
async def orchestrator():
    """Создаём оркестратор для тестов"""
    with patch('nats.connect') as mock_connect:
        mock_nc = AsyncMock()
        mock_connect.return_value = mock_nc
        
        orchestrator = Orchestrator()
        orchestrator.nc = mock_nc
        orchestrator.agents = {
            "agent-1": {"bid": 0.3, "skill": 0.8, "load": 0.5},
            "agent-2": {"bid": 0.1, "skill": 0.6, "load": 0.5},
            "agent-3": {"bid": 0.9, "skill": 0.9, "load": 0.0}
        }
        orchestrator.current_agents_count = 3
        
        return orchestrator

def test_find_best_agent(orchestrator):
    """Тест выбора лучшего агента по аукциону"""
    with patch.object(orchestrator, '_cleanup_stale_agents') as mock_cleanup:
        best_agent = asyncio.run(orchestrator.find_best_agent("collect_metrics"))
        
        # Агент-2 имеет наименьшую ставку (0.1)
        assert best_agent == "agent-2"
        mock_cleanup.assert_called_once()

def test_execute_task(orchestrator):
    """Тест выполнения задачи"""
    with patch('asyncio.sleep') as mock_sleep:
        mock_sleep.return_value = None
        
        result = asyncio.run(orchestrator.execute_task("collect_metrics"))
        
        # Проверяем, что задача была отправлена
        orchestrator.nc.publish.assert_called()
        call_args = orchestrator.nc.publish.call_args
        topic = call_args[0][0]
        data = json.loads(call_args[0][1].decode())
        
        assert topic == "tasks.monitoring.agent-2"
        assert data["type"] == "collect_metrics"
        assert "Task collect_metrics completed by agent agent-2" in result

def test_run_pipeline_success(orchestrator):
    """Тест успешного выполнения пайплайна"""
    with patch.object(orchestrator, 'execute_task') as mock_execute:
        # Настраиваем моки для успешного выполнения
        mock_execute.side_effect = [
            "Task collect_metrics completed",
            "ANOMALY DETECTED: high CPU usage",
            "alert sent (ID: alert-123): ANOMALY DETECTED: high CPU usage",
            "auto recovery completed: service restarted"
        ]
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"analysis": "Test analysis"}
            
            results = asyncio.run(orchestrator.run_pipeline())
            
            # Проверяем результаты
            assert results["collect_metrics"] == "Task collect_metrics completed"
            assert "ANOMALY" in results["detect_anomaly"]
            assert "alert sent" in results["send_alert"]
            assert "auto recovery" in results["auto_recovery"]
            assert results["llm_analysis"] == "Test analysis"

def test_run_pipeline_no_anomaly(orchestrator):
    """Тест пайплайна без аномалии"""
    with patch.object(orchestrator, 'execute_task') as mock_execute:
        mock_execute.side_effect = [
            "Task collect_metrics completed",
            "No anomaly detected"
        ]
        
        results = asyncio.run(orchestrator.run_pipeline())
        
        assert results["collect_metrics"] is not None
        assert results["detect_anomaly"] == "No anomaly detected"
        assert results["send_alert"] == "No anomaly detected"
        assert results["auto_recovery"] == "Skipped"
        assert results["llm_analysis"] == "No analysis needed"

def test_call_llm_agent_success(orchestrator):
    """Тест успешного вызова LLM-агента"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"analysis": "LLM analysis result"}
        
        mock_client.return_value.__aenter__.return_value = mock_client.return_value
        mock_client.return_value.post.return_value = mock_response
        
        result = asyncio.run(orchestrator.call_llm_agent("Test anomaly"))
        assert "LLM analysis result" in result

def test_call_llm_agent_failure(orchestrator):
    """Тест сбоя при вызове LLM-агента"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.side_effect = Exception("Network error")
        
        result = asyncio.run(orchestrator.call_llm_agent("Test anomaly"))
        assert "Failed to call LLM agent" in result

def test_scale_up(orchestrator):
    """Тест масштабирования вверх"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Started agent-123"
        
        result = asyncio.run(orchestrator.scale_up())
        
        # Проверяем, что subprocess.run был вызван
        mock_run.assert_called()
        # Проверяем, что current_agents_count увеличился
        assert orchestrator.current_agents_count == 4  # было 3, стало 4

def test_manual_scale_up_limit(orchestrator):
    """Тест ручного масштабирования при достижении лимита"""
    orchestrator.current_agents_count = 5  # Максимум
    result = asyncio.run(orchestrator.manual_scale_up())
    assert "maximum 5 agents reached" in result

def test_get_agents(orchestrator):
    """Тест получения списка агентов"""
    agents = asyncio.run(orchestrator.get_agents())
    assert len(agents) == 3
    assert any(a["agent_id"] == "agent-1" for a in agents)
