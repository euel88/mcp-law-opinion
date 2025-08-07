"""
공통 API 클라이언트 모듈
법제처 API와 OpenAI API 통합 관리
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
from urllib.parse import urlencode
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
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
    """법제처 API 클라이언트"""
    
    BASE_URL = "http://www.law.go.kr/DRF"
    
    def __init__(self, oc_key: Optional[str] = None, cache_ttl: int = 3600):
        """
        초기화
        
        Args:
            oc_key: 법제처 API 키 (없으면 환경변수에서 읽음)
            cache_ttl: 캐시 유효시간 (초)
        """
        self.oc_key = oc_key or os.getenv('LAW_API_KEY', 'test')
        self.session = requests.Session()
        self.cache = CacheManager(ttl_seconds=cache_ttl)
        self.retry_count = 3
        self.retry_delay = 1
    
    def _request(self, endpoint: str, params: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
        """
        API 요청 실행 (재시도 로직 포함)
        
        Args:
            endpoint: API 엔드포인트
            params: 요청 파라미터
            use_cache: 캐시 사용 여부
            
        Returns:
            파싱된 응답 데이터
        """
        # 캐시 확인
        if use_cache:
            cache_key = self.cache._generate_key(endpoint, params)
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data
        
        # OC 파라미터 추가
        params['OC'] = self.oc_key
        
        # 재시도 로직
        last_error = None
        for attempt in range(self.retry_count):
            try:
                url = f"{self.BASE_URL}{endpoint}"
                logger.info(f"API Request: {url} (Attempt {attempt + 1})")
                
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                # 응답 파싱
                content_type = response.headers.get('Content-Type', '')
                if 'xml' in content_type or params.get('type', '').upper() == 'XML':
                    result = self.parse_xml_response(response.text)
                elif 'json' in content_type or params.get('type', '').upper() == 'JSON':
                    result = self.parse_json_response(response.text)
                else:
                    # 기본적으로 XML로 처리
                    result = self.parse_xml_response(response.text)
                
                # 캐시 저장
                if use_cache:
                    self.cache.set(cache_key, result)
                
                return result
                
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Request failed (Attempt {attempt + 1}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                continue
        
        raise Exception(f"API request failed after {self.retry_count} attempts: {last_error}")
    
    def search(self, target: str, query: str = None, **params) -> Dict[str, Any]:
        """
        검색 API 호출
        
        Args:
            target: 검색 대상 (law, prec, expc 등)
            query: 검색어
            **params: 추가 파라미터
            
        Returns:
            검색 결과
        """
        endpoint = "/lawSearch.do"
        
        request_params = {
            'target': target,
            'type': params.pop('type', 'JSON'),
            'display': params.pop('display', 20),
            'page': params.pop('page', 1)
        }
        
        if query:
            request_params['query'] = query
        
        request_params.update(params)
        
        return self._request(endpoint, request_params)
    
    def get_detail(self, target: str, id: str = None, **params) -> Dict[str, Any]:
        """
        상세 조회 API 호출
        
        Args:
            target: 조회 대상
            id: 문서 ID
            **params: 추가 파라미터
            
        Returns:
            상세 정보
        """
        endpoint = "/lawService.do"
        
        request_params = {
            'target': target,
            'type': params.pop('type', 'JSON')
        }
        
        if id:
            # ID 또는 MST 파라미터 처리
            if target in ['law', 'eflaw', 'lsHistory']:
                request_params['MST'] = id
            else:
                request_params['ID'] = id
        
        request_params.update(params)
        
        return self._request(endpoint, request_params)
    
    def parse_xml_response(self, xml_text: str) -> Dict[str, Any]:
        """
        XML 응답 파싱
        
        Args:
            xml_text: XML 텍스트
            
        Returns:
            파싱된 데이터
        """
        try:
            root = ET.fromstring(xml_text)
            return self._xml_to_dict(root)
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            return {"error": "XML parsing failed", "raw": xml_text[:500]}
    
    def parse_json_response(self, json_text: str) -> Dict[str, Any]:
        """
        JSON 응답 파싱
        
        Args:
            json_text: JSON 텍스트
            
        Returns:
            파싱된 데이터
        """
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {"error": "JSON parsing failed", "raw": json_text[:500]}
    
    def _xml_to_dict(self, element) -> Union[Dict, List, str]:
        """
        XML Element를 딕셔너리로 변환
        
        Args:
            element: XML Element
            
        Returns:
            변환된 딕셔너리
        """
        if element is None:
            return None
        
        # 자식 요소가 없으면 텍스트 반환
        if not list(element):
            return element.text
        
        result = {}
        
        # 자식 요소들을 딕셔너리로 변환
        for child in element:
            child_data = self._xml_to_dict(child)
            
            # 같은 태그가 여러 개 있으면 리스트로 처리
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        # 속성이 있으면 추가
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # 텍스트가 있으면 추가
        if element.text and element.text.strip():
            result['@text'] = element.text.strip()
        
        return result


class OpenAIHelper:
    """OpenAI API 헬퍼 클래스"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        초기화
        
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("OpenAI API key not found. AI features will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("OpenAI library not installed. Run: pip install openai")
                self.enabled = False
    
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
            4. 추가 고려사항"""
            
            user_prompt = f"""
            질문: {query}
            
            참고 자료:
            {context_text}
            
            위 자료를 바탕으로 질문에 대해 답변해주세요.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
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
                model="gpt-3.5-turbo",
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
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """
        컨텍스트 정보를 텍스트로 포맷팅
        
        Args:
            context: 컨텍스트 정보
            
        Returns:
            포맷팅된 텍스트
        """
        formatted = []
        
        if 'laws' in context:
            formatted.append("관련 법령:")
            for law in context['laws'][:3]:  # 최대 3개만
                formatted.append(f"- {law.get('법령명', '')} : {law.get('조문내용', '')[:200]}...")
        
        if 'cases' in context:
            formatted.append("\n관련 판례:")
            for case in context['cases'][:3]:
                formatted.append(f"- {case.get('사건명', '')} ({case.get('선고일자', '')})")
                formatted.append(f"  {case.get('판시사항', '')[:200]}...")
        
        if 'interpretations' in context:
            formatted.append("\n관련 해석:")
            for interp in context['interpretations'][:3]:
                formatted.append(f"- {interp.get('안건명', '')}")
                formatted.append(f"  {interp.get('회답', '')[:200]}...")
        
        return "\n".join(formatted)


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


# 테스트 코드
if __name__ == "__main__":
    # API 클라이언트 테스트
    print("=== 법제처 API 클라이언트 테스트 ===")
    
    # 법제처 API 테스트
    law_client = LawAPIClient()
    
    # 법령 검색 테스트
    print("\n1. 법령 검색 테스트")
    results = law_client.search('law', '도로교통법', display=5)
    if 'law' in results:
        laws = results['law'] if isinstance(results['law'], list) else [results['law']]
        for law in laws[:3]:
            print(f"- {law.get('법령명한글', 'N/A')} ({law.get('공포일자', 'N/A')})")
    
    # 캐시 테스트
    print("\n2. 캐시 테스트")
    start_time = time.time()
    results1 = law_client.search('law', '민법', display=5)
    time1 = time.time() - start_time
    
    start_time = time.time()
    results2 = law_client.search('law', '민법', display=5)  # 캐시에서 가져옴
    time2 = time.time() - start_time
    
    print(f"첫 번째 요청: {time1:.2f}초")
    print(f"두 번째 요청 (캐시): {time2:.2f}초")
    
    # OpenAI 테스트 (API 키가 있는 경우만)
    print("\n3. OpenAI Helper 테스트")
    ai_helper = OpenAIHelper()
    if ai_helper.enabled:
        summary = ai_helper.summarize_law("이 법은 도로에서 일어나는 교통상의 모든 위험과 장해를 방지하고 제거하여 안전하고 원활한 교통을 확보함을 목적으로 한다.", 50)
        print(f"요약: {summary}")
    else:
        print("OpenAI API 키가 설정되지 않아 테스트를 건너뜁니다.")
    
    print("\n테스트 완료!")
