# Weather API Service 🌤️

현대적인 비동기 처리와 AWS Lambda 기반의 확장 가능한 날씨 조회 API 서비스입니다.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900.svg)](https://aws.amazon.com/lambda/)
[![AWS CDK](https://img.shields.io/badge/AWS-CDK-FF9900.svg)](https://aws.amazon.com/cdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)



## 🎯 개요

이 프로젝트는 기존의 동기식 Flask 기반 날씨 API를 AWS Lambda와 FastAPI를 활용한 현대적인 서버리스 아키텍처로 리팩토링하고자 합니다.
AWS CDK와 Gitaction을 통해 차후 Dev,Stage,PRD의 서비스 계정별 배포를와 확장을 용의하게 하고자합니다.
프로젝트 Test 뿐만아니라 향후 데이터 분석에 자주 사용되는 날씨 api 데이터 처리를 위한
학습의 목료로도 사용하고자 합니다.

### 핵심 개선사항
- **동기 → 비동기**: Flask에서 FastAPI + AWS Lambda로 전환
- **성능 최적화**: Dynamodb 활용 캐싱
- **확장성**: AWS Lambda의 자동 스케일링 활용
- **견고성**: 지수 백오프 재시도 로직 및 Circuit Breaker 패턴
- **모니터링**: CloudWatch, X-Ray를 통한 완전한 관찰 가능성

## ✨ 주요 기능

### 🌍 단일 도시 날씨 조회
```http
GET /weather/{city}
```
- 실시간 날씨 정보 조회
- Redis 캐싱으로 빠른 응답 (캐시 TTL: 10분)
- 자동 재시도 로직 (지수 백오프 + jitter)

### 🏙️ 배치 도시 날씨 조회
```http
POST /weather/batch
Content-Type: application/json

{
  "cities": ["Seoul", "New York", "Tokyo"]
}
```
- 최대 50개 도시 동시 조회
- 비동기 병렬 처리로 성능 최적화
- 부분 실패 허용 (일부 도시 실패 시에도 성공한 결과 반환)

### 🏥 헬스체크
```http
GET /health
```
- 시스템 상태 및 의존성 점검
- 외부 API 연결 상태 확인

## 🏗️ 아키텍처

### 시스템 구성도
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │───▶│  Lambda Functions │───▶│  External APIs  │
│                 │    │                 │    │                 │
│ • Rate Limiting │    │ • Single Weather│    │ • OpenWeatherMap│
│ • CORS          │    │ • Batch Weather │    │                 │
│ • Authentication│    │ • Health Check  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   ElastiCache   │
                       │     (Redis)     │
                       │                 │
                       │ • 10min TTL     │
                       │ • City-based    │
                       │ • Hit/Miss      │
                       └─────────────────┘
```

### AWS 서비스 구성
- **AWS Lambda**: 서버리스 컴퓨팅 (Python 3.11)
- **API Gateway**: REST API 엔드포인트
- **DynamoDB (Redis)**: 고성능 캐싱
- **Systems Manager**: 안전한 API 키 관리
- **CloudWatch**: 로깅 및 메트릭
- **X-Ray**: 분산 추적

## 🚀 시작하기

### 전제 조건
- Python 3.11+
- AWS CLI 구성
- AWS CDK v2 설치
- uv (Python 패키지 매니저)

### 로컬 개발 환경 설정

1. **저장소 클론**
```bash
git clone https://github.com/your-org/weather-api-service.git
cd weather-api-service
```

2. **Python 환경 설정 (uv 사용)**
```bash
# uv로 Python 3.11 프로젝트 초기화
uv init --python 3.11

# 개발 의존성 설치 (테스트, 린팅)
uv add --dev pytest pytest-cov black pylint

# Lambda와 CDK 의존성은 각각의 requirements.txt로 별도 관리
```

3. **환경 변수 설정**
```bash
cp .env.example .env
# .env 파일에서 다음 값들 설정:
# OPENWEATHER_API_KEY=your_api_key_here
# REDIS_URL=redis://localhost:6379
# LOG_LEVEL=INFO
```

4. **로컬 Redis 실행** (Docker 사용)
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

5. **로컬 개발**
```bash
# 로컬 테스트
cd lambda_function && python lambda_function.py

# Lambda 로컬 시뮬레이션 (SAM 사용)
sam local start-api

# 테스트 실행
uv run pytest

# 코드 포맷팅
uv run black lambda_function/ tests/
```

### 로컬 테스트
```bash
# 단일 도시 조회 테스트
curl http://localhost:8000/weather/Seoul

# 배치 조회 테스트
curl -X POST http://localhost:8000/weather/batch \
  -H "Content-Type: application/json" \
  -d '{"cities": ["Seoul", "Tokyo", "New York"]}'

# 헬스체크
curl http://localhost:8000/health
```

## 📚 API 문서

### 실시간 API 문서
로컬 서버 실행 후 다음 URL에서 확인:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API 응답 예시

#### 단일 도시 조회 성공
```json
{
  "city": "Seoul",
  "country": "KR",
  "temperature": 15.2,
  "description": "Clear sky",
  "humidity": 65,
  "wind_speed": 3.2,
  "cached": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### 배치 조회 성공
```json
{
  "results": [
    {
      "city": "Seoul",
      "country": "KR",
      "temperature": 15.2,
      "description": "Clear sky",
      "status": "success"
    },
    {
      "city": "InvalidCity",
      "error": "City not found",
      "status": "error"
    }
  ],
  "summary": {
    "total": 2,
    "success": 1,
    "failed": 1
  }
}
```

## 🚀 배포

### AWS CDK를 통한 배포

1. **CDK 초기 설정**
```bash
# CDK CLI 설치 (전역)
pip install aws-cdk

# infrastructure 디렉토리에서 CDK 부트스트랩 (최초 1회)
cd infrastructure
cdk bootstrap
```

2. **환경별 배포**
```bash
cd infrastructure

# 개발 환경 배포
cdk deploy WeatherStack-dev

# 스테이징 환경 배포
cdk deploy WeatherStack-staging

# 프로덕션 환경 배포
cdk deploy WeatherStack-prod
```

### 환경별 설정
각 환경은 독립적인 AWS 리소스를 사용하며, 다음과 같이 구분됩니다:

| 환경 | API Gateway | Lambda Memory | ElastiCache | 동시성 제한 |
|------|-------------|---------------|-------------|-------------|
| dev | HTTP API | 512MB | t3.micro | 50 |
| staging | REST API | 1024MB | t3.small | 200 |
| prod | REST API | 1024MB | t3.medium | 1000 |

## 💻 개발

### 프로젝트 구조
```
weather-api/
├── 📁 lambda_function/            # Lambda 애플리케이션 코드
│   ├── lambda_function.py         # 메인 핸들러
│   ├── weather_service.py         # 비즈니스 로직
│   ├── cache_service.py           # DynamoDB 캐싱
│   ├── retry_service.py           # 재시도 로직
│   ├── external_api.py            # 외부 API 호출
│   ├── models.py                  # 데이터 모델
│   ├── config.py                  # 설정
│   └── requirements.txt           # Lambda 의존성
│
├── 📁 infrastructure/             # CDK 인프라 코드
│   ├── app.py                     # CDK 앱 진입점
│   ├── weather_stack.py           # 메인 스택
│   ├── cdk.json                   # CDK 설정
│   └── requirements.txt           # CDK 의존성
│
├── 📁 tests/                      # 테스트 코드
│   ├── test_weather_service.py    # 서비스 테스트
│   ├── test_cache_service.py      # 캐시 테스트
│   └── conftest.py                # 테스트 설정
│
├── 📁 docs/                       # 설계 문서
│   └── architecture.md            # 아키텍처 문서
│
├── pyproject.toml                 # uv 프로젝트 설정
├── uv.lock                        # uv 의존성 락파일
└── README.md                      # 이 파일
```

### 코딩 규칙
- **PEP 8** 스타일 가이드 준수
- **Type hints** 모든 함수에 적용
- **Docstring** Google 스타일로 작성
- **테스트** 새 기능은 반드시 테스트 코드 포함

### 개발 명령어
```bash
# 테스트
uv run pytest                                      # 전체 테스트 실행
uv run pytest --cov=lambda_function --cov-report=html  # 커버리지 포함

# 코드 품질
uv run black lambda_function/ tests/               # 코드 포맷팅
uv run pylint lambda_function/                     # 린팅

# 개발
cd lambda_function && python lambda_function.py   # 로컬 테스트
sam local start-api                                # Lambda 시뮬레이션

# 배포
cd infrastructure && cdk deploy WeatherStack-dev   # 개발 환경 배포
```

## 📊 모니터링

### CloudWatch 대시보드
배포 후 AWS 콘솔에서 다음 메트릭을 확인할 수 있습니다:

- **Lambda 메트릭**: 실행 시간, 에러율, 동시성
- **API Gateway 메트릭**: 요청 수, 응답 시간, 4xx/5xx 에러
- **ElastiCache 메트릭**: 캐시 히트율, CPU/메모리 사용률
- **Custom 메트릭**: 외부 API 호출 성공률, 재시도 횟수

### X-Ray 분산 추적
- 요청 플로우 전체 추적
- 병목 지점 식별
- 외부 API 의존성 모니터링

### 알람 설정
다음 조건에서 자동 알림 발송:
- Lambda 에러율 > 5%
- API Gateway 응답 시간 > 10초
- ElastiCache CPU 사용률 > 80%
- 일일 AWS 비용 > 예산의 80%

### 로그 분석
```bash
# CloudWatch 로그 실시간 확인
aws logs tail /aws/lambda/weather-single-function --follow

# 특정 에러 로그 검색
aws logs filter-log-events \
  --log-group-name /aws/lambda/weather-single-function \
  --filter-pattern "ERROR"
```

## 🔧 문제 해결

### 자주 발생하는 문제

#### 1. Lambda Cold Start가 느림
```bash
# Provisioned Concurrency 설정
aws lambda put-provisioned-concurrency-config \
  --function-name weather-single-function \
  --provisioned-concurrency-config AllocatedConcurrency=5
```

#### 2. Redis 연결 오류
```python
# 연결 풀 설정 확인
REDIS_CONFIG = {
    "host": "your-cache-cluster.cache.amazonaws.com",
    "port": 6379,
    "decode_responses": True,
    "max_connections": 20,
    "retry_on_timeout": True
}
```

#### 3. API 키 관리
```bash
# Parameter Store에 API 키 저장
aws ssm put-parameter \
  --name "/weather-api/openweather-key" \
  --value "your-api-key" \
  --type "SecureString"
```
