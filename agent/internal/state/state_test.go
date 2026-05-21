package state

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNewClient(t *testing.T) {
	client := NewClient("localhost:6379")
	assert.NotNil(t, client)
}

func TestClientStruct(t *testing.T) {
	client := &Client{rdb: nil}
	assert.NotNil(t, client)
}

func TestSaveTaskCounts(t *testing.T) {
	// Пропускаем тест требующий Redis
	t.Skip("Skipping test that requires Redis connection")
}

func TestRestoreTaskCounts(t *testing.T) {
	// Пропускаем тест требующий Redis
	t.Skip("Skipping test that requires Redis connection")
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
	// Пропускаем тест требующий Redis
	t.Skip("Skipping test that requires Redis connection")
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
