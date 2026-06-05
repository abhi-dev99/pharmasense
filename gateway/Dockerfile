# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod go.sum* ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /gateway ./main.go

# Run stage
FROM alpine:latest

WORKDIR /app

COPY --from=builder /gateway /app/gateway

EXPOSE 8080

CMD ["/app/gateway"]
