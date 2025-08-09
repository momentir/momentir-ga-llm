# KoNLPy 설정 및 문제 해결 가이드

## 개요

KoNLPy는 한국어 자연어 처리를 위한 Python 라이브러리로, 형태소 분석 기능을 제공합니다. 하지만 Java 런타임 환경이 필요하여 때로는 설정에 문제가 발생할 수 있습니다.

## 현재 구현된 안전장치

### 1. 자동 Fallback 시스템
- KoNLPy 초기화 실패 시 자동으로 패턴 매칭 방식으로 전환
- 애플리케이션 시작은 KoNLPy 없이도 정상 작동
- 실행 중 Java 오류 발생 시 KoNLPy 비활성화

### 2. 지연 초기화 (Lazy Loading)
- 애플리케이션 시작 시 KoNLPy를 즉시 로드하지 않음
- 실제 형태소 분석이 필요한 시점에만 초기화 시도
- 초기화 실패 시에도 다른 기능에 영향 없음

### 3. 환경변수 제어
- `DISABLE_KONLPY=true` 환경변수로 KoNLPy 완전 비활성화 가능
- 시작 스크립트에서 import 검증 시 KoNLPy 임시 비활성화

## 사용 상황별 가이드

### 상황 1: Java 런타임 오류 발생
```
# A fatal error has been detected by the Java Runtime Environment:
# SIGBUS (0xa) at pc=0x...
```

**해결 방법:**
1. 환경변수로 KoNLPy 비활성화:
```bash
export DISABLE_KONLPY=true
./scripts/02-envrinment/02-start-local.sh
```

2. 또는 .env 파일에 추가:
```
DISABLE_KONLPY=true
```

### 상황 2: KoNLPy 완전 제거하고 싶은 경우
1. requirements.txt에서 konlpy 제거:
```bash
pip uninstall konlpy
```

2. Java 의존성들도 제거 (선택적):
```bash
pip uninstall JPype1 lxml
```

### 상황 3: KoNLPy를 사용하고 싶은 경우
1. Java 설치 확인:
```bash
java -version
```

2. macOS의 경우:
```bash
brew install openjdk@11
export JAVA_HOME=/opt/homebrew/opt/openjdk@11
```

3. Ubuntu의 경우:
```bash
sudo apt-get install openjdk-11-jdk
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
```

4. KoNLPy 테스트:
```bash
python -c "
import os
os.environ['DISABLE_KONLPY'] = 'false'
from konlpy.tag import Okt
okt = Okt()
print(okt.pos('안녕하세요'))
"
```

## 성능 비교

### 패턴 매칭 방식 (KoNLPy 비활성화)
- **장점**: 
  - 빠른 초기화 (0.01초)
  - Java 의존성 없음
  - 안정적 동작
  - 메모리 사용량 적음

- **단점**: 
  - 제한적인 한국어 분석
  - 정확도 다소 낮음
  - 복잡한 문법 구조 분석 어려움

### KoNLPy 방식
- **장점**: 
  - 정확한 형태소 분석
  - 품사 태깅 지원
  - 복잡한 한국어 구조 분석 가능

- **단점**: 
  - 초기화 시간 오래 걸림 (1-3초)
  - Java 런타임 필요
  - 메모리 사용량 많음
  - 환경 설정 복잡

## 현재 상태 확인

### 1. API를 통한 확인
```bash
curl http://localhost:8000/api/lcel-sql/health
```

응답에서 `intent_classifier` 상태를 확인할 수 있습니다.

### 2. 로그를 통한 확인
애플리케이션 시작 시 다음 로그들을 확인하세요:

```
# KoNLPy 사용 가능한 경우
INFO:app.services.intent_classifier:✅ KoNLPy 사용 가능 확인 완료

# KoNLPy 비활성화된 경우
WARNING:app.services.intent_classifier:KoNLPy 사용 불가: ... 기본 패턴 매칭을 사용합니다.

# 환경변수로 비활성화된 경우
INFO:app.services.intent_classifier:KoNLPy가 환경변수로 비활성화되었습니다.
```

### 3. 프로그래밍적 확인
```python
from app.services.intent_classifier import korean_intent_classifier

print(f"KoNLPy 사용 상태: {korean_intent_classifier.use_konlpy}")
print(f"KoNLPy 설정: {korean_intent_classifier.use_konlpy_preference}")
```

## 문제 해결 단계

### 단계 1: 기본 진단
```bash
# Java 설치 확인
java -version

# Python 환경 확인
python -c "import sys; print(sys.version)"

# 라이브러리 설치 확인
pip list | grep konlpy
```

### 단계 2: 환경변수 설정
```bash
# KoNLPy 비활성화 (임시)
export DISABLE_KONLPY=true

# KoNLPy 활성화 (Java 문제 해결 후)
unset DISABLE_KONLPY
```

### 단계 3: Java 환경 설정 (KoNLPy 사용 원하는 경우)
```bash
# macOS
export JAVA_HOME=$(/usr/libexec/java_home -v 11)

# Linux
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64

# 설정 저장
echo 'export JAVA_HOME=$(/usr/libexec/java_home -v 11)' >> ~/.zshrc  # macOS
echo 'export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64' >> ~/.bashrc  # Linux
```

### 단계 4: KoNLPy 재설치 (필요시)
```bash
pip uninstall konlpy jpype1
pip install konlpy
```

## 운영 환경 권장사항

### 개발 환경
- KoNLPy 사용 권장 (높은 정확도)
- Java 11 또는 17 사용
- 충분한 메모리 할당 (최소 2GB)

### 프로덕션 환경
- **안정성 우선**: `DISABLE_KONLPY=true` 설정
- **정확도 우선**: KoNLPy 사용, Java 환경 안정화 필수
- 메모리 모니터링 필수
- Fallback 로직 활용

### CI/CD 환경
- `DISABLE_KONLPY=true` 설정 권장
- Java 설치 과정 생략 가능
- 빠른 테스트 실행

## FAQ

**Q: KoNLPy 없이 한국어 분석이 가능한가요?**
A: 네, 패턴 매칭 방식으로 기본적인 한국어 분석이 가능합니다. 정확도는 다소 떨어지지만 실용적 수준입니다.

**Q: 성능 차이가 얼마나 나나요?**
A: 패턴 매칭은 약 0.1초, KoNLPy는 약 0.5-1초 소요됩니다. 정확도는 KoNLPy가 약 10-15% 높습니다.

**Q: Java 버전이 중요한가요?**
A: Java 11 이상 권장합니다. 너무 최신 버전(21+)은 호환성 문제가 있을 수 있습니다.

**Q: Docker 환경에서 사용하려면?**
A: Dockerfile에 Java 설치 추가하거나, `DISABLE_KONLPY=true` 설정 권장합니다.

**Q: 런타임 중 KoNLPy 활성화/비활성화가 가능한가요?**
A: 아니요, 애플리케이션 재시작이 필요합니다.

## 참고 자료

- [KoNLPy 공식 문서](https://konlpy.org/ko/latest/)
- [Java 설치 가이드](https://docs.oracle.com/en/java/javase/11/install/)
- [JPype1 문제 해결](https://jpype.readthedocs.io/en/latest/)
- [Intent Classifier 사용 가이드](./INTENT_CLASSIFIER_GUIDE.md)

## 업데이트 로그

- **v1.0**: 기본 KoNLPy 통합
- **v2.0**: 지연 초기화 및 Fallback 시스템 추가
- **v2.1**: 환경변수 제어 기능 추가
- **v2.2**: 시작 스크립트 안정화