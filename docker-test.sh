#!/bin/bash

# Docker Test Script for Secure P2P Messenger
# This script tests the Docker deployment

echo "🐳 Testing Docker Deployment for Secure P2P Messenger"
echo "======================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Build the Docker image
echo "📦 Building Docker image..."
docker build -t secure-messenger:latest .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed"
    exit 1
fi

echo "✅ Docker image built successfully"

# Run the container
echo "🚀 Starting container..."
docker run -d --name messenger-test -p 8080:8080 -p 8765:8765 secure-messenger:latest

if [ $? -ne 0 ]; then
    echo "❌ Failed to start container"
    exit 1
fi

echo "✅ Container started successfully"

# Wait for the application to start
echo "⏳ Waiting for application to start..."
sleep 10

# Test if the application is responding
if curl -f http://localhost:8080/ > /dev/null 2>&1; then
    echo "✅ Application is responding on http://localhost:8080"
else
    echo "❌ Application is not responding"
    docker stop messenger-test
    docker rm messenger-test
    exit 1
fi

# Cleanup
echo "🧹 Cleaning up..."
docker stop messenger-test
docker rm messenger-test

echo "✅ Docker test completed successfully!"
echo ""
echo "🎉 You can now run the application with:"
echo "   docker-compose up --build"
