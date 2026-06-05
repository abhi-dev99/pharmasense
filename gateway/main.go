package main

import (
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"pharmasense/gateway/middleware"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

func main() {
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379/0"
	}

	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		log.Fatalf("Invalid REDIS_URL: %v", err)
	}
	rdb := redis.NewClient(opt)

	r := gin.Default()
	r.Use(middleware.JSONLogger())

	// Healthcheck
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok", "service": "gateway"})
	})

	api := r.Group("/api/v1")
	// Use Auth and RateLimit middleware
	api.Use(middleware.RequireAuth())
	api.Use(middleware.RateLimit(rdb))

	// Proxy to FastAPI backend
	backendURL, err := url.Parse("http://localhost:8000")
	if err != nil {
		log.Fatalf("Invalid backend URL: %v", err)
	}
	proxy := httputil.NewSingleHostReverseProxy(backendURL)

	// In a real app we would map exact routes. Here we proxy all /api/v1 
	// after middleware verification
	api.Any("/*path", func(c *gin.Context) {
		proxy.ServeHTTP(c.Writer, c.Request)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("Gateway running on port %s", port)
	r.Run(":" + port)
}
