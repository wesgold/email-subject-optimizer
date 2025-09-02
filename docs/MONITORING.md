# Email Subject Line Optimizer - Monitoring Guide

## Overview
This guide covers monitoring, observability, and alerting for the Email Subject Line Optimizer application.

## Table of Contents
1. [Metrics Collection](#metrics-collection)
2. [Logging](#logging)
3. [Health Checks](#health-checks)
4. [Dashboards](#dashboards)
5. [Alerting](#alerting)
6. [Performance Monitoring](#performance-monitoring)
7. [Error Tracking](#error-tracking)
8. [Business Metrics](#business-metrics)

## Metrics Collection

### Prometheus Metrics

The application exposes Prometheus metrics at `/metrics` endpoint.

#### Available Metrics

**HTTP Metrics:**
- `email_optimizer_http_requests_total`: Total HTTP requests by method, endpoint, and status
- `email_optimizer_http_request_duration_seconds`: Request duration histogram
- `email_optimizer_http_request_size_bytes`: Request size summary
- `email_optimizer_http_response_size_bytes`: Response size summary

**AI Provider Metrics:**
- `email_optimizer_ai_requests_total`: Total AI provider requests
- `email_optimizer_ai_request_duration_seconds`: AI request duration
- `email_optimizer_ai_tokens_used_total`: Total tokens consumed

**Cache Metrics:**
- `email_optimizer_cache_operations_total`: Cache operations by type and status
- `email_optimizer_cache_size_bytes`: Current cache size

**Database Metrics:**
- `email_optimizer_db_operations_total`: Database operations by type
- `email_optimizer_db_operation_duration_seconds`: Query duration
- `email_optimizer_db_connections_active`: Active connection count

**Business Metrics:**
- `email_optimizer_subjects_generated_total`: Total subjects generated
- `email_optimizer_ab_tests_created_total`: Total A/B tests created
- `email_optimizer_email_opens_total`: Email open tracking
- `email_optimizer_email_clicks_total`: Email click tracking
- `email_optimizer_mab_selections_total`: MAB algorithm selections

**System Metrics:**
- `email_optimizer_cpu_usage_percent`: CPU usage
- `email_optimizer_memory_usage_bytes`: Memory usage by type
- `email_optimizer_disk_usage_percent`: Disk usage

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - 'alerts.yml'

scrape_configs:
  - job_name: 'email-optimizer'
    static_configs:
      - targets: ['app:8000']
    metrics_path: /metrics
    scrape_interval: 10s
```

### Custom Metrics

Add custom metrics in your code:

```python
from src.monitoring.metrics import (
    track_api_call,
    track_cache_hit,
    track_error,
    track_request_duration
)

# Track API calls
track_api_call(provider="openai", model="gpt-4", success=True)

# Track cache operations
track_cache_hit(hit=True)

# Track errors
track_error(error_type="validation", component="api")

# Decorator for request tracking
@track_request_duration(endpoint="/api/v1/generate")
async def generate_subjects(request):
    # Your code here
    pass
```

## Logging

### Log Format

Logs are output in JSON format for easy parsing:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "logger": "email_optimizer.api",
  "message": "Request processed",
  "correlation_id": "req_123abc",
  "method": "POST",
  "path": "/api/v1/generate",
  "status_code": 200,
  "duration_ms": 1234,
  "hostname": "app-server-1",
  "environment": "production"
}
```

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical failures requiring immediate attention

### Structured Logging

```python
from src.monitoring.logging import get_logger

logger = get_logger(__name__)

# Basic logging
logger.info("Processing request", request_id=request_id)

# With context
logger.info(
    "Subject generation completed",
    request_id=request_id,
    num_subjects=5,
    processing_time_ms=1234,
    cache_hit=False
)

# Error logging
try:
    process_request()
except Exception as e:
    logger.error(
        "Request processing failed",
        error=str(e),
        request_id=request_id,
        exc_info=True
    )
```

### Log Aggregation

#### Using ELK Stack

```yaml
# docker-compose.elk.yml
services:
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false

  logstash:
    image: logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch

  kibana:
    image: kibana:8.11.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

Logstash configuration:
```ruby
# logstash.conf
input {
  tcp {
    port => 5000
    codec => json
  }
}

filter {
  date {
    match => [ "timestamp", "ISO8601" ]
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "email-optimizer-%{+YYYY.MM.dd}"
  }
}
```

## Health Checks

### Endpoint Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 5
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 2
    },
    "ai_provider": {
      "status": "healthy",
      "latency_ms": 100
    }
  }
}
```

### Automated Health Monitoring

```bash
# Run health check script
./scripts/health_check.sh production

# Schedule health checks
*/5 * * * * /opt/email-optimizer/scripts/health_check.sh
```

### Docker Health Checks

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

## Dashboards

### Grafana Dashboard Setup

1. Import dashboard from `grafana/dashboards/email-optimizer.json`
2. Configure data source pointing to Prometheus
3. Set refresh interval to 5s for real-time monitoring

#### Key Dashboard Panels

**Overview:**
- Request rate (requests/sec)
- Error rate (errors/sec)
- Response time (p50, p95, p99)
- Active users

**AI Performance:**
- AI requests per minute
- Token usage over time
- Model performance comparison
- Cost tracking

**Cache Performance:**
- Cache hit ratio
- Cache size
- Eviction rate
- Operation latency

**Business Metrics:**
- Subjects generated per hour
- A/B test performance
- Email open/click rates
- MAB algorithm performance

### Custom Dashboard Queries

```promql
# Request rate
rate(email_optimizer_http_requests_total[5m])

# Error rate
rate(email_optimizer_http_requests_total{status=~"5.."}[5m])

# P95 latency
histogram_quantile(0.95, 
  rate(email_optimizer_http_request_duration_seconds_bucket[5m])
)

# Cache hit ratio
rate(email_optimizer_cache_operations_total{status="hit"}[5m]) /
rate(email_optimizer_cache_operations_total[5m])

# AI token usage rate
rate(email_optimizer_ai_tokens_used_total[1h])
```

## Alerting

### Alert Rules

```yaml
# alerts.yml
groups:
  - name: email_optimizer
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(email_optimizer_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
          description: "Error rate is {{ $value }} errors/sec"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(email_optimizer_http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High response time
          description: "P95 response time is {{ $value }} seconds"

      - alert: LowCacheHitRate
        expr: |
          rate(email_optimizer_cache_operations_total{status="hit"}[5m]) /
          rate(email_optimizer_cache_operations_total[5m]) < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: Low cache hit rate
          description: "Cache hit rate is {{ $value }}"

      - alert: DatabaseConnectionPoolExhausted
        expr: email_optimizer_db_connections_active >= 18
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Database connection pool nearly exhausted
          description: "{{ $value }} active connections out of 20"

      - alert: AIProviderErrors
        expr: rate(email_optimizer_ai_requests_total{status="error"}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: AI provider experiencing errors
          description: "AI error rate is {{ $value }} errors/sec"
```

### Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  slack_api_url: 'YOUR_SLACK_WEBHOOK_URL'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'slack'

receivers:
  - name: 'slack'
    slack_configs:
      - channel: '#email-optimizer-alerts'
        title: 'Email Optimizer Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
```

### PagerDuty Integration

```yaml
receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY'
        description: '{{ .GroupLabels.alertname }}'
        details:
          severity: '{{ .CommonLabels.severity }}'
          summary: '{{ .CommonAnnotations.summary }}'
```

## Performance Monitoring

### Application Performance Monitoring (APM)

#### Using New Relic

```python
# newrelic.ini
[newrelic]
license_key = YOUR_LICENSE_KEY
app_name = Email Optimizer
monitor_mode = true
log_level = info
```

#### Using DataDog

```python
from ddtrace import tracer

@tracer.wrap()
async def generate_subjects(request):
    # Your code here
    pass
```

### Database Performance

Monitor slow queries:

```sql
-- PostgreSQL slow query log
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log queries slower than 1s
SELECT pg_reload_conf();

-- Query performance statistics
SELECT 
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### Redis Performance

```bash
# Monitor Redis performance
redis-cli --stat

# Get slow log
redis-cli SLOWLOG GET 10

# Monitor commands
redis-cli MONITOR
```

## Error Tracking

### Sentry Integration

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment="production"
)
```

### Error Aggregation

Track errors by type:

```promql
# Top error types
topk(5, sum by (type) (
  rate(email_optimizer_errors_total[1h])
))

# Error rate by component
sum by (component) (
  rate(email_optimizer_errors_total[5m])
)
```

## Business Metrics

### Key Performance Indicators (KPIs)

1. **Subject Generation Performance**
   - Average generation time
   - Cache hit ratio
   - AI token usage per request

2. **A/B Testing Effectiveness**
   - Test completion rate
   - Statistical significance achievement rate
   - Average improvement over baseline

3. **Email Performance**
   - Open rate improvement
   - Click-through rate improvement
   - Conversion rate impact

### Custom Business Dashboards

```promql
# Daily subject generation trend
increase(email_optimizer_subjects_generated_total[1d])

# A/B test winner selection rate
rate(email_optimizer_mab_selections_total[1h])

# Email performance improvement
(
  sum(rate(email_optimizer_email_opens_total[1d])) /
  sum(rate(email_optimizer_subjects_generated_total[1d]))
) * 100
```

### Reporting

Generate automated reports:

```python
from src.monitoring.reporting import generate_report

# Daily performance report
report = generate_report(
    start_date="2024-01-01",
    end_date="2024-01-31",
    metrics=["generation_volume", "performance", "costs"]
)

# Send to stakeholders
send_email_report(report, recipients=["team@example.com"])
```

## Monitoring Best Practices

1. **Set Baseline Metrics**: Establish normal operating ranges
2. **Progressive Alerting**: Start with warnings before critical alerts
3. **Avoid Alert Fatigue**: Only alert on actionable issues
4. **Regular Review**: Weekly review of metrics and alerts
5. **Capacity Planning**: Monitor trends for scaling decisions
6. **Correlation**: Correlate business and technical metrics
7. **Documentation**: Document alert response procedures
8. **Testing**: Regularly test alerting mechanisms

## Troubleshooting Monitoring Issues

### Missing Metrics
```bash
# Verify metrics endpoint
curl http://localhost:8000/metrics

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify scrape configuration
curl http://localhost:9090/api/v1/query?query=up
```

### High Cardinality Issues
```promql
# Find high cardinality metrics
prometheus_tsdb_symbol_table_size_bytes

# Identify problematic labels
count by (__name__)({__name__=~"email_optimizer_.*"})
```

### Dashboard Not Loading
```bash
# Check Grafana logs
docker logs email-optimizer-grafana

# Verify data source
curl -u admin:admin http://localhost:3001/api/datasources

# Test query
curl http://localhost:9090/api/v1/query?query=up
```

## Support

For monitoring support:
- Slack: #email-optimizer-monitoring
- Wiki: https://wiki.example.com/monitoring
- On-call: PagerDuty escalation policy