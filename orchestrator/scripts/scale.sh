#!/bin/bash
# scale.sh - DevOps script to scale monitoring agents dynamically

# Exit on any error
set -e

# Default values (can be overridden by environment)
DOCKER_HOST=${DOCKER_HOST:-"unix:///var/run/docker.sock"}
NETWORK_NAME=${NETWORK_NAME:-"zad13_1_monitoring-net"}
AGENT_IMAGE=${AGENT_IMAGE:-"monitoring-agent:latest"}
NATS_URL=${NATS_URL:-"nats://nats:4222"}
REDIS_URL=${REDIS_URL:-"redis:6379"}
JAEGER_ENDPOINT=${JAEGER_ENDPOINT:-"jaeger:4317"}

# Function to generate unique agent ID
generate_agent_id() {
    echo "agent-$(date +%s)-$(openssl rand -hex 2)"
}

# Function to check if network exists
check_network() {
    if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
        echo "Error: Docker network '$NETWORK_NAME' not found."
        echo "Please ensure the network exists and is created by docker-compose."
        exit 1
    fi
}

# Function to run new agent container
run_agent_container() {
    local agent_id="$1"
    
    echo "Starting new agent: $agent_id"
    
    docker run -d \
        --network "$NETWORK_NAME" \
        --name "$agent_id" \
        -e "OTEL_EXPORTER_OTLP_ENDPOINT=$JAEGER_ENDPOINT" \
        -e "OTEL_EXPORTER_OTLP_PROTOCOL=grpc" \
        "$AGENT_IMAGE" \
        --id "$agent_id" \
        --nats-url "$NATS_URL" \
        --redis-url "$REDIS_URL" \
        --jaeger-endpoint "$JAEGER_ENDPOINT"
    
    echo "Agent $agent_id started successfully"
}

# Function to list running agent containers
list_agent_containers() {
    docker ps --filter "name=^agent-" --format "{{.Names}},{{.CreatedAt}}"
}

# Function to stop oldest agent container
stop_oldest_agent() {
    local containers=$(list_agent_containers)
    
    if [ -z "$containers" ]; then
        echo "No agent containers found to stop."
        return 0
    fi
    
    # Sort by creation time (oldest first) and get the first one
    local oldest=$(echo "$containers" | sort -t',' -k2 | head -n1 | cut -d',' -f1)
    
    if [ -n "$oldest" ]; then
        echo "Stopping oldest agent: $oldest"
        docker stop "$oldest" && docker rm "$oldest"
        echo "Agent $oldest stopped and removed."
    else
        echo "No agents to stop."
    fi
}

# Function to scale down agents if needed
scale_down() {
    local current_count=$(list_agent_containers | wc -l)
    local target_count=${1:-1}
    
    if [ "$current_count" -le "$target_count" ]; then
        echo "No scaling down needed. Current: $current_count, Target: $target_count"
        return 0
    fi
    
    local scale_count=$((current_count - target_count))
    echo "Scaling down by $scale_count agents..."
    
    for i in $(seq 1 $scale_count); do
        stop_oldest_agent
        sleep 1
    done
}

# Main script logic
main() {
    local action=${1:-"up"}
    local agent_id
    
    # Check prerequisites
    check_network
    
    case "$action" in
        "up")
            agent_id=$(generate_agent_id)
            run_agent_container "$agent_id"
            ;;
        "down")
            stop_oldest_agent
            ;;
        "scale-down")
            local target=${2:-1}
            scale_down "$target"
            ;;
        *)
            echo "Usage: $0 [up|down|scale-down [target_count]]"
            echo "  up           - start one new agent"
            echo "  down         - stop one oldest agent"
            echo "  scale-down N - scale down to N agents"
            exit 1
            ;;
    esac
}

# Run main with all arguments
main "$@"