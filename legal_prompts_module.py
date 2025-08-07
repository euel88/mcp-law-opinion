"""
법률 검토 프롬프트 템플릿 모듈
AI 변호사 GPT 통합 지침 v6.0 - 할루시네이션 방지 강화
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


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
    """법률 검토용 프롬프트 템플릿 - 할루시네이션 방지 강화"""
    
    # ===== 1. 시스템 프롬프트 (할루시네이션 방지 최우선) =====
    SYSTEM_PROMPT = """당신은 **AI 법률 도우미**입니다.

## 🚨 절대 준수 규칙 (위반 시 심각한 오류)
1. **실제 데이터만 인용**: 제공된 검색 결과에 있는 법령, 판례, 해석례만 인용
2. **허위 정보 생성 절대 금지**: 
   - 절대로 "2005다1234" 같은 가짜 판례번호를 만들지 마세요
   - 실제로 제공되지 않은 법령명이나 조항을 만들지 마세요
   - 날짜, 기관명, 사건명을 임의로 생성하지 마세요
3. **검색 결과 없음 명시**: 관련 자료가 없으면 반드시 "검색된 자료 없음"이라고 표시
4. **인용 정확성**: 모든 인용은 제공된 검색 결과의 원문 그대로 사용
5. **추측 금지**: 일반적인 법리 설명은 가능하나, 구체적 사례는 검색 결과만 인용

## ❌ 금지 패턴 (절대 사용 금지)
- "대법원 YYYY다NNNN" 형식의 임의 번호
- "법제처 YYYY해석NNNN" 형식의 임의 번호
- "헌법재판소 YYYY헌가N" 형식의 임의 번호
- "제N조의N" 같은 구체적 조항 (검색 결과에 없는 경우)

## 필수 고지사항
⚖️ 본 내용은 실제 검색된 법률자료를 기반으로 AI가 작성한 참고자료이며, 법률자문이 아닙니다.
구체적인 사안에 대해서는 반드시 변호사 등 전문가의 검토가 필요합니다."""

    # ===== 2. 법률 정보 제공 프롬프트 (엄격한 인용 규칙) =====
    LEGAL_INFO_PROMPT = """
## 사용자 질문
{query}

## 실제 검색된 법률자료
{context}

## 답변 작성 규칙
위 질문에 대해 **오직 위에 제공된 검색 결과만을 사용하여** 답변하세요.

### 작성 형식

#### 1. 핵심 답변
- 질문에 대한 직접적인 답변 (3-5줄)
- 일반적인 법리 설명은 가능
- 구체적인 법령이나 판례는 위 검색 결과에 있는 것만 인용

#### 2. 관련 법령
{laws_section}

#### 3. 관련 판례
{cases_section}

#### 4. 관련 해석례
{interpretations_section}

#### 5. 실무적 조언
- 일반적인 실무 조언 (검색 결과 기반)
- 추가 확인이 필요한 사항

### ⚠️ 중요 지침
- 검색 결과에 없는 판례번호, 법령, 날짜를 절대 만들지 마세요
- 각 섹션에서 검색 결과가 없으면 "검색된 자료 없음"이라고 명시하세요
- "일반적으로", "통상", "대부분" 같은 표현으로 가짜 정보를 포장하지 마세요
"""

    # ===== 3. 계약서 검토 프롬프트 =====
    CONTRACT_REVIEW_PROMPT = """
## 계약서 검토 요청

### 계약 정보
- 당사자: {parties}
- 목적: {purpose}
- 우려사항: {concerns}

### 계약서 내용
{contract_text}

### 검색된 관련 법률자료
{legal_references}

## 검토 지침
**오직 위에 제공된 검색 결과만을 근거로** 계약서를 검토하세요.

### 1. 문제점 분석
- 발견된 문제점 (검색 결과 기반)
- 리스크 등급 (High/Medium/Low)
- 법적 근거 (검색 결과에서만 인용)

### 2. 법령 위반 검토
{law_violations}

### 3. 관련 판례
{case_references}

### 4. 개선 제안
- 수정이 필요한 조항
- 추가가 필요한 내용

### ⚠️ 인용 규칙
- 검색 결과에 없는 법령이나 판례를 인용하지 마세요
- 관련 자료가 없으면 "검색된 관련 자료 없음"이라고 명시하세요
"""

    # ===== 4. 법률자문의견서 프롬프트 =====
    LEGAL_OPINION_PROMPT = """
## 법률자문의견서 작성 요청

### 의뢰인 정보
{client_info}

### 질의사항
{questions}

### 사실관계
{facts}

### 검색된 법률자료
{legal_materials}

## 작성 지침
**오직 위에 제공된 검색 결과를 근거로** 의견서를 작성하세요.

### 제목
[핵심 쟁점 요약]

### 검토 자료 현황
- 법령: {law_count}건
- 판례: {case_count}건
- 해석례: {interp_count}건

### 쟁점 및 검토

#### 쟁점 1: [쟁점명]
- **Issue**: 법적 문제
- **Rule**: (검색 결과에서만 인용)
  - 관련 법령: {relevant_laws}
  - 관련 판례: {relevant_cases}
- **Application**: 사실관계 적용
- **Conclusion**: 결론

### 결론
[요약]

### 작성일자
{date}

⚖️ 본 의견서는 AI가 실제 검색된 자료를 기반으로 작성한 참고자료입니다.

### ⚠️ 작성 제한
- 검색되지 않은 판례번호나 법령을 만들지 마세요
- 검색 결과가 부족하면 "관련 자료 부족"이라고 명시하세요
"""

    # ===== 5. 검증용 프롬프트 =====
    VALIDATION_PROMPT = """
다음 AI 응답을 검토하세요:

응답 내용:
{response}

제공된 검색 결과:
{search_results}

확인사항:
1. 모든 판례번호가 검색 결과에 실제로 존재하는가?
2. 인용된 법령이 검색 결과에 있는가?
3. 날짜와 기관명이 정확한가?

허위 정보가 발견되면 제거하고 "검색된 자료 없음"으로 대체하세요.
"""


class PromptBuilder:
    """프롬프트 빌더 클래스 - 할루시네이션 방지 강화"""
    
    def __init__(self):
        self.templates = LegalPromptTemplates()
        self.suspicious_patterns = [
            r'대법원\s*\d{4}[다도허누]\d{4}',
            r'헌법재판소\s*\d{4}헌[가나다라마바사]\d+',
            r'법제처\s*\d{4}해석\d{4}',
        ]
    
    def build_prompt(self, 
                    service_type: ServiceType,
                    query: str,
                    context: Optional[Dict] = None,
                    **kwargs) -> tuple[str, str]:
        """
        서비스 유형에 따른 프롬프트 생성 (할루시네이션 방지 강화)
        """
        system_prompt = self.templates.SYSTEM_PROMPT
        
        # 컨텍스트 정리 및 포맷팅
        formatted_context, sections = self._format_context_strict(context)
        
        # 서비스별 프롬프트 생성
        if service_type == ServiceType.LEGAL_INFO:
            user_prompt = self.templates.LEGAL_INFO_PROMPT.format(
                query=query,
                context=formatted_context if formatted_context else "❌ 검색된 관련 법률자료가 없습니다.",
                laws_section=sections.get('laws', '- 검색된 법령 없음'),
                cases_section=sections.get('cases', '- 검색된 판례 없음'),
                interpretations_section=sections.get('interpretations', '- 검색된 해석례 없음')
            )
        
        elif service_type == ServiceType.CONTRACT_REVIEW:
            user_prompt = self.templates.CONTRACT_REVIEW_PROMPT.format(
                parties=kwargs.get('parties', ''),
                purpose=kwargs.get('purpose', ''),
                concerns=kwargs.get('concerns', ''),
                contract_text=kwargs.get('contract_text', query),
                legal_references=formatted_context if formatted_context else "❌ 검색된 관련 법률자료가 없습니다.",
                law_violations=sections.get('laws', '검색된 관련 법령 없음'),
                case_references=sections.get('cases', '검색된 관련 판례 없음')
            )
        
        elif service_type == ServiceType.LEGAL_OPINION:
            # 검색 결과 수 계산
            law_count = len(context.get('laws', [])) if context else 0
            case_count = len(context.get('cases', [])) if context else 0
            interp_count = len(context.get('interpretations', [])) if context else 0
            
            user_prompt = self.templates.LEGAL_OPINION_PROMPT.format(
                client_info=kwargs.get('client_info', ''),
                questions=query,
                facts=kwargs.get('facts', ''),
                legal_materials=formatted_context if formatted_context else "❌ 검색된 관련 법률자료가 없습니다.",
                law_count=law_count,
                case_count=case_count,
                interp_count=interp_count,
                relevant_laws=sections.get('laws', '검색된 법령 없음'),
                relevant_cases=sections.get('cases', '검색된 판례 없음'),
                date="2025년 8월 7일"
            )
        
        else:
            # 기본 프롬프트
            user_prompt = f"""
질문: {query}

검색된 자료:
{formatted_context if formatted_context else "❌ 검색된 관련 법률자료가 없습니다."}

⚠️ 위 검색 결과만 사용하여 답변하세요. 검색되지 않은 정보는 만들지 마세요.
"""
        
        return system_prompt, user_prompt
    
    def _format_context_strict(self, context: Optional[Dict]) -> tuple[str, Dict[str, str]]:
        """
        컨텍스트를 엄격하게 포맷팅 (실제 데이터만 포함)
        """
        if not context:
            return "", {}
        
        formatted = []
        sections = {}
        
        # 법령 섹션
        if 'laws' in context and context['laws']:
            laws_list = []
            formatted.append("### 📚 검색된 법령")
            
            for idx, law in enumerate(context['laws'][:10], 1):
                law_name = law.get('법령명한글', law.get('법령명', ''))
                law_date = law.get('공포일자', law.get('시행일자', ''))
                law_id = law.get('법령ID', '')
                
                if law_name:
                    law_entry = f"{idx}. {law_name}"
                    if law_date:
                        law_entry += f" (공포: {law_date})"
                    if law_id:
                        law_entry += f" [ID: {law_id}]"
                    
                    laws_list.append(f"- {law_entry}")
                    formatted.append(f"- {law_entry}")
                    
                    # 조문 내용이 있으면 추가
                    if law.get('조문내용'):
                        formatted.append(f"  내용: {law['조문내용'][:200]}...")
            
            if laws_list:
                sections['laws'] = "\n".join(laws_list)
            else:
                sections['laws'] = "- 검색된 법령 없음"
            
            formatted.append("")  # 빈 줄 추가
        
        # 판례 섹션
        if 'cases' in context and context['cases']:
            cases_list = []
            formatted.append("### ⚖️ 검색된 판례")
            
            for idx, case in enumerate(context['cases'][:10], 1):
                case_title = case.get('title', case.get('사건명', ''))
                case_number = case.get('case_number', case.get('사건번호', ''))
                case_court = case.get('court', case.get('법원명', ''))
                case_date = case.get('date', case.get('선고일자', ''))
                
                if case_number and case_court:
                    case_entry = f"{idx}. {case_court} {case_date} {case_number}"
                    if case_title:
                        case_entry += f" - {case_title}"
                    
                    cases_list.append(f"- {case_entry}")
                    formatted.append(f"- {case_entry}")
                    
                    # 판시사항이 있으면 추가
                    if case.get('판시사항'):
                        formatted.append(f"  판시: {case['판시사항'][:200]}...")
            
            if cases_list:
                sections['cases'] = "\n".join(cases_list)
            else:
                sections['cases'] = "- 검색된 판례 없음"
            
            formatted.append("")  # 빈 줄 추가
        
        # 헌재결정례 섹션
        if 'constitutional' in context and context['constitutional']:
            const_list = []
            formatted.append("### 🏛️ 검색된 헌재결정례")
            
            for idx, decision in enumerate(context['constitutional'][:5], 1):
                dec_title = decision.get('title', decision.get('사건명', ''))
                dec_number = decision.get('case_number', decision.get('사건번호', ''))
                dec_date = decision.get('date', decision.get('종국일자', ''))
                
                if dec_number:
                    dec_entry = f"{idx}. 헌법재판소 {dec_date} {dec_number}"
                    if dec_title:
                        dec_entry += f" - {dec_title}"
                    
                    const_list.append(f"- {dec_entry}")
                    formatted.append(f"- {dec_entry}")
            
            if const_list:
                sections['constitutional'] = "\n".join(const_list)
            
            formatted.append("")  # 빈 줄 추가
        
        # 법령해석례 섹션
        if 'interpretations' in context and context['interpretations']:
            interp_list = []
            formatted.append("### 📋 검색된 법령해석례")
            
            for idx, interp in enumerate(context['interpretations'][:5], 1):
                title = interp.get('title', interp.get('안건명', ''))
                agency = interp.get('responding_agency', interp.get('해석기관명', ''))
                number = interp.get('case_number', interp.get('안건번호', ''))
                date = interp.get('date', interp.get('회신일자', ''))
                
                if title and agency:
                    interp_entry = f"{idx}. {agency} {number} ({date})"
                    interp_entry += f" - {title}"
                    
                    interp_list.append(f"- {interp_entry}")
                    formatted.append(f"- {interp_entry}")
                    
                    # 회답이 있으면 추가
                    if interp.get('회답'):
                        formatted.append(f"  회답: {interp['회답'][:150]}...")
            
            if interp_list:
                sections['interpretations'] = "\n".join(interp_list)
            else:
                sections['interpretations'] = "- 검색된 해석례 없음"
            
            formatted.append("")  # 빈 줄 추가
        
        # 행정규칙 섹션
        if 'admin_rules' in context and context['admin_rules']:
            admin_list = []
            formatted.append("### 📑 검색된 행정규칙")
            
            for idx, rule in enumerate(context['admin_rules'][:5], 1):
                rule_name = rule.get('행정규칙명', '')
                rule_date = rule.get('발령일자', '')
                rule_agency = rule.get('소관부처', '')
                
                if rule_name:
                    admin_entry = f"{idx}. {rule_name}"
                    if rule_agency:
                        admin_entry += f" ({rule_agency})"
                    if rule_date:
                        admin_entry += f" - {rule_date}"
                    
                    admin_list.append(f"- {admin_entry}")
                    formatted.append(f"- {admin_entry}")
            
            if admin_list:
                sections['admin_rules'] = "\n".join(admin_list)
            
            formatted.append("")  # 빈 줄 추가
        
        # 섹션이 없으면 기본값 설정
        if 'laws' not in sections:
            sections['laws'] = "- 검색된 법령 없음"
        if 'cases' not in sections:
            sections['cases'] = "- 검색된 판례 없음"
        if 'interpretations' not in sections:
            sections['interpretations'] = "- 검색된 해석례 없음"
        
        return "\n".join(formatted), sections
    
    def validate_response(self, response: str, context: Dict) -> tuple[bool, List[str]]:
        """
        AI 응답에서 허위 인용 검증
        """
        errors = []
        
        if not context:
            # 컨텍스트가 없는데 구체적 인용이 있는지 확인
            for pattern in self.suspicious_patterns:
                if re.search(pattern, response):
                    errors.append(f"검색 결과 없이 패턴 사용: {pattern}")
            return len(errors) == 0, errors
        
        # 실제 데이터 추출
        real_case_numbers = set()
        real_law_names = set()
        
        # 판례번호 수집
        for case in context.get('cases', []):
            if case.get('case_number'):
                real_case_numbers.add(case['case_number'])
            if case.get('사건번호'):
                real_case_numbers.add(case['사건번호'])
        
        # 법령명 수집
        for law in context.get('laws', []):
            if law.get('법령명한글'):
                real_law_names.add(law['법령명한글'])
            if law.get('법령명'):
                real_law_names.add(law['법령명'])
        
        # 의심스러운 패턴 검사
        for pattern in self.suspicious_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                # 실제 데이터에 있는지 확인
                found = False
                for real_num in real_case_numbers:
                    if match in real_num or real_num in match:
                        found = True
                        break
                
                if not found:
                    errors.append(f"허위 판례번호 감지: {match}")
        
        # 법령명 검증
        law_pattern = r'「([^」]+)」'
        law_matches = re.findall(law_pattern, response)
        for law_name in law_matches:
            found = False
            for real_law in real_law_names:
                if law_name in real_law or real_law in law_name:
                    found = True
                    break
            
            if not found and len(law_name) > 3:  # 짧은 일반 용어 제외
                errors.append(f"검증되지 않은 법령명: {law_name}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def clean_response(self, response: str, errors: List[str]) -> str:
        """
        응답에서 오류 제거 및 경고 추가
        """
        if errors:
            # 허위 정보를 [검증 필요]로 대체
            for error in errors:
                if "허위 판례번호" in error:
                    fake_number = error.split(": ")[1]
                    response = response.replace(fake_number, "[검증 필요]")
                elif "검증되지 않은 법령명" in error:
                    fake_law = error.split(": ")[1]
                    response = response.replace(f"「{fake_law}」", f"[{fake_law} - 검증 필요]")
            
            # 경고 메시지 추가
            warning = "\n\n⚠️ **데이터 검증 알림**\n"
            warning += "다음 항목은 검색 결과에서 확인되지 않았습니다:\n"
            for error in errors[:5]:  # 최대 5개만 표시
                warning += f"• {error}\n"
            warning += "\n정확한 정보 확인을 위해 법률 전문가와 상담하시기 바랍니다."
            
            response += warning
        
        return response
    
    def get_response_template(self, template_type: str) -> str:
        """응답 템플릿 반환"""
        templates = {
            "증거_부족": """
현재 제공된 정보만으로는 정확한 법적 판단이 어렵습니다.
다음 자료를 추가로 제공해 주시면 더 구체적인 검토가 가능합니다:
- 관련 계약서나 문서
- 구체적인 사실관계
- 날짜와 경위
""",
            "복잡한_사안": """
이 사안은 여러 법적 쟁점이 복합적으로 얽혀 있습니다.
단계별로 신중하게 검토하겠습니다.
먼저 가장 중요한 쟁점부터 살펴보겠습니다.
""",
            "면책_고지": """
⚖️ 본 내용은 AI가 실제 검색된 법률자료를 기반으로 작성한 참고자료이며, 
법률자문이 아닙니다. 구체적인 사안에 대해서는 반드시 변호사 등 
전문가의 검토가 필요합니다.
"""
        }
        return templates.get(template_type, "")
    
    def format_legal_citation(self, citation_type: str, **kwargs) -> str:
        """
        법률 인용 형식 생성
        """
        citations = {
            "law": "「{law_name}」 제{article}조{paragraph}",
            "case": "{court} {date} 선고 {case_no} 판결",
            "constitutional": "헌법재판소 {date} {case_no} 결정",
            "admin_rule": "{ministry} {rule_type} 제{rule_no}호 ({date})",
            "interpretation": "{agency} 법령해석 {interp_no} ({date})"
        }
        
        template = citations.get(citation_type, "")
        if template:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logger.warning(f"인용 형식 생성 실패: {e}")
                return str(kwargs)
        return ""


def detect_service_type(query: str) -> ServiceType:
    """
    사용자 질문에서 서비스 유형 자동 판별
    """
    query_lower = query.lower()
    
    # 계약서 검토 키워드
    contract_keywords = ['계약서', '계약 검토', '독소조항', '불공정', '조항 분석', '계약 위험']
    if any(keyword in query_lower for keyword in contract_keywords):
        return ServiceType.CONTRACT_REVIEW
    
    # 법률자문의견서 키워드
    opinion_keywords = ['법률 의견', '자문의견서', '법적 검토', '사안 검토', '대응 방안', '법률자문', '소송']
    if any(keyword in query_lower for keyword in opinion_keywords):
        return ServiceType.LEGAL_OPINION
    
    # 기본값: 법률 정보 제공
    return ServiceType.LEGAL_INFO


# 검증 헬퍼 함수
def verify_citation(citation: str, search_results: Dict) -> bool:
    """
    특정 인용이 검색 결과에 있는지 확인
    """
    # 판례번호 패턴
    case_patterns = [
        r'(\d{4}[다도허누]\d+)',
        r'(\d{4}헌[가나다라마바사]\d+)'
    ]
    
    for pattern in case_patterns:
        match = re.search(pattern, citation)
        if match:
            case_num = match.group(1)
            # 검색 결과에서 확인
            for case in search_results.get('cases', []):
                if case_num in str(case.get('case_number', '')):
                    return True
            return False
    
    # 법령명 패턴
    law_pattern = r'「([^」]+)」'
    match = re.search(law_pattern, citation)
    if match:
        law_name = match.group(1)
        for law in search_results.get('laws', []):
            if law_name in str(law.get('법령명한글', '')):
                return True
        return False
    
    return True  # 패턴에 매치되지 않으면 일반 텍스트로 간주


# 사용 예시
if __name__ == "__main__":
    print("=== 법률 프롬프트 모듈 테스트 ===\n")
    
    # 프롬프트 빌더 초기화
    builder = PromptBuilder()
    
    # 테스트 컨텍스트 (실제 검색 결과 시뮬레이션)
    test_context = {
        'laws': [
            {
                '법령명한글': '도로교통법',
                '공포일자': '2023-12-31',
                '법령ID': '123456',
                '조문내용': '제44조(술에 취한 상태에서의 운전 금지)...'
            }
        ],
        'cases': [
            {
                'case_number': '2023다123456',
                'court': '대법원',
                'date': '2023. 5. 15.',
                '판시사항': '음주운전 관련 판시사항...'
            }
        ]
    }
    
    # 1. 법률 정보 프롬프트 테스트
    print("1. 법률 정보 제공 프롬프트 (할루시네이션 방지)")
    system, user = builder.build_prompt(
        ServiceType.LEGAL_INFO,
        "음주운전 처벌 기준이 어떻게 되나요?",
        test_context
    )
    print(f"System Prompt Length: {len(system)}")
    print(f"User Prompt Length: {len(user)}")
    print("포함된 실제 데이터:")
    print("- 법령: 도로교통법")
    print("- 판례: 대법원 2023다123456")
    
    # 2. 응답 검증 테스트
    print("\n2. 응답 검증 테스트")
    
    # 허위 응답 예시
    fake_response = """
    관련 판례로는 대법원 2005다1234 판결과 대법원 2010도5678 판결이 있습니다.
    실제로는 대법원 2023다123456 판결도 있습니다.
    """
    
    is_valid, errors = builder.validate_response(fake_response, test_context)
    print(f"검증 결과: {'통과' if is_valid else '실패'}")
    if errors:
        print("발견된 오류:")
        for error in errors:
            print(f"  - {error}")
    
    # 3. 응답 정제 테스트
    print("\n3. 응답 정제 테스트")
    cleaned = builder.clean_response(fake_response, errors)
    print("정제된 응답:")
    print(cleaned[:200] + "...")
    
    print("\n테스트 완료!")
