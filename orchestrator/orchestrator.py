import asyncio
import json
import logging
import os
import random
import subprocess
import time
from collections import defaultdict
from typing import Dict, List, Optional

import nats
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrTimeout
from opentelemetry import trace
from opentelemetry.trace import Span

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка трассировки
tracer = trace.get_tracer(__name__)

# Конфигурация
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
MAX_AGENTS = int(os.getenv("MAX_AGENTS", "5"))
SCALE_UP_THRESHOLD = int(os.getenv("SCALE_UP_THRESHOLD", "3"))
AUCTION_TIMEOUT = float(os.getenv("AUCTION_TIMEOUT", "2.0"))
LLM_AGENT_URL = os.getenv("LLM_AGENT_URL", "http://llm-agent:8000/analyze")


class Orchestrator:
    def __init__(self):
        self.nc: Optional[NATS] = None
        self.agents: Dict[str, dict] = {}  # agent_id -> agent info
        self.agent_tasks: Dict[str, int] = defaultdict(int)  # agent_id -> task count
        self.current_agents_count = 0
        self.stats_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Подключение к NATS"""
        try:
            self.nc = await nats.connect(NATS_URL)
            logger.info(f"Connected to NATS at {NATS_URL}")
            await self.setup_subscriptions()
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def setup_subscriptions(self):
        """Настройка подписок"""
        # Подписка на результаты задач
        await self.nc.subscribe("tasks.result", cb=self.handle_result)

        # Подписка на ставки агентов
        await self.nc.subscribe("tasks.auction.bids", cb=self.handle_bid)

        # Подписка на запросы аукциона (если будут)
        await self.nc.subscribe("tasks.auction.request", cb=self.handle_auction_request)

    async def handle_result(self, msg):
        """Обработка результата выполнения задачи"""
        with tracer.start_as_current_span("handle_result") as span:
            result = msg.data.decode()
            logger.info(f"Task result received: {result}")
            span.set_attribute("task.result", result)

    async def handle_bid(self, msg):
        """Обработка ставки от агента"""
        with tracer.start_as_current_span("handle_bid") as span:
            try:
                bid_data = json.loads(msg.data.decode())
                agent_id = bid_data["agent_id"]
                skill = bid_data["skill"]
                load = bid_data["load"]
                bid = bid_data["bid"]  # Мы храним bid как skill - load

                self.agents[agent_id] = {
                    "skill": skill,
                    "load": load,
                    "bid": bid,
                    "last_seen": time.time()
                }
                logger.debug(f"Received bid from {agent_id}: {bid}")

                span.set_attribute("agent.id", agent_id)
                span.set_attribute("agent.bid", bid)
            except Exception as e:
                logger.error(f"Failed to parse bid: {e}")

    async def handle_auction_request(self, msg):
        """Обработка запроса аукциона (если оркестратор получит такой запрос)"""
        with tracer.start_as_current_span("handle_auction_request"):
            # В текущей архитектуре оркестратор инициирует аукцион, а не отвечает на запрос
            logger.warning("Orchestrator received auction request, but it should initiate")

    async def find_best_agent(self, task_type: str) -> Optional[str]:
        """Найти лучшего агента для задачи через аукцион"""
        with tracer.start_as_current_span("find_best_agent") as span:
            span.set_attribute("task.type", task_type)

            # Очистка старых агентов
            self._cleanup_stale_agents()

            if not self.agents:
                logger.warning("No agents available")
                return None

            # Публикуем запрос на аукцион
            request_msg = {"task_type": task_type, "timestamp": time.time()}
            await self.nc.publish("tasks.auction.request", json.dumps(request_msg).encode())

            # Ждём ставки (имитируем, так как они уже приходят через handle_bid)
            await asyncio.sleep(AUCTION_TIMEOUT)

            # Выбираем агента с наименьшей ценой (bid)
            best_agent = None
            best_bid = float('inf')

            for agent_id, info in self.agents.items():
                if info["bid"] < best_bid:
                    best_bid = info["bid"]
                    best_agent = agent_id

            if best_agent:
                logger.info(f"Selected agent {best_agent} for task {task_type} with bid {best_bid}")
                span.set_attribute("selected_agent.id", best_agent)
                span.set_attribute("selected_agent.bid", best_bid)
            else:
                logger.warning(f"No suitable agent found for task {task_type}")

            return best_agent

    def _cleanup_stale_agents(self, timeout: float = 30.0):
        """Очистка устаревших агентов"""
        now = time.time()
        to_remove = [aid for aid, info in self.agents.items() 
                    if now - info["last_seen"] > timeout]
        for aid in to_remove:
            del self.agents[aid]
            logger.info(f"Removed stale agent {aid}")

    async def execute_task(self, task_type: str, payload: dict = None) -> str:
        """Выполнить задачу через аукцион и получить результат"""
        with tracer.start_as_current_span("execute_task") as span:
            span.set_attribute("task.type", task_type)

            agent_id = await self.find_best_agent(task_type)
            if not agent_id:
                error_msg = f"No agent available for task {task_type}"
                logger.error(error_msg)
                span.set_status(trace.StatusCode.ERROR)
                span.record_exception(Exception(error_msg))
                return error_msg

            # Формируем сообщение
            task_msg = {"type": task_type}
            if payload:
                task_msg.update(payload)

            # Отправляем задачу конкретному агенту
            topic = f"tasks.monitoring.{agent_id}"
            await self.nc.publish(topic, json.dumps(task_msg).encode())
            logger.info(f"Sent task {task_type} to agent {agent_id} at {topic}")

            # Ждём результата (упрощённо — мы получим его через handle_result)
            # В реальности нужно использовать запрос-ответ или отслеживать по ID
            await asyncio.sleep(1.0)  # Имитация ожидания

            return f"Task {task_type} completed by agent {agent_id}"

    async def run_pipeline(self) -> dict:
        """Запуск полного пайплайна"""
        with tracer.start_as_current_span("run_pipeline") as span:
            results = {}
            payload = None

            try:
                # Шаг 1: Сбор метрик
                result1 = await self.execute_task("collect_metrics")
                results["collect_metrics"] = result1
                payload = {"metrics": "simulated"}  # В реальности извлекается из результата

                # Шаг 2: Детекция аномалий
                result2 = await self.execute_task("detect_anomaly", payload)
                results["detect_anomaly"] = result2

                # Если есть аномалия, продолжаем
                if "ANOMALY" in result2.upper():
                    # Шаг 3: Оповещение
                    result3 = await self.execute_task("send_alert", {"message": result2})
                    results["send_alert"] = result3

                    # Шаг 4: Автовосстановление
                    result4 = await self.execute_task("auto_recovery")
                    results["auto_recovery"] = result4

                    # Интеграция с LLM-агентом
                    llm_result = await self.call_llm_agent(result2)
                    results["llm_analysis"] = llm_result
                else:
                    results["send_alert"] = "No anomaly detected"
                    results["auto_recovery"] = "Skipped"
                    results["llm_analysis"] = "No analysis needed"

                span.set_attribute("pipeline.status", "success")
            except Exception as e:
                logger.error(f"Pipeline failed: {e}")
                span.set_status(trace.StatusCode.ERROR)
                span.record_exception(e)
                results["error"] = str(e)

            return results

    async def call_llm_agent(self, anomaly_data: str) -> str:
        """Вызов LLM-агента для анализа аномалии"""
        with tracer.start_as_current_span("call_llm_agent") as span:
            span.set_attribute("llm.url", LLM_AGENT_URL)

            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        LLM_AGENT_URL,
                        json={"anomaly": anomaly_data},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        result = response.json().get("analysis", "No analysis returned")
                        span.set_attribute("llm.result", result)
                        return result
                    else:
                        error = f"LLM agent returned {response.status_code}: {response.text}"
                        span.set_status(trace.StatusCode.ERROR)
                        return error
            except Exception as e:
                span.record_exception(e)
                return f"Failed to call LLM agent: {e}"

    async def monitor_queue_and_scale(self):
        """Мониторинг очереди и автоматическое масштабирование"""
        while True:
            try:
                await asyncio.sleep(5)  # Каждые 5 секунд
                await self.check_queue_and_scale()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scaling monitor: {e}")

    async def check_queue_and_scale(self):
        """Проверка длины очереди и масштабирование"""
        with tracer.start_as_current_span("check_queue_and_scale") as span:
            try:
                # Получаем статистику
                stats = await self.nc.stats()
                # В NATS нет прямого способа получить длину subject, мы можем использовать количество подписок
                # или внешние инструменты. Упрощённо: считаем активные задачи по нагрузке
                current_load = len(self.agents)  # Упрощённая метрика

                logger.info(f"Queue stats: {stats}, current agents: {self.current_agents_count}")

                # Если нагрузка высока и есть свободные слоты
                if current_load > SCALE_UP_THRESHOLD and self.current_agents_count < MAX_AGENTS:
                    await self.scale_up()
                    span.add_event("Scaling up triggered")
                else:
                    span.add_event("No scaling needed")

            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
                span.record_exception(e)

    async def scale_up(self):
        """Масштабирование вверх — запуск нового агента"""
        with tracer.start_as_current_span("scale_up") as span:
            try:
                # Генерируем случайный ID
                agent_id = f"agent-{random.randint(1000, 9999)}"
                
                # Вызываем скрипт масштабирования
                result = subprocess.run(
                    ["bash", "scripts/scale.sh", agent_id],
                    cwd="orchestrator",
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    self.current_agents_count += 1
                    logger.info(f"Scaled up: {agent_id} started")
                    span.set_attribute("scaled.agent_id", agent_id)
                    span.set_attribute("current_agents_count", self.current_agents_count)
                else:
                    logger.error(f"Failed to scale up: {result.stderr}")
                    span.record_exception(Exception(result.stderr))
            except Exception as e:
                logger.error(f"Exception during scale up: {e}")
                span.record_exception(e)

    async def manual_scale_up(self) -> str:
        """Ручное масштабирование"""
        if self.current_agents_count >= MAX_AGENTS:
            return f"Cannot scale up: maximum {MAX_AGENTS} agents reached"
        
        await self.scale_up()
        return f"Scaling up initiated, current agents: {self.current_agents_count}"

    async def get_agents(self) -> List[dict]:
        """Получить список активных агентов"""
        return [
            {"agent_id": aid, **info} 
            for aid, info in self.agents.items()
        ]

    async def close(self):
        """Закрытие соединения"""
        if self.nc:
            await self.nc.close()
        if self.stats_task:
            self.stats_task.cancel()
            try:
                await self.stats_task
            except asyncio.CancelledError:
                pass