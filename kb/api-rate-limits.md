# API Rate Limits & Quota Specifications

## Rate Limit Thresholds by Plan
SupportFlow protects API infrastructure through token-bucket rate limiting based on your subscription tier:
- **Starter Plan:** 60 requests per minute (RPM) per API key. Burst allowance up to 10 requests.
- **Pro Plan:** 300 requests per minute (RPM) per API key. Burst allowance up to 30 requests.
- **Enterprise Plan:** 1,200 requests per minute (RPM) per API key. Burst allowance up to 100 requests.

## HTTP Headers Returned
Every API request includes standard rate-limiting headers in the response:
- `X-RateLimit-Limit`: The total allowed requests per 60-second window.
- `X-RateLimit-Remaining`: The remaining number of requests available in the current window.
- `X-RateLimit-Reset`: UTC epoch timestamp indicating when the current window resets.

## Handling 429 Responses
When a client exceeds its quota, the API responds with HTTP 429 Too Many Requests and a JSON body containing error details. To handle this gracefully:
1. Check the `Retry-After` header value (seconds to wait).
2. Use exponential backoff with randomized jitter in retry logic.
3. Batch operations where available using our bulk endpoints.
