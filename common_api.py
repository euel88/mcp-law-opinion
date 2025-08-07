"""
common_api.py - 공통 API 클라이언트 모듈 (수정 버전)
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
    
    def search(self, target: str, **params) -> Dict[str, Any]:
        """
        검색 API 호출
        
        Args:
            target: 검색 대상 (law, prec, detc 등)
            **params: 검색 파라미터
        
        Returns:
            API 응답을 파싱한 딕셔너리
        """
        url = f"{self.BASE_URL}/lawSearch.do"
        
        # 필수 파라미터 설정
        params['OC'] = self.oc_key
        params['target'] = target
        
        # type 파라미터가 없으면 JSON 기본값 설정
        if 'type' not in params:
            params['type'] = 'json'
        
        # query 파라미터가 없으면 기본값 설정
        if 'query' not in params:
            params['query'] = ''
        
        logger.info(f"API 호출: {url} with target={target}, query={params.get('query')}")
        
        # 캐시 확인
        cache_key = self.cache._generate_key(f"{target}_search", params)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # 응답 파싱
            result = self._parse_response(response, target)
            
            # 캐시 저장
            self.cache.set(cache_key, result)
            
            return result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {str(e)}")
            return {'status': 'error', 'error': str(e), 'totalCnt': 0, 'data': []}
    
    def get_detail(self, target: str, **params) -> Dict[str, Any]:
        """
        상세 조회 API 호출
        
        Args:
            target: 조회 대상
            **params: 조회 파라미터
        
        Returns:
            API 응답
        """
        url = f"{self.BASE_URL}/lawService.do"
        
        # 필수 파라미터 설정
        params['OC'] = self.oc_key
        params['target'] = target
        
        if 'type' not in params:
            params['type'] = 'json'
        
        logger.info(f"API 상세 조회: {url} with target={target}")
        
        # 캐시 확인
        cache_key = self.cache._generate_key(f"{target}_detail", params)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # 응답 파싱
            result = self._parse_response(response, target)
            
            # 캐시 저장
            self.cache.set(cache_key, result)
            
            return result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API 상세 조회 실패: {str(e)}")
            return {'status': 'error', 'error': str(e), 'data': {}}
    
    def _parse_response(self, response: requests.Response, target: str) -> Dict[str, Any]:
        """
        API 응답을 파싱하여 통일된 형태로 반환
        
        Args:
            response: requests Response 객체
            target: API 타겟
        
        Returns:
            파싱된 결과
        """
        try:
            content_type = response.headers.get('Content-Type', '')
            
            # JSON 응답 처리
            if 'json' in content_type.lower() or response.text.strip().startswith('{'):
                try:
                    data = response.json()
                    
                    # 법제처 API JSON 응답 구조에 맞게 파싱
                    if isinstance(data, dict):
                        # 에러 체크
                        if 'errorCode' in data or 'error' in data:
                            return {
                                'status': 'error',
                                'error': data.get('errorMsg', data.get('error', 'Unknown error')),
                                'totalCnt': 0,
                                'data': []
                            }
                        
                        # 성공 응답 파싱
                        result = {
                            'status': 'success',
                            'totalCnt': data.get('totalCnt', 0),
                            'currentCnt': data.get('currentCnt', 0),
                            'page': data.get('page', 1),
                            'data': []
                        }
                        
                        # 데이터 추출 (target에 따라 다른 키 사용)
                        if target == 'law':
                            result['data'] = data.get('law', [])
                        elif target == 'prec':
                            result['data'] = data.get('prec', [])
                        elif target == 'detc':
                            result['data'] = data.get('detc', [])
                        elif target == 'expc':
                            result['data'] = data.get('expc', [])
                        elif target == 'decc':
                            result['data'] = data.get('decc', [])
                        else:
                            # 기타 타겟의 경우 일반적인 키 시도
                            for key in ['items', 'list', 'data', target]:
                                if key in data and isinstance(data[key], list):
                                    result['data'] = data[key]
                                    break
                        
                        return result
                    
                except json.JSONDecodeError:
                    pass
            
            # XML 응답 처리
            if 'xml' in content_type.lower() or response.text.strip().startswith('<?xml'):
                try:
                    root = ET.fromstring(response.text)
                    
                    # 에러 체크
                    error_msg = root.findtext('.//errorMsg')
                    if error_msg:
                        return {'status': 'error', 'error': error_msg, 'totalCnt': 0, 'data': []}
                    
                    # 기본 정보 추출
                    result = {
                        'status': 'success',
                        'totalCnt': int(root.findtext('.//totalCnt', '0')),
                        'page': int(root.findtext('.//page', '1')),
                        'data': []
                    }
                    
                    # 데이터 추출
                    items = []
                    if target == 'law':
                        items = root.findall('.//law')
                    elif target == 'prec':
                        items = root.findall('.//prec')
                    elif target == 'detc':
                        items = root.findall('.//detc')
                    elif target == 'expc':
                        items = root.findall('.//expc')
                    elif target == 'decc':
                        items = root.findall('.//decc')
                    else:
                        # 일반적인 item 태그 찾기
                        items = root.findall('.//item')
                    
                    # XML 요소를 딕셔너리로 변환
                    for item in items:
                        item_dict = {}
                        for child in item:
                            if child.text:
                                item_dict[child.tag] = child.text
                        if item_dict:
                            result['data'].append(item_dict)
                    
                    return result
                    
                except ET.ParseError as e:
                    logger.error(f"XML 파싱 오류: {str(e)}")
            
            # HTML 응답인 경우
            if response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                return {
                    'status': 'success',
                    'html': response.text,
                    'totalCnt': 0,
                    'data': []
                }
            
            # 기타 응답
            return {
                'status': 'error',
                'error': 'Unknown response format',
                'raw': response.text[:500],
                'totalCnt': 0,
                'data': []
            }
                
        except Exception as e:
            logger.error(f"응답 파싱 중 오류: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'totalCnt': 0,
                'data': []
            }


class OpenAIHelper:
    """OpenAI API 헬퍼 클래스"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        초기화
        
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
            model: 사용할 모델
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
            except ImportError:
                logger.error("OpenAI library not installed. Run: pip install openai")
                self.enabled = False
    
    def set_model(self, model: str):
        """모델 변경"""
        self.model = model
    
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
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """컨텍스트 정보를 텍스트로 포맷팅"""
        formatted = []
        
        # 법령
        if 'laws' in context and context['laws']:
            formatted.append("관련 법령:")
            for law in context['laws'][:3]:
                formatted.append(f"- {law.get('법령명한글', '')} : {law.get('조문내용', '')[:200]}...")
        
        # 판례
        if 'cases' in context and context['cases']:
            formatted.append("\n관련 판례:")
            for case in context['cases'][:3]:
                formatted.append(f"- {case.get('사건명', '')} ({case.get('선고일자', '')})")
                formatted.append(f"  {case.get('판시사항', '')[:200]}...")
        
        return "\n".join(formatted)
