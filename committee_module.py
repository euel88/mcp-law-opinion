"""
위원회 결정문 검색 모듈
법제처 API를 통해 14개 위원회의 결정문을 검색하고 조회합니다.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta

# common_api.py의 LawAPIClient를 import (이미 구현되어 있다고 가정)
# from common_api import LawAPIClient

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
    id_field: str  # 결과 ID 필드명
    detail_fields: List[str]  # 상세조회 시 포함되는 주요 필드


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
            id_field='ppc id',
            detail_fields=['안건명', '의안번호', '회의종류', '결정구분', '의결일', '주문', '이유']
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
            id_field='eiac id',
            detail_fields=['사건명', '사건번호', '청구인', '피청구인', '주문', '이유', '의결일자']
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
            id_field='ftc id',
            detail_fields=['사건명', '사건번호', '문서유형', '회의종류', '결정번호', '결정일자', '주문', '이유']
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
            id_field='acr id',
            detail_fields=['제목', '민원표시', '의안번호', '신청인', '피신청인', '주문', '이유']
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
            id_field='fsc id',
            detail_fields=['안건명', '의결번호', '조치대상자의인적사항', '조치내용', '조치이유']
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
            id_field='nlrc id',
            detail_fields=['제목', '사건번호', '자료구분', '담당부서', '등록일', '내용', '판정사항']
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
            id_field='kcc id',
            detail_fields=['안건명', '안건번호', '사건번호', '피심인', '의결일자', '주문', '이유']
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
            id_field='iaciac id',
            detail_fields=['사건', '사건번호', '청구인', '재해근로자', '주문', '청구취지', '이유']
        ),
        'oclt': CommitteeInfo(
            code='oclt',
            name='중앙토지수용위원회',
            search_field='제목',
            search_options={1: '제목', 2: '본문검색'},
            sort_options={
                'lasc': '제목 오름차순', 'ldes': '제목 내림차순'
            },
            id_field='oclt id',
            detail_fields=['제목', '관련법리', '관련규정', '판단', '근거']
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
            id_field='ecc id',
            detail_fields=['사건명', '의결번호', '신청인', '피신청인', '사건의개요', '주문', '이유']
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
            id_field='sfc id',
            detail_fields=['안건명', '의결번호', '조치대상자의인적사항', '조치내용', '조치이유']
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
            id_field='nhrck id',
            detail_fields=['사건명', '사건번호', '의결일자', '주문', '이유', '결정유형', '신청인', '피신청인']
        )
    }
    
    def __init__(self, api_client=None):
        """
        초기화 메서드
        
        Args:
            api_client: LawAPIClient 인스턴스 (None이면 내부에서 생성)
        """
        # 실제 구현 시 common_api.py의 LawAPIClient를 사용
        # self.api_client = api_client or LawAPIClient()
        
        # 임시로 api_client를 None으로 설정 (실제 구현 시 제거)
        self.api_client = api_client
        logger.info("CommitteeDecisionSearcher 초기화 완료")
    
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
        logger.info(f"{committee.name} 결정문 검색 - 검색어: {query}")
        
        # API 파라미터 구성
        params = {
            'target': committee_code,
            'type': 'JSON',  # JSON 형식으로 요청
            'display': min(display, 100),  # 최대 100개
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
            # 실제 구현 시 api_client.search() 호출
            # result = self.api_client.search(params)
            
            # 임시 응답 (실제 구현 시 제거)
            result = {
                'success': True,
                'committee': committee.name,
                'query': query,
                'totalCnt': 0,
                'page': page,
                'decisions': []
            }
            
            logger.info(f"검색 완료 - 총 {result.get('totalCnt', 0)}건")
            return result
            
        except Exception as e:
            logger.error(f"검색 중 오류 발생: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'committee': committee.name
            }
    
    def get_decision_detail(
        self,
        committee_code: str,
        decision_id: int,
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
        
        # API 파라미터 구성
        params = {
            'target': committee_code,
            'type': 'JSON',
            'ID': decision_id
        }
        
        # 국가인권위원회의 경우 fields 파라미터 지원
        if committee_code == 'nhrck' and fields:
            params['fields'] = fields
        
        try:
            # 실제 구현 시 api_client.get_detail() 호출
            # result = self.api_client.get_detail(params)
            
            # 임시 응답 (실제 구현 시 제거)
            result = {
                'success': True,
                'committee': committee.name,
                'decision_id': decision_id,
                'detail': {}
            }
            
            logger.info(f"상세 조회 완료 - ID: {decision_id}")
            return result
            
        except Exception as e:
            logger.error(f"상세 조회 중 오류 발생: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'committee': committee.name,
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
        logger.info(f"통합 검색 시작 - 검색어: {query}")
        
        # 검색할 위원회 목록 결정
        target_committees = committees or list(self.COMMITTEES.keys())
        
        results = {
            'query': query,
            'total_count': 0,
            'committees': {}
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
                results['committees'][code] = {
                    'name': committee.name,
                    'count': committee_result.get('totalCnt', 0),
                    'decisions': committee_result.get('decisions', [])
                }
                results['total_count'] += committee_result.get('totalCnt', 0)
            else:
                results['committees'][code] = {
                    'name': committee.name,
                    'error': committee_result.get('error')
                }
        
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
        
        # 날짜 계산 (실제 구현 시 활용)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        target_committees = committees or list(self.COMMITTEES.keys())
        
        results = {
            'period': f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
            'committees': {}
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
                results['committees'][code] = {
                    'name': committee.name,
                    'decisions': committee_result.get('decisions', [])
                }
        
        return results
    
    def get_committee_info(self, committee_code: str = None) -> Any:
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
                'detail_fields': committee.detail_fields
            }
        else:
            # 전체 위원회 목록 반환
            return {
                code: {
                    'name': info.name,
                    'search_field': info.search_field
                }
                for code, info in self.COMMITTEES.items()
            }
    
    def search_with_filter(
        self,
        committee_code: str,
        query: str = "",
        date_from: str = None,
        date_to: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        고급 필터를 적용한 검색 (확장 기능)
        
        Args:
            committee_code: 위원회 코드
            query: 검색어
            date_from: 시작일 (YYYY-MM-DD)
            date_to: 종료일 (YYYY-MM-DD)
            **kwargs: 추가 필터 옵션
            
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
        
        # 날짜 필터링 (클라이언트 사이드)
        # 실제 구현 시 API가 날짜 필터를 지원하지 않으므로
        # 결과를 받아와서 필터링하는 로직 추가 필요
        
        if date_from or date_to:
            logger.info(f"날짜 필터 적용: {date_from} ~ {date_to}")
            # 필터링 로직 구현
            pass
        
        return results


# 모듈 테스트 코드
if __name__ == "__main__":
    """
    모듈 단독 테스트
    실제 사용 시에는 common_api.py의 LawAPIClient를 import하여 사용
    """
    
    # 검색 클래스 생성
    searcher = CommitteeDecisionSearcher()
    
    # 1. 위원회 목록 확인
    print("\n=== 지원 위원회 목록 ===")
    committees = searcher.get_committee_info()
    for code, info in committees.items():
        print(f"- {code}: {info['name']} (검색필드: {info['search_field']})")
    
    # 2. 특정 위원회 상세 정보
    print("\n=== 개인정보보호위원회 상세 정보 ===")
    ppc_info = searcher.get_committee_info('ppc')
    print(f"위원회명: {ppc_info['name']}")
    print(f"검색 옵션: {ppc_info['search_options']}")
    print(f"정렬 옵션: {ppc_info['sort_options']}")
    
    # 3. 개별 위원회 검색 테스트
    print("\n=== 공정거래위원회 검색 테스트 ===")
    ftc_result = searcher.search_by_committee(
        committee_code='ftc',
        query='불공정',
        display=10
    )
    print(f"검색 결과: {ftc_result}")
    
    # 4. 통합 검색 테스트
    print("\n=== 통합 검색 테스트 ===")
    all_results = searcher.search_all_committees(
        query='개인정보',
        display_per_committee=3,
        committees=['ppc', 'kcc', 'nhrck']  # 3개 위원회만 검색
    )
    print(f"총 검색 건수: {all_results['total_count']}")
    
    # 5. 최근 결정문 조회
    print("\n=== 최근 7일 결정문 ===")
    recent = searcher.get_recent_decisions(
        days=7,
        committees=['ftc', 'fsc'],  # 공정거래위, 금융위만
        display_per_committee=5
    )
    print(f"조회 기간: {recent['period']}")
    
    print("\n테스트 완료!")
