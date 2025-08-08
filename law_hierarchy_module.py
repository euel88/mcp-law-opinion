"""
법령 체계도 검색 및 다운로드 전문 모듈 (완전 개선판)
Law Hierarchy Search and Download Module - Complete Enhanced Version
Version 3.0 - 다중 검색 전략 및 관련성 개선
"""

import os
import re
import json
import zipfile
import io
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# ===========================
# 데이터 클래스 정의
# ===========================

@dataclass
class AdminRules:
    """행정규칙 분류"""
    directive: List[Dict] = field(default_factory=list)  # 훈령
    regulation: List[Dict] = field(default_factory=list)  # 예규
    notice: List[Dict] = field(default_factory=list)      # 고시
    guideline: List[Dict] = field(default_factory=list)   # 지침
    rule: List[Dict] = field(default_factory=list)        # 규정
    etc: List[Dict] = field(default_factory=list)         # 기타
    
    def total_count(self) -> int:
        """전체 행정규칙 수"""
        return sum(len(v) for v in asdict(self).values())
    
    def get_all(self) -> List[Dict]:
        """모든 행정규칙 반환"""
        all_rules = []
        for rules_list in asdict(self).values():
            all_rules.extend(rules_list)
        return all_rules

@dataclass
class LawHierarchy:
    """법령 체계 구조"""
    main: Dict = field(default_factory=dict)
    decree: List[Dict] = field(default_factory=list)
    rule: List[Dict] = field(default_factory=list)
    admin_rules: AdminRules = field(default_factory=AdminRules)
    local_laws: List[Dict] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)
    admin_attachments: List[Dict] = field(default_factory=list)
    delegated: List[Dict] = field(default_factory=list)
    related: List[Dict] = field(default_factory=list)  # 관련법령 추가
    
    def get_all_laws(self) -> List[Dict]:
        """모든 관련 법령 반환"""
        all_laws = []
        if self.main:
            all_laws.append(self.main)
        all_laws.extend(self.decree)
        all_laws.extend(self.rule)
        all_laws.extend(self.admin_rules.get_all())
        all_laws.extend(self.local_laws)
        all_laws.extend(self.attachments)
        all_laws.extend(self.admin_attachments)
        all_laws.extend(self.delegated)
        all_laws.extend(self.related)
        return all_laws
    
    def get_statistics(self) -> Dict[str, int]:
        """통계 정보 반환"""
        return {
            'law': 1 if self.main else 0,
            'decree': len(self.decree),
            'rule': len(self.rule),
            'admin': self.admin_rules.total_count(),
            'local': len(self.local_laws),
            'attachment': len(self.attachments) + len(self.admin_attachments),
            'delegated': len(self.delegated),
            'related': len(self.related)
        }

@dataclass
class SearchConfig:
    """검색 설정"""
    include_decree: bool = True
    include_rule: bool = True
    include_admin_rules: bool = True
    include_local: bool = True
    include_attachments: bool = True
    include_admin_attachments: bool = True
    include_delegated: bool = True
    include_related: bool = True  # 관련법령 추가
    search_depth: str = "최대"  # 표준/확장/최대
    debug_mode: bool = False

# ===========================
# 유틸리티 함수
# ===========================

class LawNameProcessor:
    """법령명 처리 유틸리티 (개선)"""
    
    # 부처별 키워드 매핑 (확장)
    DEPARTMENT_KEYWORDS = {
        '금융위원회': ['금융', '자본시장', '증권', '보험', '은행', '여신', '신용', '금융투자', 
                   '펀드', '파생상품', '채권', '주식', '투자', '자산운용', '신탁', '예금'],
        '고용노동부': ['근로', '노동', '고용', '산업안전', '임금', '퇴직', '최저임금', '산재', 
                   '노동조합', '단체협약', '해고', '근로시간'],
        '국토교통부': ['도로', '건축', '주택', '교통', '철도', '항공', '부동산', '국토', 
                   '도시', '택지', '건설', '자동차', '물류', '항만'],
        '행정안전부': ['지방', '행정', '공무원', '재난', '안전', '개인정보', '정보공개', 
                   '지방자치', '선거', '주민등록', '민원'],
        '법무부': ['형법', '민법', '상법', '형사', '민사', '사법', '법무', '교정', 
                '출입국', '국적', '검찰', '변호사'],
        '기획재정부': ['세법', '조세', '관세', '국세', '부가가치세', '소득세', '법인세', 
                   '재정', '예산', '기금', '국유재산', '계약'],
        '보건복지부': ['의료', '건강', '복지', '국민연금', '건강보험', '의약품', '식품', 
                   '장애', '노인', '아동', '보육', '사회보장'],
        '환경부': ['환경', '대기', '수질', '폐기물', '자연', '생태', '기후', '오염', 
                '환경영향평가', '화학물질', '소음', '진동'],
        '산업통상자원부': ['산업', '에너지', '전력', '무역', '통상', '중소기업', '특허', 
                      '표준', '계량', '디자인', '상표', '전기'],
        '과학기술정보통신부': ['정보통신', '과학기술', '방송', '통신', '데이터', '인터넷', 
                        '전파', '소프트웨어', '정보보호', '우주', '원자력'],
        '교육부': ['교육', '학교', '대학', '학원', '평생교육', '교육과정', '교원', 
                '학생', '입학', '학위', '장학'],
        '국방부': ['국방', '군사', '병역', '국군', '방위', '군인', '예비군', '민방위'],
        '외교부': ['외교', '외무', '영사', '여권', '국제', '조약', '재외국민'],
        '문화체육관광부': ['문화', '예술', '체육', '관광', '문화재', '저작권', '콘텐츠', 
                     '게임', '영화', '출판', '스포츠'],
        '농림축산식품부': ['농업', '축산', '농촌', '농지', '식품산업', '농산물', '축산물', 
                     '동물', '식물', '검역', '농협'],
        '해양수산부': ['해양', '수산', '어업', '항만', '선박', '해운', '어촌', '수산물', 
                  '해사', '선원']
    }
    
    # 부처 코드 매핑 (확장)
    DEPARTMENT_CODES = {
        '금융위원회': '1320471',
        '고용노동부': '1492000',
        '국토교통부': '1613000',
        '행정안전부': '1741000',
        '법무부': '1270000',
        '기획재정부': '1051000',
        '보건복지부': '1352000',
        '환경부': '1480000',
        '산업통상자원부': '1450000',
        '과학기술정보통신부': '1721000',
        '교육부': '1342000',
        '외교부': '1262000',
        '통일부': '1263000',
        '국방부': '1290000',
        '문화체육관광부': '1371000',
        '농림축산식품부': '1543000',
        '여성가족부': '1383000',
        '해양수산부': '1192000',
        '중소벤처기업부': '1421000',
        '국세청': '1220000',
        '관세청': '1220100',
        '조달청': '1230000',
        '통계청': '1240000',
        '검찰청': '1280000',
        '병무청': '1300000',
        '방위사업청': '1290300',
        '경찰청': '1320000',
        '소방청': '1661000',
        '문화재청': '1550000',
        '농촌진흥청': '1390000',
        '산림청': '1400000',
        '특허청': '1430000',
        '기상청': '1360000',
        '행정중심복합도시건설청': '1311000',
        '새만금개발청': '1311200'
    }
    
    # 행정규칙 키워드 패턴
    ADMIN_RULE_PATTERNS = {
        '고시': [
            r'[가-힣]+\s*고시(?:\s*제\d+호)?',
            r'[가-힣]+(?:의|에 관한|를 위한)\s*고시',
            r'[가-힣]+\s*기준(?:에 관한)?\s*고시',
            r'[가-힣]+\s*지정\s*고시',
            r'[가-힣]+\s*운영\s*고시'
        ],
        '훈령': [
            r'[가-힣]+\s*훈령(?:\s*제\d+호)?',
            r'[가-힣]+(?:의|에 관한|를 위한)\s*훈령',
            r'[가-힣]+\s*사무처리\s*훈령',
            r'[가-힣]+\s*운영\s*훈령'
        ],
        '예규': [
            r'[가-힣]+\s*예규(?:\s*제\d+호)?',
            r'[가-힣]+(?:의|에 관한|를 위한)\s*예규',
            r'[가-힣]+\s*처리\s*예규',
            r'[가-힣]+\s*사무\s*예규'
        ],
        '지침': [
            r'[가-힣]+\s*지침',
            r'[가-힣]+(?:의|에 관한|를 위한)\s*지침',
            r'[가-힣]+\s*운영\s*지침',
            r'[가-힣]+\s*처리\s*지침',
            r'[가-힣]+\s*가이드라인'
        ],
        '규정': [
            r'[가-힣]+\s*규정',
            r'[가-힣]+(?:의|에 관한|를 위한)\s*규정',
            r'[가-힣]+\s*운영\s*규정',
            r'[가-힣]+\s*처리\s*규정'
        ]
    }
    
    @staticmethod
    def extract_base_name(law_name: str) -> str:
        """법령명에서 기본 명칭 추출 (개선)"""
        # 법령 접미사 제거
        base_name = re.sub(r'(에 관한 |의 |을 위한 |와 |및 )', ' ', law_name)
        base_name = re.sub(r'(법|령|규칙|규정|지침|훈령|예규|고시)(?:$|\s)', '', base_name).strip()
        # 특수문자 제거
        base_name = re.sub(r'[「」『』【】\(\)]', '', base_name)
        # 연속 공백 제거
        base_name = re.sub(r'\s+', ' ', base_name).strip()
        return base_name
    
    @staticmethod
    def extract_core_keywords(law_name: str) -> List[str]:
        """법령명에서 핵심 키워드 추출 (신규)"""
        base_name = LawNameProcessor.extract_base_name(law_name)
        
        # 불용어 제거
        stop_words = {'관한', '법률', '시행', '규칙', '등에', '대한', '및', '의', '을', '를', 
                     '특별', '일반', '기본', '진흥', '지원', '관리', '보호', '증진', '활성화'}
        
        # 키워드 추출
        keywords = []
        words = re.findall(r'[가-힣]+', base_name)
        
        for word in words:
            if len(word) >= 2 and word not in stop_words:
                keywords.append(word)
        
        # 복합어 추출 (2단어 조합)
        if len(words) >= 2:
            for i in range(len(words) - 1):
                compound = words[i] + words[i + 1]
                if len(compound) <= 8:  # 너무 긴 복합어 제외
                    keywords.append(compound)
        
        return list(set(keywords))
    
    @classmethod
    def generate_keywords(cls, law_name: str, law_id: str = None) -> List[str]:
        """검색 키워드 생성 (개선)"""
        keywords = []
        base_name = cls.extract_base_name(law_name)
        
        # 기본 키워드
        keywords.append(law_name)
        keywords.append(base_name)
        
        # 핵심 키워드
        core_keywords = cls.extract_core_keywords(law_name)
        keywords.extend(core_keywords)
        
        # 축약형 생성
        if '과' in base_name:
            parts = base_name.split('과')
            if len(parts) == 2:
                keywords.extend([p.strip() for p in parts])
        
        # 공백 제거 버전
        keywords.append(base_name.replace(' ', ''))
        
        # 법령 ID 추가
        if law_id:
            keywords.append(law_id)
            # MST 번호만 추출 (앞 6자리)
            if len(law_id) >= 6:
                keywords.append(law_id[:6])
        
        # 중복 제거하여 반환
        return list(dict.fromkeys(keywords))
    
    @classmethod
    def estimate_department(cls, law_name: str) -> Optional[str]:
        """법령명으로 소관부처 추정 (개선)"""
        scores = {}
        
        for dept, keywords in cls.DEPARTMENT_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in law_name:
                    # 키워드 길이에 따라 가중치 부여
                    score += len(keyword)
            
            if score > 0:
                scores[dept] = score
        
        if scores:
            # 가장 높은 점수의 부처 반환
            return max(scores, key=scores.get)
        
        return None
    
    @classmethod
    def get_department_code(cls, department: str) -> Optional[str]:
        """부처명으로 부처 코드 반환"""
        return cls.DEPARTMENT_CODES.get(department)
    
    @classmethod
    def extract_admin_rule_references(cls, text: str) -> List[str]:
        """텍스트에서 행정규칙 참조 추출 (신규)"""
        references = []
        
        for rule_type, patterns in cls.ADMIN_RULE_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text)
                references.extend(matches)
        
        # 「」 안의 내용 추출
        bracket_matches = re.findall(r'「([^」]+(?:고시|훈령|예규|지침|규정)[^」]*)」', text)
        references.extend(bracket_matches)
        
        # 중복 제거 및 정제
        cleaned = []
        for ref in references:
            ref = ref.strip()
            if len(ref) >= 3 and len(ref) <= 100:  # 너무 짧거나 긴 것 제외
                cleaned.append(ref)
        
        return list(set(cleaned))

# ===========================
# 법령 체계도 검색 클래스 (완전 개선판)
# ===========================

class LawHierarchySearcher:
    """법령 체계도 검색 클래스 - 다중 검색 전략"""
    
    def __init__(self, law_client: Any, law_searcher: Any = None):
        self.law_client = law_client
        self.law_searcher = law_searcher
        self.name_processor = LawNameProcessor()
        
    def search_hierarchy(self, law_info: Dict, config: SearchConfig) -> LawHierarchy:
        """법령 체계도 전체 검색 (완전 개선)"""
        hierarchy = LawHierarchy(main=law_info)
        
        law_id = law_info.get('법령ID') or law_info.get('법령일련번호')
        law_name = law_info.get('법령명한글', '')
        law_mst = law_info.get('법령MST')
        
        if not law_id or not law_name:
            logger.warning("법령 ID 또는 명칭이 없습니다.")
            return hierarchy
        
        logger.info(f"법령 체계도 검색 시작: {law_name} (ID: {law_id})")
        
        # 1. 법령 상세 정보 조회 (소관부처, 조문내용 등)
        law_detail = self._get_law_detail(law_id, law_mst)
        department = law_detail.get('소관부처명')
        dept_code = law_detail.get('소관부처코드')
        
        # 소관부처 추정
        if not department and not dept_code:
            department = self.name_processor.estimate_department(law_name)
            if department:
                dept_code = self.name_processor.get_department_code(department)
                logger.info(f"소관부처 추정: {department} (코드: {dept_code})")
        
        logger.info(f"소관부처: {department or '미확인'} (코드: {dept_code or '없음'})")
        
        # 2. 관련법령 조회 (lsRlt API)
        if config.include_related and config.search_depth in ["확장", "최대"]:
            hierarchy.related = self._search_related_laws(law_id, law_mst)
        
        # 3. 법령 체계도 API를 통한 직접 연계 조회
        if config.search_depth in ["확장", "최대"]:
            hierarchy_links = self._get_law_hierarchy_links(law_id, law_mst)
            self._process_hierarchy_links(hierarchy_links, hierarchy)
        
        # 4. 법령-자치법규 연계 API (lnkLs)
        if config.include_local:
            linked_locals = self._get_linked_local_laws(law_id, law_mst)
            hierarchy.local_laws.extend(linked_locals)
        
        # 5. 위임 법령 조회
        if config.include_delegated:
            hierarchy.delegated = self._search_delegated_laws_enhanced(law_id, law_mst)
        
        # 6. 시행령/시행규칙 검색
        if config.include_decree:
            hierarchy.decree = self._search_decree_enhanced(law_id, law_name, law_mst, law_detail)
        
        if config.include_rule:
            hierarchy.rule = self._search_rule_enhanced(law_id, law_name, law_mst, law_detail)
        
        # 7. 행정규칙 검색 (다중 전략)
        if config.include_admin_rules:
            hierarchy.admin_rules = self._search_admin_rules_multi_strategy(
                law_id, law_name, law_mst, dept_code, law_detail, config
            )
        
        # 8. 별표서식 검색
        if config.include_attachments:
            hierarchy.attachments = self._search_attachments_enhanced(law_id, law_name, law_mst)
        
        # 9. 행정규칙 별표서식
        if config.include_admin_attachments:
            hierarchy.admin_attachments = self._search_admin_attachments_enhanced(
                hierarchy.admin_rules
            )
        
        # 10. 추가 자치법규 검색 (행정규칙 기반)
        if config.include_local and hierarchy.admin_rules.total_count() > 0:
            additional_locals = self._search_local_laws_from_admin_rules(
                hierarchy.admin_rules, dept_code
            )
            hierarchy.local_laws.extend(additional_locals)
        
        # 중복 제거
        hierarchy.local_laws = self._remove_duplicates(hierarchy.local_laws, '자치법규ID')
        
        logger.info(f"법령 체계도 검색 완료: 총 {len(hierarchy.get_all_laws())}건")
        
        return hierarchy
    
    def _get_law_detail(self, law_id: str, law_mst: Optional[str] = None) -> Dict:
        """법령 상세 정보 조회 (개선)"""
        try:
            params = {'type': 'XML'}
            if law_mst:
                params['MST'] = law_mst
            else:
                params['ID'] = law_id
            
            result = self.law_client.get_detail(target='law', **params)
            
            if result and 'error' not in result:
                # results가 있으면 첫 번째 항목 사용
                if 'results' in result and result['results']:
                    return result['results'][0]
                return result
        except Exception as e:
            logger.error(f"법령 상세 조회 실패: {e}")
        
        return {}
    
    def _search_related_laws(self, law_id: str, law_mst: Optional[str] = None) -> List[Dict]:
        """관련법령 검색 (lsRlt API)"""
        try:
            params = {'display': 100}
            if law_mst:
                params['MST'] = law_mst
            else:
                params['ID'] = law_id
            
            result = self.law_client.search(target='lsRlt', **params)
            
            if result and result.get('totalCnt', 0) > 0:
                logger.info(f"관련법령 {result['totalCnt']}건 발견")
                return result.get('results', [])
        except Exception as e:
            logger.error(f"관련법령 검색 오류: {e}")
        
        return []
    
    def _get_linked_local_laws(self, law_id: str, law_mst: Optional[str] = None) -> List[Dict]:
        """법령-자치법규 연계 조회 (lnkLs API)"""
        try:
            params = {'display': 100}
            if law_mst:
                params['MST'] = law_mst
            else:
                params['ID'] = law_id
            
            result = self.law_client.search(target='lnkLs', **params)
            
            if result and result.get('totalCnt', 0) > 0:
                logger.info(f"연계 자치법규 {result['totalCnt']}건 발견")
                return result.get('results', [])
        except Exception as e:
            logger.error(f"법령-자치법규 연계 조회 오류: {e}")
        
        return []
    
    def _search_admin_rules_multi_strategy(self, law_id: str, law_name: str, law_mst: Optional[str],
                                          dept_code: Optional[str], law_detail: Dict, 
                                          config: SearchConfig) -> AdminRules:
        """행정규칙 검색 - 다중 전략 (완전 개선)"""
        admin_rules = AdminRules()
        seen_ids = set()
        
        # 전략 1: 법령 본문에서 참조된 행정규칙 추출 및 검색
        if law_detail:
            self._search_referenced_admin_rules_from_detail(
                law_detail, admin_rules, seen_ids, dept_code
            )
        
        # 전략 2: 핵심 키워드 기반 검색
        core_keywords = self.name_processor.extract_core_keywords(law_name)
        for keyword in core_keywords[:5]:  # 상위 5개 키워드만
            self._search_admin_rules_by_keyword(
                keyword, admin_rules, seen_ids, dept_code
            )
        
        # 전략 3: 소관부처 전체 행정규칙 필터링 (최대 검색 모드)
        if config.search_depth == "최대" and dept_code:
            self._search_admin_rules_by_department_filtered(
                law_name, core_keywords, dept_code, admin_rules, seen_ids
            )
        
        # 전략 4: 관련법령의 행정규칙 검색
        if config.include_related and hasattr(self, '_related_laws'):
            for related_law in self._related_laws[:5]:  # 상위 5개만
                related_id = related_law.get('법령ID')
                if related_id:
                    self._search_admin_rules_for_related_law(
                        related_id, admin_rules, seen_ids
                    )
        
        # 전략 5: 법령명 변형 검색
        variations = self._generate_law_name_variations(law_name)
        for variation in variations:
            self._search_admin_rules_by_variation(
                variation, admin_rules, seen_ids, dept_code
            )
        
        logger.info(f"행정규칙 검색 완료: 총 {admin_rules.total_count()}건")
        
        return admin_rules
    
    def _search_referenced_admin_rules_from_detail(self, law_detail: Dict, admin_rules: AdminRules,
                                                  seen_ids: Set, dept_code: Optional[str]):
        """법령 상세에서 참조된 행정규칙 검색"""
        # 조문내용에서 행정규칙 참조 추출
        all_content = ""
        
        if '조문내용' in law_detail:
            if isinstance(law_detail['조문내용'], list):
                all_content = " ".join(law_detail['조문내용'])
            else:
                all_content = law_detail['조문내용']
        
        # 법령 전문이 있으면 추가
        if '법령내용' in law_detail:
            all_content += " " + law_detail['법령내용']
        
        # 행정규칙 참조 추출
        references = self.name_processor.extract_admin_rule_references(all_content)
        
        for ref in references:
            try:
                # 정확한 명칭으로 검색
                params = {
                    'target': 'admrul',
                    'query': ref,
                    'display': 10
                }
                
                if dept_code:
                    params['org'] = dept_code
                
                result = self.law_client.search(**params)
                
                if result and result.get('totalCnt', 0) > 0:
                    for rule in result.get('results', []):
                        rule_id = rule.get('행정규칙ID')
                        if rule_id and rule_id not in seen_ids:
                            self._categorize_admin_rule(rule, admin_rules, seen_ids)
                            logger.debug(f"참조 행정규칙 발견: {rule.get('행정규칙명')}")
            except Exception as e:
                logger.error(f"참조 행정규칙 검색 오류: {e}")
    
    def _search_admin_rules_by_keyword(self, keyword: str, admin_rules: AdminRules,
                                      seen_ids: Set, dept_code: Optional[str]):
        """키워드별 행정규칙 검색"""
        rule_types = ['고시', '훈령', '예규', '지침', '규정']
        
        for rule_type in rule_types:
            try:
                # 키워드 + 규칙유형 조합
                params = {
                    'target': 'admrul',
                    'query': f"{keyword} {rule_type}",
                    'display': 20
                }
                
                if dept_code:
                    params['org'] = dept_code
                
                result = self.law_client.search(**params)
                
                if result and result.get('totalCnt', 0) > 0:
                    for rule in result.get('results', []):
                        rule_id = rule.get('행정규칙ID')
                        rule_name = rule.get('행정규칙명', '')
                        
                        # 키워드가 실제로 포함되어 있는지 확인
                        if rule_id and rule_id not in seen_ids and keyword in rule_name:
                            self._categorize_admin_rule(rule, admin_rules, seen_ids)
                            logger.debug(f"키워드 '{keyword}'로 발견: {rule_name}")
            except Exception as e:
                logger.error(f"키워드 행정규칙 검색 오류: {e}")
    
    def _search_admin_rules_by_department_filtered(self, law_name: str, core_keywords: List[str],
                                                  dept_code: str, admin_rules: AdminRules,
                                                  seen_ids: Set):
        """소관부처 전체 행정규칙 필터링"""
        try:
            # 소관부처의 최근 행정규칙 대량 조회
            result = self.law_client.search(
                target='admrul',
                query='*',
                org=dept_code,
                display=1000,  # 최대한 많이
                sort='date'  # 최신순
            )
            
            if result and result.get('totalCnt', 0) > 0:
                for rule in result.get('results', []):
                    rule_id = rule.get('행정규칙ID')
                    rule_name = rule.get('행정규칙명', '')
                    
                    if rule_id and rule_id not in seen_ids:
                        # 관련성 점수 계산
                        relevance_score = self._calculate_relevance_score(
                            rule_name, law_name, core_keywords
                        )
                        
                        # 임계값 이상인 경우만 추가
                        if relevance_score >= 0.3:  # 30% 이상 관련성
                            self._categorize_admin_rule(rule, admin_rules, seen_ids)
                            logger.debug(f"부처 필터링으로 발견 (관련도 {relevance_score:.2f}): {rule_name}")
        except Exception as e:
            logger.error(f"부처 행정규칙 필터링 오류: {e}")
    
    def _calculate_relevance_score(self, rule_name: str, law_name: str, 
                                  core_keywords: List[str]) -> float:
        """관련성 점수 계산"""
        if not core_keywords:
            return 0.0
        
        rule_name_lower = rule_name.lower()
        matches = 0
        
        for keyword in core_keywords:
            if keyword.lower() in rule_name_lower:
                matches += 1
        
        # 법령명 직접 포함 시 높은 점수
        base_law_name = self.name_processor.extract_base_name(law_name)
        if base_law_name in rule_name:
            matches += 3
        
        # 점수 정규화
        score = matches / (len(core_keywords) + 3)
        
        return min(score, 1.0)
    
    def _search_admin_rules_for_related_law(self, related_law_id: str, admin_rules: AdminRules,
                                           seen_ids: Set):
        """관련법령의 행정규칙 검색"""
        try:
            # 관련법령 ID로 행정규칙 검색
            result = self.law_client.search(
                target='admrul',
                query=related_law_id,
                display=10
            )
            
            if result and result.get('totalCnt', 0) > 0:
                for rule in result.get('results', []):
                    rule_id = rule.get('행정규칙ID')
                    if rule_id and rule_id not in seen_ids:
                        self._categorize_admin_rule(rule, admin_rules, seen_ids)
        except Exception as e:
            logger.error(f"관련법령 행정규칙 검색 오류: {e}")
    
    def _generate_law_name_variations(self, law_name: str) -> List[str]:
        """법령명 변형 생성"""
        variations = []
        base_name = self.name_processor.extract_base_name(law_name)
        
        # 약어 변형
        if '자본시장과 금융투자업에 관한 법률' in law_name:
            variations.extend(['자본시장법', '자통법', '자본시장'])
        elif '전자금융거래' in law_name:
            variations.extend(['전자금융', '전금법'])
        elif '개인정보' in law_name:
            variations.extend(['개인정보보호', '개보법'])
        elif '정보통신망' in law_name:
            variations.extend(['정통망법', '정보통신'])
        
        # 일반 변형
        if '에 관한' in law_name:
            variations.append(law_name.replace('에 관한', ''))
        
        if '및' in law_name:
            parts = law_name.split('및')
            variations.extend([p.strip() for p in parts])
        
        return variations
    
    def _search_admin_rules_by_variation(self, variation: str, admin_rules: AdminRules,
                                        seen_ids: Set, dept_code: Optional[str]):
        """법령명 변형으로 행정규칙 검색"""
        try:
            params = {
                'target': 'admrul',
                'query': variation,
                'display': 20
            }
            
            if dept_code:
                params['org'] = dept_code
            
            result = self.law_client.search(**params)
            
            if result and result.get('totalCnt', 0) > 0:
                for rule in result.get('results', []):
                    rule_id = rule.get('행정규칙ID')
                    if rule_id and rule_id not in seen_ids:
                        self._categorize_admin_rule(rule, admin_rules, seen_ids)
        except Exception as e:
            logger.error(f"변형 행정규칙 검색 오류: {e}")
    
    def _search_decree_enhanced(self, law_id: str, law_name: str, law_mst: Optional[str],
                               law_detail: Dict) -> List[Dict]:
        """시행령 검색 (개선)"""
        decrees = []
        seen_ids = set()
        
        # 1. 법령 체계도에서 직접 연계된 시행령 확인
        if law_detail.get('시행령ID'):
            decree_id = law_detail['시행령ID']
            decree_detail = self._get_law_detail(decree_id)
            if decree_detail:
                decrees.append(decree_detail)
                seen_ids.add(decree_id)
        
        # 2. 관련법령에서 시행령 찾기
        related_laws = self._search_related_laws(law_id, law_mst)
        for law in related_laws:
            if '시행령' in law.get('법령명한글', ''):
                law_id = law.get('법령ID')
                if law_id and law_id not in seen_ids:
                    decrees.append(law)
                    seen_ids.add(law_id)
        
        # 3. 법령명 기반 검색 (보조)
        if self.law_searcher and len(decrees) < 3:
            base_name = self.name_processor.extract_base_name(law_name)
            search_queries = [
                f"{base_name} 시행령",
                f"{base_name}시행령"
            ]
            
            for query in search_queries:
                result = self.law_searcher.search_laws(query=query, display=10)
                
                if result.get('totalCnt', 0) > 0:
                    for decree in result.get('results', []):
                        decree_id = decree.get('법령ID')
                        decree_name = decree.get('법령명한글', '')
                        
                        if decree_id not in seen_ids and '시행령' in decree_name:
                            if self._is_related_law(base_name, decree_name):
                                decrees.append(decree)
                                seen_ids.add(decree_id)
        
        return decrees
    
    def _search_rule_enhanced(self, law_id: str, law_name: str, law_mst: Optional[str],
                            law_detail: Dict) -> List[Dict]:
        """시행규칙 검색 (개선)"""
        rules = []
        seen_ids = set()
        
        # 1. 법령 체계도에서 직접 연계된 시행규칙 확인
        if law_detail.get('시행규칙ID'):
            rule_id = law_detail['시행규칙ID']
            rule_detail = self._get_law_detail(rule_id)
            if rule_detail:
                rules.append(rule_detail)
                seen_ids.add(rule_id)
        
        # 2. 관련법령에서 시행규칙 찾기
        related_laws = self._search_related_laws(law_id, law_mst)
        for law in related_laws:
            if '시행규칙' in law.get('법령명한글', ''):
                law_id = law.get('법령ID')
                if law_id and law_id not in seen_ids:
                    rules.append(law)
                    seen_ids.add(law_id)
        
        # 3. 법령명 기반 검색 (보조)
        if self.law_searcher and len(rules) < 3:
            base_name = self.name_processor.extract_base_name(law_name)
            search_queries = [
                f"{base_name} 시행규칙",
                f"{base_name}시행규칙"
            ]
            
            for query in search_queries:
                result = self.law_searcher.search_laws(query=query, display=10)
                
                if result.get('totalCnt', 0) > 0:
                    for rule in result.get('results', []):
                        rule_id = rule.get('법령ID')
                        rule_name = rule.get('법령명한글', '')
                        
                        if rule_id not in seen_ids and '시행규칙' in rule_name:
                            if self._is_related_law(base_name, rule_name):
                                rules.append(rule)
                                seen_ids.add(rule_id)
        
        return rules
    
    def _search_attachments_enhanced(self, law_id: str, law_name: str, 
                                   law_mst: Optional[str]) -> List[Dict]:
        """별표서식 검색 (개선)"""
        attachments = []
        seen_ids = set()
        
        try:
            # 1. MST로 검색 (더 정확)
            if law_mst:
                result = self.law_client.search(
                    target='licbyl',
                    MST=law_mst,
                    display=500
                )
                
                if result and result.get('totalCnt', 0) > 0:
                    for attach in result.get('results', []):
                        attach_id = attach.get('별표서식ID')
                        if attach_id and attach_id not in seen_ids:
                            attachments.append(attach)
                            seen_ids.add(attach_id)
            
            # 2. 법령ID로 검색
            if len(attachments) < 10:
                result = self.law_client.search(
                    target='licbyl',
                    query=law_id,
                    search=2,  # 해당법령검색
                    display=200
                )
                
                if result and result.get('totalCnt', 0) > 0:
                    for attach in result.get('results', []):
                        attach_id = attach.get('별표서식ID')
                        if attach_id and attach_id not in seen_ids:
                            attachments.append(attach)
                            seen_ids.add(attach_id)
            
            # 3. 법령명으로 검색
            if len(attachments) < 5:
                base_name = self.name_processor.extract_base_name(law_name)
                result = self.law_client.search(
                    target='licbyl',
                    query=base_name,
                    display=50
                )
                
                if result and result.get('totalCnt', 0) > 0:
                    for attach in result.get('results', []):
                        attach_id = attach.get('별표서식ID')
                        attach_law = attach.get('해당법령명', '')
                        
                        if attach_id and attach_id not in seen_ids:
                            if self._is_related_law(base_name, attach_law):
                                attachments.append(attach)
                                seen_ids.add(attach_id)
            
        except Exception as e:
            logger.error(f"별표서식 검색 오류: {e}")
        
        return attachments
    
    def _search_admin_attachments_enhanced(self, admin_rules: AdminRules) -> List[Dict]:
        """행정규칙 별표서식 검색 (개선)"""
        attachments = []
        seen_ids = set()
        
        for rule in admin_rules.get_all()[:50]:  # 상위 50개만
            rule_id = rule.get('행정규칙ID')
            rule_name = rule.get('행정규칙명', '')
            
            if not rule_id:
                continue
            
            try:
                # 행정규칙ID로 직접 검색
                result = self.law_client.search(
                    target='admbyl',
                    query=rule_id,
                    search=2,  # 해당행정규칙검색
                    display=50
                )
                
                if result and result.get('totalCnt', 0) > 0:
                    for attach in result.get('results', []):
                        attach_id = attach.get('별표서식ID')
                        if attach_id and attach_id not in seen_ids:
                            attach['관련행정규칙'] = rule_name
                            attachments.append(attach)
                            seen_ids.add(attach_id)
                
            except Exception as e:
                logger.error(f"행정규칙 별표서식 검색 오류: {e}")
        
        return attachments
    
    def _search_local_laws_from_admin_rules(self, admin_rules: AdminRules, 
                                           dept_code: Optional[str]) -> List[Dict]:
        """행정규칙 기반 자치법규 검색"""
        local_laws = []
        seen_ids = set()
        
        # 주요 행정규칙의 핵심 키워드로 자치법규 검색
        for rule in admin_rules.get_all()[:10]:  # 상위 10개만
            rule_name = rule.get('행정규칙명', '')
            if rule_name:
                core_keywords = self.name_processor.extract_core_keywords(rule_name)
                
                for keyword in core_keywords[:3]:  # 각 규칙당 3개 키워드
                    try:
                        result = self.law_client.search(
                            target='ordin',
                            query=keyword,
                            display=10
                        )
                        
                        if result and result.get('totalCnt', 0) > 0:
                            for law in result.get('results', []):
                                law_id = law.get('자치법규ID')
                                if law_id and law_id not in seen_ids:
                                    law['연계행정규칙'] = rule_name
                                    local_laws.append(law)
                                    seen_ids.add(law_id)
                    except Exception as e:
                        logger.error(f"자치법규 검색 오류: {e}")
        
        return local_laws
    
    def _get_law_hierarchy_links(self, law_id: str, law_mst: Optional[str] = None) -> Dict:
        """법령 체계도 API를 통한 연계 정보 조회"""
        try:
            params = {'display': 1000}
            
            if law_mst:
                params['MST'] = law_mst
            else:
                params['ID'] = law_id
            
            result = self.law_client.search(target='lsStmd', **params)
            
            if result and result.get('totalCnt', 0) > 0:
                return result
        except Exception as e:
            logger.error(f"법령 체계도 조회 오류: {e}")
        
        return {}
    
    def _process_hierarchy_links(self, links: Dict, hierarchy: LawHierarchy):
        """체계도 연계 정보 처리"""
        if not links or 'results' not in links:
            return
        
        seen_ids = set()
        
        for item in links.get('results', []):
            # 시행령
            if item.get('시행령ID') and item.get('시행령ID') not in seen_ids:
                hierarchy.decree.append({
                    '법령ID': item.get('시행령ID'),
                    '법령명한글': item.get('시행령명'),
                    '법령구분': '시행령'
                })
                seen_ids.add(item.get('시행령ID'))
            
            # 시행규칙
            if item.get('시행규칙ID') and item.get('시행규칙ID') not in seen_ids:
                hierarchy.rule.append({
                    '법령ID': item.get('시행규칙ID'),
                    '법령명한글': item.get('시행규칙명'),
                    '법령구분': '시행규칙'
                })
                seen_ids.add(item.get('시행규칙ID'))
    
    def _search_delegated_laws_enhanced(self, law_id: str, law_mst: Optional[str] = None) -> List[Dict]:
        """위임 법령 검색 (개선)"""
        try:
            params = {}
            if law_mst:
                params['MST'] = law_mst
            else:
                params['ID'] = law_id
            
            result = self.law_client.search(target='lsDelegated', **params)
            
            if result and result.get('totalCnt', 0) > 0:
                return result.get('results', [])
        except Exception as e:
            logger.error(f"위임 법령 검색 오류: {e}")
        
        return []
    
    def _categorize_admin_rule(self, rule: Dict, admin_rules: AdminRules, seen_ids: Set):
        """행정규칙 분류"""
        rule_name = rule.get('행정규칙명', '')
        rule_id = rule.get('행정규칙ID')
        
        if not rule_id or rule_id in seen_ids:
            return
        
        seen_ids.add(rule_id)
        
        if '훈령' in rule_name:
            admin_rules.directive.append(rule)
        elif '예규' in rule_name:
            admin_rules.regulation.append(rule)
        elif '고시' in rule_name:
            admin_rules.notice.append(rule)
        elif '지침' in rule_name or '가이드라인' in rule_name:
            admin_rules.guideline.append(rule)
        elif '규정' in rule_name:
            admin_rules.rule.append(rule)
        else:
            admin_rules.etc.append(rule)
    
    def _is_related_law(self, base_name: str, target_name: str) -> bool:
        """법령 관련성 체크 (개선)"""
        # 기본 이름이 포함되어 있는지
        if base_name in target_name:
            return True
        
        # 핵심 키워드 비교
        base_keywords = set(self.name_processor.extract_core_keywords(base_name))
        target_keywords = set(self.name_processor.extract_core_keywords(target_name))
        
        if not base_keywords:
            return False
        
        # 공통 키워드 비율 계산
        common = base_keywords & target_keywords
        if len(common) >= 2:  # 2개 이상 공통 키워드
            return True
        
        if len(base_keywords) > 0:
            ratio = len(common) / len(base_keywords)
            if ratio >= 0.5:  # 50% 이상 일치
                return True
        
        return False
    
    def _remove_duplicates(self, items: List[Dict], id_field: str) -> List[Dict]:
        """중복 제거"""
        seen = set()
        unique = []
        
        for item in items:
            item_id = item.get(id_field)
            if item_id and item_id not in seen:
                unique.append(item)
                seen.add(item_id)
        
        return unique

# ===========================
# 다운로드 및 내보내기 클래스
# ===========================

class LawHierarchyExporter:
    """법령 체계도 내보내기 클래스"""
    
    def __init__(self):
        self.name_processor = LawNameProcessor()
    
    def export_to_markdown(self, hierarchies: Dict[str, LawHierarchy], 
                          include_content: bool = False) -> str:
        """마크다운 형식으로 내보내기"""
        md_content = f"# 법령 체계도 기반 통합 문서\n\n"
        md_content += f"**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        
        total_count = sum(len(h.get_all_laws()) for h in hierarchies.values())
        md_content += f"**총 법령 수:** {total_count}개\n\n"
        md_content += "---\n\n"
        
        # 체계도 요약
        md_content += "## 📊 법령 체계도 요약\n\n"
        
        for law_name, hierarchy in hierarchies.items():
            stats = hierarchy.get_statistics()
            md_content += f"### {law_name}\n\n"
            md_content += f"- **시행령:** {stats['decree']}개\n"
            md_content += f"- **시행규칙:** {stats['rule']}개\n"
            md_content += f"- **행정규칙:** {stats['admin']}개\n"
            
            # 행정규칙 세부
            admin_rules = hierarchy.admin_rules
            if admin_rules.directive:
                md_content += f"  - 훈령: {len(admin_rules.directive)}개\n"
            if admin_rules.regulation:
                md_content += f"  - 예규: {len(admin_rules.regulation)}개\n"
            if admin_rules.notice:
                md_content += f"  - 고시: {len(admin_rules.notice)}개\n"
            if admin_rules.guideline:
                md_content += f"  - 지침: {len(admin_rules.guideline)}개\n"
            if admin_rules.rule:
                md_content += f"  - 규정: {len(admin_rules.rule)}개\n"
            
            md_content += f"- **자치법규:** {stats['local']}개\n"
            md_content += f"- **별표서식:** {stats['attachment']}개\n"
            md_content += f"- **위임법령:** {stats['delegated']}개\n"
            md_content += f"- **관련법령:** {stats.get('related', 0)}개\n\n"
        
        md_content += "---\n\n"
        
        # 법령별 상세 내용
        md_content += "## 📚 법령 상세 내용\n\n"
        
        for law_name, hierarchy in hierarchies.items():
            md_content += f"### {law_name}\n\n"
            md_content += self._export_hierarchy_detail(hierarchy)
        
        return md_content
    
    def _export_hierarchy_detail(self, hierarchy: LawHierarchy) -> str:
        """체계도 상세 내용 생성"""
        content = ""
        
        # 주 법령
        if hierarchy.main:
            content += f"#### 📚 주 법령\n\n"
            content += self._format_law_info(hierarchy.main)
            content += "\n---\n\n"
        
        # 시행령
        if hierarchy.decree:
            content += f"#### 📘 시행령 ({len(hierarchy.decree)}개)\n\n"
            for idx, decree in enumerate(hierarchy.decree, 1):
                content += f"##### {idx}. {decree.get('법령명한글', 'N/A')}\n"
                content += self._format_law_info(decree)
                content += "\n"
        
        # 시행규칙
        if hierarchy.rule:
            content += f"#### 📗 시행규칙 ({len(hierarchy.rule)}개)\n\n"
            for idx, rule in enumerate(hierarchy.rule, 1):
                content += f"##### {idx}. {rule.get('법령명한글', 'N/A')}\n"
                content += self._format_law_info(rule)
                content += "\n"
        
        # 행정규칙
        admin_total = hierarchy.admin_rules.total_count()
        if admin_total > 0:
            content += f"#### 📑 행정규칙 ({admin_total}개)\n\n"
            content += self._format_admin_rules(hierarchy.admin_rules)
        
        # 자치법규
        if hierarchy.local_laws:
            content += f"#### 🏛️ 자치법규 ({len(hierarchy.local_laws)}개)\n\n"
            for idx, law in enumerate(hierarchy.local_laws[:20], 1):
                content += f"##### {idx}. {law.get('자치법규명', 'N/A')}\n"
                content += f"- **지자체:** {law.get('지자체명', 'N/A')}\n"
                content += f"- **발령일자:** {law.get('발령일자', 'N/A')}\n"
                if law.get('연계행정규칙'):
                    content += f"- **연계 행정규칙:** {law.get('연계행정규칙')}\n"
                content += "\n"
            if len(hierarchy.local_laws) > 20:
                content += f"... 외 {len(hierarchy.local_laws)-20}개\n\n"
        
        # 별표서식
        if hierarchy.attachments:
            content += f"#### 📋 법령 별표서식 ({len(hierarchy.attachments)}개)\n\n"
            for idx, attach in enumerate(hierarchy.attachments[:20], 1):
                content += f"##### {idx}. {attach.get('별표서식명', 'N/A')}\n"
                content += f"- **해당법령:** {attach.get('해당법령명', 'N/A')}\n"
                content += f"- **구분:** {attach.get('별표구분', 'N/A')}\n\n"
            if len(hierarchy.attachments) > 20:
                content += f"... 외 {len(hierarchy.attachments)-20}개\n\n"
        
        # 위임법령
        if hierarchy.delegated:
            content += f"#### 🔗 위임법령 ({len(hierarchy.delegated)}개)\n\n"
            for idx, law in enumerate(hierarchy.delegated[:10], 1):
                content += f"##### {idx}. {law.get('위임법령명', 'N/A')}\n"
                content += f"- **유형:** {law.get('위임유형', 'N/A')}\n\n"
            if len(hierarchy.delegated) > 10:
                content += f"... 외 {len(hierarchy.delegated)-10}개\n\n"
        
        # 관련법령
        if hierarchy.related:
            content += f"#### 🔗 관련법령 ({len(hierarchy.related)}개)\n\n"
            for idx, law in enumerate(hierarchy.related[:10], 1):
                content += f"##### {idx}. {law.get('법령명한글', 'N/A')}\n"
                content += self._format_law_info(law)
                content += "\n"
            if len(hierarchy.related) > 10:
                content += f"... 외 {len(hierarchy.related)-10}개\n\n"
        
        return content
    
    def _format_law_info(self, law: Dict) -> str:
        """법령 정보 포맷팅"""
        info = ""
        if law.get('법령ID'):
            info += f"- **법령ID:** {law.get('법령ID')}\n"
        if law.get('공포일자'):
            info += f"- **공포일자:** {law.get('공포일자')}\n"
        if law.get('시행일자'):
            info += f"- **시행일자:** {law.get('시행일자')}\n"
        if law.get('발령일자'):
            info += f"- **발령일자:** {law.get('발령일자')}\n"
        if law.get('소관부처명'):
            info += f"- **소관부처:** {law.get('소관부처명')}\n"
        return info
    
    def _format_admin_rules(self, admin_rules: AdminRules) -> str:
        """행정규칙 포맷팅"""
        content = ""
        
        # 카테고리별 정리
        categories = [
            ('훈령', admin_rules.directive),
            ('예규', admin_rules.regulation),
            ('고시', admin_rules.notice),
            ('지침', admin_rules.guideline),
            ('규정', admin_rules.rule),
            ('기타', admin_rules.etc)
        ]
        
        for category_name, rules in categories:
            if rules:
                content += f"##### {category_name} ({len(rules)}개)\n\n"
                for idx, rule in enumerate(rules[:20], 1):
                    content += f"{idx}. **{rule.get('행정규칙명', 'N/A')}**\n"
                    if rule.get('행정규칙ID'):
                        content += f"   - ID: {rule.get('행정규칙ID')}\n"
                    if rule.get('발령일자'):
                        content += f"   - 발령일자: {rule.get('발령일자')}\n"
                    if rule.get('소관부처명'):
                        content += f"   - 소관부처: {rule.get('소관부처명')}\n"
                if len(rules) > 20:
                    content += f"   ... 외 {len(rules)-20}개\n"
                content += "\n"
        
        return content
    
    def export_to_zip(self, hierarchies: Dict[str, LawHierarchy], 
                     format_type: str = "markdown") -> bytes:
        """ZIP 파일로 내보내기"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 폴더 구조 생성
            folders = self._organize_by_folders(hierarchies)
            
            # 각 폴더별로 파일 생성
            for folder_path, laws in folders.items():
                if laws:
                    for idx, law in enumerate(laws, 1):
                        file_content = self._create_file_content(law, format_type)
                        file_name = self._create_safe_filename(law, idx, folder_path, format_type)
                        zip_file.writestr(file_name, file_content.encode('utf-8'))
            
            # 메타데이터 추가
            metadata = self._create_metadata(hierarchies)
            zip_file.writestr('00_metadata.json', 
                            json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8'))
            
            # README 추가
            readme = self._create_readme(hierarchies, folders)
            zip_file.writestr('00_README.md', readme.encode('utf-8'))
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    
    def _organize_by_folders(self, hierarchies: Dict[str, LawHierarchy]) -> Dict[str, List]:
        """폴더 구조로 정리"""
        folders = {
            '01_법률': [],
            '02_시행령': [],
            '03_시행규칙': [],
            '04_행정규칙/1_훈령': [],
            '04_행정규칙/2_예규': [],
            '04_행정규칙/3_고시': [],
            '04_행정규칙/4_지침': [],
            '04_행정규칙/5_규정': [],
            '04_행정규칙/9_기타': [],
            '05_자치법규': [],
            '06_별표서식': [],
            '07_위임법령': [],
            '08_관련법령': [],
            '99_기타': []
        }
        
        for hierarchy in hierarchies.values():
            # 주 법령
            if hierarchy.main:
                folders['01_법률'].append(hierarchy.main)
            
            # 시행령
            folders['02_시행령'].extend(hierarchy.decree)
            
            # 시행규칙
            folders['03_시행규칙'].extend(hierarchy.rule)
            
            # 행정규칙
            folders['04_행정규칙/1_훈령'].extend(hierarchy.admin_rules.directive)
            folders['04_행정규칙/2_예규'].extend(hierarchy.admin_rules.regulation)
            folders['04_행정규칙/3_고시'].extend(hierarchy.admin_rules.notice)
            folders['04_행정규칙/4_지침'].extend(hierarchy.admin_rules.guideline)
            folders['04_행정규칙/5_규정'].extend(hierarchy.admin_rules.rule)
            folders['04_행정규칙/9_기타'].extend(hierarchy.admin_rules.etc)
            
            # 자치법규
            folders['05_자치법규'].extend(hierarchy.local_laws)
            
            # 별표서식
            folders['06_별표서식'].extend(hierarchy.attachments)
            folders['06_별표서식'].extend(hierarchy.admin_attachments)
            
            # 위임법령
            folders['07_위임법령'].extend(hierarchy.delegated)
            
            # 관련법령
            folders['08_관련법령'].extend(hierarchy.related)
        
        return folders
    
    def _create_file_content(self, law: Dict, format_type: str) -> str:
        """파일 내용 생성"""
        law_name = (law.get('법령명한글') or law.get('행정규칙명') or 
                   law.get('자치법규명') or law.get('별표서식명') or 
                   law.get('별표명', 'N/A'))
        
        law_id = (law.get('법령ID') or law.get('행정규칙ID') or 
                 law.get('자치법규ID') or law.get('별표서식ID', ''))
        
        if format_type == "markdown":
            content = f"# {law_name}\n\n"
            if law_id:
                content += f"**ID:** {law_id}\n\n"
            content += self._format_law_info(law)
        elif format_type == "json":
            content = json.dumps(law, ensure_ascii=False, indent=2)
        else:  # text
            content = f"{law_name}\n"
            content += "=" * 50 + "\n"
            if law_id:
                content += f"ID: {law_id}\n"
            content += self._format_law_info(law).replace('**', '').replace(':', ':')
        
        return content
    
    def _create_safe_filename(self, law: Dict, idx: int, 
                            folder_path: str, format_type: str) -> str:
        """안전한 파일명 생성"""
        law_name = (law.get('법령명한글') or law.get('행정규칙명') or 
                   law.get('자치법규명') or law.get('별표서식명') or 
                   law.get('별표명', 'N/A'))
        
        # 특수문자 제거
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', law_name)[:80]
        
        # 확장자 결정
        ext_map = {
            'markdown': 'md',
            'json': 'json',
            'text': 'txt'
        }
        ext = ext_map.get(format_type, 'txt')
        
        return f"{folder_path}/{idx:04d}_{safe_name}.{ext}"
    
    def _create_metadata(self, hierarchies: Dict[str, LawHierarchy]) -> Dict:
        """메타데이터 생성"""
        total_stats = {
            'law': 0, 'decree': 0, 'rule': 0, 'admin': 0,
            'local': 0, 'attachment': 0, 'delegated': 0, 'related': 0
        }
        
        for hierarchy in hierarchies.values():
            stats = hierarchy.get_statistics()
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
        
        return {
            'generated_at': datetime.now().isoformat(),
            'total_count': sum(total_stats.values()),
            'statistics': total_stats,
            'laws': list(hierarchies.keys())
        }
    
    def _create_readme(self, hierarchies: Dict[str, LawHierarchy], 
                      folders: Dict[str, List]) -> str:
        """README 파일 생성"""
        readme = f"""# 법령 체계도 기반 통합 다운로드

생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}
검색 법령: {', '.join(hierarchies.keys())}

## 폴더 구조
- 01_법률: 기본 법률
- 02_시행령: 법률 시행령
- 03_시행규칙: 법률 시행규칙
- 04_행정규칙: 훈령, 예규, 고시, 지침, 규정
- 05_자치법규: 조례, 규칙
- 06_별표서식: 법령 및 행정규칙 별표서식
- 07_위임법령: 위임 법령
- 08_관련법령: 관련 법령
- 99_기타: 분류되지 않은 법령

## 통계
"""
        for folder, items in folders.items():
            if items:
                readme += f"- {folder}: {len(items)}개\n"
        
        return readme

# ===========================
# 통합 인터페이스
# ===========================

class LawHierarchyManager:
    """법령 체계도 관리 통합 클래스"""
    
    def __init__(self, law_client: Any, law_searcher: Any = None):
        self.searcher = LawHierarchySearcher(law_client, law_searcher)
        self.exporter = LawHierarchyExporter()
        self.hierarchies = {}
    
    def search_law_hierarchy(self, law_info: Dict, 
                            config: SearchConfig = None) -> LawHierarchy:
        """법령 체계도 검색"""
        if config is None:
            config = SearchConfig()
        
        hierarchy = self.searcher.search_hierarchy(law_info, config)
        
        # 결과 저장
        law_name = law_info.get('법령명한글', 'Unknown')
        self.hierarchies[law_name] = hierarchy
        
        return hierarchy
    
    def export_markdown(self, include_content: bool = False) -> str:
        """마크다운으로 내보내기"""
        if not self.hierarchies:
            return "# 검색된 법령이 없습니다.\n"
        
        return self.exporter.export_to_markdown(self.hierarchies, include_content)
    
    def export_zip(self, format_type: str = "markdown") -> bytes:
        """ZIP 파일로 내보내기"""
        if not self.hierarchies:
            raise ValueError("검색된 법령이 없습니다.")
        
        return self.exporter.export_to_zip(self.hierarchies, format_type)
    
    def get_statistics(self) -> Dict:
        """전체 통계 반환"""
        total_stats = {
            'law': 0, 'decree': 0, 'rule': 0, 'admin': 0,
            'local': 0, 'attachment': 0, 'delegated': 0, 'related': 0
        }
        
        for hierarchy in self.hierarchies.values():
            stats = hierarchy.get_statistics()
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
        
        total_stats['total'] = sum(total_stats.values())
        return total_stats
    
    def clear(self):
        """저장된 체계도 초기화"""
        self.hierarchies.clear()
