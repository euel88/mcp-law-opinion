# K-Law Assistant - AI 법률 검토 지원 시스템

⚖️ 법령, 판례, 행정규칙 등을 종합 검토하여 AI가 법률 자문을 제공하는 통합 시스템

## 🌟 주요 기능

### 1. 통합 법률자료 검색
- **법령**: 현행법령, 시행일법령, 영문법령, 법령연혁
- **판례**: 대법원/하급법원 판례, 헌재결정례
- **행정해석**: 법령해석례, 행정규칙, 위원회 결정문
- **기타**: 자치법규, 조약, 별표서식, 법령용어

### 2. AI 법률 분석
- **자동 질문 유형 판별**: 단순 검색 vs AI 분석 자동 구분
- **GPT 모델 선택**: GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo
- **서비스 유형**:
  - 법률 정보 제공
  - 계약서 검토
  - 법률자문의견서 작성

### 3. 스마트 기능
- 검색 이력 관리
- 즐겨찾기
- 캐싱을 통한 빠른 응답
- 빠른 검색 버튼

## 🚀 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/k-law-assistant.git
cd k-law-assistant
```

### 2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정
```bash
# .env.example을 .env로 복사
cp .env.example .env

# .env 파일을 편집하여 API 키 입력
# LAW_API_KEY=your_law_api_key
# OPENAI_API_KEY=sk-your_openai_api_key
```

### 5. 실행
```bash
streamlit run main.py
```

## 🔑 API 키 발급

### 법제처 Open API
1. [법제처 오픈API](https://open.law.go.kr) 접속
2. 회원가입 및 로그인
3. 마이페이지 → API 신청
4. 발급받은 OC 키를 `.env` 파일에 입력

### OpenAI API
1. [OpenAI Platform](https://platform.openai.com) 접속
2. 회원가입 및 로그인
3. API keys 메뉴에서 새 키 생성
4. 발급받은 키를 `.env` 파일에 입력

## 📁 프로젝트 구조

```
k-law-assistant/
├── main.py                      # Streamlit 메인 애플리케이션
├── common_api.py               # 공통 API 클라이언트
├── legal_prompts_module.py    # AI 프롬프트 템플릿
├── law_module.py               # 법령 검색 모듈
├── committee_module.py         # 위원회 결정문 모듈
├── case_module.py              # 판례/헌재결정 모듈
├── treaty_admin_module.py      # 조약/행정규칙 모듈
├── requirements.txt            # 패키지 의존성
├── .env                        # 환경변수 (생성 필요)
├── .env.example                # 환경변수 예시
└── README.md                   # 프로젝트 설명서
```

## 💡 사용 방법

### 1. 단순 검색
- 통합 검색 탭에서 검색어 입력
- 시스템이 자동으로 단순 검색으로 판별
- 법령, 판례 등 직접 검색 결과 표시

### 2. AI 법률 분석
- AI 법률 분석 탭 선택
- 서비스 유형 선택 (정보제공/계약검토/자문의견서)
- 질문 입력 후 AI 분석 시작
- GPT가 관련 자료를 종합하여 분석 제공

### 3. 계약서 검토
- AI 법률 분석 탭에서 "계약서 검토" 선택
- 계약서 내용 붙여넣기
- AI가 독소조항 발견 및 수정안 제시

## 🎯 활용 예시

### 예시 1: 법령 검색
```
검색어: "도로교통법 음주운전"
결과: 도로교통법 관련 조문, 판례, 행정해석 표시
```

### 예시 2: AI 법률 상담
```
질문: "회사에서 갑자기 해고 통보를 받았는데 어떻게 대응해야 하나요?"
결과: 근로기준법 분석, 관련 판례 검토, 대응 방안 제시
```

### 예시 3: 계약서 검토
```
입력: 부동산 매매계약서 전문
결과: 불공정 조항 발견, 리스크 평가, 수정안 제시
```

## ⚖️ 면책 고지

**중요**: 본 시스템은 AI가 작성한 참고자료를 제공하며, 법률자문이 아닙니다.
- 법령, 판례, 행정규칙 등을 종합 검토하나, 구체적 사안은 변호사 상담 필요
- AI 분석 결과는 참고용이며, 법적 효력이 없음
- 중요한 법적 결정 전 반드시 전문가 검토 필요

## 🔧 문제 해결

### API 키 오류
- `.env` 파일의 API 키가 올바른지 확인
- 사이드바의 API 설정에서 직접 입력 가능

### 검색 결과 없음
- 법제처 API 서버 상태 확인
- 검색어를 단순하게 수정 (예: "도로교통법" → "교통")

### AI 분석 오류
- OpenAI API 크레딧 확인
- GPT 모델을 다른 것으로 변경 시도

## 📊 성능 최적화

- **캐싱**: 동일 검색은 캐시에서 빠르게 로드
- **병렬 처리**: 여러 API 동시 호출로 속도 향상
- **모델 선택**: 간단한 질문은 GPT-3.5로 비용 절감

## 🤝 기여 방법

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 👨‍💻 개발자

- 개발: K-Law Assistant Team
- 문의: support@klawassistant.com

## 🙏 감사의 말

- 법제처 Open API 제공
- OpenAI GPT API
- Streamlit 프레임워크

---

**Version**: 1.0.0  
**Last Updated**: 2025-01-01