#!/bin/bash

# Test Docker images before Kubernetes deployment

echo "🐳 Testing Docker Images..."

# Test 1: Build backend image
echo ""
echo "🔨 Building backend image..."
docker build -t candidate-finder-backend:test ./backend

if [ $? -eq 0 ]; then
    echo "✅ Backend image built successfully"
else
    echo "❌ Backend image build failed"
    exit 1
fi

# Test 2: Build frontend image
echo ""
echo "🔨 Building frontend image..."
docker build -t candidate-finder-frontend:test ./frontend

if [ $? -eq 0 ]; then
    echo "✅ Frontend image built successfully"
else
    echo "❌ Frontend image build failed"
    exit 1
fi

# Test 3: Run backend container
echo ""
echo "🚀 Testing backend container..."
docker run -d --name backend-test \
    --env-file .env \
    -p 8001:8000 \
    candidate-finder-backend:test

# Wait for container to start
sleep 5

# Test health endpoint
echo "🔍 Testing backend container health..."
curl -f http://localhost:8001/health && echo "✅ Backend container working" || echo "❌ Backend container failed"

# Test 4: Run frontend container
echo ""
echo "🚀 Testing frontend container..."
docker run -d --name frontend-test \
    -p 8002:80 \
    candidate-finder-frontend:test

sleep 3

# Test frontend
echo "🔍 Testing frontend container..."
curl -f http://localhost:8002/health && echo "✅ Frontend container working" || echo "❌ Frontend container failed"

echo ""
echo "🌐 Test URLs:"
echo "  - Backend: http://localhost:8001/health"
echo "  - Backend API Docs: http://localhost:8001/docs"
echo "  - Frontend: http://localhost:8002"
echo ""
echo "Press any key to cleanup containers..."
read -n 1

# Cleanup
echo ""
echo "🧹 Cleaning up test containers..."
docker stop backend-test frontend-test
docker rm backend-test frontend-test

echo "✅ Docker testing completed"
