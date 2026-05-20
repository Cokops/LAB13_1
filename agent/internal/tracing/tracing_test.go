package tracing

import (
	"context"
	"testing"

	"go.opentelemetry.io/otel"
)

func TestInitTracer(t *testing.T) {
	// Сохраняем оригинального провайдера
	originalProvider := otel.GetTracerProvider()
	defer otel.SetTracerProvider(originalProvider)

	// Тестируем инициализацию трейсера
	provider, err := InitTracer("localhost:4317", "test-agent")

	if err != nil {
		t.Fatalf("InitTracer failed: %v", err)
	}

	if provider == nil {
		t.Fatal("Expected non-nil TracerProvider")
	}

	// Проверяем, что трейсер инициализирован
	if Tracer == nil {
		t.Error("Tracer not initialized")
	}

	// Проверяем shutdown
	ctx := context.Background()
	if err := provider.Shutdown(ctx); err != nil {
		t.Errorf("Shutdown failed: %v", err)
	}
}

func TestInitTracerWithEmptyEndpoint(t *testing.T) {
	// Сохраняем оригинального провайдера
	originalProvider := otel.GetTracerProvider()
	defer otel.SetTracerProvider(originalProvider)

	// Пустой endpoint должен вызвать ошибку или использовать значение по умолчанию
	provider, err := InitTracer("", "test-agent")

	// Проверяем, что функция не паникует
	if err != nil && provider != nil {
		t.Logf("Got error: %v", err)
	}
}

func TestTracerCreation(t *testing.T) {
	// Сохраняем оригинального провайдера
	originalProvider := otel.GetTracerProvider()
	defer otel.SetTracerProvider(originalProvider)

	// Инициализируем tracer
	provider, err := InitTracer("localhost:4317", "test-agent")
	if err != nil {
		t.Skipf("Skipping tracer test: %v", err)
	}
	defer provider.Shutdown(context.Background())

	// Создаём span
	ctx := context.Background()
	_, span := Tracer.Start(ctx, "test-operation")
	defer span.End()

	// Проверяем, что span создан
	if span == nil {
		t.Error("Expected non-nil span")
	}
}

func TestInitTracerMultipleTimes(t *testing.T) {
	// Сохраняем оригинального провайдера
	originalProvider := otel.GetTracerProvider()
	defer otel.SetTracerProvider(originalProvider)

	// Инициализируем несколько раз
	for i := 0; i < 3; i++ {
		provider, err := InitTracer("localhost:4317", "test-agent")
		if err != nil {
			t.Skipf("Skipping iteration %d: %v", i, err)
		}
		if provider == nil {
			t.Errorf("Iteration %d: provider is nil", i)
		}
	}
}

func BenchmarkInitTracer(b *testing.B) {
	b.Skip("Skipping benchmark as it requires network connection")

	originalProvider := otel.GetTracerProvider()
	defer otel.SetTracerProvider(originalProvider)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		provider, err := InitTracer("localhost:4317", "bench-agent")
		if err != nil {
			b.Fatal(err)
		}
		provider.Shutdown(context.Background())
	}
}
