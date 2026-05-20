package metrics

import (
	"context"
	"testing"

	"go.opentelemetry.io/otel/trace"
)

func TestCollect(t *testing.T) {
	ctx := context.Background()
	result := Collect(ctx)

	// Проверяем, что результат не пустой
	if result == "" {
		t.Fatal("Collect returned empty result")
	}

	// Проверяем, что содержит ключевые метрики
	if !containsAll(result, "CPU=", "Memory=", "Disk=") {
		t.Errorf("Result does not contain expected metrics: got %s", result)
	}
}

// containsAll проверяет, что строка содержит все подстроки
func containsAll(s string, substrs ...string) bool {
	for _, substr := range substrs {
		if !contains(s, substr) {
			return false
		}
	}
	return true
}

// contains проверяет наличие подстроки (аналог strings.Contains)
func contains(s, substr string) bool {
	n := len(substr)
	for i := 0; i <= len(s)-n; i++ {
		if s[i:i+n] == substr {
			return true
		}
	}
	return false
}

// Мок для трассировки (упрощённый)

type mockTracer struct{}

func (m mockTracer) Start(ctx context.Context, spanName string, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	return ctx, trace.SpanFromContext(ctx)
}

func BenchmarkCollect(b *testing.B) {
	ctx := context.Background()
	b.ResetTimer()
	
	for i := 0; i < b.N; i++ {
		Collect(ctx)
	}
}