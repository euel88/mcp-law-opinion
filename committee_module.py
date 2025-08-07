"""
위원회 결정문 검색 모듈
법제처 API를 통해 14개 위원회의 결정문을 검색하고 조회합니다.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import json
import re

# common_api.py의 LawAPIClient를 import
from common_api import LawAPIClient

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CommitteeInfo:
    """위원회 정보를 담는 데이터 클래스"""
    code: str  # 위원회 코드 (예: ppc, ftc 등)
    name: str  # 위원회 한글명
    search_field: str  # 기본 검색 필드명
    search_options: Dict[int, str]  # 검색 범위 옵션
    sort_options: Dict[str, str]  # 정렬 옵션
    list_fields: Dict[str, str]  # 목록 조회 시 필드 매핑
    detail_fields: Dict[str, str]  # 상세 조회 시 필드 매핑


class CommitteeDecisionSearcher:
    """
    위원회 결정문 검색 클래스
    14개 위원회의 결정문을 통합적으로 검색하고 조회할 수 있습니다.
    """
    
    # 위원회별 메타데이터 정의
    COMMITTEES = {
        'ppc': CommitteeInfo(
            code='ppc',
            name='개인정보보호위원회',
            search_field='안건명',
            search_options={1: '안건명', 2: '본문검색'},
            sort_options={
                'lasc': '안건명 오름차순', 'ldes': '안건명 내림차순',
                'dasc': '의결일자 오름차순', 'ddes': '의결일자 내림차순',
                'nasc': '의안번호 오름차순', 'ndes': '의안번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '안건명',
                'number': '의안번호',
                'date': '의결일',
                'type': '회의종류',
                'decision': '결정구분',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'org': '기관명',
                'title': '안건명',
                'number': '의안번호',
                'meeting_type': '회의종류',
                'decision': '결정',
                'applicant': '신청인',
                'date': '의결연월일',
                'order': '주문',
                'reason': '이유',
                'background': '배경',
                'main_content': '주요내용',
                'summary': '결정요지'
            }
        ),
        'eiac': CommitteeInfo(
            code='eiac',
            name='고용보험심사위원회',
            search_field='사건명',
            search_options={1: '사건명', 2: '본문검색'},
            sort_options={
                'lasc': '사건명 오름차순', 'ldes': '사건명 내림차순',
                'dasc': '의결일자 오름차순', 'ddes': '의결일자 내림차순',
                'nasc': '사건번호 오름차순', 'ndes': '사건번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '사건명',
                'number': '사건번호',
                'date': '의결일자',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'case_type': '사건의분류',
                'doc_type': '의결서종류',
                'summary': '개요',
                'number': '사건번호',
                'title': '사건명',
                'applicant': '청구인',
                'agent': '대리인',
                'respondent': '피청구인',
                'interested': '이해관계인',
                'order': '주문',
                'claim': '청구취지',
                'reason': '이유',
                'date': '의결일자',
                'org': '기관명'
            }
        ),
        'ftc': CommitteeInfo(
            code='ftc',
            name='공정거래위원회',
            search_field='사건명',
            search_options={1: '사건명', 2: '본문검색'},
            sort_options={
                'lasc': '사건명 오름차순', 'ldes': '사건명 내림차순',
                'dasc': '의결일자 오름차순', 'ddes': '의결일자 내림차순',
                'nasc': '사건번호 오름차순', 'ndes': '사건번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '사건명',
                'number': '사건번호',
                'doc_type': '문서유형',
                'meeting_type': '회의종류',
                'decision_number': '결정번호',
                'date': '결정일자',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'doc_type': '문서유형',
                'number': '사건번호',
                'title': '사건명',
                'defendant': '피심정보명',
                'defendant_content': '피심정보내용',
                'meeting_type': '회의종류',
                'decision_number': '결정번호',
                'date': '결정일자',
                'decision_text': '의결문',
                'order': '주문',
                'claim': '신청취지',
                'reason': '이유',
                'commissioner': '위원정보',
                'summary': '결정요지'
            }
        ),
        'acr': CommitteeInfo(
            code='acr',
            name='국민권익위원회',
            search_field='민원표시',
            search_options={1: '민원표시', 2: '본문검색'},
            sort_options={
                'lasc': '민원표시 오름차순', 'ldes': '민원표시 내림차순',
                'dasc': '의결일 오름차순', 'ddes': '의결일 내림차순',
                'nasc': '의안번호 오름차순', 'ndes': '의안번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '제목',
                'complaint': '민원표시명',
                'number': '의안번호',
                'meeting_type': '회의종류',
                'decision': '결정구분',
                'date': '의결일',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'org': '기관명',
                'meeting_type': '회의종류',
                'decision': '결정구분',
                'number': '의안번호',
                'complaint': '민원표시',
                'title': '제목',
                'applicant': '신청인',
                'agent': '대리인',
                'respondent': '피신청인',
                'related_org': '관계기관',
                'date': '의결일',
                'order': '주문',
                'reason': '이유',
                'decision_text': '의결문',
                'commissioner': '위원정보',
                'summary': '결정요지'
            }
        ),
        'fsc': CommitteeInfo(
            code='fsc',
            name='금융위원회',
            search_field='안건명',
            search_options={1: '안건명', 2: '본문검색'},
            sort_options={
                'lasc': '안건명 오름차순', 'ldes': '안건명 내림차순',
                'nasc': '의결번호 오름차순', 'ndes': '의결번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '안건명',
                'number': '의결번호',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'org': '기관명',
                'number': '의결번호',
                'title': '안건명',
                'target_info': '조치대상자의인적사항',
                'target': '조치대상',
                'action': '조치내용',
                'reason': '조치이유'
            }
        ),
        'nlrc': CommitteeInfo(
            code='nlrc',
            name='노동위원회',
            search_field='제목',
            search_options={1: '제목', 2: '본문검색'},
            sort_options={
                'lasc': '제목 오름차순', 'ldes': '제목 내림차순',
                'dasc': '등록일 오름차순', 'ddes': '등록일 내림차순',
                'nasc': '사건번호 오름차순', 'ndes': '사건번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '제목',
                'number': '사건번호',
                'date': '등록일',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'org': '기관명',
                'number': '사건번호',
                'data_type': '자료구분',
                'department': '담당부서',
                'date': '등록일',
                'title': '제목',
                'content': '내용',
                'judgment': '판정사항',
                'judgment_summary': '판정요지',
                'result': '판정결과'
            }
        ),
        'kcc': CommitteeInfo(
            code='kcc',
            name='방송통신위원회',
            search_field='안건명',
            search_options={1: '안건명', 2: '본문검색'},
            sort_options={
                'lasc': '안건명 오름차순', 'ldes': '안건명 내림차순',
                'dasc': '의결연월일 오름차순', 'ddes': '의결연월일 내림차순',
                'nasc': '안건번호 오름차순', 'ndes': '안건번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '안건명',
                'number': '안건번호',
                'date': '의결일자',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'org': '기관명',
                'doc_type': '의결서유형',
                'agenda_number': '안건번호',
                'case_number': '사건번호',
                'title': '안건명',
                'case_title': '사건명',
                'defendant': '피심인',
                'defendant2': '피심의인',
                'applicant': '청구인',
                'reference': '참고인',
                'original': '원심결정',
                'date': '의결일자',
                'order': '주문',
                'reason': '이유'
            }
        ),
        'iaciac': CommitteeInfo(
            code='iaciac',
            name='산업재해보상보험재심사위원회',
            search_field='사건',
            search_options={1: '사건', 2: '본문검색'},
            sort_options={
                'lasc': '사건 오름차순', 'ldes': '사건 내림차순',
                'dasc': '의결일자 오름차순', 'ddes': '의결일자 내림차순',
                'nasc': '사건번호 오름차순', 'ndes': '사건번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '사건',
                'number': '사건번호',
                'date': '의결일자',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'case_major': '사건대분류',
                'case_middle': '사건중분류',
                'case_minor': '사건소분류',
                'issue': '쟁점',
                'number': '사건번호',
                'date': '의결일자',
                'title': '사건',
                'applicant': '청구인',
                'injured_worker': '재해근로자',
                'injured': '재해자',
                'original_org': '원처분기관',
                'order': '주문',
                'claim': '청구취지',
                'reason': '이유'
            }
        ),
        'oclt': CommitteeInfo(
            code='oclt',
            name='중앙토지수용위원회',
            search_field='제목',
            search_options={1: '제목', 2: '본문검색'},
            sort_options={
                'lasc': '제목 오름차순',
                'ldes': '제목 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '제목',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'title': '제목',
                'related_law': '관련법리',
                'related_rule': '관련규정',
                'judgment': '판단',
                'basis': '근거',
                'annotation': '주해'
            }
        ),
        'ecc': CommitteeInfo(
            code='ecc',
            name='중앙환경분쟁조정위원회',
            search_field='사건명',
            search_options={1: '사건명', 2: '본문검색'},
            sort_options={
                'lasc': '사건명 오름차순', 'ldes': '사건명 내림차순',
                'nasc': '의결번호 오름차순', 'ndes': '의결번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '사건명',
                'number': '의결번호',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'number': '의결번호',
                'title': '사건명',
                'summary': '사건의개요',
                'applicant': '신청인',
                'respondent': '피신청인',
                'progress': '분쟁의경과',
                'party_claim': '당사자주장',
                'investigation': '사실조사결과',
                'evaluation': '평가의견',
                'order': '주문',
                'reason': '이유'
            }
        ),
        'sfc': CommitteeInfo(
            code='sfc',
            name='증권선물위원회',
            search_field='안건명',
            search_options={1: '안건명', 2: '본문검색'},
            sort_options={
                'lasc': '안건명 오름차순', 'ldes': '안건명 내림차순',
                'nasc': '의결번호 오름차순', 'ndes': '의결번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '안건명',
                'number': '의결번호',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'org': '기관명',
                'number': '의결번호',
                'title': '안건명',
                'target_info': '조치대상자의인적사항',
                'target': '조치대상',
                'action': '조치내용',
                'reason': '조치이유'
            }
        ),
        'nhrck': CommitteeInfo(
            code='nhrck',
            name='국가인권위원회',
            search_field='사건명',
            search_options={1: '사건명', 2: '본문검색'},
            sort_options={
                'lasc': '사건명 오름차순', 'ldes': '사건명 내림차순',
                'nasc': '의결번호 오름차순', 'ndes': '의결번호 내림차순'
            },
            list_fields={
                'id': '결정문일련번호',
                'title': '사건명',
                'number': '사건번호',
                'date': '의결일자',
                'base_date': '데이터기준일시',
                'link': '결정문상세링크'
            },
            detail_fields={
                'id': '결정문일련번호',
                'org': '기관명',
                'committee': '위원회명',
                'title': '사건명',
                'number': '사건번호',
                'date': '의결일자',
                'order': '주문',
                'reason': '이유',
                'commissioner': '위원정보',
                'summary': '결정요지',
                'judgment_summary': '판단요지',
                'order_summary': '주문요지',
                'category': '분류명',
                'decision_type': '결정유형',
                'applicant': '신청인',
                'respondent': '피신청인',
                'victim': '피해자',
                'investigated': '피조사자',
                'download_url': '원본다운로드URL',
                'view_url': '바로보기URL',
                'full_text': '결정례전문',
                'base_date': '데이터기준일시'
            }
        )
    }
    
    def __init__(self, api_client: Optional[LawAPIClient] = None):
        """
        초기화 메서드
        
        Args:
            api_client: LawAPIClient 인스턴스 (None이면 내부에서 생성)
        """
        self.api_client = api_client or LawAPIClient()
        self._cache = {}  # 간단한 메모리 캐시
        logger.info(f"CommitteeDecisionSearcher 초기화 완료 - {len(self.COMMITTEES)}개 위원회 지원")
    
    def _normalize_list_item(self, item: Dict, committee_info: CommitteeInfo) -> Dict[str, Any]:
        """
        목록 검색 결과를 정규화된 형식으로 변환
        
        Args:
            item: 원본 검색 결과 항목
            committee_info: 위원회 정보
            
        Returns:
            정규화된 결과 딕셔너리
        """
        normalized = {
            'committee_code': committee_info.code,
            'committee_name': committee_info.name
        }
        
        # 필드 매핑
        for key, field_name in committee_info.list_fields.items():
            value = item.get(field_name, '')
            if value:
                normalized[key] = value
        
        return normalized
    
    def _normalize_detail(self, detail: Dict, committee_info: CommitteeInfo) -> Dict[str, Any]:
        """
        상세 조회 결과를 정규화된 형식으로 변환
        
        Args:
            detail: 원본 상세 조회 결과
            committee_info: 위원회 정보
            
        Returns:
            정규화된 결과 딕셔너리
        """
        normalized = {
            'committee_code': committee_info.code,
            'committee_name': committee_info.name
        }
        
        # 필드 매핑
        for key, field_name in committee_info.detail_fields.items():
            value = detail.get(field_name, '')
            if value:
                # HTML 태그 제거
                if isinstance(value, str) and '<' in value:
                    value = re.sub(r'<[^>]+>', '', value)
                normalized[key] = value
        
        return normalized
    
    def search_by_committee(
        self,
        committee_code: str,
        query: str = "",
        search: int = 1,
        display: int = 20,
        page: int = 1,
        sort: str = "lasc",
        gana: str = None
    ) -> Dict[str, Any]:
        """
        특정 위원회의 결정문을 검색합니다.
        
        Args:
            committee_code: 위원회 코드 (예: 'ppc', 'ftc' 등)
            query: 검색어
            search: 검색범위 (1: 기본필드, 2: 본문검색)
            display: 검색 결과 개수 (최대 100)
            page: 페이지 번호
            sort: 정렬 옵션
            gana: 사전식 검색 (가나다순)
            
        Returns:
            검색 결과 딕셔너리
        """
        if committee_code not in self.COMMITTEES:
            raise ValueError(f"지원하지 않는 위원회 코드입니다: {committee_code}")
        
        committee = self.COMMITTEES[committee_code]
        logger.info(f"{committee.name} 결정문 검색 - 검색어: {query}, 페이지: {page}")
        
        # 캐시 키 생성
        cache_key = f"search_{committee_code}_{query}_{search}_{display}_{page}_{sort}"
        if cache_key in self._cache:
            logger.debug(f"캐시에서 결과 반환: {cache_key}")
            return self._cache[cache_key]
        
        # API 파라미터 구성
        params = {
            'target': committee_code,
            'display': min(display, 100),
            'page': page,
            'sort': sort
        }
        
        # 선택적 파라미터 추가
        if query:
            params['query'] = query
            params['search'] = search
        if gana:
            params['gana'] = gana
        
        try:
            # API 호출
            response = self.api_client.search(
                target=committee_code,
                query=query if query else None,
                **params
            )
            
            # 결과 파싱 및 정규화
            if response.get('success'):
                decisions = []
                items = response.get('decisions', response.get('items', []))
                
                for item in items:
                    normalized_item = self._normalize_list_item(item, committee)
                    decisions.append(normalized_item)
                
                result = {
                    'success': True,
                    'committee_code': committee_code,
                    'committee_name': committee.name,
                    'query': query,
                    'total_count': response.get('totalCnt', len(decisions)),
                    'page': page,
                    'display': display,
                    'decisions': decisions
                }
                
                # 캐시 저장
                self._cache[cache_key] = result
                
                logger.info(f"검색 완료 - 총 {result['total_count']}건, 현재 페이지 {len(decisions)}건")
                return result
            else:
                raise Exception(response.get('error', '검색 실패'))
                
        except Exception as e:
            logger.error(f"{committee.name} 검색 중 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'committee_code': committee_code,
                'committee_name': committee.name,
                'query': query
            }
    
    def get_decision_detail(
        self,
        committee_code: str,
        decision_id: Union[int, str],
        fields: str = None
    ) -> Dict[str, Any]:
        """
        특정 결정문의 상세 내용을 조회합니다.
        
        Args:
            committee_code: 위원회 코드
            decision_id: 결정문 일련번호
            fields: 응답 항목 옵션 (특정 필드만 조회, nhrck만 지원)
            
        Returns:
            결정문 상세 내용 딕셔너리
        """
        if committee_code not in self.COMMITTEES:
            raise ValueError(f"지원하지 않는 위원회 코드입니다: {committee_code}")
        
        committee = self.COMMITTEES[committee_code]
        logger.info(f"{committee.name} 결정문 상세 조회 - ID: {decision_id}")
        
        # 캐시 키 생성
        cache_key = f"detail_{committee_code}_{decision_id}"
        if cache_key in self._cache:
            logger.debug(f"캐시에서 결과 반환: {cache_key}")
            return self._cache[cache_key]
        
        # API 파라미터 구성
        params = {
            'target': committee_code,
            'ID': str(decision_id)
        }
        
        # 국가인권위원회의 경우 fields 파라미터 지원
        if committee_code == 'nhrck' and fields:
            params['fields'] = fields
        
        try:
            # API 호출
            response = self.api_client.get_detail(
                target=committee_code,
                id=str(decision_id),
                **params
            )
            
            # 결과 파싱 및 정규화
            if response.get('success'):
                detail = response.get('detail', response.get('data', {}))
                normalized_detail = self._normalize_detail(detail, committee)
                
                result = {
                    'success': True,
                    'committee_code': committee_code,
                    'committee_name': committee.name,
                    'decision_id': decision_id,
                    'detail': normalized_detail
                }
                
                # 캐시 저장
                self._cache[cache_key] = result
                
                logger.info(f"상세 조회 완료 - ID: {decision_id}")
                return result
            else:
                raise Exception(response.get('error', '조회 실패'))
                
        except Exception as e:
            logger.error(f"{committee.name} 상세 조회 중 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'committee_code': committee_code,
                'committee_name': committee.name,
                'decision_id': decision_id
            }
    
    def search_all_committees(
        self,
        query: str,
        search: int = 1,
        display_per_committee: int = 5,
        committees: List[str] = None
    ) -> Dict[str, Any]:
        """
        모든 위원회(또는 지정된 위원회들)를 대상으로 통합 검색합니다.
        
        Args:
            query: 검색어
            search: 검색범위 (1: 기본필드, 2: 본문검색)
            display_per_committee: 위원회당 검색 결과 개수
            committees: 검색할 위원회 코드 리스트 (None이면 전체)
            
        Returns:
            위원회별 검색 결과를 포함한 딕셔너리
        """
        if not query:
            return {
                'success': False,
                'error': '검색어가 필요합니다.',
                'query': query
            }
        
        logger.info(f"통합 검색 시작 - 검색어: {query}")
        
        # 검색할 위원회 목록 결정
        target_committees = committees or list(self.COMMITTEES.keys())
        
        results = {
            'success': True,
            'query': query,
            'search_type': '본문검색' if search == 2 else '제목검색',
            'total_count': 0,
            'committees': {},
            'all_decisions': []  # 통합 결과
        }
        
        for code in target_committees:
            if code not in self.COMMITTEES:
                logger.warning(f"잘못된 위원회 코드 무시: {code}")
                continue
            
            committee = self.COMMITTEES[code]
            logger.info(f"{committee.name} 검색 중...")
            
            # 각 위원회별로 검색
            committee_result = self.search_by_committee(
                committee_code=code,
                query=query,
                search=search,
                display=display_per_committee
            )
            
            if committee_result.get('success'):
                decisions = committee_result.get('decisions', [])
                
                results['committees'][code] = {
                    'name': committee.name,
                    'count': committee_result.get('total_count', 0),
                    'decisions': decisions
                }
                
                # 통합 결과에 추가
                results['all_decisions'].extend(decisions)
                results['total_count'] += committee_result.get('total_count', 0)
            else:
                results['committees'][code] = {
                    'name': committee.name,
                    'error': committee_result.get('error', '검색 실패'),
                    'count': 0,
                    'decisions': []
                }
        
        # 통합 결과를 날짜순으로 정렬 (최신순)
        results['all_decisions'].sort(
            key=lambda x: x.get('date', ''),
            reverse=True
        )
        
        logger.info(f"통합 검색 완료 - 총 {results['total_count']}건")
        return results
    
    def get_recent_decisions(
        self,
        days: int = 7,
        committees: List[str] = None,
        display_per_committee: int = 10
    ) -> Dict[str, Any]:
        """
        최근 며칠간의 결정문을 조회합니다.
        
        Args:
            days: 조회할 일수 (기본 7일)
            committees: 조회할 위원회 코드 리스트 (None이면 전체)
            display_per_committee: 위원회당 조회 개수
            
        Returns:
            위원회별 최근 결정문 목록
        """
        logger.info(f"최근 {days}일간 결정문 조회")
        
        # 날짜 계산
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        target_committees = committees or list(self.COMMITTEES.keys())
        
        results = {
            'success': True,
            'period': f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
            'days': days,
            'total_count': 0,
            'committees': {},
            'recent_decisions': []  # 통합된 최근 결정문
        }
        
        for code in target_committees:
            if code not in self.COMMITTEES:
                continue
            
            committee = self.COMMITTEES[code]
            
            # 날짜순으로 정렬하여 최근 결정문 조회
            # 대부분의 위원회가 'ddes' (날짜 내림차순) 정렬을 지원
            sort_option = 'ddes' if 'ddes' in committee.sort_options else 'ldes'
            
            committee_result = self.search_by_committee(
                committee_code=code,
                query="",  # 전체 조회
                display=display_per_committee,
                sort=sort_option
            )
            
            if committee_result.get('success'):
                decisions = committee_result.get('decisions', [])
                
                # 날짜 필터링 (가능한 경우)
                filtered_decisions = []
                for decision in decisions:
                    decision_date_str = decision.get('date', '')
                    if decision_date_str:
                        try:
                            # 다양한 날짜 형식 처리
                            for fmt in ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d', '%Y년 %m월 %d일']:
                                try:
                                    decision_date = datetime.strptime(decision_date_str[:10], fmt)
                                    if start_date <= decision_date <= end_date:
                                        filtered_decisions.append(decision)
                                    break
                                except:
                                    continue
                        except:
                            # 날짜 파싱 실패 시 포함
                            filtered_decisions.append(decision)
                    else:
                        # 날짜 정보가 없으면 포함
                        filtered_decisions.append(decision)
                
                results['committees'][code] = {
                    'name': committee.name,
                    'count': len(filtered_decisions),
                    'decisions': filtered_decisions
                }
                
                # 통합 결과에 추가
                results['recent_decisions'].extend(filtered_decisions)
                results['total_count'] += len(filtered_decisions)
            else:
                results['committees'][code] = {
                    'name': committee.name,
                    'error': committee_result.get('error', '조회 실패'),
                    'count': 0,
                    'decisions': []
                }
        
        # 통합 결과를 날짜순으로 정렬 (최신순)
        results['recent_decisions'].sort(
            key=lambda x: x.get('date', ''),
            reverse=True
        )
        
        logger.info(f"최근 {days}일 결정문 조회 완료 - 총 {results['total_count']}건")
        return results
    
    def get_committee_info(self, committee_code: str = None) -> Union[Dict, List[Dict]]:
        """
        위원회 정보를 반환합니다.
        
        Args:
            committee_code: 위원회 코드 (None이면 전체 목록)
            
        Returns:
            위원회 정보 또는 전체 위원회 목록
        """
        if committee_code:
            if committee_code not in self.COMMITTEES:
                raise ValueError(f"지원하지 않는 위원회 코드입니다: {committee_code}")
            
            committee = self.COMMITTEES[committee_code]
            return {
                'code': committee.code,
                'name': committee.name,
                'search_field': committee.search_field,
                'search_options': committee.search_options,
                'sort_options': committee.sort_options,
                'list_fields': list(committee.list_fields.keys()),
                'detail_fields': list(committee.detail_fields.keys())
            }
        else:
            # 전체 위원회 목록 반환
            return [
                {
                    'code': code,
                    'name': info.name,
                    'search_field': info.search_field
                }
                for code, info in self.COMMITTEES.items()
            ]
    
    def search_with_filter(
        self,
        committee_code: str,
        query: str = "",
        date_from: str = None,
        date_to: str = None,
        keywords: List[str] = None,
        exclude_keywords: List[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        고급 필터를 적용한 검색 (확장 기능)
        
        Args:
            committee_code: 위원회 코드
            query: 검색어
            date_from: 시작일 (YYYY-MM-DD)
            date_to: 종료일 (YYYY-MM-DD)
            keywords: 포함해야 할 키워드 리스트
            exclude_keywords: 제외할 키워드 리스트
            **kwargs: 추가 검색 옵션
            
        Returns:
            필터링된 검색 결과
        """
        logger.info(f"고급 검색 - {committee_code}, 검색어: {query}")
        
        # 기본 검색 수행
        results = self.search_by_committee(
            committee_code=committee_code,
            query=query,
            **kwargs
        )
        
        if not results.get('success'):
            return results
        
        filtered_decisions = results.get('decisions', [])
        
        # 날짜 필터링
        if date_from or date_to:
            logger.info(f"날짜 필터 적용: {date_from} ~ {date_to}")
            date_filtered = []
            
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d') if date_from else datetime.min
                end_date = datetime.strptime(date_to, '%Y-%m-%d') if date_to else datetime.max
                
                for decision in filtered_decisions:
                    decision_date_str = decision.get('date', '')
                    if decision_date_str:
                        try:
                            # 다양한 날짜 형식 처리
                            for fmt in ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d']:
                                try:
                                    decision_date = datetime.strptime(decision_date_str[:10], fmt)
                                    if start_date <= decision_date <= end_date:
                                        date_filtered.append(decision)
                                    break
                                except:
                                    continue
                        except:
                            date_filtered.append(decision)
                    else:
                        date_filtered.append(decision)
                
                filtered_decisions = date_filtered
            except Exception as e:
                logger.error(f"날짜 필터링 오류: {str(e)}")
        
        # 키워드 필터링
        if keywords:
            logger.info(f"포함 키워드 필터 적용: {keywords}")
            keyword_filtered = []
            for decision in filtered_decisions:
                text = ' '.join(str(v) for v in decision.values() if v)
                if any(keyword in text for keyword in keywords):
                    keyword_filtered.append(decision)
            filtered_decisions = keyword_filtered
        
        # 제외 키워드 필터링
        if exclude_keywords:
            logger.info(f"제외 키워드 필터 적용: {exclude_keywords}")
            exclude_filtered = []
            for decision in filtered_decisions:
                text = ' '.join(str(v) for v in decision.values() if v)
                if not any(keyword in text for keyword in exclude_keywords):
                    exclude_filtered.append(decision)
            filtered_decisions = exclude_filtered
        
        # 결과 업데이트
        results['decisions'] = filtered_decisions
        results['filtered_count'] = len(filtered_decisions)
        results['filters_applied'] = {
            'date_range': f"{date_from or '전체'} ~ {date_to or '전체'}",
            'include_keywords': keywords or [],
            'exclude_keywords': exclude_keywords or []
        }
        
        logger.info(f"필터링 완료 - {len(filtered_decisions)}건")
        return results
    
    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()
        logger.info("캐시가 초기화되었습니다.")
    
    def get_statistics(self, committee_code: str = None) -> Dict[str, Any]:
        """
        위원회별 통계 정보 제공
        
        Args:
            committee_code: 위원회 코드 (None이면 전체)
            
        Returns:
            통계 정보 딕셔너리
        """
        stats = {
            'timestamp': datetime.now().isoformat(),
            'committees': {}
        }
        
        target_committees = [committee_code] if committee_code else list(self.COMMITTEES.keys())
        
        for code in target_committees:
            if code not in self.COMMITTEES:
                continue
            
            committee = self.COMMITTEES[code]
            
            # 최근 결정문 수 조회
            recent_result = self.search_by_committee(
                committee_code=code,
                display=1,
                sort='ddes' if 'ddes' in committee.sort_options else 'ldes'
            )
            
            stats['committees'][code] = {
                'name': committee.name,
                'total_decisions': recent_result.get('total_count', 0) if recent_result.get('success') else 'N/A',
                'search_options': len(committee.search_options),
                'sort_options': len(committee.sort_options),
                'fields_available': len(committee.detail_fields)
            }
        
        return stats


# 모듈 테스트 코드
if __name__ == "__main__":
    """
    모듈 단독 테스트
    실제 사용 시에는 common_api.py의 LawAPIClient가 필요합니다.
    """
    
    # 테스트를 위한 Mock API Client (실제 환경에서는 제거)
    class MockAPIClient:
        def search(self, target, query=None, **params):
            return {
                'success': True,
                'totalCnt': 10,
                'decisions': [
                    {
                        '결정문일련번호': f'{i}',
                        '안건명': f'테스트 안건 {i}',
                        '의안번호': f'2024-{i:03d}',
                        '의결일': '2024-01-01',
                        '회의종류': '정기회의',
                        '결정구분': '인용'
                    }
                    for i in range(1, 6)
                ]
            }
        
        def get_detail(self, target, id, **params):
            return {
                'success': True,
                'detail': {
                    '결정문일련번호': id,
                    '안건명': f'테스트 안건 상세',
                    '주문': '청구를 인용한다.',
                    '이유': '상세한 이유...'
                }
            }
    
    # Mock 클라이언트로 테스트
    api_client = MockAPIClient()
    searcher = CommitteeDecisionSearcher(api_client)
    
    # 1. 위원회 목록 확인
    print("\n=== 지원 위원회 목록 ===")
    committees = searcher.get_committee_info()
    for committee in committees[:5]:  # 처음 5개만 출력
        print(f"- {committee['code']}: {committee['name']} (검색필드: {committee['search_field']})")
    print(f"... 총 {len(committees)}개 위원회 지원")
    
    # 2. 특정 위원회 상세 정보
    print("\n=== 개인정보보호위원회 상세 정보 ===")
    ppc_info = searcher.get_committee_info('ppc')
    print(f"위원회명: {ppc_info['name']}")
    print(f"검색 옵션: {ppc_info['search_options']}")
    print(f"정렬 옵션 수: {len(ppc_info['sort_options'])}개")
    
    # 3. 개별 위원회 검색 테스트
    print("\n=== 공정거래위원회 검색 테스트 ===")
    ftc_result = searcher.search_by_committee(
        committee_code='ftc',
        query='불공정',
        display=10
    )
    print(f"검색 성공: {ftc_result.get('success')}")
    print(f"총 검색 건수: {ftc_result.get('total_count', 0)}")
    
    # 4. 통합 검색 테스트
    print("\n=== 통합 검색 테스트 ===")
    all_results = searcher.search_all_committees(
        query='개인정보',
        display_per_committee=3,
        committees=['ppc', 'kcc', 'nhrck']
    )
    print(f"검색 성공: {all_results.get('success')}")
    print(f"총 검색 건수: {all_results.get('total_count', 0)}")
    
    # 5. 최근 결정문 조회
    print("\n=== 최근 7일 결정문 ===")
    recent = searcher.get_recent_decisions(
        days=7,
        committees=['ftc', 'fsc'],
        display_per_committee=5
    )
    print(f"조회 기간: {recent['period']}")
    print(f"총 건수: {recent.get('total_count', 0)}")
    
    # 6. 고급 검색 테스트
    print("\n=== 고급 검색 (필터 적용) ===")
    filtered = searcher.search_with_filter(
        committee_code='ppc',
        query='정보',
        date_from='2024-01-01',
        date_to='2024-12-31',
        keywords=['개인', '보호'],
        exclude_keywords=['거부']
    )
    print(f"필터링된 결과: {filtered.get('filtered_count', 0)}건")
    
    # 7. 통계 정보
    print("\n=== 위원회 통계 ===")
    stats = searcher.get_statistics('ppc')
    print(f"통계 시점: {stats['timestamp']}")
    for code, stat in stats['committees'].items():
        print(f"- {stat['name']}: 총 {stat.get('total_decisions', 'N/A')}건")
    
    print("\n✅ 모든 테스트 완료!")
