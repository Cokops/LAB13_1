import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
import redis

# Имитируем окружение
from llm_agent.llm_agent import LLMAgent

@pytest.fixture
async def llm_agent():
    """Создаём LLM-агента для тестов"""
    with patch('nats.connect') as mock_nats_connect, \
         patch('redis.from_url') as mock_redis_connect:
        
        mock_nc = AsyncMock()
        mock_nats_connect.return_value = mock_nc
        
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # Изначально нет в кэше
        mock_redis.setex.return_value = True
        mock_redis_connect.return_value = mock_redis
        
        agent = LLMAgent(nats_url="nats://localhost:4222", redis_url="localhost:6379")
        agent.nc = mock_nc
        agent.redis_client = mock_redis
        
        return agent

def test_generate_analysis_success(llm_agent):
    """Тест успешной генерации анализа"""
    with patch('ollama.generate') as mock_generate:
        mock_generate.return_value = {
            'response': '{"cause": "High CPU load", "recommendation": "Check processes", "criticality": "High"}'
        }
        
        analysis = asyncio.run(llm_agent._generate_analysis("CPU spike", None))
        
        assert analysis["cause"] == "High CPU load"
        assert analysis["recommendation"] == "Check processes"
        assert analysis["criticality"] == "High"
        mock_generate.assert_called()

def test_generate_analysis_json_parse_error(llm_agent):
    """Тест ошибки парсинга JSON от LLM"""
    with patch('ollama.generate') as mock_generate:
        mock_generate.return_value = {
            'response': 'Invalid JSON response'
        }
        
        analysis = asyncio.run(llm_agent._generate_analysis("CPU spike", None))
        
        # Должен вернуться fallback
        assert analysis["cause"] == "Unable to determine cause"
        assert analysis["criticality"] == "Medium"

def test_generate_analysis_ollama_failure(llm_agent):
    """Тест сбоя при вызове Ollama"""
    with patch('ollama.generate') as mock_generate:
        mock_generate.side_effect = Exception("Ollama server down")
        
        analysis = asyncio.run(llm_agent._generate_analysis("CPU spike", None))
        
        assert analysis is None

def test_get_cached_result_hit(llm_agent):
    """Тест получения результата из кэша (hit)"""
    # Настраиваем кэш
    llm_agent.redis_client.get.return_value = json.dumps({
        "cause": "Cached cause",
        "recommendation": "Cached recommendation",
        "criticality": "High"
    })
    
    result = asyncio.run(llm_agent._get_cached_result("llm_result:abc123"))
    
    assert result["cause"] == "Cached cause"
    llm_agent.redis_client.get.assert_called_with("llm_result:abc123")

def test_get_cached_result_miss(llm_agent):
    """Тест отсутствия в кэше (miss)"""
    llm_agent.redis_client.get.return_value = None
    
    result = asyncio.run(llm_agent._get_cached_result("llm_result:abc123"))
    
    assert result is None

def test_cache_result_success(llm_agent):
    """Тест сохранения результата в кэш"""
    result = {
        "cause": "Test cause",
        "recommendation": "Test recommendation",
        "criticality": "Medium"
    }
    
    asyncio.run(llm_agent._cache_result("llm_result:abc123", result))
    
    llm_agent.redis_client.setex.assert_called_with(
        "llm_result:abc123", 300, json.dumps(result)
    )

def test_cache_result_failure(llm_agent):
    """Тест сбоя при сохранении в кэш"""
    llm_agent.redis_client.setex.side_effect = redis.RedisError("Connection failed")
    
    result = {"cause": "Test cause", "recommendation": "Test", "criticality": "Low"}
    # Не должно падать
    asyncio.run(llm_agent._cache_result("llm_result:abc123", result))
    
    llm_agent.redis_client.setex.assert_called()

def test_publish_result_success(llm_agent):
    """Тест публикации результата"""
    analysis = {"cause": "Test", "recommendation": "Fix", "criticality": "High"}
    
    asyncio.run(llm_agent._publish_result(analysis, "req-123"))
    
    llm_agent.nc.publish.assert_called()
    call_args = llm_agent.nc.publish.call_args
    topic = call_args[0][0]
    data = json.loads(call_args[0][1].decode())
    
    assert topic == "tasks.llm.result"
    assert data["request_id"] == "req-123"
    assert data["status"] == "success"
    assert data["analysis"]["cause"] == "Test"

def test_publish_error_result(llm_agent):
    """Тест публикации ошибки"""
    asyncio.run(llm_agent._publish_error_result("Test error", "req-123"))
    
    llm_agent.nc.publish.assert_called()
    call_args = llm_agent.nc.publish.call_args
    data = json.loads(call_args[0][1].decode())
    
    assert data["request_id"] == "req-123"
    assert data["status"] == "error"
    assert data["error"] == "Test error"

def test_handle_analyze_request_cache_hit(llm_agent):
    """Тест обработки запроса с попаданием в кэш"""
    # Мокаем кэш
    llm_agent.redis_client.get.return_value = json.dumps({
        "cause": "Cached cause",
        "recommendation": "Cached fix",
        "criticality": "Medium"
    })
    
    # Создаём сообщение
    msg = AsyncMock()
    msg.data.decode.return_value = json.dumps({
        "anomaly": "Test anomaly",
        "request_id": "req-456"
    })
    
    # Вызываем обработчик
    asyncio.run(llm_agent.handle_analyze_request(msg))
    
    # Проверяем, что результат опубликован и LLM не вызывался
    llm_agent._publish_result.assert_called()
    llm_agent._generate_analysis.assert_not_called()

def test_handle_analyze_request_cache_miss(llm_agent):
    """Тест обработки запроса без попадания в кэш"""
    llm_agent.redis_client.get.return_value = None
    
    # Мокаем генерацию анализа
    with patch.object(llm_agent, '_generate_analysis') as mock_gen:
        mock_gen.return_value = {
            "cause": "Generated cause",
            "recommendation": "Generated fix",
            "criticality": "High"
        }
        
        msg = AsyncMock()
        msg.data.decode.return_value = json.dumps({
            "anomaly": "Test anomaly",
            "request_id": "req-789"
        })
        
        asyncio.run(llm_agent.handle_analyze_request(msg))
        
        mock_gen.assert_called()
        llm_agent._cache_result.assert_called()
        llm_agent._publish_result.assert_called()

def test_handle_analyze_request_no_anomaly(llm_agent):
    """Тест обработки запроса без текста аномалии"""
    msg = AsyncMock()
    msg.data.decode.return_value = json.dumps({
        "request_id": "req-999"
    })
    
    asyncio.run(llm_agent.handle_analyze_request(msg))
    
    llm_agent._publish_error_result.assert_called_with("No anomaly text provided", "req-999")