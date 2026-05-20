import asyncio
import json
import logging
import os
import sys
from hashlib import sha256
from typing import Dict, Any

import nats
import ollama
import redis
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка трассировки
resource = Resource(attributes={
    "service.name": "llm-agent"
})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# Конфигурация
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
REDIS_URL = os.getenv("REDIS_URL", "localhost:6379")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "300"))  # 5 минут


class LLMAgent:
    def __init__(self, nats_url: str, redis_url: str):
        self.nats_url = nats_url
        self.redis_client = redis.from_url(f"redis://{redis_url}", decode_responses=True)
        self.nc = None

    async def connect(self):
        """Подключение к NATS"""
        try:
            self.nc = await nats.connect(self.nats_url)
            logger.info(f"Connected to NATS at {self.nats_url}")
            await self.setup_subscriptions()
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def setup_subscriptions(self):
        """Подписка на тему анализа аномалий"""
        await self.nc.subscribe("tasks.llm.analyze", cb=self.handle_analyze_request)
        logger.info("Subscribed to tasks.llm.analyze")

    async def handle_analyze_request(self, msg):
        """Обработка запроса на анализ аномалии"""
        with tracer.start_as_current_span("handle_analyze_request") as span:
            try:
                request = json.loads(msg.data.decode())
                anomaly_text = request.get("anomaly", "")
                request_id = request.get("request_id", "unknown")

                if not anomaly_text:
                    error_msg = "No anomaly text provided"
                    await self._publish_error_result(error_msg, request_id)
                    return

                # Генерация ключа кэша
                cache_key = f"llm_result:{sha256(anomaly_text.encode()).hexdigest()}"

                # Попытка получить из кэша
                cached_result = await self._get_cached_result(cache_key)
                if cached_result:
                    span.set_attribute("cache.hit", True)
                    await self._publish_result(cached_result, request_id)
                    return

                span.set_attribute("cache.hit", False)
                span.set_attribute("anomaly.text", anomaly_text)
                span.set_attribute("request.id", request_id)

                # Генерация анализа через LLM
                analysis = await self._generate_analysis(anomaly_text, span)

                if analysis:
                    # Кэширование результата
                    await self._cache_result(cache_key, analysis)
                    await self._publish_result(analysis, request_id)
                else:
                    await self._publish_error_result("Failed to generate analysis", request_id)

            except Exception as e:
                logger.error(f"Error handling analyze request: {e}")
                span.record_exception(e)
                await self._publish_error_result(str(e), request_id)

    async def _generate_analysis(self, anomaly_text: str, parent_span: trace.Span) -> Dict[str, Any]:
        """Генерация анализа аномалии через LLM"""
        with tracer.start_as_current_span("generate_analysis") as span:
            try:
                prompt = f"""Analyze the following system anomaly and provide structured response.

Anomaly: {anomaly_text}

Please provide:
1. Probable cause
2. Recovery recommendation
3. Criticality (High/Medium/Low)

Respond in JSON format with keys: cause, recommendation, criticality"""

                # Используем ollama Python клиент
                response = ollama.generate(
                    model=OLLAMA_MODEL,
                    prompt=prompt,
                    format='json'
                )

                # Извлекаем и парсим ответ
                raw_response = response['response'].strip()
                span.set_attribute("llm.raw_response", raw_response)

                try:
                    analysis = json.loads(raw_response)
                    # Валидация структуры
                    if all(k in analysis for k in ["cause", "recommendation", "criticality"]):
                        span.set_attribute("llm.cause", analysis["cause"])
                        span.set_attribute("llm.criticality", analysis["criticality"])
                        return analysis
                    else:
                        logger.warning(f"Invalid JSON structure: {analysis}")
                        span.add_event("Invalid JSON structure", {
                            "expected_keys": ["cause", "recommendation", "criticality"],
                            "actual_keys": list(analysis.keys())
                        })
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}")
                    span.record_exception(e)

                # Fallback при ошибке парсинга
                return {
                    "cause": "Unable to determine cause",
                    "recommendation": "Manual investigation required",
                    "criticality": "Medium"
                }

            except Exception as e:
                logger.error(f"Error generating analysis: {e}")
                span.record_exception(e)
                return None

    async def _get_cached_result(self, cache_key: str) -> Dict[str, Any]:
        """Получение результата из кэша Redis"""
        with tracer.start_as_current_span("get_cached_result") as span:
            span.set_attribute("cache.key", cache_key)
            try:
                result_json = self.redis_client.get(cache_key)
                if result_json:
                    result = json.loads(result_json)
                    span.set_attribute("cache.hit", True)
                    return result
                span.set_attribute("cache.hit", False)
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
                span.record_exception(e)
            return None

    async def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Кэширование результата в Redis"""
        with tracer.start_as_current_span("cache_result") as span:
            span.set_attribute("cache.key", cache_key)
            try:
                self.redis_client.setex(cache_key, REDIS_CACHE_TTL, json.dumps(result))
                span.set_attribute("cache.ttl", REDIS_CACHE_TTL)
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")
                span.record_exception(e)

    async def _publish_result(self, analysis: Dict[str, Any], request_id: str):
        """Публикация результата анализа"""
        with tracer.start_as_current_span("publish_result") as span:
            span.set_attribute("request.id", request_id)
            result_msg = {
                "request_id": request_id,
                "analysis": analysis,
                "status": "success"
            }
            await self.nc.publish("tasks.llm.result", json.dumps(result_msg).encode())
            logger.info(f"Analysis result published for request {request_id}")

    async def _publish_error_result(self, error_msg: str, request_id: str):
        """Публикация ошибки"""
        with tracer.start_as_current_span("publish_error_result") as span:
            span.set_attribute("request.id", request_id)
            span.set_attribute("error.message", error_msg)
            result_msg = {
                "request_id": request_id,
                "error": error_msg,
                "status": "error"
            }
            await self.nc.publish("tasks.llm.result", json.dumps(result_msg).encode())
            logger.error(f"Error published for request {request_id}: {error_msg}")

    async def close(self):
        """Закрытие соединений"""
        if self.nc:
            await self.nc.close()
        # Закрытие провайдера трассировки
        await trace.get_tracer_provider().shutdown()


def parse_args():
    """Парсинг аргументов командной строки"""
    import argparse
    parser = argparse.ArgumentParser(description="LLM Agent for anomaly analysis")
    parser.add_argument("--nats-url", type=str, default=NATS_URL,
                       help="NATS server URL (default: nats://localhost:4222)")
    parser.add_argument("--redis-url", type=str, default=REDIS_URL,
                       help="Redis server URL (default: localhost:6379)")
    return parser.parse_args()

async def main():
    """Главная функция"""
    args = parse_args()
    
    agent = LLMAgent(nats_url=args.nats_url, redis_url=args.redis_url)
    
    try:
        await agent.connect()
        logger.info("LLM Agent started and listening for requests")
        
        # Keep alive
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Agent failed: {e}")
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main())