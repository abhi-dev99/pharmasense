package middleware

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

func RateLimit(rdb *redis.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetString("user_id")
		if userID == "" {
			userID = c.ClientIP()
		}

		// 60-second window
		window := time.Now().Unix() / 60
		key := fmt.Sprintf("rl:%s:%s:%d", userID, c.Request.URL.Path, window)

		ctx := context.Background()
		count, err := rdb.Incr(ctx, key).Result()
		if err != nil {
			c.Next() // fail open if Redis is down
			return
		}

		if count == 1 {
			rdb.Expire(ctx, key, 70*time.Second)
		}

		limit := int64(100) // Default limit
		role := c.GetString("role")
		if role == "state_minister" {
			limit = 1000
		} else if role == "pharmacist" {
			limit = 200
		}

		if count > limit {
			c.Header("Retry-After", "60")
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{"error": "rate limit exceeded"})
			return
		}

		c.Next()
	}
}
