package alert

import (
	"bytes"
	"context"
	"os"
	"testing"
)

func TestSendWithStdout(t *testing.T) {
	// Сохраняем оригинальный stdout
	oldStdout := os.Stdout
	defer func() { os.Stdout = oldStdout }()

	// Создаем pipe для перехвата
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	os.Stdout = w

	message := "Test anomaly detected"
	result := Send(context.Background(), message)

	// Восстанавливаем stdout и читаем вывод
	w.Close()
	var buf bytes.Buffer
	_, err = buf.ReadFrom(r)
	if err != nil {
		t.Fatal(err)
	}
	printed := buf.String()
	os.Stdout = oldStdout

	// Проверяем результат функции
	expectedResult := "alert sent: " + message
	if result != expectedResult {
		t.Errorf("Expected result %q, got %q", expectedResult, result)
	}

	// Проверяем, что было напечатано в stdout
	expectedPrint := "[ALERT] " + message
	if !contains(printed, expectedPrint) {
		t.Errorf("Expected output to contain %q, got %q", expectedPrint, printed)
	}
}

func contains(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func TestSendSimple(t *testing.T) {
	// Простой тест без перехвата stdout
	message := "Test message"
	result := Send(context.Background(), message)

	expected := "alert sent: " + message
	if result != expected {
		t.Errorf("Expected %q, got %q", expected, result)
	}
}
