import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
import redis
from llm_agent.llm_agent import LLMAgent

@pytest.fixture
def llm_agent():
    """Создаём LLM-агента для тестов (синхронная фикстура)"""
    with patch('nats.connect') as mock_nats_connect, \
         patch('redis.from_url') as mock_redis_connect:
        
        mock_nc = AsyncMock()
        mock_nats_connect.return_value = mock_nc
        
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis_connect.return_value = mock_redis
        
        agent = LLMAgent(nats_url="nats://localhost:4222", redis_url="localhost:6379")
        agent.nc = mock_nc
        agent.redis_client = mock_redis
        
        return agent

@pytest.mark.asyncio
async def test_generate_analysis_success(llm_agent):
    """Тест успешной генерации анализа"""
    with patch('ollama.generate') as mock_generate:
        mock_generate.return_value = {
            'response': '{"cause": "High CPU load", "recommendation": "Check processes", "criticality": "High"}'
        }
        
        analysis = await llm_agent._generate_analysis("CPU spike", None)
        
        assert analysis["cause"] == "High CPU load"
        assert analysis["recommendation"] == "Check processes"
        assert analysis["criticality"] == "High"
        mock_generate.assert_called()