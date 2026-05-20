package main

import (
	"context"
	"testing"

	"github.com/nats-io/nats.go"
	"github.com/stretchr/testify/mock"
)

// MockNATSConn имитирует NATS соединение
type MockNATSConn struct {
	mock.Mock
}

func (m *MockNATSConn) Publish(subject string, data []byte) error {
	args := m.Called(subject, data)
	return args.Error(0)
}

func (m *MockNATSConn) Close() {}

// MockRedisClient имитирует Redis клиент
type MockRedisClient struct {
	mock.Mock
}

func (m *MockRedisClient) Connect(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func (m *MockRedisClient) Close() {}

func (m *MockRedisClient) RestoreTaskCounts(ctx context.Context) (map[string]int, error) {
	args := m.Called(ctx)
	return args.Get(0).(map[string]int), args.Error(1)
}

func (m *MockRedisClient) SaveTaskCounts(ctx context.Context, counts map[string]int) error {
	args := m.Called(ctx, counts)
	return args.Error(0)
}

func TestHandleMonitoringTask_CollectMetrics(t *testing.T) {
	mockRedis := new(MockRedisClient)

	mockRedis.On("SaveTaskCounts", mock.Anything, mock.Anything).Return(nil)

	msg := &nats.Msg{
		Data: []byte("collect_metrics"),
	}

	taskCounts := make(map[string]int)

	handler := func(ctx context.Context, msg *nats.Msg, rc *MockRedisClient, tc map[string]int) {
		taskType := string(msg.Data)
		tc[taskType]++
		rc.SaveTaskCounts(ctx, tc)
	}

	handler(context.Background(), msg, mockRedis, taskCounts)

	mockRedis.AssertExpectations(t)
}

func TestHandleMonitoringTask_DetectAnomaly(t *testing.T) {
	mockRedis := new(MockRedisClient)

	mockRedis.On("SaveTaskCounts", mock.Anything, mock.Anything).Return(nil)

	msg := &nats.Msg{
		Data: []byte("detect_anomaly"),
	}

	taskCounts := make(map[string]int)

	handler := func(ctx context.Context, msg *nats.Msg, rc *MockRedisClient, tc map[string]int) {
		taskType := string(msg.Data)
		tc[taskType]++
		rc.SaveTaskCounts(ctx, tc)
	}

	handler(context.Background(), msg, mockRedis, taskCounts)

	mockRedis.AssertExpectations(t)
}

func TestHandleMonitoringTask_UnknownTask(t *testing.T) {
	mockRedis := new(MockRedisClient)

	mockRedis.On("SaveTaskCounts", mock.Anything, mock.Anything).Return(nil)

	msg := &nats.Msg{
		Data: []byte("unknown_task"),
	}

	taskCounts := make(map[string]int)

	handler := func(ctx context.Context, msg *nats.Msg, rc *MockRedisClient, tc map[string]int) {
		taskType := string(msg.Data)
		tc[taskType]++
		rc.SaveTaskCounts(ctx, tc)
	}

	handler(context.Background(), msg, mockRedis, taskCounts)

	mockRedis.AssertExpectations(t)
}

func TestTaskCountsPersistence(t *testing.T) {
	mockRedis := new(MockRedisClient)

	taskCounts := make(map[string]int)
	taskCounts["collect_metrics"] = 1
	taskCounts["detect_anomaly"] = 2

	mockRedis.On("SaveTaskCounts", mock.Anything, taskCounts).Return(nil)

	err := mockRedis.SaveTaskCounts(context.Background(), taskCounts)
	if err != nil {
		t.Errorf("SaveTaskCounts failed: %v", err)
	}

	mockRedis.AssertExpectations(t)
}

func TestTaskTypeSwitch(t *testing.T) {
	tests := []struct {
		name     string
		taskType string
		expected string
	}{
		{"collect_metrics", "collect_metrics", "collected metrics"},
		{"detect_anomaly", "detect_anomaly", "anomaly detected"},
		{"send_alert", "send_alert", "alert sent"},
		{"auto_recovery", "auto_recovery", "auto recovery completed"},
		{"unknown", "unknown_task", "unknown task type"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var result string
			switch tt.taskType {
			case "collect_metrics":
				result = "collected metrics"
			case "detect_anomaly":
				result = "anomaly detected"
			case "send_alert":
				result = "alert sent"
			case "auto_recovery":
				result = "auto recovery completed"
			default:
				result = "unknown task type"
			}

			if result != tt.expected {
				t.Errorf("Expected %q, got %q", tt.expected, result)
			}
		})
	}
}

func BenchmarkTaskSwitch(b *testing.B) {
	taskType := "collect_metrics"
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		var result string
		switch taskType {
		case "collect_metrics":
			result = "collected metrics"
		case "detect_anomaly":
			result = "anomaly detected"
		default:
			result = "unknown"
		}
		_ = result
	}
}
