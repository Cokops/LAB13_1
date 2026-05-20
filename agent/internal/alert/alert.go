package alert

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// Send simulates sending an alert
func Send(ctx context.Context, message string) string {
	tracer := trace.SpanFromContext(ctx).TracerProvider().Tracer("agent/alert")
	_, span := tracer.Start(ctx, "sendAlert")
	defer span.End()

	// Simulate alert delivery
	time.Sleep(50 * time.Millisecond)

	alertID := fmt.Sprintf("alert-%d", time.Now().Unix())
	result := fmt.Sprintf("alert sent (ID: %s): %s", alertID, message)

	// Log to console
	fmt.Printf("[ALERT] %s\n", result)

	span.SetAttributes(
		attribute.String("alert.id", alertID),
		attribute.String("alert.message", message),
	)

	return result
}