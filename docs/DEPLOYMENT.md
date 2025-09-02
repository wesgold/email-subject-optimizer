# Email Subject Line Optimizer - Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Cloud Deployment](#cloud-deployment)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Monitoring Setup](#monitoring-setup)
7. [Backup and Recovery](#backup-and-recovery)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- Docker 20.10+ and Docker Compose 2.0+
- Git 2.30+
- Python 3.11+ (for local development)
- PostgreSQL client tools (optional)
- Redis client tools (optional)

### Required Accounts/Services
- GitHub account (for CI/CD)
- OpenAI API key or Anthropic API key
- Cloud provider account (AWS/GCP/Azure) for production
- Domain name and SSL certificates for production
- Monitoring services (optional): Sentry, DataDog, New Relic

## Environment Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/email-subject-optimizer.git
cd email-subject-optimizer
```

### 2. Configure Environment Variables
```bash
# Copy example environment file
cp .env.example .env

# Edit environment variables
nano .env
```

Required environment variables:
```env
# Core Settings
APP_ENV=production
SECRET_KEY=your-secure-secret-key-here
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0

# AI Provider (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional Services
SENTRY_DSN=https://...@sentry.io/...
SLACK_WEBHOOK=https://hooks.slack.com/...
```

### 3. Generate Secure Keys
```bash
# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate tracking secret
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

## Docker Deployment

### Local Development
```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment
```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or use deployment script
./scripts/deploy.sh production
```

### Docker Commands Reference
```bash
# Build image
docker build -t email-optimizer:latest .

# Run container
docker run -d \
  --name email-optimizer \
  -p 8000:8000 \
  --env-file .env \
  email-optimizer:latest

# Execute commands in container
docker exec -it email-optimizer bash

# View container logs
docker logs -f email-optimizer

# Clean up
docker system prune -af
```

## Cloud Deployment

### AWS Deployment

#### Using ECS (Elastic Container Service)
```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure

# Create ECR repository
aws ecr create-repository --repository-name email-optimizer

# Build and push image
$(aws ecr get-login --no-include-email)
docker build -t email-optimizer .
docker tag email-optimizer:latest $ECR_URI:latest
docker push $ECR_URI:latest

# Deploy to ECS
aws ecs create-cluster --cluster-name email-optimizer-cluster
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
aws ecs create-service --cli-input-json file://ecs-service.json
```

#### Using EC2
```bash
# SSH to EC2 instance
ssh -i key.pem ubuntu@ec2-instance

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone repository and deploy
git clone https://github.com/yourusername/email-subject-optimizer.git
cd email-subject-optimizer
sudo docker-compose up -d
```

### Google Cloud Platform Deployment

#### Using Cloud Run
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Initialize gcloud
gcloud init

# Build and push to Container Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/email-optimizer

# Deploy to Cloud Run
gcloud run deploy email-optimizer \
  --image gcr.io/$PROJECT_ID/email-optimizer \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Azure Deployment

#### Using Container Instances
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Create resource group
az group create --name email-optimizer-rg --location eastus

# Create container registry
az acr create --resource-group email-optimizer-rg \
  --name emailoptimizeracr --sku Basic

# Build and push image
az acr build --registry emailoptimizeracr \
  --image email-optimizer:latest .

# Deploy container
az container create \
  --resource-group email-optimizer-rg \
  --name email-optimizer \
  --image emailoptimizeracr.azurecr.io/email-optimizer:latest \
  --dns-name-label email-optimizer \
  --ports 8000
```

### Kubernetes Deployment
```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: email-optimizer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: email-optimizer
  template:
    metadata:
      labels:
        app: email-optimizer
    spec:
      containers:
      - name: app
        image: email-optimizer:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: email-optimizer-secrets
              key: database-url
```

Deploy to Kubernetes:
```bash
# Create secrets
kubectl create secret generic email-optimizer-secrets \
  --from-env-file=.env

# Apply deployment
kubectl apply -f k8s-deployment.yaml

# Expose service
kubectl expose deployment email-optimizer \
  --type=LoadBalancer --port=80 --target-port=8000
```

## CI/CD Pipeline

### GitHub Actions Setup

1. Configure repository secrets in GitHub:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `SLACK_WEBHOOK`
   - `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`
   - `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`

2. Push to trigger deployment:
```bash
# Deploy to staging
git push origin staging

# Deploy to production
git push origin main
```

3. Manual deployment:
   - Go to Actions tab in GitHub
   - Select "Deploy Email Optimizer" workflow
   - Click "Run workflow"
   - Select environment and run

### GitLab CI/CD
```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  script:
    - docker-compose -f docker-compose.test.yml up --abort-on-container-exit

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  script:
    - ./scripts/deploy.sh production $CI_COMMIT_SHA
  only:
    - main
```

## Monitoring Setup

### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'email-optimizer'
    static_configs:
      - targets: ['app:8000']
    metrics_path: /metrics
```

### Grafana Dashboard Setup
1. Access Grafana at http://localhost:3001
2. Login with admin/admin (change password)
3. Add Prometheus data source:
   - URL: http://prometheus:9090
4. Import dashboard from `grafana/dashboards/email-optimizer.json`

### Health Checks
```bash
# Run health check script
./scripts/health_check.sh production

# Manual health check
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics
```

### Log Aggregation
```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs app

# Follow logs in real-time
docker-compose logs -f app

# Export logs
docker-compose logs > logs_$(date +%Y%m%d).txt
```

## Backup and Recovery

### Automated Backups
```bash
# Run backup script
./scripts/backup.sh

# Schedule daily backups (crontab)
0 2 * * * /opt/email-optimizer/scripts/backup.sh
```

### Manual Backup
```bash
# Backup database
docker exec email-optimizer-postgres \
  pg_dump -U postgres email_optimizer | gzip > backup.sql.gz

# Backup Redis
docker exec email-optimizer-redis redis-cli BGSAVE
docker cp email-optimizer-redis:/data/dump.rdb redis_backup.rdb

# Backup application data
tar -czf app_data_backup.tar.gz data/ logs/
```

### Recovery Process
```bash
# Restore database
gunzip -c backup.sql.gz | docker exec -i email-optimizer-postgres \
  psql -U postgres email_optimizer

# Restore Redis
docker cp redis_backup.rdb email-optimizer-redis:/data/dump.rdb
docker restart email-optimizer-redis

# Restore application data
tar -xzf app_data_backup.tar.gz
```

### Rollback Procedure
```bash
# Automatic rollback to previous version
./scripts/rollback.sh

# Manual rollback to specific version
./scripts/rollback.sh v1.2.3

# Emergency rollback with database restore
RESTORE_DATABASE=true ./scripts/rollback.sh
```

## Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check logs
docker-compose logs app

# Verify environment variables
docker-compose config

# Check port availability
netstat -tulpn | grep 8000
```

#### Database Connection Issues
```bash
# Test database connection
docker exec email-optimizer-postgres pg_isready

# Check database logs
docker-compose logs postgres

# Verify connection string
docker exec email-optimizer-app python -c "
from sqlalchemy import create_engine
engine = create_engine('$DATABASE_URL')
engine.connect()
"
```

#### Redis Connection Issues
```bash
# Test Redis connection
docker exec email-optimizer-redis redis-cli ping

# Check Redis logs
docker-compose logs redis

# Clear Redis cache
docker exec email-optimizer-redis redis-cli FLUSHALL
```

#### High Memory Usage
```bash
# Check memory usage
docker stats

# Limit container memory
docker-compose down
# Edit docker-compose.yml to add memory limits
docker-compose up -d
```

#### SSL Certificate Issues
```bash
# Generate self-signed certificate (development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Use Let's Encrypt (production)
docker run -it --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d yourdomain.com
```

### Performance Optimization

#### Database Optimization
```sql
-- Add indexes
CREATE INDEX idx_subjects_created_at ON subjects(created_at);
CREATE INDEX idx_analytics_subject_id ON email_analytics(subject_id);

-- Vacuum and analyze
VACUUM ANALYZE;
```

#### Redis Optimization
```bash
# Configure max memory
docker exec email-optimizer-redis redis-cli CONFIG SET maxmemory 1gb
docker exec email-optimizer-redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

#### Application Optimization
```python
# Increase worker connections
WORKER_CONNECTIONS=2000

# Enable connection pooling
DATABASE_POOL_SIZE=50
REDIS_MAX_CONNECTIONS=100
```

### Emergency Procedures

#### Complete System Recovery
```bash
# 1. Stop all services
docker-compose down

# 2. Restore from backup
./scripts/backup.sh restore backup_20240101_120000

# 3. Start services
docker-compose up -d

# 4. Verify health
./scripts/health_check.sh
```

#### Data Corruption Recovery
```bash
# 1. Stop application
docker-compose stop app

# 2. Backup corrupted data
docker exec email-optimizer-postgres pg_dump email_optimizer > corrupted_backup.sql

# 3. Restore from last known good backup
./scripts/rollback.sh

# 4. Verify and restart
./scripts/health_check.sh
docker-compose start app
```

## Security Best Practices

1. **Environment Variables**: Never commit `.env` files to git
2. **Secrets Management**: Use cloud provider secret managers
3. **Network Security**: Configure firewalls and security groups
4. **SSL/TLS**: Always use HTTPS in production
5. **Updates**: Regularly update dependencies and base images
6. **Monitoring**: Set up alerts for suspicious activity
7. **Backups**: Test backup restoration regularly
8. **Access Control**: Use principle of least privilege

## Support and Resources

- Documentation: `/docs`
- API Reference: `/docs/API.md`
- Monitoring Guide: `/docs/MONITORING.md`
- Troubleshooting: `/docs/TROUBLESHOOTING.md`
- GitHub Issues: https://github.com/yourusername/email-subject-optimizer/issues

For urgent production issues, contact the on-call engineer via PagerDuty or Slack #email-optimizer-alerts channel.