package main

import (
	"context"
	"flag"
	"log"
	"math/rand"
	"os"
	"os/signal"
	"syscall"
	"time"

	"agent/internal/alert"
	"agent/internal/anomaly"
	"agent/internal/auction"
	"agent/internal/metrics"
	"agent/internal/recovery"
	"agent/internal/state"
	"agent/internal/tracing"

	"github.com/nats-io/nats.go"
)

func main() {
	// Command line flags
	agentID := flag.String("id", "", "Agent ID")
	natsURL := flag.String("nats-url", "nats://localhost:4222", "NATS server URL")
	redisURL := flag.String("redis-url", "localhost:6379", "Redis server URL")
	jaegerEndpoint := flag.String("jaeger-endpoint", "localhost:4317", "Jaeger OTLP gRPC endpoint")
	flag.Parse()

	if *agentID == "" {
		log.Fatal("--id is required")
	}

	// Context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Setup signal handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		log.Println("Shutting down...")
		cancel()
	}()

	// Initialize tracing
	tracerProvider, err := tracing.InitTracer(*jaegerEndpoint, *agentID)
	if err != nil {
		log.Fatalf("Failed to initialize tracer: %v", err)
	}
	defer func() {
		if err := tracerProvider.Shutdown(ctx); err != nil {
			log.Printf("Error shutting down tracer: %v", err)
		}
	}()

	// Connect to NATS
	natsConn, err := nats.Connect(*natsURL)
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}
	defer natsConn.Close()

	// Connect to Redis and restore state
	redisClient := state.NewClient(*redisURL)
	if err := redisClient.Connect(ctx); err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	defer redisClient.Close()

	// Restore task counts
	taskCounts, err := redisClient.RestoreTaskCounts(ctx)
	if err != nil {
		log.Printf("Failed to restore task counts: %v", err)
	}

	log.Printf("Agent %s started, restored task counts: %+v", *agentID, taskCounts)

	// Subscribe to monitoring tasks
	_, err = natsConn.QueueSubscribe("tasks.monitoring", "monitoring_group", func(msg *nats.Msg) {
		go handleMonitoringTask(ctx, msg, natsConn, redisClient, *agentID, taskCounts)
	})
	if err != nil {
		log.Fatalf("Failed to subscribe to tasks.monitoring: %v", err)
	}

	// Start auction bidding
	auction.StartBidding(ctx, natsConn, *agentID)

	// Wait for shutdown
	<-ctx.Done()
	log.Println("Agent stopped")
}

func handleMonitoringTask(
	ctx context.Context,
	msg *nats.Msg,
	natsConn *nats.Conn,
	redisClient *state.Client,
	agentID string,
	taskCounts map[string]int,
) {
	tracer := tracing.Tracer
	ctx, span := tracer.Start(ctx, "handleMonitoringTask")
	defer span.End()

	taskType := string(msg.Data)

	// Update and persist task count
	taskCounts[taskType]++
	if err := redisClient.SaveTaskCounts(ctx, taskCounts); err != nil {
		span.RecordError(err)
		log.Printf("Failed to save task count: %v", err)
	}

	var result string
	switch taskType {
	case "collect_metrics":
		result = metrics.Collect(ctx)
	case "detect_anomaly":
		metricsData := metrics.Collect(ctx) // In real case, this would come from context or previous step
		result = anomaly.Detect(ctx, metricsData)
	case "send_alert":
		result = alert.Send(ctx, "Anomaly detected in system metrics")
	case "auto_recovery":
		result = recovery.Perform(ctx)
	default:
		result = "unknown task type"
	}

	// Publish result
	if err := natsConn.Publish("tasks.result", []byte(result)); err != nil {
		span.RecordError(err)
		log.Printf("Failed to publish result: %v", err)
	}
}

// initRandom initializes the random number generator
func init() {
	rand.Seed(time.Now().UnixNano())
}
