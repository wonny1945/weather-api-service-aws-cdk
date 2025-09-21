"""
배포된 Weather API 서비스 캐시 성능 테스트

간단한 캐시 성능 검증:
1. DynamoDB 캐시 초기화
2. 도시별 첫 번째 조회 (캐시 미스)
3. 캐시 생성 확인
4. 동일 도시 두 번째 조회 (캐시 히트)
5. 응답 시간 비교 분석

실행 방법:
    uv run pytest tests/service_functionality_test/test_deployed_service.py -v
    또는
    python tests/service_functionality_test/test_deployed_service.py
"""

import os
import time
import logging
from typing import Dict
import requests
import boto3
from dotenv import load_dotenv
import pytest

# 환경 변수 로드
load_dotenv(".env.local")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleCacheTest:
    """간단한 캐시 성능 테스트"""

    def __init__(self):
        # 환경 변수 로드
        self.api_endpoint = os.getenv("DEPLOYED_API_ENDPOINT")
        self.openweather_api_key = os.getenv("TEST_OPENWEATHER_API_KEY")
        self.aws_region = os.getenv("AWS_REGION", "ap-northeast-2")
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.dynamodb_table_name = os.getenv("DYNAMODB_TABLE_NAME")

        # 테스트 도시 목록
        self.test_cities = [
            "Seoul",
            "Busan",
            "Incheon",
            "Daegu",
            "Daejeon",
            "Gwangju",
            "Ulsan",
            "Suwon",
            "Changwon",
            "Goyang",
        ]

        # 결과 저장
        self.results = []

        # 설정 검증
        self._validate_config()

        # DynamoDB 초기화
        self._init_dynamodb()

    def _validate_config(self):
        """필수 설정 검증"""
        missing = []
        if not self.api_endpoint:
            missing.append("DEPLOYED_API_ENDPOINT")
        if not self.openweather_api_key:
            missing.append("TEST_OPENWEATHER_API_KEY")
        if not self.aws_access_key_id:
            missing.append("AWS_ACCESS_KEY_ID")
        if not self.aws_secret_access_key:
            missing.append("AWS_SECRET_ACCESS_KEY")
        if not self.dynamodb_table_name:
            missing.append("DYNAMODB_TABLE_NAME")

        if missing:
            raise ValueError(f"환경 변수 누락: {', '.join(missing)}")

        logger.info("✅ 환경 설정 검증 완료")
        logger.info(f"API 엔드포인트: {self.api_endpoint}")
        logger.info(f"OpenWeather API 키: {self.openweather_api_key[:8]}...")
        logger.info(f"DynamoDB 테이블: {self.dynamodb_table_name}")

    def _init_dynamodb(self):
        """DynamoDB 초기화"""
        try:
            self.dynamodb = boto3.resource(
                "dynamodb",
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
            self.table = self.dynamodb.Table(self.dynamodb_table_name)
            logger.info("✅ DynamoDB 연결 성공")
        except Exception as e:
            raise RuntimeError(f"DynamoDB 연결 실패: {e}")

    def clear_all_cache(self):
        """DynamoDB 전체 캐시 삭제"""
        logger.info("🗑️  DynamoDB 캐시 전체 삭제 중...")

        try:
            # 모든 캐시 항목 조회
            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix)",
                ExpressionAttributeValues={":pk_prefix": "WEATHER#"},
            )

            # 배치 삭제
            with self.table.batch_writer() as batch:
                for item in response.get("Items", []):
                    batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

            deleted_count = len(response.get("Items", []))
            logger.info(f"✅ {deleted_count}개 캐시 항목 삭제 완료")

        except Exception as e:
            logger.error(f"❌ 캐시 삭제 실패: {e}")
            raise

    def check_cache_exists(self, city: str) -> bool:
        """특정 도시 캐시 존재 확인"""
        try:
            cache_key = f"WEATHER#{city.strip().title()}"
            response = self.table.get_item(Key={"PK": cache_key, "SK": "DATA"})
            exists = "Item" in response
            print(f"   DynamoDB 조회 결과: {'캐시 있음' if exists else '캐시 없음'}")
            return exists
        except Exception as e:
            print(f"   ❌ DynamoDB 조회 실패: {e}")
            return False

    def call_weather_api(self, city: str) -> Dict:
        """날씨 API 호출"""
        url = f"{self.api_endpoint.rstrip('/')}/weather/{city}"

        # API 키를 헤더 또는 쿼리 파라미터로 전달
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.openweather_api_key,
        }

        params = {"api_key": self.openweather_api_key}

        start_time = time.time()
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            end_time = time.time()

            response_time = end_time - start_time

            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response_time,
                "data": response.json() if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None,
            }

        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "status_code": None,
                "response_time": end_time - start_time,
                "data": None,
                "error": str(e),
            }

    def test_single_city_cache_performance(self, city: str) -> Dict:
        """단일 도시 캐시 성능 테스트"""
        print(f"\n{'='*60}")
        print(f"🏙️  {city} 캐시 성능 테스트")
        print(f"{'='*60}")

        # 1. 해당 도시 캐시 삭제
        cache_key = f"WEATHER#{city.strip().title()}"
        try:
            self.table.delete_item(Key={"PK": cache_key, "SK": "DATA"})
            print(f"✅ {city} 캐시 삭제 완료")
        except:
            print(f"ℹ️  {city} 캐시 없음 (정상)")

        # 2. 첫 번째 조회 (캐시 미스)
        print(f"\n📞 {city} 첫 번째 호출 (캐시 미스 예상)...")
        first_call = self.call_weather_api(city)

        if not first_call["success"]:
            print(f"❌ {city} 첫 번째 호출 실패: {first_call['error']}")
            return {"city": city, "success": False, "error": first_call["error"]}

        print(f"⏱️  첫 번째 호출 응답 시간: {first_call['response_time']:.3f}초")

        # 3. DynamoDB 캐시 생성 확인
        print(f"\n🔍 DynamoDB 캐시 확인 중...")
        cache_created = self.check_cache_exists(city)
        print(f"✅ 캐시 생성 확인: {'성공' if cache_created else '실패'}")

        # 4. 두 번째 조회 (캐시 히트)
        print(f"\n📞 {city} 두 번째 호출 (캐시 히트 예상)...")
        second_call = self.call_weather_api(city)

        if not second_call["success"]:
            print(f"❌ {city} 두 번째 호출 실패: {second_call['error']}")
            return {"city": city, "success": False, "error": second_call["error"]}

        print(f"⏱️  두 번째 호출 응답 시간: {second_call['response_time']:.3f}초")

        # 5. 결과 분석
        cache_miss_time = first_call["response_time"]
        cache_hit_time = second_call["response_time"]
        speed_improvement = (
            cache_miss_time / cache_hit_time if cache_hit_time > 0 else 1
        )
        time_saved = cache_miss_time - cache_hit_time

        print(f"\n⚡ {city} 성능 비교:")
        print(f"   캐시 미스 (외부 API): {cache_miss_time:.3f}초")
        print(f"   캐시 히트 (DynamoDB): {cache_hit_time:.3f}초")
        print(f"   성능 향상: {speed_improvement:.2f}배 빠름")
        print(
            f"   시간 절약: {time_saved:.3f}초 ({((time_saved / cache_miss_time) * 100):.1f}%)"
        )

        result = {
            "city": city,
            "success": True,
            "cache_created": cache_created,
            "cache_miss_time": cache_miss_time,
            "cache_hit_time": cache_hit_time,
            "speed_improvement": speed_improvement,
            "time_saved": time_saved,
            "percentage_faster": (
                ((time_saved / cache_miss_time) * 100) if cache_miss_time > 0 else 0
            ),
        }

        return result

    def test_batch_cache_performance(self) -> Dict:
        """배치 캐시 성능 테스트"""
        print(f"\n{'='*60}")
        print(f"🏙️  배치 서비스 캐시 성능 테스트")
        print(f"{'='*60}")

        # 테스트용 도시 목록 (전체 10개 도시)
        batch_cities = self.test_cities
        print(f"📋 배치 테스트 도시: {', '.join(batch_cities)}")

        # 1. 배치 도시들 캐시 삭제
        print(f"\n🗑️  배치 도시들 캐시 삭제 중...")
        for city in batch_cities:
            cache_key = f"WEATHER#{city.strip().title()}"
            try:
                self.table.delete_item(Key={"PK": cache_key, "SK": "DATA"})
            except:
                pass

        # 2. 첫 번째 배치 호출 (캐시 미스)
        print(f"\n📞 첫 번째 배치 호출 (캐시 미스 예상)...")
        payload = {"cities": batch_cities}
        first_call = self.call_batch_api(payload)

        if not first_call["success"]:
            print(f"❌ 첫 번째 배치 호출 실패: {first_call['error']}")
            return {"success": False, "error": first_call["error"]}

        print(f"⏱️  첫 번째 배치 호출 응답 시간: {first_call['response_time']:.3f}초")

        # 3. DynamoDB 캐시 생성 확인
        print(f"\n🔍 배치 도시들 캐시 확인 중...")
        cached_count = 0
        for city in batch_cities:
            if self.check_cache_exists(city):
                cached_count += 1

        print(f"✅ 캐시 생성 확인: {cached_count}/{len(batch_cities)}개 도시 캐시됨")

        # 4. 두 번째 배치 호출 (캐시 히트)
        print(f"\n📞 두 번째 배치 호출 (캐시 히트 예상)...")
        second_call = self.call_batch_api(payload)

        if not second_call["success"]:
            print(f"❌ 두 번째 배치 호출 실패: {second_call['error']}")
            return {"success": False, "error": second_call["error"]}

        print(f"⏱️  두 번째 배치 호출 응답 시간: {second_call['response_time']:.3f}초")

        # 5. 결과 분석
        cache_miss_time = first_call["response_time"]
        cache_hit_time = second_call["response_time"]
        speed_improvement = (
            cache_miss_time / cache_hit_time if cache_hit_time > 0 else 1
        )
        time_saved = cache_miss_time - cache_hit_time

        print(f"\n⚡ 배치 성능 비교:")
        print(f"   캐시 미스 (외부 API): {cache_miss_time:.3f}초")
        print(f"   캐시 히트 (DynamoDB): {cache_hit_time:.3f}초")
        print(f"   성능 향상: {speed_improvement:.2f}배 빠름")
        print(
            f"   시간 절약: {time_saved:.3f}초 ({((time_saved / cache_miss_time) * 100):.1f}%)"
        )

        return {
            "success": True,
            "cities": batch_cities,
            "cached_count": cached_count,
            "cache_miss_time": cache_miss_time,
            "cache_hit_time": cache_hit_time,
            "speed_improvement": speed_improvement,
            "time_saved": time_saved,
        }

    def call_batch_api(self, payload: Dict) -> Dict:
        """배치 날씨 API 호출"""
        url = f"{self.api_endpoint.rstrip('/')}/weather/batch"

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.openweather_api_key,
        }

        start_time = time.time()
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            end_time = time.time()

            response_time = end_time - start_time

            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response_time,
                "data": response.json() if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None,
            }

        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "status_code": None,
                "response_time": end_time - start_time,
                "data": None,
                "error": str(e),
            }

    def run_batch_cache_performance_test(self, iterations: int = 10):
        """배치 캐시 성능 테스트 실행 (10회 반복)"""
        print("\n" + "=" * 80)
        print("🚀 배포된 Weather API 배치 서비스 캐시 성능 테스트")
        print("=" * 80)
        print(f"🔄 반복 횟수: {iterations}회")
        print(
            f"📋 배치 도시: {', '.join(self.test_cities)} (총 {len(self.test_cities)}개)"
        )
        print(f"🔧 API 엔드포인트: {self.api_endpoint}")
        print(f"🗄️  DynamoDB 테이블: {self.dynamodb_table_name}")

        batch_results = []

        # 초기 캐시 전체 삭제
        print(f"\n🗑️  초기 캐시 전체 삭제 중...")
        self.clear_all_cache()

        # 10회 반복 테스트
        for i in range(iterations):
            print(f"\n📍 배치 테스트 진행: {i+1}/{iterations}")
            result = self.test_batch_cache_performance()
            batch_results.append(result)

        # 최종 결과 출력
        self._print_batch_final_results(batch_results)

        # 최종 캐시 전체 삭제
        print(f"\n🗑️  최종 캐시 전체 삭제 중...")
        self.clear_all_cache()

        return batch_results

    def _print_batch_final_results(self, results):
        """배치 테스트 최종 결과 출력"""
        print(f"\n{'='*80}")
        print("🎯 배치 캐시 성능 테스트 최종 결과")
        print(f"{'='*80}")

        successful_tests = [r for r in results if r["success"]]
        failed_tests = [r for r in results if not r["success"]]

        print(
            f"📊 테스트 요약: 전체 {len(results)}회 | 성공 {len(successful_tests)}회 | 실패 {len(failed_tests)}회"
        )

        if successful_tests:
            # 표 헤더
            print(f"\n📋 배치 캐시 성능 비교표 (10개 도시 × 10회 테스트)")
            print("─" * 80)
            print(
                f"{'테스트':^8} │ {'캐시 미스':^12} │ {'캐시 히트':^12} │ {'시간 절약':^12} │ {'성능 향상':^12}"
            )
            print(
                f"{'회차':^8} │ {'(외부 API)':^12} │ {'(DynamoDB)':^12} │ {'(초)':^12} │ {'(배수)':^12}"
            )
            print("─" * 80)

            # 각 테스트 결과
            for i, result in enumerate(successful_tests, 1):
                test_num = f"{i}회차"
                cache_miss = f"{result['cache_miss_time']:.3f}초"
                cache_hit = f"{result['cache_hit_time']:.3f}초"
                time_saved = f"{result['time_saved']:.3f}초"
                improvement = f"{result['speed_improvement']:.1f}배"

                print(
                    f"{test_num:^8} │ {cache_miss:^12} │ {cache_hit:^12} │ {time_saved:^12} │ {improvement:^12}"
                )

            print("─" * 80)

            # 평균 계산
            avg_cache_miss = sum(r["cache_miss_time"] for r in successful_tests) / len(
                successful_tests
            )
            avg_cache_hit = sum(r["cache_hit_time"] for r in successful_tests) / len(
                successful_tests
            )
            avg_improvement = sum(
                r["speed_improvement"] for r in successful_tests
            ) / len(successful_tests)
            avg_time_saved = sum(r["time_saved"] for r in successful_tests) / len(
                successful_tests
            )

            # 평균 행
            avg_miss_str = f"{avg_cache_miss:.3f}초"
            avg_hit_str = f"{avg_cache_hit:.3f}초"
            avg_saved_str = f"{avg_time_saved:.3f}초"
            avg_improvement_str = f"{avg_improvement:.1f}배"

            print(
                f"{'⚡ 평균':^8} │ {avg_miss_str:^12} │ {avg_hit_str:^12} │ {avg_saved_str:^12} │ {avg_improvement_str:^12}"
            )
            print("═" * 80)

            # 성능 검증 결과
            print(f"\n🏆 배치 캐시 성능 검증 결과:")
            performance_improvement_percent = (
                (avg_cache_miss - avg_cache_hit) / avg_cache_miss
            ) * 100

            print(
                f"   📈 평균 응답 시간 개선: {avg_cache_miss:.3f}초 → {avg_cache_hit:.3f}초"
            )
            print(f"   ⚡ 성능 향상률: {performance_improvement_percent:.1f}% 개선")
            print(f"   🚀 속도 향상: {avg_improvement:.1f}배 빠름")
            print(f"   💾 캐시 효과: 평균 {avg_time_saved:.3f}초 시간 절약")

            # 단순 검증: 캐시 히트가 더 빠르면 성공
            if avg_cache_hit < avg_cache_miss:
                print(
                    f"\n✅ 검증 성공: 배치 캐시가 {avg_improvement:.1f}배 더 빠릅니다!"
                )
            else:
                print(f"\n⚠️  검증 실패: 배치 캐시 성능 향상이 없습니다.")

        if failed_tests:
            print(f"\n❌ 실패한 테스트:")
            for i, result in enumerate(failed_tests, 1):
                print(f"   {i}회차: {result.get('error', 'Unknown error')}")

        print(f"\n{'='*80}")

    def run_cache_performance_test(self):
        """전체 캐시 성능 테스트 실행"""
        print("\n" + "=" * 80)
        print("🚀 배포된 Weather API 서비스 캐시 성능 테스트")
        print("=" * 80)
        print(f"📋 테스트 도시: {', '.join(self.test_cities)}")
        print(f"🔧 API 엔드포인트: {self.api_endpoint}")
        print(f"🗄️  DynamoDB 테이블: {self.dynamodb_table_name}")

        # 초기 캐시 전체 삭제
        print(f"\n🗑️  초기 캐시 전체 삭제 중...")
        self.clear_all_cache()

        # 각 도시별 테스트
        for i, city in enumerate(self.test_cities, 1):
            print(f"\n📍 테스트 진행: {i}/{len(self.test_cities)}")
            result = self.test_single_city_cache_performance(city)
            self.results.append(result)

        # 최종 결과 출력
        self._print_final_results()

        # 최종 캐시 전체 삭제
        print(f"\n🗑️  최종 캐시 전체 삭제 중...")
        self.clear_all_cache()

        return self.results

    def _print_final_results(self):
        """최종 결과 출력"""
        print(f"\n{'='*90}")
        print("🎯 최종 캐시 성능 테스트 결과")
        print(f"{'='*90}")

        successful_tests = [r for r in self.results if r["success"]]
        failed_tests = [r for r in self.results if not r["success"]]

        print(
            f"📊 테스트 요약: 전체 {len(self.results)}개 도시 | 성공 {len(successful_tests)}개 | 실패 {len(failed_tests)}개"
        )

        if successful_tests:
            # 표 헤더
            print(f"\n📋 도시별 캐시 성능 비교표")
            print("─" * 90)
            print(
                f"{'도시명':^10} │ {'캐시 미스':^12} │ {'캐시 히트':^12} │ {'시간 절약':^12} │ {'성능 향상':^12}"
            )
            print(
                f"{'':^10} │ {'(외부 API)':^12} │ {'(DynamoDB)':^12} │ {'(초)':^12} │ {'(배수)':^12}"
            )
            print("─" * 90)

            # 각 도시별 결과
            for result in successful_tests:
                city = result["city"][:8]  # 도시명 길이 제한
                cache_miss = f"{result['cache_miss_time']:.3f}초"
                cache_hit = f"{result['cache_hit_time']:.3f}초"
                time_saved = f"{result['time_saved']:.3f}초"
                improvement = f"{result['speed_improvement']:.1f}배"

                print(
                    f"{city:^10} │ {cache_miss:^12} │ {cache_hit:^12} │ {time_saved:^12} │ {improvement:^12}"
                )

            print("─" * 90)

            # 평균 계산
            avg_cache_miss = sum(r["cache_miss_time"] for r in successful_tests) / len(
                successful_tests
            )
            avg_cache_hit = sum(r["cache_hit_time"] for r in successful_tests) / len(
                successful_tests
            )
            avg_improvement = sum(
                r["speed_improvement"] for r in successful_tests
            ) / len(successful_tests)
            avg_time_saved = sum(r["time_saved"] for r in successful_tests) / len(
                successful_tests
            )

            # 평균 행
            avg_miss_str = f"{avg_cache_miss:.3f}초"
            avg_hit_str = f"{avg_cache_hit:.3f}초"
            avg_saved_str = f"{avg_time_saved:.3f}초"
            avg_improvement_str = f"{avg_improvement:.1f}배"

            print(
                f"{'⚡ 평균':^10} │ {avg_miss_str:^12} │ {avg_hit_str:^12} │ {avg_saved_str:^12} │ {avg_improvement_str:^12}"
            )
            print("═" * 90)

            # 성능 검증 결과
            print(f"\n🏆 캐시 성능 검증 결과:")
            performance_improvement_percent = (
                (avg_cache_miss - avg_cache_hit) / avg_cache_miss
            ) * 100

            print(
                f"   📈 평균 응답 시간 개선: {avg_cache_miss:.3f}초 → {avg_cache_hit:.3f}초"
            )
            print(f"   ⚡ 성능 향상률: {performance_improvement_percent:.1f}% 개선")
            print(f"   🚀 속도 향상: {avg_improvement:.1f}배 빠름")
            print(f"   💾 캐시 효과: 평균 {avg_time_saved:.3f}초 시간 절약")

            # 검증 기준
            if avg_improvement >= 2.0:
                print(
                    f"\n✅ 검증 성공: 캐시로 인한 성능 향상이 {avg_improvement:.1f}배로 충분합니다!"
                )
                print(
                    f"   🎯 기준: 2배 이상 성능 향상 → 결과: {avg_improvement:.1f}배 ✓"
                )
            else:
                print(
                    f"\n⚠️  검증 주의: 캐시 성능 향상이 {avg_improvement:.1f}배로 기대보다 낮습니다."
                )
                print(f"   🎯 기준: 2배 이상 성능 향상 → 결과: {avg_improvement:.1f}배")

        if failed_tests:
            print(f"\n❌ 실패한 테스트:")
            for result in failed_tests:
                print(f"   {result['city']}: {result.get('error', 'Unknown error')}")

        print(f"\n{'='*90}")


# Pytest 테스트 함수
def test_cache_performance():
    """캐시 성능 테스트"""
    test_instance = SimpleCacheTest()
    results = test_instance.run_cache_performance_test()

    # 기본 검증
    successful_results = [r for r in results if r["success"]]
    assert len(successful_results) > 0, "모든 테스트가 실패했습니다"

    # 평균 성능 계산
    avg_cache_miss = sum(r["cache_miss_time"] for r in successful_results) / len(
        successful_results
    )
    avg_cache_hit = sum(r["cache_hit_time"] for r in successful_results) / len(
        successful_results
    )

    # 단순 검증: 캐시 히트가 캐시 미스보다 빠르면 성공
    assert (
        avg_cache_hit < avg_cache_miss
    ), f"캐시 성능 향상 없음: 캐시 미스 {avg_cache_miss:.3f}초 vs 캐시 히트 {avg_cache_hit:.3f}초"

    improvement = avg_cache_miss / avg_cache_hit if avg_cache_hit > 0 else 1
    print(f"\n✅ 캐시 성능 검증 통과!")
    print(f"   캐시 미스 평균: {avg_cache_miss:.3f}초")
    print(f"   캐시 히트 평균: {avg_cache_hit:.3f}초")
    print(f"   성능 향상: {improvement:.1f}배 빠름")


def test_batch_cache_performance():
    """배치 캐시 성능 테스트"""
    test_instance = SimpleCacheTest()
    results = test_instance.run_batch_cache_performance_test()

    # 기본 검증
    successful_results = [r for r in results if r["success"]]
    assert len(successful_results) > 0, "모든 배치 테스트가 실패했습니다"

    # 평균 성능 계산
    avg_cache_miss = sum(r["cache_miss_time"] for r in successful_results) / len(
        successful_results
    )
    avg_cache_hit = sum(r["cache_hit_time"] for r in successful_results) / len(
        successful_results
    )

    # 단순 검증: 캐시 히트가 캐시 미스보다 빠르면 성공
    assert (
        avg_cache_hit < avg_cache_miss
    ), f"배치 캐시 성능 향상 없음: 캐시 미스 {avg_cache_miss:.3f}초 vs 캐시 히트 {avg_cache_hit:.3f}초"

    improvement = avg_cache_miss / avg_cache_hit if avg_cache_hit > 0 else 1
    print(f"\n✅ 배치 캐시 성능 검증 통과!")
    print(f"   캐시 미스 평균: {avg_cache_miss:.3f}초")
    print(f"   캐시 히트 평균: {avg_cache_hit:.3f}초")
    print(f"   성능 향상: {improvement:.1f}배 빠름")


if __name__ == "__main__":
    # 직접 실행
    print("🚀 배포된 서비스 캐시 성능 테스트 시작\n")
    try:
        test_instance = SimpleCacheTest()
        test_instance.run_cache_performance_test()
        print("\n✅ 테스트 완료!")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
