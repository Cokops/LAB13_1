import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
import time

from orchestrator.orchestrator import Orchestrator

@pytest.fixture
def orchestrator():
    """Создаём оркестратор для тестов (синхронная фикстура)"""
    with patch('nats.connect') as mock_connect:
        mock_nc = AsyncMock()
        mock_connect.return_value = mock_nc
        
        orchestrator = Orchestrator()
        orchestrator.nc = mock_nc
        # Добавляем last_seen для каждого агента
        current_time = time.time()
        orchestrator.agents = {
            "agent-1": {"bid": 0.3, "skill": 0.8, "load": 0.5, "last_seen": current_time},
            "agent-2": {"bid": 0.1, "skill": 0.6, "load": 0.5, "last_seen": current_time},
            "agent-3": {"bid": 0.9, "skill": 0.9, "load": 0.0, "last_seen": current_time}
        }
        orchestrator.current_agents_count = 3
        
        return orchestrator

@pytest.mark.asyncio
async def test_find_best_agent(orchestrator):
    """Тест выбора лучшего агента по аукциону"""
    best_agent = await orchestrator.find_best_agent("collect_metrics")
    
    # Агент-2 имеет наименьшую ставку (0.1)
    assert best_agent == "agent-2"

@pytest.mark.asyncio
async def test_execute_task(orchestrator):
    """Тест выполнения задачи"""
    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = await orchestrator.execute_task("collect_metrics")
        
        # Проверяем, что задача была отправлена
        orchestrator.nc.publish.assert_called()
        call_args = orchestrator.nc.publish.call_args
        topic = call_args[0][0]
        data = json.loads(call_args[0][1].decode())
        
        assert topic == "tasks.monitoring.agent-2"
        assert data["type"] == "collect_metrics"
        assert "Task collect_metrics completed by agent agent-2" in result

@pytest.mark.asyncio
async def test_run_pipeline_success(orchestrator):
    """Тест успешного выполнения пайплайна"""
    # Мокаем execute_task как асинхронную функцию
    call_count = 0
    async def mock_execute_task(task_type, payload=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Task collect_metrics completed"
        elif call_count == 2:
            return "ANOMALY DETECTED: high CPU usage"
        elif call_count == 3:
            return "alert sent (ID: alert-123): ANOMALY DETECTED: high CPU usage"
        elif call_count == 4:
            return "auto recovery completed: service restarted"
        return "Unknown task"
    
    with patch.object(orchestrator, 'execute_task', side_effect=mock_execute_task):
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={"analysis": "Test analysis"})
            
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            
            results = await orchestrator.run_pipeline()
            
            # Проверяем результаты
            assert "error" not in results, f"Pipeline failed with error: {results.get('error', '')}"
            assert results["collect_metrics"] == "Task collect_metrics completed"
            assert "ANOMALY" in results["detect_anomaly"]
            assert "alert sent" in results["send_alert"]
            assert "auto recovery" in results["auto_recovery"]
            assert results["llm_analysis"] == "Test analysis"

@pytest.mark.asyncio
async def test_run_pipeline_failure(orchestrator):
    """Тест пайплайна с ошибкой"""
    async def mock_execute_task_error(task_type, payload=None):
        raise Exception("Task execution failed")
    
    with patch.object(orchestrator, 'execute_task', side_effect=mock_execute_task_error):
        results = await orchestrator.run_pipeline()
        
        # Проверяем, что ошибка зафиксирована
        assert "error" in results
        assert "Task execution failed" in results["error"]

@pytest.mark.asyncio
async def test_call_llm_agent_success(orchestrator):
    """Тест успешного вызова LLM-агента"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"analysis": "LLM analysis result"})
        
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await orchestrator.call_llm_agent("Test anomaly")
        assert "LLM analysis result" in result

@pytest.mark.asyncio
async def test_call_llm_agent_http_error(orchestrator):
    """Тест HTTP ошибки при вызове LLM-агента"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await orchestrator.call_llm_agent("Test anomaly")
        assert "500" in result
        assert "Internal Server Error" in result

@pytest.mark.asyncio
async def test_call_llm_agent_failure(orchestrator):
    """Тест сбоя при вызове LLM-агента"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await orchestrator.call_llm_agent("Test anomaly")
        assert "Failed to call LLM agent" in result
        assert "Network error" in result

@pytest.mark.asyncio
async def test_scale_up(orchestrator):
    """Тест масштабирования вверх"""
    with patch('subprocess.run') as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Started agent-123"
        mock_run.return_value = mock_process
        
        await orchestrator.scale_up()
        
        # Проверяем, что subprocess.run был вызван
        mock_run.assert_called_once()
        # Проверяем, что current_agents_count увеличился
        assert orchestrator.current_agents_count == 4

@pytest.mark.asyncio
async def test_scale_up_failure(orchestrator):
    """Тест ошибки при масштабировании"""
    with patch('subprocess.run') as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "Failed to start container"
        mock_run.return_value = mock_process
        
        # current_agents_count не должен измениться
        old_count = orchestrator.current_agents_count
        await orchestrator.scale_up()
        assert orchestrator.current_agents_count == old_count

@pytest.mark.asyncio
async def test_manual_scale_up_success(orchestrator):
    """Тест успешного ручного масштабирования"""
    with patch.object(orchestrator, 'scale_up', new_callable=AsyncMock) as mock_scale_up:
        result = await orchestrator.manual_scale_up()
        
        mock_scale_up.assert_called_once()
        assert "Scaling up initiated" in result
        assert str(orchestrator.current_agents_count) in result

@pytest.mark.asyncio
async def test_manual_scale_up_limit(orchestrator):
    """Тест ручного масштабирования при достижении лимита"""
    orchestrator.current_agents_count = 5  # MAX_AGENTS по умолчанию
    result = await orchestrator.manual_scale_up()
    assert "maximum 5 agents reached" in result

@pytest.mark.asyncio
async def test_get_agents(orchestrator):
    """Тест получения списка агентов"""
    agents = await orchestrator.get_agents()
    assert len(agents) == 3
    assert any(a["agent_id"] == "agent-1" for a in agents)
    assert any(a["agent_id"] == "agent-2" for a in agents)
    assert any(a["agent_id"] == "agent-3" for a in agents)

@pytest.mark.asyncio
async def test_get_agents_empty():
    """Тест получения пустого списка агентов"""
    with patch('nats.connect') as mock_connect:
        mock_nc = AsyncMock()
        mock_connect.return_value = mock_nc
        
        orchestrator = Orchestrator()
        orchestrator.nc = mock_nc
        orchestrator.agents = {}
        
        agents = await orchestrator.get_agents()
        assert len(agents) == 0
        assert isinstance(agents, list)

@pytest.mark.asyncio
async def test_cleanup_stale_agents(orchestrator):
    """Тест очистки устаревших агентов"""
    # Делаем agent-1 устаревшим (last_seen старше 30 секунд)
    orchestrator.agents["agent-1"]["last_seen"] = time.time() - 31.0
    
    # Вызываем find_best_agent, который вызывает _cleanup_stale_agents
    await orchestrator.find_best_agent("collect_metrics")
    
    # agent-1 должен быть удалён
    assert "agent-1" not in orchestrator.agents
    assert "agent-2" in orchestrator.agents
    assert "agent-3" in orchestrator.agents
    assert len(orchestrator.agents) == 2