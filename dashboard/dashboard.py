import streamlit as st
import nats
import asyncio
import json
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time

# Настройка страницы
st.set_page_config(page_title="Multi-Agent Monitoring Dashboard", layout="wide")

# Конфигурация
NATS_URL = st.secrets.get("NATS_URL", "nats://localhost:4222")
ORCHESTRATOR_URL = st.secrets.get("ORCHESTRATOR_URL", "http://localhost:8000")
REDIS_URL = st.secrets.get("REDIS_URL", "localhost:6379")

# Состояние приложения
if 'agents' not in st.session_state:
    st.session_state.agents = []
if 'tasks' not in st.session_state:
    st.session_state.tasks = []
if 'llm_results' not in st.session_state:
    st.session_state.llm_results = []
if 'queue_history' not in st.session_state:
    st.session_state.queue_history = []
if 'nats_connected' not in st.session_state:
    st.session_state.nats_connected = False

# Заголовок
st.title("🤖 Multi-Agent Monitoring System Dashboard")
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("**Real-time monitoring of AI-powered infrastructure agents**")
with col2:
    status = st.empty()
    status.success("Connected")

# Класс для работы с NATS
class DashboardClient:
    def __init__(self):
        self.nc = None
        self.running = True

    async def connect(self):
        try:
            self.nc = await nats.connect(NATS_URL)
            st.session_state.nats_connected = True
            st.toast("Connected to NATS successfully!")
            await self.setup_subscriptions()
        except Exception as e:
            st.error(f"Failed to connect to NATS: {e}")
            st.session_state.nats_connected = False

    async def setup_subscriptions(self):
        # Подписка на обновления агентов (имитация)
        await self.nc.subscribe("agent.status.*", cb=self.handle_agent_status)
        
        # Подписка на результаты задач
        await self.nc.subscribe("tasks.result", cb=self.handle_task_result)
        
        # Подписка на результаты LLM
        await self.nc.subscribe("tasks.llm.result", cb=self.handle_llm_result)

    async def handle_agent_status(self, msg):
        try:
            data = json.loads(msg.data.decode())
            agent_id = msg.subject.split(".")[-1]
            
            agent_info = {
                "id": agent_id,
                "status": "online",
                "last_seen": datetime.now().isoformat(),
                "task_count": data.get("task_count", 0),
                "load": data.get("load", 0.5)
            }
            
            # Обновляем список агентов
            current_ids = [a["id"] for a in st.session_state.agents]
            if agent_id in current_ids:
                st.session_state.agents = [
                    agent_info if a["id"] == agent_id else a 
                    for a in st.session_state.agents
                ]
            else:
                st.session_state.agents.append(agent_info)
                
        except Exception as e:
            st.error(f"Error processing agent status: {e}")

    async def handle_task_result(self, msg):
        try:
            result = msg.data.decode()
            task_record = {
                "timestamp": datetime.now().isoformat(),
                "result": result[:100] + "..." if len(result) > 100 else result,
                "status": "completed" if "completed" in result.lower() else "error"
            }
            st.session_state.tasks.insert(0, task_record)
            # Ограничиваем историю 50 последними задачами
            st.session_state.tasks = st.session_state.tasks[:50]
            
        except Exception as e:
            st.error(f"Error processing task result: {e}")

    async def handle_llm_result(self, msg):
        try:
            data = json.loads(msg.data.decode())
            if data.get("status") == "success":
                analysis = data["analysis"]
                llm_record = {
                    "timestamp": datetime.now().isoformat(),
                    "cause": analysis.get("cause", "N/A"),
                    "recommendation": analysis.get("recommendation", "N/A"),
                    "criticality": analysis.get("criticality", "N/A")
                }
                st.session_state.llm_results.insert(0, llm_record)
                # Ограничиваем 20 последними результатами
                st.session_state.llm_results = st.session_state.llm_results[:20]
            
        except Exception as e:
            st.error(f"Error processing LLM result: {e}")

    async def get_nats_stats(self):
        """Имитация получения статистики очереди"""
        try:
            # В реальности это было бы получение stats от NATS
            # Здесь имитируем случайную нагрузку
            import random
            queue_size = random.randint(0, 10)
            
            # Добавляем в историю
            now = datetime.now()
            st.session_state.queue_history.append({
                "time": now,
                "queue_size": queue_size
            })
            
            # Ограничиваем историю последними 100 точками
            st.session_state.queue_history = st.session_state.queue_history[-100:]
            
            return queue_size
            
        except Exception as e:
            st.error(f"Error getting queue stats: {e}")
            return 0

# Функции для взаимодействия с оркестратором
def run_pipeline():
    try:
        response = requests.post(f"{ORCHESTRATOR_URL}/run-pipeline", timeout=30)
        if response.status_code == 200:
            result = response.json()
            st.success("Pipeline started successfully!")
            return result
        else:
            st.error(f"Failed to start pipeline: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error calling orchestrator: {e}")
        return None

def send_anomaly_test(anomaly_text):
    try:
        response = requests.post(
            f"{ORCHESTRATOR_URL}/llm-analyze",
            json={"anomaly": anomaly_text, "request_id": f"test-{int(time.time())}"},
            timeout=10
        )
        if response.status_code == 200:
            st.success("Test anomaly sent successfully!")
            return True
        else:
            st.error(f"Failed to send anomaly: {response.text}")
            return False
    except Exception as e:
        st.error(f"Error sending anomaly: {e}")
        return False

# Асинхронный клиент NATS
@st.cache_resource
def get_nats_client():
    return DashboardClient()

# Запуск NATS клиента
client = get_nats_client()

# Интерфейс вкладок
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Agents", "🧠 LLM Analysis", "⚙️ Control"])

with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Agents", len(st.session_state.agents))
    with col2:
        st.metric("Recent Tasks", len(st.session_state.tasks))
    with col3:
        st.metric("LLM Analyses", len(st.session_state.llm_results))
    
    # График нагрузки
    st.subheader("NATS Queue Load")
    queue_chart = st.empty()
    
    # Запуск мониторинга очереди
    if 'monitoring' not in st.session_state:
        st.session_state.monitoring = True
    
    if st.session_state.monitoring:
        # Имитация данных очереди
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Обновляем график каждые 2 секунды
        for _ in range(50):  # Ограничиваем цикл для Streamlit
            queue_size = loop.run_until_complete(client.get_nats_stats())
            
            # Создаем график
            if len(st.session_state.queue_history) > 1:
                df = pd.DataFrame(st.session_state.queue_history)
                fig = px.line(df, x='time', y='queue_size',
                           title='NATS Queue Size Over Time',
                           labels={'queue_size': 'Queue Size', 'time': 'Time'})
                fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
                queue_chart.plotly_chart(fig, use_container_width=True)
            else:
                queue_chart.text("Collecting queue data...")
                
            time.sleep(2)
            
            # Проверяем, нужно ли продолжать
            if not st.session_state.get('monitoring', True):
                break

with tab2:
    st.subheader("Active Agents")
    
    if st.session_state.agents:
        df_agents = pd.DataFrame(st.session_state.agents)
        st.dataframe(df_agents, use_container_width=True)
        
        # График нагрузки агентов
        fig = px.bar(df_agents, x='id', y='load', color='load',
                   title="Agent Load Distribution",
                   labels={'id': 'Agent ID', 'load': 'Load'})  # ← Заменили : на =
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No agents connected yet. Start some agents to see them here.")

with tab3:
    st.subheader("LLM Analysis Results")
    
    if st.session_state.llm_results:
        df_llm = pd.DataFrame(st.session_state.llm_results)
        st.data_editor(df_llm, use_container_width=True)
        
        # Статистика по критичности
        criticality_counts = df_llm['criticality'].value_counts()
        fig = px.pie(values=criticality_counts.values, names=criticality_counts.index,
                   title="Criticality Distribution")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No LLM analysis results yet. Trigger a pipeline to generate some.")

with tab4:
    st.subheader("Control Panel")
    
    if st.button("🚀 Run Monitoring Pipeline", type="primary"):
        with st.spinner("Starting pipeline..."):
            result = run_pipeline()
    
    st.divider()
    
    st.subheader("Send Test Anomaly")
    anomaly_input = st.text_area(
        "Enter anomaly description:",
        "CPU usage spiked to 98% for 10 minutes on database server"
    )
    if st.button("Send Test Anomaly"):
        if anomaly_input.strip():
            with st.spinner("Sending anomaly..."):
                send_anomaly_test(anomaly_input)
        else:
            st.warning("Please enter an anomaly description")
    
    st.divider()
    
    st.subheader("System Status")
    st.write(f"**NATS**: {"✅ Connected" if st.session_state.nats_connected else "❌ Disconnected"}")
    st.write(f"**Orchestrator API**: {"✅ Reachable" if requests.get(f"{ORCHESTRATOR_URL}/health", timeout=5).status_code == 200 else "❌ Unreachable"}")
    
    if st.button("Refresh Dashboard"):
        st.rerun()

# Запуск NATS клиента в фоне
if not st.session_state.nats_connected:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(client.connect())