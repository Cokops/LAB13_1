package alert

import (
	"bytes"
	"context"
	"os"
	"strings"
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

	// Проверяем результат функции (содержит ID и сообщение)
	if !strings.Contains(result, "alert sent") {
		t.Errorf("Expected result to contain 'alert sent', got %q", result)
	}
	if !strings.Contains(result, message) {
		t.Errorf("Expected result to contain %q, got %q", message, result)
	}

	// Проверяем, что было напечатано в stdout
	if !strings.Contains(printed, "[ALERT]") {
		t.Errorf("Expected output to contain '[ALERT]', got %q", printed)
	}
	if !strings.Contains(printed, message) {
		t.Errorf("Expected output to contain %q, got %q", message, printed)
	}
}

func TestSendSimple(t *testing.T) {
	// Простой тест без перехвата stdout
	message := "Test message"
	result := Send(context.Background(), message)

	if !strings.Contains(result, "alert sent") {
		t.Errorf("Expected result to contain 'alert sent', got %q", result)
	}
	if !strings.Contains(result, message) {
		t.Errorf("Expected result to contain %q, got %q", message, result)
	}
}
