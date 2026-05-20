package recovery

import (
	"context"
	"testing"
)

func TestPerform(t *testing.T) {
	result := Perform(context.Background())

	// Проверяем, что результат содержит ожидаемый текст
	expected := "auto recovery completed"
	if result != expected {
		t.Errorf("Expected %q, got %q", expected, result)
	}
}

func TestPerformMultiple(t *testing.T) {
	// Проверяем, что функция всегда возвращает одинаковый результат
	ctx := context.Background()

	expected := "auto recovery completed"
	for i := 0; i < 10; i++ {
		result := Perform(ctx)
		if result != expected {
			t.Errorf("Iteration %d: expected %q, got %q", i, expected, result)
		}
	}
}

func TestPerformWithContext(t *testing.T) {
	ctx := context.Background()
	result := Perform(ctx)

	if result == "" {
		t.Error("Expected non-empty result, got empty string")
	}

	if len(result) < 10 {
		t.Errorf("Result too short: %q", result)
	}
}

func BenchmarkPerform(b *testing.B) {
	ctx := context.Background()
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		Perform(ctx)
	}
}
