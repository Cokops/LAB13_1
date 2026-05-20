package metrics

import (
	"context"
	"fmt"
	"math/rand"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// Metric represents system metric
type Metric struct {
	CPUUsage    float64 `json:"cpu_usage"`
	MemoryUsage float64 `json:"memory_usage"`
	DiskUsage   float64 `json:"disk_usage"`
}

// Collect simulates metrics collection
func Collect(ctx context.Context) string {
	tracer := trace.SpanFromContext(ctx).TracerProvider().Tracer("agent/metrics")
	_, span := tracer.Start(ctx, "collectMetrics")
	defer span.End()

	// Simulate real metrics collection
	metric := Metric{
		CPUUsage:    rand.Float64() * 100,
		MemoryUsage: rand.Float64() * 100,
		DiskUsage:   rand.Float64() * 100,
	}

	// Add metrics as attributes
	span.SetAttributes(
		attribute.Float64("system.cpu.usage", metric.CPUUsage),
		attribute.Float64("system.memory.usage", metric.MemoryUsage),
		attribute.Float64("system.disk.usage", metric.DiskUsage),
	)

	return "collected: CPU=" + fmt.Sprintf("%.2f", metric.CPUUsage) + "% " +
		"Memory=" + fmt.Sprintf("%.2f", metric.MemoryUsage) + "% " +
		"Disk=" + fmt.Sprintf("%.2f", metric.DiskUsage) + "%"
}
