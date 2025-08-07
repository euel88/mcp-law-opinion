"""
법률 검토 프롬프트 템플릿 모듈
AI 변호사 GPT 통합 지침 v5.0
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ServiceType(Enum):
    """서비스 유형"""
    LEGAL_INFO = "legal_info"          # 법률 정보 제공
    CONTRACT_REVIEW = "contract_review" # 계약서 검토
    LEGAL_OPINION = "legal_opinion"     # 법률자문의견서


class RiskLevel(Enum):
    """리스크 등급"""
    HIGH = "🔴 High"
    MEDIUM = "🟠 Medium"
    LOW = "🟡 Low"


@dataclass
class LegalPromptTemplates:
    """법률 검토용 프롬프트 템플릿"""
    
    # ===== 1. 시스템 프롬프트 =====
    SYSTEM_PROMPT = """당신은 **AI 변호사 GPT**입니다.

## 역할 정의
- 전문 법률자문의견서 작성 전문가이자 가상의 변호사로서, 실제 변호사의 사고 방식(사실관계 파악 → Issue-Spotting → 법리 검토 → 위험측정 → 전략 수립)을 완벽히 구현합니다.
- 의뢰인의 사실관계·증빙자료·업계 관행을 면밀히 조사·검증한 뒤, **법령, 판례, 헌재결정례, 행정규칙, 자치법규, 법령해석례, 행정심판례, 위원회결정문, 조약** 등 모든 법적 근거를 종합 분석하여 실무적이고 전략적인 법률 솔루션을 제공합니다.

## 핵심 원칙
1. **증거 우선주의**: 구두 진술만으로 판단하지 않고, 물적 증빙 확보를 최우선으로 함
2. **근거 기반 분석**: 모든 법적 주장은 반드시 출처를 명시하며, 최신성을 교차 검증
3. **사용자 중심 접근**: 모든 쟁점을 의뢰인 관점에서 유리/불리로 평가
4. **IRAC 방법론**: Issue → Rule → Application → Conclusion 구조로 체계적 분석
5. **리스크 계층화**: 발견된 문제를 리스크 매트릭스(High/Medium/Low)로 등급화
6. **실행가능한 해결책**: 법적·경제적·시간적 비용을 비교한 최소 2가지 이상의 대안 제시
7. **통합적 법률 검토**: 법령뿐만 아니라 판례, 헌재결정례, 행정규칙, 자치법규, 법령해석례, 행정심판례, 위원회결정문 등 모든 법적 근거를 종합 검토

## 필수 고지사항
⚖️ 본 내용은 AI가 작성한 참고자료이며, 법률자문이 아닙니다.
법령, 판례, 행정규칙, 법령해석 등을 종합 검토하였으나,
구체적인 사안에 대해서는 반드시 변호사 등 전문가의 검토가 필요합니다."""

    # ===== 2. 서비스별 사용자 프롬프트 템플릿 =====
    
    # 2.1 법률 정보 제공
    LEGAL_INFO_PROMPT = """
## 질문
{query}

## 요청사항
위 질문에 대해 다음 형식으로 답변해주세요:

### 1. 핵심 답변 (3줄 요약)

### 2. 관련 법령
- 주요 법령 및 조항
- 하위 법령 (시행령, 시행규칙)

### 3. 관련 판례
- 대법원 판례
- 하급법원 판례 (필요시)

### 4. 관련 행정해석
- 법령해석례
- 행정규칙 (고시, 훈령, 예규)
- 위원회 결정문 (해당시)

### 5. 실무적 조언
- 주의사항
- 추가 검토사항

## 참고자료
{context}
"""

    # 2.2 계약서 검토
    CONTRACT_REVIEW_PROMPT = """
## 계약서 검토 요청

### 계약 배경
- 계약 당사자: {parties}
- 계약 목적: {purpose}
- 주요 우려사항: {concerns}

### 계약서 내용
{contract_text}

## 검토 요청사항
다음 체크리스트에 따라 계약서를 전수 검토하고 보고서를 작성해주세요:

### 1. Red Flag 분석 (독소조항/불공정조항)
- 발견된 문제점을 리스크 등급(High/Medium/Low)으로 분류
- 각 문제점에 대한 법적 근거 제시

### 2. 법령 위반 여부 검토
- 강행법규 위반 여부
- 관련 판례 기준 검토
- 행정규칙/가이드라인 준수 여부

### 3. 조항별 상세 분석
| 조항 | 내용 요약 | 리스크 | 법적 근거 | 수정 제안 |
|------|-----------|---------|-----------|-----------|

### 4. 협상 전략
- 우선순위별 수정 요구사항
- 협상 포인트 및 대안

### 5. 개선안
- 수정 조항 제시

## 관련 법률자료
{legal_references}
"""

    # 2.3 법률자문의견서 작성
    LEGAL_OPINION_PROMPT = """
## 법률자문의견서 작성 요청

### 의뢰인 정보
{client_info}

### 질의사항
{questions}

### 사실관계
{facts}

## 작성 요청사항
다음 구조에 따라 전문적인 법률자문의견서를 작성해주세요:

### 제목
[핵심 쟁점과 관계 법령을 포함한 20자 내외]

### 관련 법률자료 일람표
| 구분 | 조항·번호 | 제목 | 주요 취지 | 비고 |
|------|-----------|------|-----------|------|

### 사실관계 Timeline
[시간순 정리]

### 쟁점 및 법리 검토 (IRAC 방법론)

#### 쟁점 1: [쟁점명]
- **Issue**: 구체적 법적 문제
- **Rule**: 
  - 관련 법령: 
  - 대법원 판례: 
  - 행정규칙: 
  - 법령해석례: 
- **Application**: 사실관계 포섭
- **Conclusion**: 잠정 결론
- **리스크 등급**: High/Medium/Low

### 대응 방안 (Action Plan)

#### 전략 1 (권장안)
- 개요
- 법적 근거
- 절차 및 예상 기간
- 예상 비용 및 성공 가능성

#### 전략 2 (대안)
- 개요 및 장단점

### 결론
[3줄 요약]

### 작성일자 및 서명
2025년 8월 7일
AI 변호사 GPT

⚖️ 본 의견서는 AI가 작성한 참고자료이며, 최종 결정 전 반드시 변호사 등 전문가의 검토가 필요합니다.

## 검토한 법률자료
{legal_materials}
"""

    # ===== 3. 통합 법률자료 검토 프롬프트 =====
    LEGAL_RESEARCH_PROMPT = """
## 법률자료 검색 및 검토 요청

### 검색 키워드
{keywords}

### 검토 요청사항
다음 우선순위에 따라 법률자료를 검색하고 분석해주세요:

1. **1차 검토**: 관련 법령 및 하위법령 (시행령, 시행규칙)
2. **2차 검토**: 대법원 판례 및 헌재결정례
3. **3차 검토**: 소관부처 법령해석례 및 행정규칙
4. **4차 검토**: 관련 위원회 결정문 및 행정심판례
5. **5차 검토**: 하급법원 판례 및 자치법규

### 검토 결과 정리
| 자료 유형 | 검색 결과 | 주요 내용 | 관련성 |
|-----------|-----------|-----------|---------|
| 법령 | | | |
| 판례 | | | |
| 헌재결정 | | | |
| 행정규칙 | | | |
| 법령해석 | | | |
| 위원회결정 | | | |
| 행정심판 | | | |
| 자치법규 | | | |

### 종합 분석
- 시간적 우선순위 (최신 자료 우선)
- 효력 우선순위 (법령 > 판례 > 행정규칙 > 해석례)
- 상충 내용 정리
"""

    # ===== 4. IRAC 분석 프롬프트 =====
    IRAC_ANALYSIS_PROMPT = """
## IRAC 분석 요청

### 분석 대상
{issue_description}

### 관련 사실관계
{facts}

## 분석 요청사항
다음 IRAC 구조에 따라 체계적으로 분석해주세요:

### Issue (쟁점)
- 핵심 법적 문제를 명확히 정의
- 하위 쟁점 구분

### Rule (규범)
- 관련 법령 조항
- 대법원 판례
- 헌재 결정례
- 행정규칙 및 가이드라인
- 법령해석례
- 위원회 결정문

### Application (적용)
- 사실관계를 법규범에 포섭
- 유사 사례와 비교
- 반대 논리 검토

### Conclusion (결론)
- 법적 판단
- 리스크 평가 (High/Medium/Low)
- 대안 제시

## 참고 법률자료
{legal_materials}
"""

    # ===== 5. 리스크 평가 프롬프트 =====
    RISK_ASSESSMENT_PROMPT = """
## 리스크 평가 요청

### 평가 대상
{subject}

### 관련 사실관계
{facts}

## 평가 요청사항
다음 기준에 따라 리스크를 평가해주세요:

### 리스크 매트릭스
| 쟁점 | 발생가능성 | 예상 손실 | 법적 판단 | 관련 법률자료 | 리스크 등급 | 대응 우선순위 |
|------|------------|----------|----------|--------------|-------------|--------------|

### 등급별 기준
- 🔴 **High**: 치명적 위험 (매출 20% 이상 손실, 형사처벌 가능, 영업정지 위험)
  - 법령 위반, 대법원 판례 반대, 시정명령 대상
  
- 🟠 **Medium**: 상당한 위험 (매출 5-20% 손실, 민사소송 패소 위험)
  - 하급심 판례 분리, 법령해석 상충, 행정지도 대상
  
- 🟡 **Low**: 관리가능 위험 (매출 5% 미만, 경미한 불이익)
  - 업계 관행과 차이, 권고사항 수준

### 대응 방안
각 리스크별 구체적인 대응 전략 제시

## 검토 법률자료
{legal_references}
"""

    # ===== 6. 체크리스트 템플릿 =====
    CONTRACT_CHECKLIST = """
## 계약서 검토 체크리스트

### 일반 계약 공통 체크포인트
- [ ] 계약 성립: 청약·승낙, 계약 체결 능력, 대리권
- [ ] 계약 내용: 확정성, 실현가능성, 적법성
- [ ] 이행·변제: 이행 방법, 시기, 장소, 비용부담
- [ ] 담보·보증: 담보 범위, 보증인 자격, 물적담보
- [ ] 채무불이행: 지연·불완전이행, 이행불능
- [ ] 위험부담: 위험 이전 시기, 불가항력

### 규제 Compliance 체크
- [ ] 공정거래법 (불공정약관, 거래상 지위남용)
- [ ] 하도급법 (부당 단가인하, 기술자료 요구)
- [ ] 개인정보보호법 (수집·이용 동의, 위탁)
- [ ] 전자상거래법 (청약철회, 표시광고)
- [ ] 산업별 특별법
"""

    # ===== 7. 응답 구조 템플릿 =====
    RESPONSE_TEMPLATES = {
        "증거_부족": """
현재 제공된 정보만으로는 정확한 법적 판단이 어렵습니다.
다음 자료를 추가로 제공해 주시면 법령, 판례, 행정해석 등을 
종합하여 더 구체적인 검토가 가능합니다:
- [ ] 계약서 원본
- [ ] 관련 이메일/문자
- [ ] 거래 내역
- [ ] 행정기관 통지서
""",
        
        "복잡한_사안": """
이 사안은 여러 법적 쟁점이 얽혀 있어 단계별로 검토하겠습니다.
법령, 대법원 판례, 헌재결정, 관련 부처 해석례, 위원회 결정 등을
모두 검토하여 종합적인 의견을 드리겠습니다.
먼저 가장 중요한 [쟁점1]부터 살펴보고, 순차적으로 분석하겠습니다.
""",
        
        "면책_고지": """
⚖️ 본 내용은 AI가 작성한 참고자료이며, 법률자문이 아닙니다.
법령, 판례, 행정규칙, 법령해석 등을 종합 검토하였으나,
구체적인 사안에 대해서는 반드시 변호사 등 전문가의 검토가 필요합니다.
"""
    }


class PromptBuilder:
    """프롬프트 빌더 클래스"""
    
    def __init__(self):
        self.templates = LegalPromptTemplates()
    
    def build_prompt(self, 
                    service_type: ServiceType,
                    query: str,
                    context: Optional[Dict] = None,
                    **kwargs) -> tuple[str, str]:
        """
        서비스 유형에 따른 프롬프트 생성
        
        Args:
            service_type: 서비스 유형
            query: 사용자 질문
            context: 법률 자료 컨텍스트
            **kwargs: 추가 파라미터
            
        Returns:
            (system_prompt, user_prompt) 튜플
        """
        system_prompt = self.templates.SYSTEM_PROMPT
        
        # 컨텍스트 포맷팅
        formatted_context = self._format_context(context) if context else ""
        
        # 서비스별 프롬프트 선택
        if service_type == ServiceType.LEGAL_INFO:
            user_prompt = self.templates.LEGAL_INFO_PROMPT.format(
                query=query,
                context=formatted_context
            )
        
        elif service_type == ServiceType.CONTRACT_REVIEW:
            user_prompt = self.templates.CONTRACT_REVIEW_PROMPT.format(
                parties=kwargs.get('parties', ''),
                purpose=kwargs.get('purpose', ''),
                concerns=kwargs.get('concerns', ''),
                contract_text=kwargs.get('contract_text', query),
                legal_references=formatted_context
            )
        
        elif service_type == ServiceType.LEGAL_OPINION:
            user_prompt = self.templates.LEGAL_OPINION_PROMPT.format(
                client_info=kwargs.get('client_info', ''),
                questions=query,
                facts=kwargs.get('facts', ''),
                legal_materials=formatted_context
            )
        
        else:
            # 기본 프롬프트
            user_prompt = f"질문: {query}\n\n관련 자료:\n{formatted_context}"
        
        return system_prompt, user_prompt
    
    def build_irac_prompt(self, issue: str, facts: str, materials: Dict) -> tuple[str, str]:
        """IRAC 분석 프롬프트 생성"""
        system_prompt = self.templates.SYSTEM_PROMPT
        user_prompt = self.templates.IRAC_ANALYSIS_PROMPT.format(
            issue_description=issue,
            facts=facts,
            legal_materials=self._format_context(materials)
        )
        return system_prompt, user_prompt
    
    def build_risk_assessment_prompt(self, subject: str, facts: str, references: Dict) -> tuple[str, str]:
        """리스크 평가 프롬프트 생성"""
        system_prompt = self.templates.SYSTEM_PROMPT
        user_prompt = self.templates.RISK_ASSESSMENT_PROMPT.format(
            subject=subject,
            facts=facts,
            legal_references=self._format_context(references)
        )
        return system_prompt, user_prompt
    
    def build_research_prompt(self, keywords: List[str]) -> tuple[str, str]:
        """법률자료 검색 프롬프트 생성"""
        system_prompt = self.templates.SYSTEM_PROMPT
        user_prompt = self.templates.LEGAL_RESEARCH_PROMPT.format(
            keywords=", ".join(keywords)
        )
        return system_prompt, user_prompt
    
    def _format_context(self, context: Dict) -> str:
        """
        컨텍스트 정보를 텍스트로 포맷팅
        
        Args:
            context: 법률 자료 딕셔너리
            
        Returns:
            포맷팅된 텍스트
        """
        formatted = []
        
        # 법령
        if 'laws' in context and context['laws']:
            formatted.append("### 관련 법령")
            for law in context['laws'][:5]:
                formatted.append(f"- 「{law.get('법령명', '')}」")
                if '조문내용' in law:
                    formatted.append(f"  {law['조문내용'][:200]}...")
        
        # 판례
        if 'cases' in context and context['cases']:
            formatted.append("\n### 관련 판례")
            for case in context['cases'][:5]:
                formatted.append(f"- {case.get('사건명', '')} ({case.get('법원명', '')} {case.get('선고일자', '')})")
                if '판시사항' in case:
                    formatted.append(f"  {case['판시사항'][:200]}...")
        
        # 헌재결정례
        if 'constitutional_decisions' in context and context['constitutional_decisions']:
            formatted.append("\n### 헌재결정례")
            for decision in context['constitutional_decisions'][:3]:
                formatted.append(f"- {decision.get('사건번호', '')} ({decision.get('종국일자', '')})")
                if '결정요지' in decision:
                    formatted.append(f"  {decision['결정요지'][:200]}...")
        
        # 행정규칙
        if 'admin_rules' in context and context['admin_rules']:
            formatted.append("\n### 행정규칙")
            for rule in context['admin_rules'][:3]:
                formatted.append(f"- {rule.get('행정규칙명', '')} ({rule.get('발령일자', '')})")
        
        # 법령해석례
        if 'interpretations' in context and context['interpretations']:
            formatted.append("\n### 법령해석례")
            for interp in context['interpretations'][:3]:
                formatted.append(f"- {interp.get('안건명', '')} ({interp.get('해석기관명', '')})")
                if '회답' in interp:
                    formatted.append(f"  {interp['회답'][:200]}...")
        
        # 위원회 결정문
        if 'committee_decisions' in context and context['committee_decisions']:
            formatted.append("\n### 위원회 결정문")
            for decision in context['committee_decisions'][:3]:
                formatted.append(f"- {decision.get('사건명', '')} ({decision.get('위원회명', '')})")
                if '주문' in decision:
                    formatted.append(f"  주문: {decision['주문'][:150]}...")
        
        # 행정심판례
        if 'admin_tribunals' in context and context['admin_tribunals']:
            formatted.append("\n### 행정심판례")
            for tribunal in context['admin_tribunals'][:3]:
                formatted.append(f"- {tribunal.get('사건명', '')} ({tribunal.get('의결일자', '')})")
                if '재결요지' in tribunal:
                    formatted.append(f"  {tribunal['재결요지'][:150]}...")
        
        return "\n".join(formatted)
    
    def get_response_template(self, template_type: str) -> str:
        """응답 템플릿 반환"""
        return self.templates.RESPONSE_TEMPLATES.get(template_type, "")
    
    def get_checklist(self) -> str:
        """계약서 검토 체크리스트 반환"""
        return self.templates.CONTRACT_CHECKLIST


# 인용 형식 헬퍼 함수
def format_legal_citation(citation_type: str, **kwargs) -> str:
    """
    법률 인용 형식 생성
    
    Args:
        citation_type: 인용 유형 (law, case, constitutional, admin_rule, interpretation, committee, tribunal)
        **kwargs: 인용에 필요한 정보
        
    Returns:
        형식화된 인용 문자열
    """
    citations = {
        "law": "「{law_name}」 제{article}조{paragraph}",
        "case": "대법원 {date} 선고 {case_no} 판결",
        "constitutional": "헌법재판소 {date} {case_no} 결정",
        "admin_rule": "{ministry} {rule_type} 제{rule_no}호 ({date})",
        "interpretation": "{agency} 법령해석 {interp_no} ({date})",
        "committee": "{committee} 의결 제{decision_no}호 ({date})",
        "tribunal": "{tribunal} {case_no} ({date})",
        "local_law": "{region} {law_type} 제{law_no}호 ({date})"
    }
    
    template = citations.get(citation_type, "")
    if template:
        # 제공된 값이 있는 경우만 포맷팅
        try:
            return template.format(**kwargs)
        except KeyError:
            return str(kwargs)  # 포맷팅 실패시 원본 반환
    return ""


# 서비스 유형 자동 판별 함수
def detect_service_type(query: str) -> ServiceType:
    """
    사용자 질문에서 서비스 유형 자동 판별
    
    Args:
        query: 사용자 질문
        
    Returns:
        서비스 유형
    """
    query_lower = query.lower()
    
    # 계약서 검토 키워드
    contract_keywords = ['계약서', '계약 검토', '독소조항', '불공정', '조항 분석', '계약 위험']
    if any(keyword in query_lower for keyword in contract_keywords):
        return ServiceType.CONTRACT_REVIEW
    
    # 법률자문의견서 키워드
    opinion_keywords = ['법률 의견', '자문의견서', '법적 검토', '사안 검토', '대응 방안', '법률자문']
    if any(keyword in query_lower for keyword in opinion_keywords):
        return ServiceType.LEGAL_OPINION
    
    # 기본값: 법률 정보 제공
    return ServiceType.LEGAL_INFO


# 테스트 코드
if __name__ == "__main__":
    print("=== 법률 프롬프트 모듈 테스트 ===\n")
    
    # 프롬프트 빌더 초기화
    builder = PromptBuilder()
    
    # 1. 법률 정보 프롬프트 테스트
    print("1. 법률 정보 제공 프롬프트")
    system, user = builder.build_prompt(
        ServiceType.LEGAL_INFO,
        "음주운전 처벌 기준이 어떻게 되나요?",
        {"laws": [{"법령명": "도로교통법", "조문내용": "음주운전 관련 조항..."}]}
    )
    print(f"System Prompt Length: {len(system)}")
    print(f"User Prompt Length: {len(user)}\n")
    
    # 2. 서비스 유형 자동 판별 테스트
    print("2. 서비스 유형 자동 판별")
    test_queries = [
        "계약서 검토해주세요",
        "법률자문의견서 작성 부탁드립니다",
        "상속세는 어떻게 계산하나요?"
    ]
    for query in test_queries:
        service_type = detect_service_type(query)
        print(f"- '{query}' → {service_type.value}")
    
    # 3. 법률 인용 형식 테스트
    print("\n3. 법률 인용 형식")
    citation = format_legal_citation(
        "case",
        date="2023. 5. 12.",
        case_no="2021다12345"
    )
    print(f"판례 인용: {citation}")
    
    citation = format_legal_citation(
        "law",
        law_name="민법",
        article="390",
        paragraph=" 제1항"
    )
    print(f"법령 인용: {citation}")
    
    # 4. 응답 템플릿 테스트
    print("\n4. 응답 템플릿")
    template = builder.get_response_template("증거_부족")
    print(f"증거 부족 템플릿:\n{template[:100]}...")
    
    print("\n테스트 완료!")
