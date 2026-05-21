package recovery

import (
	"context"
	"strings"
	"testing"
)

func TestPerform(t *testing.T) {
	result := Perform(context.Background())

	// Проверяем, что результат содержит ожидаемый текст
	if !strings.Contains(result, "auto recovery completed") {
		t.Errorf("Expected result to contain 'auto recovery completed', got %q", result)
	}
}

func TestPerformMultiple(t *testing.T) {
	// Проверяем, что функция всегда возвращает результат с "auto recovery completed"
	ctx := context.Background()

	for i := 0; i < 10; i++ {
		result := Perform(ctx)
		if !strings.Contains(result, "auto recovery completed") {
			t.Errorf("Iteration %d: expected result to contain 'auto recovery completed', got %q", i, result)
		}
	}
}

func TestPerformWithContext(t *testing.T) {
	ctx := context.Background()
	result := Perform(ctx)

	if result == "" {
		t.Error("Expected non-empty result, got empty string")
	}

	if !strings.Contains(result, "auto recovery completed") {
		t.Errorf("Result should contain 'auto recovery completed', got %q", result)
	}
}

func BenchmarkPerform(b *testing.B) {
	ctx := context.Background()
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		Perform(ctx)
	}
}
