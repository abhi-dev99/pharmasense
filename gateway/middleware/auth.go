package middleware

import (
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// In a real app we'd parse the JWT. Here we just ensure a Bearer token exists.
func RequireAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing authorization header"})
			return
		}

		parts := strings.Split(authHeader, " ")
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token format"})
			return
		}

		// Stub JWT decode
		// For the hackathon, if token == "pharmacist", we assign role pharmacist
		role := "user"
		if parts[1] == "pharmacist_token" {
			role = "pharmacist"
		} else if parts[1] == "minister_token" {
			role = "state_minister"
		}

		c.Set("role", role)
		c.Set("user_id", "stub-user-id")
		c.Next()
	}
}
