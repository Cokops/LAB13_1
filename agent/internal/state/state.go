package state

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
)

// Client wraps Redis connection
type Client struct {
	rdb *redis.Client
}

// NewClient creates new Redis client
func NewClient(addr string) *Client {
	rdb := redis.NewClient(&redis.Options{
		Addr: addr,
	})
	return &Client{rdb: rdb}
}

// Connect establishes connection to Redis
func (c *Client) Connect(ctx context.Context) error {
	return c.rdb.Ping(ctx).Err()
}

// Close closes Redis connection
func (c *Client) Close() {
	c.rdb.Close()
}

// SaveTaskCounts saves task counts to Redis
func (c *Client) SaveTaskCounts(ctx context.Context, counts map[string]int) error {
	data, err := json.Marshal(counts)
	if err != nil {
		return err
	}
	return c.rdb.Set(ctx, "agent:task_counts", data, 0).Err()
}

// RestoreTaskCounts restores task counts from Redis
func (c *Client) RestoreTaskCounts(ctx context.Context) (map[string]int, error) {
	var counts = map[string]int{
		"collect_metrics": 0,
		"detect_anomaly":  0,
		"send_alert":      0,
		"auto_recovery":   0,
	}

	val, err := c.rdb.Get(ctx, "agent:task_counts").Result()
	if err == redis.Nil {
		// No saved state, return default
		return counts, nil
	} else if err != nil {
		return nil, fmt.Errorf("failed to get task counts: %v", err)
	}

	if err := json.Unmarshal([]byte(val), &counts); err != nil {
		return nil, fmt.Errorf("failed to unmarshal task counts: %v", err)
	}

	return counts, nil
}