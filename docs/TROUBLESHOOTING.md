# Email Subject Line Optimizer - Troubleshooting Guide

## Common Issues and Solutions

### Application Won't Start

#### Issue: Port Already in Use
**Error:** `[ERROR] bind(): Address already in use`

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill the process
kill -9 <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows

# Or use a different port
docker-compose up -d -e PORT=8001
```

#### Issue: Environment Variables Not Loading
**Error:** `KeyError: 'OPENAI_API_KEY'`

**Solution:**
```bash
# Check if .env file exists
ls -la .env

# Copy from example if missing
cp .env.example .env

# Verify environment variables
docker-compose config

# Export manually if needed
export OPENAI_API_KEY="your-key-here"
docker-compose up -d
```

#### Issue: Docker Daemon Not Running
**Error:** `Cannot connect to the Docker daemon`

**Solution:**
```bash
# Start Docker daemon
sudo systemctl start docker  # Linux
open -a Docker  # Mac

# Verify Docker is running
docker info
```

### Database Connection Issues

#### Issue: Cannot Connect to PostgreSQL
**Error:** `psycopg2.OperationalError: could not connect to server`

**Solution:**
```bash
# Check if PostgreSQL container is running
docker ps | grep postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection
docker exec -it email-optimizer-postgres psql -U postgres -c "SELECT 1"

# Reset database
docker-compose down -v
docker-compose up -d postgres
sleep 10
docker-compose up -d app
```

#### Issue: Database Migrations Failed
**Error:** `alembic.util.exc.CommandError`

**Solution:**
```bash
# Check current migration status
docker-compose exec app alembic current

# Revert to previous migration
docker-compose exec app alembic downgrade -1

# Apply migrations manually
docker-compose exec app alembic upgrade head

# Reset migrations (CAUTION: Data loss)
docker-compose exec postgres psql -U postgres -d email_optimizer -c "DROP TABLE alembic_version"
docker-compose exec app alembic stamp head
```

#### Issue: Connection Pool Exhausted
**Error:** `sqlalchemy.exc.TimeoutError: QueuePool limit exceeded`

**Solution:**
```python
# Increase pool size in production.py
DATABASE_POOL_SIZE = 50  # Increase from 20
DATABASE_MAX_OVERFLOW = 20  # Increase from 10

# Or in environment variables
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=20
```

### Redis Connection Issues

#### Issue: Redis Connection Refused
**Error:** `redis.exceptions.ConnectionError: Connection refused`

**Solution:**
```bash
# Check if Redis is running
docker ps | grep redis

# Test Redis connection
docker exec -it email-optimizer-redis redis-cli ping

# Check Redis logs
docker-compose logs redis

# Restart Redis
docker-compose restart redis

# Clear Redis data if corrupted
docker exec -it email-optimizer-redis redis-cli FLUSHALL
```

#### Issue: Redis Out of Memory
**Error:** `OOM command not allowed when used memory > 'maxmemory'`

**Solution:**
```bash
# Check memory usage
docker exec -it email-optimizer-redis redis-cli INFO memory

# Increase max memory
docker exec -it email-optimizer-redis redis-cli CONFIG SET maxmemory 2gb

# Set eviction policy
docker exec -it email-optimizer-redis redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Clear cache if necessary
docker exec -it email-optimizer-redis redis-cli FLUSHDB
```

### AI Provider Issues

#### Issue: OpenAI API Key Invalid
**Error:** `openai.error.AuthenticationError: Invalid API key`

**Solution:**
```bash
# Verify API key format
echo $OPENAI_API_KEY

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Update API key
docker-compose down
export OPENAI_API_KEY="sk-..."
docker-compose up -d
```

#### Issue: Rate Limit Exceeded
**Error:** `openai.error.RateLimitError: Rate limit exceeded`

**Solution:**
```python
# Implement exponential backoff
import time
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5)
)
def call_openai_api():
    # API call here
    pass

# Or reduce request rate
RATE_LIMIT_PER_MINUTE=30  # Reduce from 60
```

#### Issue: API Timeout
**Error:** `TimeoutError: Request timed out`

**Solution:**
```bash
# Increase timeout in environment
AI_REQUEST_TIMEOUT=60  # Increase from 30

# Or in code
client = OpenAI(timeout=60)
```

### Performance Issues

#### Issue: Slow Response Times
**Symptoms:** API responses taking > 5 seconds

**Diagnosis:**
```bash
# Check CPU and memory usage
docker stats

# Check slow queries
docker exec -it email-optimizer-postgres psql -U postgres -d email_optimizer \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10"

# Check Redis latency
docker exec -it email-optimizer-redis redis-cli --latency
```

**Solution:**
```bash
# Scale up containers
docker-compose up -d --scale app=3

# Add database indexes
docker exec -it email-optimizer-postgres psql -U postgres -d email_optimizer << EOF
CREATE INDEX idx_subjects_created_at ON subjects(created_at);
CREATE INDEX idx_analytics_subject_id ON email_analytics(subject_id);
ANALYZE;
EOF

# Enable query caching
CACHE_TTL=7200  # Increase cache TTL
```

#### Issue: High Memory Usage
**Symptoms:** Container using > 2GB RAM

**Solution:**
```yaml
# Add memory limits in docker-compose.yml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

# Optimize Python memory usage
PYTHONOPTIMIZE=2
PYTHONUNBUFFERED=1
```

#### Issue: Disk Space Full
**Error:** `No space left on device`

**Solution:**
```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -af
docker volume prune -f

# Clean up logs
find /var/log -type f -name "*.log" -mtime +7 -delete

# Rotate logs
docker-compose logs --tail=1000 > backup.log
docker-compose down
docker-compose up -d
```

### Deployment Issues

#### Issue: Docker Build Fails
**Error:** `docker build failed`

**Solution:**
```bash
# Clear Docker cache
docker builder prune -af

# Build with no cache
docker build --no-cache -t email-optimizer .

# Check Dockerfile syntax
docker build --check .

# Build with verbose output
docker build --progress=plain -t email-optimizer .
```

#### Issue: Health Check Failing
**Error:** `Health check failed`

**Solution:**
```bash
# Check health endpoint manually
curl -v http://localhost:8000/health

# Check application logs
docker-compose logs --tail=100 app

# Increase health check timeout
HEALTHCHECK --timeout=30s  # Increase from 10s

# Debug health check
docker inspect email-optimizer-app | grep -A 10 Health
```

#### Issue: CI/CD Pipeline Failing
**Error:** GitHub Actions workflow failed

**Solution:**
```yaml
# Add debugging to workflow
- name: Debug
  run: |
    echo "Environment: ${{ github.event.inputs.environment }}"
    env
    docker version
    docker-compose version

# Run workflow with debug logging
ACTIONS_STEP_DEBUG: true
ACTIONS_RUNNER_DEBUG: true
```

### Data Issues

#### Issue: Cache Inconsistency
**Symptoms:** Stale data being returned

**Solution:**
```bash
# Clear all cache
docker exec -it email-optimizer-redis redis-cli FLUSHALL

# Clear specific cache pattern
docker exec -it email-optimizer-redis redis-cli --scan --pattern "email_optimizer:*" | xargs redis-cli DEL

# Verify cache operations
curl http://localhost:8000/api/v1/cache/stats
```

#### Issue: Data Corruption
**Symptoms:** Invalid data in responses

**Solution:**
```bash
# Backup current data
./scripts/backup.sh emergency_backup

# Validate database integrity
docker exec -it email-optimizer-postgres psql -U postgres -d email_optimizer \
  -c "SELECT COUNT(*) FROM subjects WHERE created_at > NOW()"

# Restore from backup if needed
./scripts/rollback.sh
RESTORE_DATABASE=true ./scripts/rollback.sh
```

### Monitoring Issues

#### Issue: Metrics Not Appearing
**Error:** Prometheus not scraping metrics

**Solution:**
```bash
# Check metrics endpoint
curl http://localhost:8000/metrics

# Check Prometheus targets
curl http://localhost:9090/targets

# Verify Prometheus config
docker exec -it email-optimizer-prometheus cat /etc/prometheus/prometheus.yml

# Reload Prometheus config
docker exec -it email-optimizer-prometheus kill -HUP 1
```

#### Issue: Grafana Dashboard Empty
**Error:** No data in Grafana panels

**Solution:**
```bash
# Check data source
curl -u admin:admin http://localhost:3001/api/datasources

# Test Prometheus query
curl "http://localhost:9090/api/v1/query?query=up"

# Re-import dashboard
curl -u admin:admin -X POST http://localhost:3001/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/email-optimizer.json
```

### Security Issues

#### Issue: Unauthorized Access
**Error:** `401 Unauthorized`

**Solution:**
```bash
# Verify API key
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/generate

# Check CORS settings
CORS_ORIGINS=https://yourdomain.com,http://localhost:3000

# Verify authentication middleware
docker-compose logs app | grep "Auth"
```

#### Issue: SSL Certificate Issues
**Error:** `SSL certificate verify failed`

**Solution:**
```bash
# Generate self-signed cert (development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Use Let's Encrypt (production)
certbot certonly --standalone -d yourdomain.com

# Disable SSL verification (development only)
export PYTHONHTTPSVERIFY=0
```

## Debug Commands

### Application Debugging
```bash
# Enter container shell
docker exec -it email-optimizer-app bash

# Python shell with app context
docker exec -it email-optimizer-app python
>>> from src.main import app
>>> from src.database import get_session

# Check environment variables
docker exec email-optimizer-app env | grep -E "(API|DATABASE|REDIS)"

# Test database connection
docker exec email-optimizer-app python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.getenv('DATABASE_URL'))
conn = engine.connect()
print('Database connected successfully')
"
```

### Performance Profiling
```bash
# CPU profiling
docker exec email-optimizer-app py-spy top --pid 1

# Memory profiling
docker exec email-optimizer-app python -m memory_profiler src/main.py

# API endpoint timing
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/v1/generate
```

### Log Analysis
```bash
# Error frequency
docker-compose logs app | grep ERROR | wc -l

# Slow requests
docker-compose logs app | grep -E "duration_ms.*[0-9]{4,}"

# Recent errors with context
docker-compose logs --tail=1000 app | grep -B5 -A5 ERROR
```

## Getting Help

### Log Collection for Support
```bash
# Collect diagnostic information
./scripts/collect_diagnostics.sh

# Manual collection
mkdir diagnostics
docker-compose logs > diagnostics/docker_logs.txt
docker ps -a > diagnostics/containers.txt
docker images > diagnostics/images.txt
curl http://localhost:8000/health > diagnostics/health.txt
env | grep -v KEY > diagnostics/env.txt
tar -czf diagnostics.tar.gz diagnostics/
```

### Support Channels
- GitHub Issues: https://github.com/yourusername/email-subject-optimizer/issues
- Slack: #email-optimizer-support
- Email: support@email-optimizer.com
- Documentation: https://docs.email-optimizer.com

### Emergency Contacts
- On-call Engineer: PagerDuty
- Database Admin: #database-team
- Infrastructure: #platform-team
- Security: security@company.com