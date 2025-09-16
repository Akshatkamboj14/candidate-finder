#!/bin/bash

# Local testing script for candidate-finder

echo "🧪 Testing Candidate Finder Application Locally..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Please create one first."
    exit 1
fi

echo "✅ .env file found"

# Test 1: Check Python dependencies
echo ""
echo "📦 Testing Python dependencies..."
cd backend
python -c "
import sys
sys.path.append('.')
try:
    from app.main import app
    print('✅ FastAPI app imports successfully')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

# Test 2: Check environment variables
echo ""
echo "🔧 Testing environment variables..."
python -c "
import os
from dotenv import load_dotenv
load_dotenv('../.env')

required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'GITHUB_TOKEN', 'BEDROCK_REGION']
missing = []

for var in required_vars:
    if not os.getenv(var):
        missing.append(var)

if missing:
    print(f'❌ Missing environment variables: {missing}')
else:
    print('✅ All required environment variables present')
"

# Test 3: Start server and test endpoints
echo ""
echo "🚀 Starting FastAPI server for testing..."
echo "Server will start on http://localhost:8000"
echo "Press Ctrl+C to stop the server when done testing"
echo ""

# Start server in background
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Test health endpoint
echo "🔍 Testing health endpoint..."
curl -f http://localhost:8000/health && echo "✅ Health endpoint working" || echo "❌ Health endpoint failed"

echo ""
echo "🌐 You can now test the application:"
echo "  - Health: http://localhost:8000/health"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Frontend: http://localhost:3000 (if React is running)"
echo ""
echo "Press any key to stop the server..."
read -n 1

# Kill the server
kill $SERVER_PID
echo "✅ Server stopped"
