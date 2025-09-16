#!/bin/bash

# API endpoint testing script

API_BASE=${1:-"http://localhost:8000/api"}
echo "🧪 Testing API endpoints at: $API_BASE"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_endpoint() {
    local method=$1
    local endpoint=$2
    local expected_status=${3:-200}
    local data=$4
    
    echo -n "Testing $method $endpoint... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "%{http_code}" -o /dev/null "$API_BASE$endpoint")
    elif [ "$method" = "POST" ] && [ -n "$data" ]; then
        response=$(curl -s -w "%{http_code}" -o /dev/null -X POST -H "Content-Type: application/json" -d "$data" "$API_BASE$endpoint")
    else
        response=$(curl -s -w "%{http_code}" -o /dev/null -X $method "$API_BASE$endpoint")
    fi
    
    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✅ $response${NC}"
    else
        echo -e "${RED}❌ $response (expected $expected_status)${NC}"
    fi
}

echo ""
echo -e "${YELLOW}🔍 Testing API Health...${NC}"
test_endpoint "GET" "/../health" 200

echo ""
echo -e "${YELLOW}📊 Testing GitHub endpoints...${NC}"
test_endpoint "GET" "/collection" 200
test_endpoint "GET" "/filter_by_skill?skill=python&max_results=10" 200

echo ""
echo -e "${YELLOW}💼 Testing Job endpoints...${NC}"
# Test job creation with sample data
job_data='{"jd": "Looking for a Python developer with FastAPI experience", "k": 5}'
test_endpoint "POST" "/job" 200 "$job_data"

echo ""
echo -e "${YELLOW}🧹 Testing Database operations...${NC}"
test_endpoint "POST" "/clear_database" 200

echo ""
echo -e "${GREEN}✅ API testing completed!${NC}"

# Interactive testing option
echo ""
echo -e "${YELLOW}💡 Want to test interactively?${NC}"
echo "1. Open API docs: $API_BASE/../docs"
echo "2. Test with curl:"
echo "   curl -X GET $API_BASE/../health"
echo "   curl -X GET $API_BASE/collection"
echo "3. Test frontend: ${API_BASE/\/api/}"
