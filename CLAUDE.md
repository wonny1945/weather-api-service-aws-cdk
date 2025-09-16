# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a serverless weather API service built with AWS Lambda, FastAPI, and AWS CDK. The project is designed to replace a synchronous Flask-based weather API with a modern asynchronous serverless architecture. The service provides both single city weather queries and batch processing of multiple cities.

**Key Technologies:**
- FastAPI (Python 3.11) for API framework
- AWS Lambda for serverless compute
- AWS CDK (Python) for infrastructure as code
- DynamoDB/ElastiCache for caching
- OpenWeatherMap API as external data source

## Development Commands

### Local Development Setup
```bash
# Initialize Python 3.11 project with uv
uv init --python 3.11

# Install development dependencies only (Lambda/CDK deps managed separately)
uv add --dev pytest pytest-cov black pylint

# Setup environment variables
cp .env.example .env
# Edit .env with OPENWEATHER_API_KEY and other settings

# Development commands
cd lambda_function && python lambda_function.py  # Local test
sam local start-api                               # Lambda simulation
uv run pytest                                     # Run tests
uv run black lambda_function/ tests/              # Format code
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=lambda_function --cov-report=html

# Run specific test file
uv run pytest tests/test_weather_service.py
```

### Code Quality
```bash
# Format code
uv run black lambda_function/ tests/

# Lint code
uv run pylint lambda_function/
```

### AWS CDK Deployment
```bash
# Install CDK CLI globally
pip install aws-cdk

# Bootstrap CDK (first time only)
cd infrastructure && cdk bootstrap

# Deploy to environments
cd infrastructure
cdk deploy WeatherStack-dev      # Development
cdk deploy WeatherStack-staging  # Staging
cdk deploy WeatherStack-prod     # Production
```

## Architecture

### Project Structure
```
lambda_function/     # Lambda application code
├── lambda_function.py    # Main handler
├── weather_service.py    # Business logic
├── cache_service.py      # DynamoDB caching
├── retry_service.py      # Retry logic
├── external_api.py       # External API calls
├── models.py            # Data models
├── config.py            # Configuration
└── requirements.txt     # Lambda dependencies

infrastructure/      # CDK infrastructure code
├── app.py           # CDK app entry point
├── weather_stack.py # Main stack
├── cdk.json         # CDK configuration
└── requirements.txt # CDK dependencies

tests/               # Test code
├── test_weather_service.py
├── test_cache_service.py
└── conftest.py

docs/                # Documentation
└── architecture.md

pyproject.toml       # uv project configuration
uv.lock              # uv dependency lock file
```

### Key Components

**Lambda Function:**
- `lambda_function.py` - Main handler for all endpoints (single, batch, health)
- `weather_service.py` - Core business logic
- `cache_service.py` - DynamoDB caching layer
- `retry_service.py` - Exponential backoff retry logic
- `external_api.py` - OpenWeatherMap API client
- `models.py` - Pydantic data models
- `config.py` - Configuration management

**Infrastructure (CDK):**
- `weather_stack.py` - Main CDK stack containing:
  - API Gateway for REST endpoints
  - Lambda function for compute
  - DynamoDB for caching (10-minute TTL)
  - Systems Manager for secure API key storage
  - CloudWatch + X-Ray for monitoring

### API Endpoints
- `GET /weather/{city}` - Single city weather
- `POST /weather/batch` - Batch city weather (JSON body with cities array)
- `GET /health` - Health check with dependency validation

## Development Guidelines

### Environment Management
- Development, staging, and production environments use separate AWS resources
- Each environment has different Lambda memory allocations and concurrency limits
- API keys stored securely in AWS Systems Manager Parameter Store

### Caching Strategy
- 10-minute TTL for weather data
- City-based cache keys
- Fallback to external API on cache miss
- Redis for high-performance caching

### Error Handling & Resilience
- Exponential backoff retry logic with jitter
- Circuit breaker pattern for external API calls
- Graceful degradation for batch requests (partial failures allowed)
- Comprehensive logging and monitoring

### Performance Considerations
- Asynchronous processing for batch requests
- Connection pooling for Redis
- Provisioned concurrency for Lambda cold start mitigation
- Parallel processing of multiple city requests

### Monitoring & Observability
- CloudWatch metrics for Lambda, API Gateway, and ElastiCache
- X-Ray distributed tracing
- Custom metrics for external API success rates
- Automated alerts for error rates and performance thresholds

## Testing Strategy

- Unit tests for all services and utilities
- Integration tests for external API clients
- Lambda handler tests with mocked dependencies
- End-to-end tests for complete request flows
- Load testing for batch processing capabilities

Note: This project documentation is primarily in Korean (README.md), but code should follow English naming conventions and documentation standards.
