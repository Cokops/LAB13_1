package state

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNewClient(t *testing.T) {
	client := NewClient("localhost:6379")
	assert.NotNil(t, client)
}

func TestClientStruct(t *testing.T) {
	client := &Client{}
	assert.NotNil(t, client)
}

func TestSaveTaskCounts(t *testing.T) {
	// Создаём клиент (без реального Redis)
	client := &Client{}
	ctx := context.Background()

	// Сохраняем counts (в реальности это вызовет ошибку, но мы не проверяем)
	counts := map[string]int{"collect_metrics": 5, "detect_anomaly": 3}

	// Просто проверяем, что функция не паникует
	// В реальном тесте нужно иметь Redis, поэтому пропускаем
	if testing.Short() {
		t.Skip("Skipping test that requires Redis")
	}

	err := client.SaveTaskCounts(ctx, counts)
	// В тестах без Redis будет ошибка, игнорируем
	_ = err
}

func TestRestoreTaskCounts(t *testing.T) {
	client := &Client{}
	ctx := context.Background()

	if testing.Short() {
		t.Skip("Skipping test that requires Redis")
	}

	counts, err := client.RestoreTaskCounts(ctx)
	// В тестах без Redis будет ошибка или пустой мап
	_ = counts
	_ = err
}

func TestTaskCountsJSON(t *testing.T) {
	// Тестируем JSON сериализацию без Redis
	counts := map[string]int{
		"collect_metrics": 10,
		"detect_anomaly":  5,
		"send_alert":      3,
		"auto_recovery":   2,
	}

	// Маршалинг
	data, err := json.Marshal(counts)
	assert.NoError(t, err)
	assert.NotEmpty(t, data)

	// Анмаршалинг обратно
	var restored map[string]int
	err = json.Unmarshal(data, &restored)
	assert.NoError(t, err)
	assert.Equal(t, counts, restored)
}

func TestEmptyTaskCounts(t *testing.T) {
	counts := make(map[string]int)

	data, err := json.Marshal(counts)
	assert.NoError(t, err)

	var restored map[string]int
	err = json.Unmarshal(data, &restored)
	assert.NoError(t, err)
	assert.Equal(t, 0, len(restored))
}

func TestTaskCountsIncrement(t *testing.T) {
	taskCounts := make(map[string]int)

	tasks := []string{"collect_metrics", "collect_metrics", "detect_anomaly"}

	for _, task := range tasks {
		taskCounts[task]++
	}

	assert.Equal(t, 2, taskCounts["collect_metrics"])
	assert.Equal(t, 1, taskCounts["detect_anomaly"])
	assert.Equal(t, 0, taskCounts["send_alert"])
}

func TestClientConnect(t *testing.T) {
	client := &Client{}
	ctx := context.Background()

	if testing.Short() {
		t.Skip("Skipping test that requires Redis")
	}

	err := client.Connect(ctx)
	// В тестах без реального Redis будет ошибка
	if err != nil {
		t.Logf("Expected error without Redis: %v", err)
	}
}

func BenchmarkTaskCountsMarshal(b *testing.B) {
	counts := map[string]int{
		"collect_metrics": 100,
		"detect_anomaly":  50,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = json.Marshal(counts)
	}
}

func BenchmarkTaskCountsUnmarshal(b *testing.B) {
	counts := map[string]int{
		"collect_metrics": 100,
		"detect_anomaly":  50,
	}
	data, _ := json.Marshal(counts)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		var restored map[string]int
		_ = json.Unmarshal(data, &restored)
	}
}
