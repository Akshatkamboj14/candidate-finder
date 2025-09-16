#!/bin/bash

# Complete testing workflow

echo "🚀 Candidate Finder - Complete Testing Workflow"
echo "=================================================="

# Make all scripts executable
chmod +x test-local.sh test-docker.sh test-k8s.sh test-api.sh

echo ""
echo "Choose testing mode:"
echo "1. Local testing (FastAPI + React)"
echo "2. Docker testing (Build and test containers)"
echo "3. Kubernetes testing (Full deployment test)"
echo "4. API testing only"
echo "5. Complete workflow (all tests)"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        echo "🏠 Running local tests..."
        ./test-local.sh
        ;;
    2)
        echo "🐳 Running Docker tests..."
        ./test-docker.sh
        ;;
    3)
        echo "☸️  Running Kubernetes tests..."
        ./test-k8s.sh
        ;;
    4)
        echo "🔗 Running API tests..."
        echo "Enter API base URL (or press Enter for default):"
        read -p "API URL [http://localhost:8000/api]: " api_url
        api_url=${api_url:-"http://localhost:8000/api"}
        ./test-api.sh "$api_url"
        ;;
    5)
        echo "🎯 Running complete workflow..."
        echo ""
        echo "Step 1: Local testing..."
        ./test-local.sh
        echo ""
        echo "Step 2: Docker testing..."
        ./test-docker.sh
        echo ""
        echo "Step 3: Kubernetes testing..."
        ./test-k8s.sh
        echo ""
        echo "🎉 Complete workflow finished!"
        ;;
    *)
        echo "Invalid choice. Please run again with option 1-5."
        exit 1
        ;;
esac

echo ""
echo "✅ Testing completed!"
