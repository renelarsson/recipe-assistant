#!/bin/bash
# Recipe Assistant EC2 Deployment Script

set -e  # Exit on error

# 1. SSH into your EC2 instance (manual step)
# 2. Install Docker and Docker Compose
echo "Installing Docker and Docker Compose..."
sudo apt update
sudo apt install -y docker.io docker-compose
sudo apt install -y make
sudo usermod -aG docker $USER
#newgrp docker

# 3. Change to the project directory (if not already there) 
cd $(dirname "$0")/..

# 4. Build and start all services and wait for readiness using Makefile
echo "Building and starting all services and waiting for readiness..."
make up wait-postgres wait-elasticsearch wait-api

# 5. Set correct permissions for Loki log storage
echo "Setting permissions for Loki log storage..."
sudo mkdir -p ./grafana/loki-data/chunks
sudo chmod -R 777 ./grafana/loki-data

# 6. Initialize/reset the PostgreSQL database schema using Makefile
echo "Initializing the PostgreSQL database schema (make db-init)..."
make db-init

# 7. (Optional) Verify database tables exist
echo "Verifying database tables..."
docker compose exec postgres psql -U $POSTGRES_USER -d recipe_assistant -c '\dt'

# 8. Restart app and Grafana containers
echo "Restarting app and Grafana containers..."
make restart

# 9. Ingest recipe data into Elasticsearch using Makefile
echo "Ingesting recipe data into Elasticsearch (make ingest)..."
make ingest

# 10. Automated smoke test: POST a sample question to the API to verify end-to-end functionality
echo "Running smoke test: POST /question to verify API end-to-end..."
SMOKE_TEST_RESPONSE=$(curl -s -X POST http://localhost:5000/question \
	-H "Content-Type: application/json" \
	-d '{"question": "What can I cook with chicken and rice?"}')
echo "Smoke test response: $SMOKE_TEST_RESPONSE"
if echo "$SMOKE_TEST_RESPONSE" | grep -q 'answer'; then
	echo "Smoke test passed: API returned an answer."
else
	echo "Smoke test failed: API did not return a valid answer." >&2
	exit 1
fi

echo "Deployment complete!"
echo "Visit http://<ec2-public-ip>:5000 for the API and http://<ec2-public-ip>:3000 for Grafana."
echo "(Replace <ec2-public-ip> with your instance's public IP address.)"
