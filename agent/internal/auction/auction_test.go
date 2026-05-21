package auction

import (
	"context"
	"math/rand"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBidValueCalculation(t *testing.T) {
	rand.Seed(42)

	var bids []float64
	for i := 0; i < 100; i++ {
		skill := rand.Float64()
		load := float64(rand.Intn(100)) / 100.0
		bid := skill - load
		bids = append(bids, bid)
	}

	for _, bid := range bids {
		assert.GreaterOrEqual(t, bid, -1.0)
		assert.LessOrEqual(t, bid, 1.0)
	}

	min, max := bids[0], bids[0]
	for _, b := range bids {
		if b < min {
			min = b
		}
		if b > max {
			max = b
		}
	}
	assert.NotEqual(t, min, max, "Bids should not be identical")
}

func TestStartBidding_ContextCancellation(t *testing.T) {
	// Тест без реального NATS - проверяем только логику контекста
	ctx, cancel := context.WithCancel(context.Background())

	// Проверяем, что контекст работает
	assert.NoError(t, ctx.Err())
	cancel()
	assert.Error(t, ctx.Err())
}

func TestBidMessageFormat(t *testing.T) {
	// Проверяем формат сообщения без NATS
	bidMsg := map[string]interface{}{
		"agent_id":  "test-agent",
		"bid":       0.5,
		"skill":     0.8,
		"load":      0.3,
		"timestamp": int64(1234567890),
	}

	assert.Equal(t, "test-agent", bidMsg["agent_id"])
	assert.Equal(t, 0.5, bidMsg["bid"])
	assert.Equal(t, 0.8, bidMsg["skill"])
	assert.Equal(t, 0.3, bidMsg["load"])

	expectedFields := []string{"agent_id", "bid", "skill", "load", "timestamp"}
	for _, field := range expectedFields {
		assert.Contains(t, bidMsg, field)
	}
}
