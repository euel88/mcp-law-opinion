"""
법률 검토 프롬프트 템플릿 모듈 - 개선 버전
할루시네이션 방지 및 정확한 인용 강화
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ServiceType(Enum):
    """서비스 유형"""
    LEGAL_INFO = "legal_info"
    CONTRACT_REVIEW = "contract_review"
    LEGAL_OPINION = "legal_opinion"


class RiskLevel(Enum):
    """리스크 등급"""
    HIGH = "🔴 High"
    MEDIUM = "🟠 Medium"
    LOW = "🟡 Low"


@dataclass
class LegalPromptTemplates:
    """법률 검토용 프롬프트 템플릿 - 개선 버전"""
    
    # ===== 시스템 프롬프트 (할루시네이션 방지 강화) =====
    SYSTEM_PROMPT = """당신은 **AI 변호사 GPT**입니다.

## 핵심 원칙 - 절대 준수사항
1. **실제 데이터만 인용**: 제공된 검색 결과에 있는 법령, 판례, 해석례만 인용합니다.
2. **허위 정보 생성 금지**: 절대로 가상의 판례번호, 법령명, 날짜를 만들어내지 않습니다.
3. **검색 결과 없음 명시**: 관련 자료가 없으면 "검색된 자료 없음"이라고 명확히 표시합니다.
4. **인용 출처 명시**: 모든 인용은 제공된 검색 결과의 정확한 정보를 사용합니다.

## 금지사항
- ❌ 존재하지 않는 판례번호 생성 (예: 2005다1234 같은 임의 번호)
- ❌ 가상의 법령해석례나 행정규칙 인용
- ❌ 추측이나 일반화를 구체적 사례인 것처럼 표현
- ❌ 검색 결과에 없는 내용을 있는 것처럼 작성

## 필수 고지사항
⚖️ 본 내용은 AI가 실제 검색된 법률자료를 기반으로 작성한 참고자료이며, 법률자문이 아닙니다.
구체적인 사안에 대해서는 반드시 변호사 등 전문가의 검토가 필요합니다."""

    # ===== 법률 정보 제공 프롬프트 (개선) =====
    LEGAL_INFO_PROMPT = """
## 질문
{query}

## 제공된 검색 결과
{context}

## 작성 지침
위 질문에 대해 **오직 제공된 검색 결과만을 사용하여** 다음 형식으로 답변해주세요:

### 1. 핵심 답변
- 질문에 대한 직접적인 답변 (3-5줄)
- 일반적인 법리 설명은 가능하나, 구체적인 법령이나 판례는 검색 결과에 있는 것만 인용

### 2. 관련 법령
검색 결과에 포함된 법령만 기재:
{laws_section}

### 3. 관련 판례
검색 결과에 포함된 판례만 기재:
{cases_section}

### 4. 관련 행정해석
검색 결과에 포함된 해석례만 기재:
{interpretations_section}

### 5. 실무적 조언
- 검색된 자료를 바탕으로 한 실무적 조언
- 추가 확인이 필요한 사항

## 중요: 검색 결과에 특정 유형의 자료가 없으면 해당 섹션에 "검색된 자료 없음"이라고 명시하세요.
절대로 가상의 판례번호나 법령을 만들어내지 마세요.
"""

    # ===== 응답 검증 프롬프트 =====
    VALIDATION_PROMPT = """
다음 응답을 검토하여 허위 정보가 포함되어 있는지 확인하세요:

응답 내용:
{response}

검색 결과:
{search_results}

다음 사항을 확인하세요:
1. 모든 판례번호가 검색 결과에 실제로 존재하는가?
2. 인용된 법령이 검색 결과에 있는가?
3. 날짜와 법원명이 정확한가?

허위 정보가 발견되면 수정하여 다시 작성하세요.
"""


class ImprovedPromptBuilder:
    """개선된 프롬프트 빌더"""
    
    def __init__(self):
        self.templates = LegalPromptTemplates()
    
    def build_prompt_with_validation(self, 
                                    service_type: ServiceType,
                                    query: str,
                                    context: Optional[Dict] = None,
                                    **kwargs) -> tuple[str, str]:
        """
        검증이 강화된 프롬프트 생성
        """
        system_prompt = self.templates.SYSTEM_PROMPT
        
        # 컨텍스트 포맷팅 및 섹션별 내용 생성
        formatted_context = ""
        laws_section = "- 검색된 법령 없음"
        cases_section = "- 검색된 판례 없음"
        interpretations_section = "- 검색된 해석례 없음"
        
        if context:
            # 법령 섹션
            if 'laws' in context and context['laws']:
                laws_list = []
                for law in context['laws'][:10]:  # 최대 10개
                    law_name = law.get('법령명한글', law.get('법령명', ''))
                    law_date = law.get('공포일자', law.get('시행일자', ''))
                    if law_name:
                        laws_list.append(f"- {law_name} (공포: {law_date})")
                if laws_list:
                    laws_section = "\n".join(laws_list)
                    formatted_context += f"### 검색된 법령\n{laws_section}\n\n"
            
            # 판례 섹션
            if 'cases' in context and context['cases']:
                cases_list = []
                for case in context['cases'][:10]:  # 최대 10개
                    case_title = case.get('title', case.get('사건명', ''))
                    case_number = case.get('case_number', case.get('사건번호', ''))
                    case_court = case.get('court', case.get('법원명', ''))
                    case_date = case.get('date', case.get('선고일자', ''))
                    if case_number and case_court:
                        cases_list.append(f"- {case_court} {case_date} {case_number}")
                        if case.get('판시사항'):
                            cases_list.append(f"  판시사항: {case['판시사항'][:100]}...")
                if cases_list:
                    cases_section = "\n".join(cases_list)
                    formatted_context += f"### 검색된 판례\n{cases_section}\n\n"
            
            # 해석례 섹션
            if 'interpretations' in context and context['interpretations']:
                interp_list = []
                for interp in context['interpretations'][:5]:  # 최대 5개
                    title = interp.get('title', interp.get('안건명', ''))
                    agency = interp.get('responding_agency', interp.get('해석기관명', ''))
                    number = interp.get('case_number', interp.get('안건번호', ''))
                    date = interp.get('date', interp.get('회신일자', ''))
                    if title and agency:
                        interp_list.append(f"- {agency} {number} ({date}): {title}")
                if interp_list:
                    interpretations_section = "\n".join(interp_list)
                    formatted_context += f"### 검색된 해석례\n{interpretations_section}\n\n"
        
        # 프롬프트 생성
        if service_type == ServiceType.LEGAL_INFO:
            user_prompt = self.templates.LEGAL_INFO_PROMPT.format(
                query=query,
                context=formatted_context if formatted_context else "검색된 관련 자료가 없습니다.",
                laws_section=laws_section,
                cases_section=cases_section,
                interpretations_section=interpretations_section
            )
        else:
            # 다른 서비스 타입 처리...
            user_prompt = f"질문: {query}\n\n검색 결과:\n{formatted_context}"
        
        return system_prompt, user_prompt
    
    def extract_real_citations(self, context: Dict) -> Dict[str, List[str]]:
        """
        실제 검색 결과에서 인용 가능한 정보 추출
        """
        citations = {
            'laws': [],
            'cases': [],
            'interpretations': [],
            'admin_rules': []
        }
        
        # 법령 추출
        if 'laws' in context:
            for law in context.get('laws', []):
                if law.get('법령명한글'):
                    citations['laws'].append({
                        'name': law['법령명한글'],
                        'date': law.get('공포일자', ''),
                        'id': law.get('법령ID', '')
                    })
        
        # 판례 추출
        if 'cases' in context:
            for case in context.get('cases', []):
                if case.get('case_number') or case.get('사건번호'):
                    citations['cases'].append({
                        'number': case.get('case_number', case.get('사건번호', '')),
                        'court': case.get('court', case.get('법원명', '')),
                        'date': case.get('date', case.get('선고일자', '')),
                        'title': case.get('title', case.get('사건명', ''))
                    })
        
        # 해석례 추출
        if 'interpretations' in context:
            for interp in context.get('interpretations', []):
                if interp.get('title') or interp.get('안건명'):
                    citations['interpretations'].append({
                        'title': interp.get('title', interp.get('안건명', '')),
                        'agency': interp.get('responding_agency', interp.get('해석기관명', '')),
                        'number': interp.get('case_number', interp.get('안건번호', '')),
                        'date': interp.get('date', interp.get('회신일자', ''))
                    })
        
        return citations
    
    def validate_response(self, response: str, context: Dict) -> tuple[bool, List[str]]:
        """
        AI 응답에서 허위 인용 검증
        
        Returns:
            (is_valid, errors): 검증 결과와 오류 목록
        """
        errors = []
        real_citations = self.extract_real_citations(context)
        
        # 판례번호 패턴 검사 (예: 2005다1234 같은 의심스러운 패턴)
        import re
        suspicious_patterns = [
            r'\d{4}다\d{4}(?!\d)',  # 정확히 4자리 숫자로 끝나는 판례번호
            r'\d{4}도\d{4}(?!\d)',
            r'\d{4}허\d{4}(?!\d)',
            r'\d{4}누\d{4}(?!\d)'
        ]
        
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                # 실제 검색 결과에 있는지 확인
                found = False
                for case in real_citations['cases']:
                    if match in case.get('number', ''):
                        found = True
                        break
                
                if not found:
                    errors.append(f"허위 판례번호 감지: {match}")
        
        # 법령명 검증
        law_pattern = r'「([^」]+)」'
        law_matches = re.findall(law_pattern, response)
        for law_name in law_matches:
            found = False
            for law in real_citations['laws']:
                if law_name in law.get('name', ''):
                    found = True
                    break
            
            if not found and len(law_name) > 3:  # 짧은 일반 용어 제외
                errors.append(f"검증되지 않은 법령명: {law_name}")
        
        is_valid = len(errors) == 0
        return is_valid, errors


# 사용 예시
def create_safe_prompt(query: str, search_results: Dict) -> tuple[str, str]:
    """
    안전한 프롬프트 생성 (할루시네이션 방지)
    """
    builder = ImprovedPromptBuilder()
    
    # 실제 검색 결과만 포함된 프롬프트 생성
    system_prompt, user_prompt = builder.build_prompt_with_validation(
        ServiceType.LEGAL_INFO,
        query,
        search_results
    )
    
    return system_prompt, user_prompt


# 응답 후처리 함수
def post_process_response(response: str, search_results: Dict) -> str:
    """
    AI 응답 후처리 및 검증
    """
    builder = ImprovedPromptBuilder()
    
    # 응답 검증
    is_valid, errors = builder.validate_response(response, search_results)
    
    if not is_valid:
        # 오류가 있으면 경고 추가
        warning = "\n\n⚠️ **주의**: 일부 인용이 검증되지 않았습니다:\n"
        for error in errors:
            warning += f"- {error}\n"
        warning += "\n실제 법률 전문가의 확인이 필요합니다."
        
        response += warning
    
    return response
