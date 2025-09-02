# Email Subject Line Optimizer - API Documentation

## Base URL
```
Production: https://api.email-optimizer.com
Staging: https://staging-api.email-optimizer.com
Local: http://localhost:8000
```

## Authentication
Most endpoints require API key authentication. Include your API key in the request header:
```
X-API-Key: your-api-key-here
```

## Rate Limiting
- Default: 60 requests per minute
- Premium: 1000 requests per minute
- Enterprise: Custom limits

Rate limit headers returned:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Endpoints

### Health Check

#### GET /health
Check service health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "ai_provider": "healthy"
  }
}
```

### Subject Line Generation

#### POST /api/v1/generate
Generate optimized email subject lines.

**Request Body:**
```json
{
  "email_body": "Your email content here...",
  "tone": "professional",
  "target_audience": "marketing professionals",
  "industry": "technology",
  "goals": ["increase_open_rate", "drive_clicks"],
  "num_variations": 5,
  "include_emojis": false,
  "max_length": 50
}
```

**Parameters:**
- `email_body` (required): The email content to generate subjects for
- `tone` (optional): One of: professional, casual, urgent, friendly, formal
- `target_audience` (optional): Description of target audience
- `industry` (optional): Industry context
- `goals` (optional): Array of optimization goals
- `num_variations` (optional): Number of variations to generate (1-10, default: 5)
- `include_emojis` (optional): Whether to include emojis (default: false)
- `max_length` (optional): Maximum character length (default: 60)

**Response:**
```json
{
  "request_id": "req_123abc",
  "subjects": [
    {
      "id": "subj_456def",
      "text": "Unlock 5 Proven Strategies for Email Marketing Success",
      "score": 0.92,
      "characteristics": {
        "length": 48,
        "sentiment": "positive",
        "urgency_level": "medium",
        "personalization": false,
        "contains_numbers": true,
        "contains_questions": false
      }
    }
  ],
  "metadata": {
    "generated_at": "2024-01-01T12:00:00Z",
    "model_used": "gpt-4-turbo",
    "cache_hit": false,
    "processing_time_ms": 1234
  }
}
```

#### POST /api/v1/generate/batch
Generate subject lines for multiple emails.

**Request Body:**
```json
{
  "emails": [
    {
      "id": "email_1",
      "email_body": "First email content...",
      "tone": "professional"
    },
    {
      "id": "email_2",
      "email_body": "Second email content...",
      "tone": "casual"
    }
  ],
  "common_settings": {
    "num_variations": 3,
    "include_emojis": false
  }
}
```

**Response:**
```json
{
  "batch_id": "batch_789ghi",
  "results": [
    {
      "email_id": "email_1",
      "subjects": [...]
    },
    {
      "email_id": "email_2",
      "subjects": [...]
    }
  ]
}
```

### A/B Testing

#### POST /api/v1/ab-tests
Create a new A/B test.

**Request Body:**
```json
{
  "name": "Q1 Newsletter Test",
  "subjects": [
    "Subject Line A",
    "Subject Line B",
    "Subject Line C"
  ],
  "test_size": 1000,
  "duration_hours": 24,
  "success_metric": "click_rate"
}
```

**Response:**
```json
{
  "test_id": "test_abc123",
  "name": "Q1 Newsletter Test",
  "status": "active",
  "created_at": "2024-01-01T12:00:00Z",
  "variants": [
    {
      "id": "var_1",
      "subject": "Subject Line A",
      "allocation": 0.333
    }
  ]
}
```

#### GET /api/v1/ab-tests/{test_id}
Get A/B test details and results.

**Response:**
```json
{
  "test_id": "test_abc123",
  "name": "Q1 Newsletter Test",
  "status": "completed",
  "results": {
    "winner": "var_2",
    "variants": [
      {
        "id": "var_1",
        "subject": "Subject Line A",
        "metrics": {
          "impressions": 334,
          "opens": 67,
          "clicks": 12,
          "open_rate": 0.20,
          "click_rate": 0.036,
          "confidence": 0.85
        }
      }
    ],
    "statistical_significance": true,
    "confidence_level": 0.95
  }
}
```

#### POST /api/v1/ab-tests/{test_id}/select
Get variant selection using Multi-Armed Bandit algorithm.

**Request Body:**
```json
{
  "user_context": {
    "segment": "premium",
    "timezone": "PST",
    "device": "mobile"
  }
}
```

**Response:**
```json
{
  "selected_variant": "var_2",
  "subject": "Subject Line B",
  "selection_method": "thompson_sampling",
  "exploration_probability": 0.1
}
```

### Analytics

#### GET /api/v1/analytics/subjects
Get analytics for generated subjects.

**Query Parameters:**
- `start_date`: ISO 8601 date string
- `end_date`: ISO 8601 date string
- `limit`: Number of results (default: 100)
- `offset`: Pagination offset
- `sort_by`: One of: open_rate, click_rate, created_at
- `order`: asc or desc

**Response:**
```json
{
  "subjects": [
    {
      "id": "subj_456def",
      "text": "Your Subject Line",
      "created_at": "2024-01-01T12:00:00Z",
      "metrics": {
        "total_sends": 10000,
        "opens": 2500,
        "clicks": 500,
        "open_rate": 0.25,
        "click_rate": 0.05,
        "ctr": 0.20
      },
      "performance_score": 0.87
    }
  ],
  "pagination": {
    "total": 500,
    "limit": 100,
    "offset": 0,
    "has_more": true
  }
}
```

#### GET /api/v1/analytics/performance
Get overall performance metrics.

**Response:**
```json
{
  "period": "last_30_days",
  "overview": {
    "total_subjects_generated": 1500,
    "total_emails_sent": 500000,
    "average_open_rate": 0.24,
    "average_click_rate": 0.045,
    "improvement_vs_baseline": 0.15
  },
  "top_performers": [...],
  "trends": {
    "open_rate_trend": "increasing",
    "click_rate_trend": "stable"
  }
}
```

#### POST /api/v1/analytics/track
Track email events.

**Request Body:**
```json
{
  "event_type": "open",
  "subject_id": "subj_456def",
  "recipient_id": "user_789",
  "timestamp": "2024-01-01T12:00:00Z",
  "metadata": {
    "client": "gmail",
    "device": "mobile",
    "location": "US"
  }
}
```

**Response:**
```json
{
  "event_id": "evt_xyz789",
  "tracked": true
}
```

### Multi-Armed Bandit

#### GET /api/v1/mab/stats
Get Multi-Armed Bandit statistics.

**Response:**
```json
{
  "algorithm": "thompson_sampling",
  "total_selections": 50000,
  "variants": [
    {
      "id": "var_1",
      "selections": 15000,
      "successes": 3000,
      "success_rate": 0.20,
      "alpha": 3001,
      "beta": 12001
    }
  ],
  "exploration_rate": 0.1,
  "confidence_bounds": {
    "method": "ucb",
    "confidence_level": 0.95
  }
}
```

#### POST /api/v1/mab/reward
Update reward for a variant.

**Request Body:**
```json
{
  "variant_id": "var_1",
  "reward": 1,
  "context": {
    "action": "click",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

**Response:**
```json
{
  "updated": true,
  "new_stats": {
    "successes": 3001,
    "failures": 12000,
    "success_rate": 0.2001
  }
}
```

### Cache Management

#### GET /api/v1/cache/stats
Get cache statistics.

**Response:**
```json
{
  "backend": "redis",
  "stats": {
    "total_keys": 5000,
    "memory_used_mb": 128,
    "hit_rate": 0.85,
    "miss_rate": 0.15,
    "evictions": 100
  }
}
```

#### DELETE /api/v1/cache/clear
Clear cache (requires admin privileges).

**Response:**
```json
{
  "cleared": true,
  "keys_removed": 5000
}
```

### Metrics

#### GET /metrics
Prometheus metrics endpoint.

**Response:** Prometheus text format
```
# HELP email_optimizer_http_requests_total Total HTTP requests
# TYPE email_optimizer_http_requests_total counter
email_optimizer_http_requests_total{method="GET",endpoint="/health",status="200"} 1000
```

## Error Responses

All errors follow a consistent format:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after 60 seconds.",
    "details": {
      "limit": 60,
      "remaining": 0,
      "reset_at": "2024-01-01T12:01:00Z"
    }
  },
  "request_id": "req_123abc"
}
```

### Error Codes
- `INVALID_REQUEST`: Request validation failed
- `UNAUTHORIZED`: Missing or invalid API key
- `FORBIDDEN`: Insufficient permissions
- `NOT_FOUND`: Resource not found
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded
- `INTERNAL_ERROR`: Internal server error
- `SERVICE_UNAVAILABLE`: Service temporarily unavailable
- `AI_PROVIDER_ERROR`: AI provider request failed
- `DATABASE_ERROR`: Database operation failed
- `CACHE_ERROR`: Cache operation failed

## Webhooks

Configure webhooks to receive real-time updates:

### Webhook Events
- `subject.generated`: New subject lines generated
- `test.completed`: A/B test completed
- `threshold.reached`: Performance threshold reached

### Webhook Payload
```json
{
  "event": "test.completed",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "test_id": "test_abc123",
    "winner": "var_2",
    "confidence": 0.95
  }
}
```

## SDKs and Libraries

### Python
```python
from email_optimizer import Client

client = Client(api_key="your-api-key")
subjects = client.generate(
    email_body="Your email content...",
    tone="professional"
)
```

### JavaScript/TypeScript
```javascript
import { EmailOptimizer } from 'email-optimizer-sdk';

const client = new EmailOptimizer({ apiKey: 'your-api-key' });
const subjects = await client.generate({
  emailBody: 'Your email content...',
  tone: 'professional'
});
```

### cURL Examples
```bash
# Generate subject lines
curl -X POST https://api.email-optimizer.com/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"email_body": "Your email content..."}'

# Get analytics
curl https://api.email-optimizer.com/api/v1/analytics/subjects \
  -H "X-API-Key: your-api-key"
```

## Best Practices

1. **Caching**: Responses are cached for 1 hour by default. Use the same email body to benefit from caching.

2. **Batch Processing**: Use batch endpoints for processing multiple emails to reduce API calls.

3. **Error Handling**: Implement exponential backoff for retries on 5xx errors.

4. **Rate Limiting**: Monitor rate limit headers and implement client-side throttling.

5. **Webhooks**: Use webhooks instead of polling for real-time updates.

## Changelog

### v1.0.0 (2024-01-01)
- Initial release
- Subject line generation
- A/B testing
- Analytics tracking
- Multi-Armed Bandit optimization

## Support

For API support:
- Email: api-support@email-optimizer.com
- Documentation: https://docs.email-optimizer.com
- Status Page: https://status.email-optimizer.com