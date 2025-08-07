"""
common_api.py - 공통 API 클라이언트 모듈 (확장 버전)
법제처 API와 OpenAI API 통합 관리
모든 모듈의 API 호출을 지원하는 완전한 구현
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
    """법제처 API 클라이언트 - 모든 API 엔드포인트 지원"""
    
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
        
        logger.info(f"LawAPIClient 초기화 완료 - API Key: {self.oc_key[:4]}..." if self.oc_key and len(self.oc_key) > 4 else "LawAPIClient 초기화 완료")
    
    def search(self, target: str = None, **params) -> Dict[str, Any]:
        """
        검색 API 호출 (수정된 버전)
        
        Args:
            target: API 타겟 (law, prec, detc 등)
            **params: 추가 파라미터
        
        Returns:
            API 응답 (JSON 딕셔너리)
        """
        # target 처리 - params에 있으면 우선 사용
        if 'target' in params:
            target = params['target']
        elif not target:
            raise ValueError("target 파라미터가 필요합니다.")
        
        # URL 설정
        url = f"{self.BASE_URL}/lawSearch.do"
        
        # 필수 파라미터 설정
        params['OC'] = self.oc_key
        params['target'] = target
        
        # type 파라미터가 없으면 JSON 기본값 설정
        if 'type' not in params:
            params['type'] = 'json'
        
        # query가 없으면 기본값 설정 (일부 API는 query가 필수)
        if 'query' not in params and target in ['law', 'prec', 'detc', 'expc', 'decc', 
                                                  'admrul', 'ordin', 'trty']:
            params['query'] = '*'
        
        logger.info(f"API 호출: {url}")
        logger.debug(f"파라미터: {params}")
        
        # 캐시 확인
        cache_key = self.cache._generate_key(f"{target}_search", params)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # 재시도 로직
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
                        
                        # 캐시 저장
                        self.cache.set(cache_key, result)
                        
                        # 성공 로그
                        if 'totalCnt' in result:
                            logger.info(f"검색 성공 - target: {target}, 결과: {result.get('totalCnt', 0)}건")
                        
                        return result
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 파싱 실패: {str(e)}")
                        # XML로 재시도
                        if attempt < self.retry_count - 1:
                            params['type'] = 'xml'
                            continue
                        return {
                            'error': 'JSON 파싱 실패',
                            'raw': response.text[:500],
                            'totalCnt': 0
                        }
                
                # XML 응답 처리
                else:
                    result = self._parse_xml_response(response.text, target)
                    self.cache.set(cache_key, result)
                    return result
                    
            except requests.exceptions.Timeout:
                logger.warning(f"타임아웃 발생 (시도 {attempt + 1}/{self.retry_count})")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"API 요청 실패 (시도 {attempt + 1}/{self.retry_count}): {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                    
                return {
                    'error': str(e),
                    'totalCnt': 0,
                    'results': []
                }
        
        return {
            'error': '최대 재시도 횟수 초과',
            'totalCnt': 0,
            'results': []
        }
    
    def get_detail(self, target: str = None, **params) -> Dict[str, Any]:
        """
        상세 조회 API 호출 (수정된 버전)
        
        Args:
            target: API 타겟
            **params: 추가 파라미터
        
        Returns:
            API 응답
        """
        # target 처리
        if 'target' in params:
            target = params['target']
        elif not target:
            raise ValueError("target 파라미터가 필요합니다.")
        
        # URL 설정
        url = f"{self.BASE_URL}/lawService.do"
        
        # 필수 파라미터 설정
        params['OC'] = self.oc_key
        params['target'] = target
        
        # type 파라미터가 없으면 JSON 기본값 설정
        if 'type' not in params:
            params['type'] = 'json'
        
        # id나 ID 파라미터 처리
        if 'id' in params:
            params['ID'] = params.pop('id')
        
        logger.info(f"상세 조회: {url}")
        logger.debug(f"파라미터: {params}")
        
        # 캐시 확인
        cache_key = self.cache._generate_key(f"{target}_detail", params)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '')
            
            # JSON 응답 처리
            if params['type'].lower() == 'json' or 'json' in content_type.lower():
                try:
                    result = response.json()
                    
                    # 캐시 저장
                    self.cache.set(cache_key, result)
                    
                    logger.info(f"상세 조회 성공 - target: {target}")
                    
                    return result
                    
                except json.JSONDecodeError:
                    logger.error("JSON 파싱 실패")
                    return {
                        'error': 'JSON 파싱 실패',
                        'raw': response.text[:500]
                    }
            
            # XML 응답 처리
            else:
                result = self._parse_xml_response(response.text, target)
                self.cache.set(cache_key, result)
                return result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"상세 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    def _parse_xml_response(self, xml_text: str, target: str) -> Dict[str, Any]:
        """
        XML 응답을 파싱하여 JSON 형태로 변환
        
        Args:
            xml_text: XML 응답 텍스트
            target: API 타겟
        
        Returns:
            파싱된 결과
        """
        try:
            root = ET.fromstring(xml_text)
            
            # 에러 체크
            error_msg = root.findtext('.//errorMsg')
            if error_msg:
                return {'error': error_msg, 'totalCnt': 0, 'results': []}
            
            # 기본 정보 추출
            result = {
                'totalCnt': int(root.findtext('.//totalCnt', '0')),
                'page': int(root.findtext('.//page', '1')),
                'results': []
            }
            
            # 타겟별 결과 태그 매핑
            result_tags = {
                'law': 'law',
                'prec': 'prec',
                'detc': 'detc',
                'expc': 'expc',
                'decc': 'decc',
                'admrul': 'admrul',
                'ordin': 'ordin',
                'trty': 'trty',
                'eflaw': 'eflaw',
                'elaw': 'elaw'
            }
            
            # 결과 태그 결정
            tag_name = result_tags.get(target, 'item')
            
            # 결과 추출
            items = root.findall(f'.//{tag_name}')
            for item in items:
                item_dict = {}
                for child in item:
                    if child.text:
                        item_dict[child.tag] = child.text
                if item_dict:
                    result['results'].append(item_dict)
            
            # 타겟별 결과 키 설정
            if target == 'law':
                result['law'] = result['results']
            elif target == 'prec':
                result['prec'] = result['results']
            elif target == 'detc':
                result['detc'] = result['results']
            elif target == 'expc':
                result['expc'] = result['results']
            elif target == 'decc':
                result['decc'] = result['results']
            
            return result
            
        except ET.ParseError as e:
            logger.error(f"XML 파싱 오류: {str(e)}")
            return {
                'error': f'XML 파싱 오류: {str(e)}',
                'raw': xml_text[:500],
                'totalCnt': 0,
                'results': []
            }
    
    def parse_response(self, response: Any, response_type: str) -> Dict[str, Any]:
        """
        API 응답을 파싱하여 통일된 형태로 반환 (하위 호환성 유지)
        
        Args:
            response: API 응답 (XML 문자열 또는 JSON 딕셔너리)
            response_type: 응답 유형
        
        Returns:
            파싱된 결과
        """
        try:
            # JSON 응답 처리
            if isinstance(response, dict):
                # 에러 체크
                if 'error' in response:
                    return {'error': response['error'], 'results': []}
                
                # 기본 구조로 변환
                return {
                    'type': response_type,
                    'totalCnt': response.get('totalCnt', 0),
                    'page': response.get('page', 1),
                    'results': response.get('law', response.get('items', response.get('results', [])))
                }
            
            # XML 응답 처리
            elif isinstance(response, str):
                # HTML 응답인 경우 그대로 반환
                if response.strip().startswith('<!DOCTYPE') or response.strip().startswith('<html'):
                    return {
                        'type': response_type,
                        'html': response
                    }
                
                # XML 파싱
                return self._parse_xml_response(response, response_type.split('_')[0])
            
            else:
                return {
                    'type': response_type,
                    'error': f'알 수 없는 응답 형식: {type(response)}',
                    'results': []
                }
                
        except Exception as e:
            logger.error(f"응답 파싱 중 오류: {str(e)}")
            return {
                'type': response_type,
                'error': str(e),
                'results': []
            }
    
    def get_supported_targets(self) -> Dict[str, str]:
        """지원하는 모든 타겟 타입 반환"""
        return self.TARGETS.copy()
    
    def validate_target(self, target: str) -> bool:
        """타겟 타입 유효성 검사"""
        return target in self.TARGETS


class OpenAIHelper:
    """OpenAI API 헬퍼 클래스 - 확장된 기능"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "o3"):
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
                logger.info(f"OpenAI 클라이언트 초기화 완료 - 모델: {self.model}")
            except ImportError:
                logger.error("OpenAI library not installed. Run: pip install openai")
                self.enabled = False
    
    def set_model(self, model: str):
        """모델 변경"""
        self.model = model
        logger.info(f"OpenAI 모델 변경: {model}")
    
    def analyze_legal_text(self, query: str, context: Dict[str, Any]) -> Optional[str]:
        """
        법률 텍스트 분석
        
        Args:
            query: 사용자 질문
            context: 법령/판례 등 컨텍스트 정보
            
        Returns:
            분석 결과
        """
        if not self.enabled:
            return "OpenAI API가 설정되지 않았습니다."
        
        try:
            # 컨텍스트 정리
            context_text = self._format_context(context)
            
            # 프롬프트 구성
            system_prompt = """당신은 한국 법률 전문가입니다. 
            제공된 법령, 판례, 해석례를 바탕으로 정확하고 명확한 법률 자문을 제공하세요.
            답변은 다음 구조를 따라주세요:
            1. 핵심 답변
            2. 법적 근거
            3. 관련 판례/해석
            4. 추가 고려사항
            
            중요: 제공된 검색 결과만을 인용하고, 없는 내용은 만들지 마세요."""
            
            user_prompt = f"""
            질문: {query}
            
            참고 자료:
            {context_text}
            
            위 자료를 바탕으로 질문에 대해 답변해주세요.
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
        """
        신구법 비교 분석
        
        Args:
            old_law: 구법 내용
            new_law: 신법 내용
            
        Returns:
            비교 분석 결과
        """
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
        """
        위원회 결정문 분석
        
        Args:
            decision: 위원회 결정문 정보
            
        Returns:
            분석 결과
        """
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
        """
        법률 텍스트 요약
        
        Args:
            text: 요약할 텍스트
            max_length: 최대 요약 길이
            
        Returns:
            요약된 텍스트
        """
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
        """
        법률 문서 생성 (계약서, 의견서 등)
        
        Args:
            template_type: 문서 유형 (contract, opinion, complaint 등)
            context: 문서 생성에 필요한 정보
            
        Returns:
            생성된 문서
        """
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
        """
        컨텍스트 정보를 텍스트로 포맷팅
        
        Args:
            context: 컨텍스트 정보
            
        Returns:
            포맷팅된 텍스트
        """
        if not context:
            return "검색된 관련 자료가 없습니다."
        
        # 검색 결과가 없다는 명시적 표시가 있는 경우
        if context.get('no_results'):
            return "검색된 관련 자료가 없습니다."
        
        formatted = []
        
        # 법령
        if 'laws' in context:
            formatted.append("관련 법령:")
            for law in context['laws'][:3]:  # 최대 3개만
                formatted.append(f"- {law.get('법령명한글', law.get('법령명', ''))} : {law.get('조문내용', '')[:200]}...")
        
        # 판례
        if 'cases' in context:
            formatted.append("\n관련 판례:")
            for case in context['cases'][:3]:
                formatted.append(f"- {case.get('사건명', '')} ({case.get('선고일자', '')})")
                formatted.append(f"  {case.get('판시사항', '')[:200]}...")
        
        # 해석례
        if 'interpretations' in context:
            formatted.append("\n관련 해석:")
            for interp in context['interpretations'][:3]:
                formatted.append(f"- {interp.get('안건명', '')}")
                formatted.append(f"  {interp.get('회답', '')[:200]}...")
        
        # 위원회 결정
        if 'committees' in context:
            formatted.append("\n관련 위원회 결정:")
            for decision in context['committees'][:3]:
                formatted.append(f"- {decision.get('committee_name', '')} : {decision.get('title', '')}")
                formatted.append(f"  주문: {decision.get('order', '')[:200]}...")
        
        # 조약
        if 'treaties' in context:
            formatted.append("\n관련 조약:")
            for treaty in context['treaties'][:3]:
                formatted.append(f"- {treaty.get('조약명', '')} ({treaty.get('발효일자', '')})")
        
        # 행정규칙
        if 'admin_rules' in context:
            formatted.append("\n관련 행정규칙:")
            for rule in context['admin_rules'][:3]:
                formatted.append(f"- {rule.get('행정규칙명', '')} ({rule.get('발령일자', '')})")
        
        # 자치법규
        if 'local_laws' in context:
            formatted.append("\n관련 자치법규:")
            for law in context['local_laws'][:3]:
                formatted.append(f"- {law.get('자치법규명', '')} ({law.get('지자체명', '')})")
        
        return "\n".join(formatted) if formatted else "검색된 관련 자료가 없습니다."


# 유틸리티 함수들
def clean_text(text: str) -> str:
    """
    텍스트 정리 (HTML 태그 제거, 공백 정리 등)
    
    Args:
        text: 원본 텍스트
        
    Returns:
        정리된 텍스트
    """
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
    """
    날짜 문자열 파싱
    
    Args:
        date_str: 날짜 문자열 (YYYYMMDD 형식)
        
    Returns:
        datetime 객체
    """
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
    """
    날짜 범위 포맷팅
    
    Args:
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)
        
    Returns:
        포맷팅된 날짜 범위 문자열
    """
    return f"{start_date}~{end_date}"


def extract_case_number(text: str) -> Optional[str]:
    """
    텍스트에서 사건번호 추출
    
    Args:
        text: 텍스트
        
    Returns:
        사건번호 또는 None
    """
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
    # API 클라이언트 테스트
    print("=== 법제처 API 클라이언트 테스트 (확장 버전) ===")
    
    # 법제처 API 테스트
    law_client = LawAPIClient()
    
    # 지원 타겟 확인
    print("\n1. 지원하는 타겟 타입")
    targets = law_client.get_supported_targets()
    print(f"총 {len(targets)}개 타겟 지원")
    print("일부 예시:")
    for key, value in list(targets.items())[:10]:
        print(f"  - {key}: {value}")
    
    # 법령 검색 테스트
    print("\n2. 법령 검색 테스트")
    results = law_client.search(
        target='law',
        query='도로교통법',
        display=5,
        type='json'
    )
    if 'error' not in results:
        print(f"검색 결과: {results.get('totalCnt', 0)}건")
        if results.get('law'):
            for idx, law in enumerate(results['law'][:3], 1):
                print(f"  {idx}. {law.get('법령명한글', 'N/A')}")
    else:
        print(f"검색 실패: {results.get('error')}")
    
    # 위원회 결정문 검색 테스트
    print("\n3. 위원회 결정문 검색 테스트")
    results = law_client.search(
        target='ftc',  # 공정거래위원회
        query='불공정',
        display=5,
        type='json'
    )
    print(f"공정거래위원회 결정문 검색 완료")
    if 'error' not in results:
        print(f"검색 결과: {results.get('totalCnt', 0)}건")
    else:
        print(f"검색 실패: {results.get('error')}")
    
    # OpenAI 테스트 (API 키가 있는 경우만)
    print("\n4. OpenAI Helper 테스트")
    ai_helper = OpenAIHelper()
    if ai_helper.enabled:
        summary = ai_helper.summarize_law("이 법은 도로에서 일어나는 교통상의 모든 위험과 장해를 방지하고 제거하여 안전하고 원활한 교통을 확보함을 목적으로 한다.", 50)
        print(f"요약: {summary}")
    else:
        print("OpenAI API 키가 설정되지 않아 테스트를 건너뜁니다.")
    
    print("\n테스트 완료!")
