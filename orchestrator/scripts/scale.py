"""
scale.py - Python script to scale monitoring agents using Docker SDK

This script provides the same functionality as scale.sh but using Python and Docker SDK.
It can be used as an alternative to the bash script.
"""

import argparse
import datetime
import docker
import os
import sys
import time

# Configuration from environment or defaults
DOCKER_HOST = os.getenv('DOCKER_HOST', 'unix://var/run/docker.sock')
NETWORK_NAME = os.getenv('NETWORK_NAME', 'zad13_1_monitoring-net')
AGENT_IMAGE = os.getenv('AGENT_IMAGE', 'monitoring-agent:latest')
NATS_URL = os.getenv('NATS_URL', 'nats://nats:4222')
REDIS_URL = os.getenv('REDIS_URL', 'redis:6379')
JAEGER_ENDPOINT = os.getenv('JAEGER_ENDPOINT', 'jaeger:4317')


class AgentScaler:
    def __init__(self):
        self.client = docker.DockerClient(base_url=DOCKER_HOST)
    
    def generate_agent_id(self):
        """Generate unique agent ID"""
        timestamp = int(time.time())
        random_hex = os.urandom(2).hex()
        return f"agent-{timestamp}-{random_hex}"
    
    def check_network(self):
        """Check if the required Docker network exists"""
        try:
            self.client.networks.get(NETWORK_NAME)
            return True
        except docker.errors.NotFound:
            print(f"Error: Docker network '{NETWORK_NAME}' not found.")
            print("Please ensure the network exists and is created by docker-compose.")
            return False
    
    def run_agent_container(self, agent_id):
        """Run a new agent container"""
        try:
            print(f"Starting new agent: {agent_id}")
            
            container = self.client.containers.run(
                image=AGENT_IMAGE,
                name=agent_id,
                network=NETWORK_NAME,
                environment={
                    'OTEL_EXPORTER_OTLP_ENDPOINT': JAEGER_ENDPOINT,
                    'OTEL_EXPORTER_OTLP_PROTOCOL': 'grpc'
                },
                command=[
                    '--id', agent_id,
                    '--nats-url', NATS_URL,
                    '--redis-url', REDIS_URL,
                    '--jaeger-endpoint', JAEGER_ENDPOINT
                ],
                detach=True
            )
            
            print(f"Agent {agent_id} started successfully with container ID: {container.id[:12]}")
            return True
            
        except Exception as e:
            print(f"Failed to start agent {agent_id}: {e}")
            return False
    
    def list_agent_containers(self):
        """List all running agent containers with creation time"""
        try:
            containers = self.client.containers.list(
                filters={'name': '^agent-'}
            )
            
            agent_info = []
            for container in containers:
                # Parse creation time
                created = container.attrs['Created']
                # Remove timezone info if present
                if '.' in created:
                    created = created.split('.')[0]
                try:
                    created_dt = datetime.datetime.fromisoformat(created)
                except ValueError:
                    created_dt = datetime.datetime.now()
                    
                agent_info.append({
                    'id': container.id,
                    'name': container.name,
                    'created': created_dt,
                    'status': container.status
                })
                
            # Sort by creation time (oldest first)
            agent_info.sort(key=lambda x: x['created'])
            return agent_info
            
        except Exception as e:
            print(f"Error listing containers: {e}")
            return []
    
    def stop_oldest_agent(self):
        """Stop the oldest agent container"""
        agents = self.list_agent_containers()
        
        if not agents:
            print("No agent containers found to stop.")
            return False
        
        oldest = agents[0]  # Already sorted
        try:
            print(f"Stopping oldest agent: {oldest['name']} (created: {oldest['created']})")
            container = self.client.containers.get(oldest['name'])
            container.stop()
            container.remove()
            print(f"Agent {oldest['name']} stopped and removed.")
            return True
            
        except Exception as e:
            print(f"Failed to stop agent {oldest['name']}: {e}")
            return False
    
    def scale_down(self, target_count=1):
        """Scale down to target number of agents"""
        agents = self.list_agent_containers()
        current_count = len(agents)
        
        if current_count <= target_count:
            print(f"No scaling down needed. Current: {current_count}, Target: {target_count}")
            return True
        
        scale_count = current_count - target_count
        print(f"Scaling down by {scale_count} agents...")
        
        success = True
        for i in range(scale_count):
            if not self.stop_oldest_agent():
                success = False
                break
            time.sleep(1)  # Brief pause between stops
            
        return success
    
    def scale_up(self):
        """Scale up by starting one new agent"""
        if not self.check_network():
            return False
            
        agent_id = self.generate_agent_id()
        return self.run_agent_container(agent_id)


def main():
    parser = argparse.ArgumentParser(description='Scale monitoring agents')
    parser.add_argument('action', choices=['up', 'down', 'scale-down'],
                       help='Action to perform')
    parser.add_argument('target', type=int, nargs='?', default=1,
                       help='Target number of agents (for scale-down)')
    
    args = parser.parse_args()
    
    scaler = AgentScaler()
    
    if args.action == 'up':
        success = scaler.scale_up()
        sys.exit(0 if success else 1)
        
    elif args.action == 'down':
        success = scaler.stop_oldest_agent()
        sys.exit(0 if success else 1)
        
    elif args.action == 'scale-down':
        success = scaler.scale_down(args.target)
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()