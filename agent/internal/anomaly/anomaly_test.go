package anomaly

import (
	"context"
	"testing"
)

func TestDetect_Normal(t *testing.T) {
	metricsData := "collected: CPU=50.00% Memory=40.00% Disk=30.00%"
	result := Detect(context.Background(), metricsData)

	if contains(result, "ANOMALY") {
		t.Errorf("Expected no anomaly, got: %s", result)
	}
}

func TestDetect_AnomalyCPU(t *testing.T) {
	metricsData := "collected: CPU=95.00% Memory=40.00% Disk=30.00%"
	result := Detect(context.Background(), metricsData)

	if !contains(result, "ANOMALY", "high CPU usage") {
		t.Errorf("Expected CPU anomaly, got: %s", result)
	}
}

func TestDetect_AnomalyMemory(t *testing.T) {
	metricsData := "collected: CPU=40.00% Memory=95.00% Disk=30.00%"
	result := Detect(context.Background(), metricsData)

	if !contains(result, "ANOMALY", "high memory usage") {
		t.Errorf("Expected memory anomaly, got: %s", result)
	}
}

func TestDetect_AnomalyDisk(t *testing.T) {
	metricsData := "collected: CPU=40.00% Memory=40.00% Disk=95.00%"
	result := Detect(context.Background(), metricsData)

	if !contains(result, "ANOMALY", "high disk usage") {
		t.Errorf("Expected disk anomaly, got: %s", result)
	}
}

func TestDetect_MultipleAnomalies(t *testing.T) {
	metricsData := "collected: CPU=95.00% Memory=95.00% Disk=30.00%"
	result := Detect(context.Background(), metricsData)

	if !contains(result, "ANOMALY", "high CPU usage", "high memory usage") {
		t.Errorf("Expected multiple anomalies, got: %s", result)
	}
}

// contains проверяет наличие всех подстрок
func contains(s string, substrs ...string) bool {
	for _, substr := range substrs {
		if !containsOne(s, substr) {
			return false
		}
	}
	return true
}

// containsOne проверяет наличие одной подстроки
func containsOne(s, substr string) bool {
	n := len(substr)
	for i := 0; i <= len(s)-n; i++ {
		if s[i:i+n] == substr {
			return true
		}
	}
	return false
}

func BenchmarkDetect(b *testing.B) {
	metricsData := "collected: CPU=50.00% Memory=40.00% Disk=30.00%"
	ctx := context.Background()
	b.ResetTimer()
	
	for i := 0; i < b.N; i++ {
		Detect(ctx, metricsData)
	}
}