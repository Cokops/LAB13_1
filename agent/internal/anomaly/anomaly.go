package anomaly

import (
	"context"
	"strings"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// Detect simulates anomaly detection in metrics
func Detect(ctx context.Context, metricsData string) string {
	tracer := trace.SpanFromContext(ctx).TracerProvider().Tracer("agent/anomaly")
	_, span := tracer.Start(ctx, "detectAnomaly")
	defer span.End()

	// Parse metrics from string (simplified)
	isAnomaly := false
	issues := []string{}

	if strings.Contains(metricsData, "CPU=9") || strings.Contains(metricsData, "CPU=10") {
		isAnomaly = true
		issues = append(issues, "high CPU usage")
	}
	if strings.Contains(metricsData, "Memory=9") || strings.Contains(metricsData, "Memory=10") {
		isAnomaly = true
		issues = append(issues, "high memory usage")
	}
	if strings.Contains(metricsData, "Disk=9") || strings.Contains(metricsData, "Disk=10") {
		isAnomaly = true
		issues = append(issues, "high disk usage")
	}

	result := "anomaly check completed"
	if isAnomaly {
		result = "ANOMALY DETECTED: " + strings.Join(issues, ", ")
	}

	span.SetAttributes(
		attribute.String("anomaly.result", result),
		attribute.Bool("anomaly.detected", isAnomaly),
	)

	return result
}
