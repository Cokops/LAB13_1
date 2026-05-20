package auction

import (
	"context"
	"encoding/json"
	"math/rand"
	"time"

	"github.com/nats-io/nats.go"
)

// StartBidding starts publishing bids to auction
func StartBidding(ctx context.Context, natsConn *nats.Conn, agentID string) {
	// Random ticker between 5-15 seconds
	ticker := time.NewTicker(time.Duration(5+rand.Intn(10)) * time.Second)
	go func() {
		for {
			select {
			case <-ticker.C:
				// Simulate skill and load
				skill := rand.Float64() // 0.0 - 1.0
				load := float64(rand.Intn(100)) / 100.0
				bid := skill - load // Simple bid strategy

				bidMsg := map[string]interface{}{
					"agent_id":  agentID,
					"bid":       bid,
					"skill":     skill,
					"load":      load,
					"timestamp": time.Now().Unix(),
				}

				data, _ := json.Marshal(bidMsg)
				natsConn.Publish("tasks.auction.bids", data)

			case <-ctx.Done():
				ticker.Stop()
				return
			}
		}
	}()
}
