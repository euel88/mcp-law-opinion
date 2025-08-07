"""
common_api.py - 공통 API 클라이언트 모듈 (수정 버전)
법제처 API와 OpenAI API 통합 관리
모든 API 호출 문제 해결
"""

import os
import time
import json
import hashlib
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import quote, urlencode
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CacheManager:
    """간단한 메모리 캐시 관리자"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, tuple] = {}
        self.ttl_seconds = ttl_seconds
    
    def _generate_key(self, prefix: str, params: Dict) -> str:
        """캐시 키 생성"""
        param_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
        hash_obj = hashlib.md5(param_str.encode())
        return f"{prefix}_{hash_obj.hexdigest()}"
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                logger.debug(f"Cache hit: {key}")
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """캐시에 값 저장"""
        self._cache[key] = (value, datetime.now())
        logger.debug(f"Cache set: {key}")
    
    def clear(self) -> None:
        """캐시 초기화"""
        self._cache.clear()


class LawAPIClient:
    """법제처 API 클라이언트 - 수정된 버전"""
    
    BASE_URL = "http://www.law.go.kr/DRF"
    
    # 지원하는 모든 타겟 타입
    TARGETS = {
        # 법령 관련
        'law': '현행법령',
        'eflaw': '시행일법령',
        'elaw': '영문법령',
        'lawjosub': '현행법령 조항호목',
        'eflawjosub': '시행일법령 조항호목',
        'lsHistory': '법령 연혁',
        'lsHstInf': '법령 변경이력',
        'lsJoHstInf': '조문별 변경이력',
        'oldAndNew': '신구법 비교',
        'lsStmd': '법령 체계도',
        'thdCmp': '3단 비교',
        'lsDelegated': '위임 법령',
        'lnkLs': '법령-자치법규 연계',
        'lnkLsOrdJo': '법령별 조례 조문',
        'lnkDep': '소관부처별 연계',
        'drlaw': '법령-자치법규 연계현황',
        'lsAbrv': '법령명 약칭',
        'delHst': '삭제 데이터',
        'oneview': '한눈보기',
        
        # 판례/심판례
        'prec': '판례',
        'detc': '헌재결정례',
        'expc': '법령해석례',
        'decc': '행정심판례',
        
        # 행정규칙/자치법규
        'admrul': '행정규칙',
        'ordin': '자치법규',
        
        # 조약
        'trty': '조약',
        
        # 별표서식
        'licbyl': '법령 별표서식',
        'admbyl': '행정규칙 별표서식',
        'ordinbyl': '자치법규 별표서식',
        
        # 학칙/공단/공공기관
        'school': '대학 학칙',
        'public': '지방공사공단 규정',
        'pi': '공공기관 규정',
        
        # 법령용어
        'lstrm': '법령용어',
        'lstrmAI': '법령정보지식베이스 법령용어',
        'dlytrm': '일상용어',
        'lstrmRlt': '법령용어 관계',
        'dlytrmRlt': '일상용어 관계',
        'lstrmRltJo': '법령용어-조문 연계',
        'joRltLstrm': '조문-법령용어 연계',
        'lsRlt': '관련법령',
        
        # 맞춤형 분류
        'couseLs': '맞춤형 법령',
        'couseAdmrul': '맞춤형 행정규칙',
        'couseOrdin': '맞춤형 자치법규',
        
        # 위원회 결정문 (14개)
        'ppc': '개인정보보호위원회',
        'eiac': '고용보험심사위원회',
        'ftc': '공정거래위원회',
        'acr': '국민권익위원회',
        'fsc': '금융위원회',
        'nlrc': '노동위원회',
        'kcc': '방송통신위원회',
        'iaciac': '산업재해보상보험재심사위원회',
        'oclt': '중앙토지수용위원회',
        'ecc': '중앙환경분쟁조정위원회',
        'sfc': '증권선물위원회',
        'nhrck': '국가인권위원회',
        
        # 부처별 법령해석
        'moelCgmExpc': '고용노동부 법령해석',
        'molitCgmExpc': '국토교통부 법령해석',
        'moefCgmExpc': '기획재정부 법령해석',
        'mofCgmExpc': '해양수산부 법령해석',
        'moisCgmExpc': '행정안전부 법령해석',
        'meCgmExpc': '환경부 법령해석',
        'kcsCgmExpc': '관세청 법령해석',
        'ntsCgmExpc': '국세청 법령해석',
        
        # 특별행정심판재결례
        'ttSpecialDecc': '조세심판원',
        'kmstSpecialDecc': '해양안전심판원'
    }
    
    def __init__(self, oc_key: Optional[str] = None, cache_ttl: int = 3600):
        """
        초기화
        
        Args:
            oc_key: 법제처 API 키 (없으면 환경변수에서 읽음)
            cache_ttl: 캐시 유효시간 (초)
        """
        self.oc_key = oc_key or os.getenv('LAW_API_KEY', 'test')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.cache = CacheManager(ttl_seconds=cache_ttl)
        self.retry_count = 3
        self.retry_delay = 1
        
        logger.info(f"LawAPIClient initialized with key: {self.oc_key[:4]}..." if self.oc_key else "No API key")
    
    def search(self, target: str, **params) -> Dict[str, Any]:
        """
        검색 API 호출 (수정된 버전)
        
        Args:
            target: 검색 대상 (law, prec, detc 등)
            **params: 추가 파라미터
        
        Returns:
            API 응답 딕셔너리
        """
        # 엔드포인트 결정
        url = f"{self.BASE_URL}/lawSearch.do"
        
        # 필수 파라미터 설정
        params['OC'] = self.oc_key
        params['target'] = target
        
        # type 파라미터가 없으면 JSON 기본값 설정
        if 'type' not in params:
            params['type'] = 'json'
        
        # query가 없으면 기본값 설정 (일부 API는 query가 필수)
        if 'query' not in params and target in ['law', 'prec', 'detc', 'expc', 'decc']:
            params['query'] = '*'
        
        logger.info(f"API 호출: {url}")
        logger.debug(f"파라미터: {params}")
        
        # 캐시 확인
        cache_key = self.cache._generate_key(f"{target}_search", params)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info("캐시에서 데이터 반환")
            return cached_data
        
        # API 호출 (재시도 로직 포함)
        for attempt in range(self.retry_count):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                # Content-Type 확인
                content_type = response.headers.get('Content-Type', '')
                
                # JSON 응답 처리
                if params['type'].lower() == 'json' or 'json' in content_type.lower():
                    try:
                        result = response.json()
                        
                        # 에러 체크
                        if isinstance(result, dict):
                            if 'errorCode' in result:
                                logger.error(f"API 에러: {result.get('errorMsg', 'Unknown error')}")
                                return {
                                    'error': result.get('errorMsg', 'API Error'),
                                    'errorCode': result.get('errorCode'),
                                    'totalCnt': 0,
                                    target: []
                                }
                            
                            # 정상 응답 - 캐시 저장
                            self.cache.set(cache_key, result)
                            logger.info(f"API 호출 성공 - 총 {result.get('totalCnt', 0)}건")
                            return result
                        
                        # 리스트 형태의 응답 처리
                        return {
                            'totalCnt': len(result) if isinstance(result, list) else 0,
                            target: result if isinstance(result, list) else []
                        }
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 파싱 실패: {str(e)}")
                        # XML일 가능성이 있으므로 XML 파싱 시도
                        return self._parse_xml_response(response.text, target)
                
                # XML 응답 처리
                else:
                    return self._parse_xml_response(response.text, target)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"API 요청 실패 (시도 {attempt + 1}/{self.retry_count}): {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)
                else:
                    return {
                        'error': str(e),
                        'totalCnt': 0,
                        target: []
                    }
        
        return {
            'error': 'Max retries exceeded',
            'totalCnt': 0,
            target: []
        }
    
    def get_detail(self, target: str, **params) -> Dict[str, Any]:
        """
        상세 조회 API 호출 (수정된 버전)
        
        Args:
            target: 조회 대상
            **params: 추가 파라미터
        
        Returns:
            API 응답 딕셔너리
        """
        # 엔드포인트 결정
        url = f"{self.BASE_URL}/lawService.do"
        
        # 필수 파라미터 설정
        params['OC'] = self.oc_key
        params['target'] = target
        
        # type 파라미터가 없으면 JSON 기본값 설정
        if 'type' not in params:
            params['type'] = 'json'
        
        logger.info(f"상세 조회: {url}")
        logger.debug(f"파라미터: {params}")
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # JSON 응답 처리
            if params['type'].lower() == 'json':
                try:
                    result = response.json()
                    
                    # 에러 체크
                    if isinstance(result, dict) and 'errorCode' in result:
                        logger.error(f"API 에러: {result.get('errorMsg', 'Unknown error')}")
                        return {
                            'error': result.get('errorMsg', 'API Error'),
                            'errorCode': result.get('errorCode')
                        }
                    
                    return result
                    
                except json.JSONDecodeError:
                    # XML일 가능성이 있으므로 XML 파싱 시도
                    return self._parse_xml_response(response.text, target)
            
            # XML 응답
            else:
                return self._parse_xml_response(response.text, target)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    def _parse_xml_response(self, xml_text: str, target: str) -> Dict[str, Any]:
        """
        XML 응답 파싱
        
        Args:
            xml_text: XML 응답 텍스트
            target: 타겟 타입
        
        Returns:
            파싱된 딕셔너리
        """
        try:
            # HTML 응답인 경우
            if xml_text.strip().startswith('<!DOCTYPE') or xml_text.strip().startswith('<html'):
                return {
                    'type': 'html',
                    'html': xml_text
                }
            
            # XML 파싱
            root = ET.fromstring(xml_text)
            
            # 에러 체크
            error_msg = root.findtext('.//errorMsg')
            if error_msg:
                return {
                    'error': error_msg,
                    'totalCnt': 0,
                    target: []
                }
            
            # 총 개수
            total_cnt = root.findtext('.//totalCnt', '0')
            
            # 결과 추출
            items = []
            
            # 타겟별 태그명 매핑
            tag_map = {
                'law': 'law',
                'prec': 'prec',
                'detc': 'detc',
                'expc': 'expc',
                'decc': 'decc',
                'admrul': 'admrul',
                'ordin': 'ordin',
                'trty': 'trty'
            }
            
            item_tag = tag_map.get(target, target)
            
            # 아이템 찾기
            for item in root.findall(f'.//{item_tag}'):
                item_dict = {}
                for child in item:
                    if child.text:
                        item_dict[child.tag] = child.text
                if item_dict:
                    items.append(item_dict)
            
            return {
                'totalCnt': int(total_cnt) if total_cnt.isdigit() else 0,
                'page': int(root.findtext('.//page', '1')),
                target: items
            }
            
        except ET.ParseError as e:
            logger.error(f"XML 파싱 오류: {str(e)}")
            return {
                'error': f'XML 파싱 오류: {str(e)}',
                'totalCnt': 0,
                target: []
            }
    
    def validate_target(self, target: str) -> bool:
        """타겟 타입 유효성 검사"""
        return target in self.TARGETS
    
    def get_supported_targets(self) -> Dict[str, str]:
        """지원하는 모든 타겟 타입 반환"""
        return self.TARGETS.copy()


class OpenAIHelper:
    """OpenAI API 헬퍼 클래스"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        초기화
        
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
            model: 사용할 모델 (기본값: gpt-4o-mini)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        
        if not self.api_key:
            logger.warning("OpenAI API key not found. AI features will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"OpenAI client initialized with model: {self.model}")
            except ImportError:
                logger.error("OpenAI library not installed. Run: pip install openai")
                self.enabled = False
    
    def set_model(self, model: str):
        """모델 변경"""
        self.model = model
        logger.info(f"OpenAI model changed to: {model}")
    
    def analyze_legal_text(self, query: str, context: Dict[str, Any]) -> Optional[str]:
        """
        법률 텍스트 분석 (할루시네이션 방지 강화)
        
        Args:
            query: 사용자 질문
            context: 법령/판례 등 컨텍스트 정보
            
        Returns:
            분석 결과
        """
        if not self.enabled:
            return "OpenAI API가 설정되지 않았습니다."
        
        try:
            # 컨텍스트가 비어있는지 확인
            if not context or context.get('no_results'):
                return (
                    "검색된 법률 자료가 없습니다.\n\n"
                    "다음과 같이 시도해보세요:\n"
                    "1. 검색어를 더 일반적인 용어로 변경\n"
                    "2. 다른 법령명이나 판례 키워드 사용\n"
                    "3. 날짜 범위를 넓혀서 검색\n\n"
                    "일반적인 법률 상담이 필요하시면 구체적인 상황을 설명해주세요."
                )
            
            # 컨텍스트 정리
            context_text = self._format_context(context)
            
            # 프롬프트 구성 (할루시네이션 방지)
            system_prompt = """당신은 한국 법률 전문가입니다.

**절대 규칙:**
1. 제공된 검색 결과에 있는 정보만 사용하세요
2. 검색 결과에 없는 판례번호, 법령, 날짜를 만들지 마세요
3. 불확실한 경우 "검색된 자료에서는 확인할 수 없습니다"라고 답하세요
4. 일반적인 법리 설명은 가능하나, 구체적 인용은 검색 결과만 사용하세요"""
            
            user_prompt = f"""
질문: {query}

검색된 법률 자료:
{context_text}

위 검색 결과만을 바탕으로 답변해주세요. 검색 결과에 없는 정보는 언급하지 마세요.
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"AI 분석 중 오류가 발생했습니다: {str(e)}"
    
    def compare_laws(self, old_law: str, new_law: str) -> Optional[str]:
        """신구법 비교 분석"""
        if not self.enabled:
            return "OpenAI API가 설정되지 않았습니다."
        
        try:
            prompt = f"""다음 두 법령을 비교 분석해주세요:
            
            [구법]
            {old_law[:2000]}
            
            [신법]
            {new_law[:2000]}
            
            다음 관점에서 분석해주세요:
            1. 주요 변경사항
            2. 삭제된 내용
            3. 추가된 내용
            4. 변경의 의미와 영향"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "법령 비교 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Law comparison error: {e}")
            return f"법령 비교 중 오류가 발생했습니다: {str(e)}"
    
    def analyze_committee_decision(self, decision: Dict[str, Any]) -> Optional[str]:
        """위원회 결정문 분석"""
        if not self.enabled:
            return "OpenAI API가 설정되지 않았습니다."
        
        try:
            prompt = f"""다음 위원회 결정문을 분석해주세요:
            
            위원회: {decision.get('committee_name', '')}
            사건명: {decision.get('title', '')}
            주문: {decision.get('order', '')}
            이유: {decision.get('reason', '')}
            
            다음을 분석해주세요:
            1. 핵심 쟁점
            2. 위원회의 판단 기준
            3. 결정의 의미
            4. 유사 사례에 대한 시사점"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "행정법 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Committee decision analysis error: {e}")
            return f"위원회 결정문 분석 중 오류가 발생했습니다: {str(e)}"
    
    def summarize_law(self, text: str, max_length: int = 500) -> Optional[str]:
        """법률 텍스트 요약"""
        if not self.enabled:
            return text[:max_length] + "..." if len(text) > max_length else text
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "법률 조문을 명확하고 간결하게 요약해주세요."},
                    {"role": "user", "content": f"다음 법률 조문을 {max_length}자 이내로 요약해주세요:\n\n{text}"}
                ],
                temperature=0.3,
                max_tokens=max_length
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return text[:max_length] + "..." if len(text) > max_length else text
    
    def generate_legal_document(self, template_type: str, context: Dict[str, Any]) -> Optional[str]:
        """법률 문서 생성"""
        if not self.enabled:
            return "OpenAI API가 설정되지 않았습니다."
        
        templates = {
            'contract': "표준 계약서를 작성해주세요.",
            'opinion': "법률 의견서를 작성해주세요.",
            'complaint': "민원 신청서를 작성해주세요.",
            'petition': "청원서를 작성해주세요."
        }
        
        try:
            prompt = f"""{templates.get(template_type, '문서를 작성해주세요.')}
            
            관련 정보:
            {json.dumps(context, ensure_ascii=False, indent=2)}
            
            전문적이고 법적 형식을 갖춘 문서를 작성해주세요."""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "법률 문서 작성 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Document generation error: {e}")
            return f"문서 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """컨텍스트 정보를 텍스트로 포맷팅"""
        if not context:
            return "검색된 자료 없음"
        
        formatted = []
        
        # 법령
        if 'laws' in context and context['laws']:
            formatted.append("=== 관련 법령 ===")
            for idx, law in enumerate(context['laws'][:5], 1):
                formatted.append(f"{idx}. {law.get('법령명한글', law.get('법령명', '제목 없음'))}")
                if law.get('공포일자'):
                    formatted.append(f"   공포일자: {law['공포일자']}")
                if law.get('조문내용'):
                    formatted.append(f"   내용: {law['조문내용'][:200]}...")
            formatted.append("")
        
        # 판례
        if 'cases' in context and context['cases']:
            formatted.append("=== 관련 판례 ===")
            for idx, case in enumerate(context['cases'][:5], 1):
                formatted.append(f"{idx}. {case.get('사건명', case.get('title', '제목 없음'))}")
                if case.get('사건번호'):
                    formatted.append(f"   사건번호: {case['사건번호']}")
                if case.get('선고일자'):
                    formatted.append(f"   선고일자: {case['선고일자']}")
                if case.get('판시사항'):
                    formatted.append(f"   판시사항: {case['판시사항'][:200]}...")
            formatted.append("")
        
        # 해석례
        if 'interpretations' in context and context['interpretations']:
            formatted.append("=== 관련 해석례 ===")
            for idx, interp in enumerate(context['interpretations'][:5], 1):
                formatted.append(f"{idx}. {interp.get('안건명', interp.get('title', '제목 없음'))}")
                if interp.get('회신일자'):
                    formatted.append(f"   회신일자: {interp['회신일자']}")
                if interp.get('회답'):
                    formatted.append(f"   회답: {interp['회답'][:200]}...")
            formatted.append("")
        
        # 위원회 결정
        if 'committees' in context and context['committees']:
            formatted.append("=== 위원회 결정 ===")
            for idx, decision in enumerate(context['committees'][:5], 1):
                formatted.append(f"{idx}. {decision.get('title', '제목 없음')}")
                if decision.get('committee_name'):
                    formatted.append(f"   위원회: {decision['committee_name']}")
                if decision.get('date'):
                    formatted.append(f"   날짜: {decision['date']}")
            formatted.append("")
        
        return "\n".join(formatted) if formatted else "검색된 자료 없음"


# 유틸리티 함수들
def clean_text(text: str) -> str:
    """텍스트 정리 (HTML 태그 제거, 공백 정리 등)"""
    if not text:
        return ""
    
    import re
    
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # 연속된 공백 정리
    text = re.sub(r'\s+', ' ', text)
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text


def parse_date(date_str: str) -> Optional[datetime]:
    """날짜 문자열 파싱"""
    if not date_str or not date_str.isdigit():
        return None
    
    try:
        if len(date_str) == 8:
            return datetime.strptime(date_str, '%Y%m%d')
        elif len(date_str) == 6:
            return datetime.strptime(date_str, '%Y%m')
        elif len(date_str) == 4:
            return datetime.strptime(date_str, '%Y')
    except ValueError:
        return None
    
    return None


def format_date_range(start_date: str, end_date: str) -> str:
    """날짜 범위 포맷팅"""
    return f"{start_date}~{end_date}"


def extract_case_number(text: str) -> Optional[str]:
    """텍스트에서 사건번호 추출"""
    import re
    
    # 대법원 사건번호 패턴
    pattern = r'\d{4}[다도허누]\d{4,6}'
    match = re.search(pattern, text)
    if match:
        return match.group()
    
    # 헌재 사건번호 패턴
    pattern = r'\d{4}헌[가나다라마바사]\d+'
    match = re.search(pattern, text)
    if match:
        return match.group()
    
    return None


# 테스트 코드
if __name__ == "__main__":
    print("=== 법제처 API 클라이언트 테스트 (수정 버전) ===\n")
    
    # 환경변수 로드
    from dotenv import load_dotenv
    load_dotenv()
    
    # API 클라이언트 생성
    law_client = LawAPIClient()
    
    # 1. 법령 검색 테스트
    print("1. 법령 검색 테스트 - '도로교통법'")
    print("-" * 50)
    result = law_client.search(
        target='law',
        query='도로교통법',
        display=5,
        type='json'
    )
    
    if 'error' not in result:
        print(f"✅ 검색 성공: 총 {result.get('totalCnt', 0)}건")
        laws = result.get('law', [])
        for idx, law in enumerate(laws[:3], 1):
            print(f"  {idx}. {law.get('법령명한글', 'N/A')}")
            print(f"     - 공포일자: {law.get('공포일자', 'N/A')}")
            print(f"     - 시행일자: {law.get('시행일자', 'N/A')}")
    else:
        print(f"❌ 검색 실패: {result.get('error')}")
    
    # 2. 판례 검색 테스트
    print("\n2. 판례 검색 테스트 - '음주운전'")
    print("-" * 50)
    result = law_client.search(
        target='prec',
        query='음주운전',
        display=5,
        type='json'
    )
    
    if 'error' not in result:
        print(f"✅ 검색 성공: 총 {result.get('totalCnt', 0)}건")
        cases = result.get('prec', [])
        for idx, case in enumerate(cases[:3], 1):
            print(f"  {idx}. {case.get('사건명', 'N/A')}")
            print(f"     - 법원: {case.get('법원명', 'N/A')}")
            print(f"     - 사건번호: {case.get('사건번호', 'N/A')}")
            print(f"     - 선고일자: {case.get('선고일자', 'N/A')}")
    else:
        print(f"❌ 검색 실패: {result.get('error')}")
    
    # 3. 위원회 결정문 테스트
    print("\n3. 공정거래위원회 결정문 검색 테스트")
    print("-" * 50)
    result = law_client.search(
        target='ftc',
        query='불공정',
        display=5,
        type='json'
    )
    
    if 'error' not in result:
        print(f"✅ 검색 성공: 총 {result.get('totalCnt', 0)}건")
    else:
        print(f"❌ 검색 실패: {result.get('error')}")
    
    # 4. API 타겟 확인
    print("\n4. 지원하는 API 타겟")
    print("-" * 50)
    targets = law_client.get_supported_targets()
    print(f"총 {len(targets)}개 타겟 지원")
    print("일부 예시:")
    for key, value in list(targets.items())[:10]:
        print(f"  - {key}: {value}")
    
    # 5. OpenAI Helper 테스트
    print("\n5. OpenAI Helper 테스트")
    print("-" * 50)
    ai_helper = OpenAIHelper()
    if ai_helper.enabled:
        print("✅ OpenAI API 활성화됨")
        print(f"   모델: {ai_helper.model}")
    else:
        print("⚠️ OpenAI API가 설정되지 않음")
    
    print("\n" + "=" * 50)
    print("테스트 완료!")
