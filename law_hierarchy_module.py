"""
법령 체계도 검색 및 다운로드 전문 모듈
Law Hierarchy Search and Download Module
Version 1.0 - Specialized Module for Law Structure
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
            'delegated': len(self.delegated)
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
    search_depth: str = "최대"  # 표준/확장/최대
    debug_mode: bool = False

# ===========================
# 유틸리티 함수
# ===========================

class LawNameProcessor:
    """법령명 처리 유틸리티"""
    
    # 부처별 키워드 매핑
    DEPARTMENT_KEYWORDS = {
        '금융위원회': ['금융', '자본시장', '증권', '보험', '은행', '여신', '신용', '금융투자'],
        '고용노동부': ['근로', '노동', '고용', '산업안전', '임금', '퇴직', '최저임금'],
        '국토교통부': ['도로', '건축', '주택', '교통', '철도', '항공', '부동산', '국토'],
        '행정안전부': ['지방', '행정', '공무원', '재난', '안전', '개인정보', '정보공개'],
        '법무부': ['형법', '민법', '상법', '형사', '민사', '사법', '법무', '교정'],
        '기획재정부': ['세법', '조세', '관세', '국세', '부가가치세', '소득세', '법인세'],
        '보건복지부': ['의료', '건강', '복지', '국민연금', '건강보험', '의약품', '식품'],
        '환경부': ['환경', '대기', '수질', '폐기물', '자연', '생태', '기후'],
        '산업통상자원부': ['산업', '에너지', '전력', '무역', '통상', '중소기업', '특허'],
        '과학기술정보통신부': ['정보통신', '과학기술', '방송', '통신', '데이터', '인터넷', '전파'],
        '교육부': ['교육', '학교', '대학', '학원', '평생교육', '교육과정'],
        '국방부': ['국방', '군사', '병역', '국군', '방위'],
        '외교부': ['외교', '외무', '영사', '여권', '국제'],
        '문화체육관광부': ['문화', '예술', '체육', '관광', '문화재', '저작권'],
        '농림축산식품부': ['농업', '축산', '농촌', '농지', '식품산업'],
        '해양수산부': ['해양', '수산', '어업', '항만', '선박']
    }
    
    # 부처 코드 매핑
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
        '과학기술정보통신부': '1721000'
    }
    
    # 특별 법령명 패턴
    SPECIAL_CASES = {
        '자본시장': ['자본시장법', '자통법', '금융투자', '자본시장과 금융투자업', '금투법'],
        '개인정보': ['개인정보보호', '개보법', 'PIPA', '개인정보보호법'],
        '도로교통': ['도로교통', '도교법', '교통법', '도로교통법'],
        '근로기준': ['근로기준', '근기법', '노동법', '근로기준법'],
        '상호저축': ['상호저축은행', '저축은행', '상호금융', '저축은행법'],
        '전자금융': ['전자금융', '전금법', '전자금융거래법'],
        '공정거래': ['공정거래', '공정거래법', '독점규제', '독과점'],
        '부동산': ['부동산', '부동산거래', '공인중개사법', '부동산등기']
    }
    
    @staticmethod
    def extract_base_name(law_name: str) -> str:
        """법령명에서 기본 명칭 추출"""
        # 법령 접미사 제거
        base_name = re.sub(r'(에 관한 |의 |을 위한 )', ' ', law_name)
        base_name = re.sub(r'(법|령|규칙|규정|지침|훈령|예규|고시)$', '', base_name).strip()
        # 특수문자 제거
        base_name = re.sub(r'[「」『』【】]', '', base_name)
        return base_name
    
    @classmethod
    def generate_keywords(cls, law_name: str, law_id: str = None) -> List[str]:
        """검색 키워드 생성"""
        keywords = []
        base_name = cls.extract_base_name(law_name)
        
        # 기본 키워드
        keywords.append(law_name)
        keywords.append(base_name)
        
        # 축약형 생성
        if '과' in base_name:
            parts = base_name.split('과')
            if len(parts) == 2:
                keywords.extend([p.strip() for p in parts])
        
        # 공백 제거 버전
        keywords.append(base_name.replace(' ', ''))
        
        # 특별 케이스 처리
        for key, values in cls.SPECIAL_CASES.items():
            if key in law_name:
                keywords.extend(values)
        
        # 법령 ID 추가
        if law_id:
            keywords.append(law_id)
        
        # 중복 제거하여 반환
        return list(dict.fromkeys(keywords))
    
    @classmethod
    def estimate_department(cls, law_name: str) -> Optional[str]:
        """법령명으로 소관부처 추정"""
        for dept, keywords in cls.DEPARTMENT_KEYWORDS.items():
            if any(keyword in law_name for keyword in keywords):
                return dept
        return None
    
    @classmethod
    def get_department_code(cls, department: str) -> Optional[str]:
        """부처명으로 부처 코드 반환"""
        return cls.DEPARTMENT_CODES.get(department)

# ===========================
# 법령 체계도 검색 클래스
# ===========================

class LawHierarchySearcher:
    """법령 체계도 검색 클래스"""
    
    def __init__(self, law_client: Any, law_searcher: Any = None):
        self.law_client = law_client
        self.law_searcher = law_searcher
        self.name_processor = LawNameProcessor()
        
    def search_hierarchy(self, law_info: Dict, config: SearchConfig) -> LawHierarchy:
        """법령 체계도 전체 검색"""
        hierarchy = LawHierarchy(main=law_info)
        
        law_id = law_info.get('법령ID') or law_info.get('법령일련번호')
        law_name = law_info.get('법령명한글', '')
        
        if not law_id or not law_name:
            logger.warning("법령 ID 또는 명칭이 없습니다.")
            return hierarchy
        
        # 소관부처 정보 조회
        department = self._get_department_info(law_id, law_name)
        
        # 검색 키워드 생성
        keywords = self.name_processor.generate_keywords(law_name, law_id)
        
        logger.info(f"법령 체계도 검색 시작: {law_name}")
        logger.info(f"소관부처: {department or '미확인'}")
        logger.info(f"검색 키워드: {keywords[:5]}")
        
        # 각 항목별 검색 수행
        if config.include_delegated:
            hierarchy.delegated = self._search_delegated_laws(law_id)
            
        if config.include_decree:
            hierarchy.decree = self._search_decree(law_name, keywords)
            
        if config.include_rule:
            hierarchy.rule = self._search_rule(law_name, keywords)
            
        if config.include_admin_rules:
            hierarchy.admin_rules = self._search_admin_rules(law_id, law_name, department, keywords)
            
        if config.include_attachments:
            hierarchy.attachments = self._search_attachments(law_id, law_name, keywords)
            
        if config.include_admin_attachments:
            hierarchy.admin_attachments = self._search_admin_attachments(hierarchy.admin_rules)
            
        if config.include_local:
            hierarchy.local_laws = self._search_local_laws(law_name, keywords, hierarchy.admin_rules)
        
        logger.info(f"법령 체계도 검색 완료: 총 {len(hierarchy.get_all_laws())}건")
        
        return hierarchy
    
    def _get_department_info(self, law_id: str, law_name: str) -> Optional[str]:
        """소관부처 정보 조회"""
        try:
            # API로 직접 조회
            result = self.law_client.get_detail(target='law', ID=law_id)
            if result and 'error' not in result:
                department = result.get('소관부처명') or result.get('소관부처코드')
                if department:
                    return department
        except Exception as e:
            logger.error(f"소관부처 조회 실패: {e}")
        
        # 법령명으로 추정
        return self.name_processor.estimate_department(law_name)
    
    def _search_delegated_laws(self, law_id: str) -> List[Dict]:
        """위임 법령 검색"""
        try:
            result = self.law_client.search(
                target='lsDelegated',
                ID=law_id
            )
            if result and result.get('totalCnt', 0) > 0:
                return result.get('results', [])
        except Exception as e:
            logger.error(f"위임 법령 검색 오류: {e}")
        return []
    
    def _search_decree(self, law_name: str, keywords: List[str]) -> List[Dict]:
        """시행령 검색"""
        decrees = []
        seen_ids = set()
        patterns = ["시행령", " 시행령", "법 시행령", "법시행령"]
        
        if not self.law_searcher:
            logger.warning("law_searcher가 설정되지 않았습니다.")
            return decrees
        
        for keyword in keywords[:3]:
            for pattern in patterns:
                try:
                    result = self.law_searcher.search_laws(
                        query=f"{keyword}{pattern}",
                        display=50
                    )
                    
                    if result.get('totalCnt', 0) > 0:
                        for decree in result.get('results', []):
                            decree_id = decree.get('법령ID')
                            decree_name = decree.get('법령명한글', '')
                            
                            if ('시행령' in decree_name and 
                                decree_id not in seen_ids and
                                any(k in decree_name for k in keywords[:3])):
                                decrees.append(decree)
                                seen_ids.add(decree_id)
                                
                except Exception as e:
                    logger.error(f"시행령 검색 오류: {e}")
        
        return decrees
    
    def _search_rule(self, law_name: str, keywords: List[str]) -> List[Dict]:
        """시행규칙 검색"""
        rules = []
        seen_ids = set()
        patterns = ["시행규칙", " 시행규칙", "법 시행규칙", "법시행규칙"]
        
        if not self.law_searcher:
            logger.warning("law_searcher가 설정되지 않았습니다.")
            return rules
        
        for keyword in keywords[:3]:
            for pattern in patterns:
                try:
                    result = self.law_searcher.search_laws(
                        query=f"{keyword}{pattern}",
                        display=50
                    )
                    
                    if result.get('totalCnt', 0) > 0:
                        for rule in result.get('results', []):
                            rule_id = rule.get('법령ID')
                            rule_name = rule.get('법령명한글', '')
                            
                            if ('시행규칙' in rule_name and 
                                rule_id not in seen_ids and
                                any(k in rule_name for k in keywords[:3])):
                                rules.append(rule)
                                seen_ids.add(rule_id)
                                
                except Exception as e:
                    logger.error(f"시행규칙 검색 오류: {e}")
        
        return rules
    
    def _search_admin_rules(self, law_id: str, law_name: str, 
                           department: str, keywords: List[str]) -> AdminRules:
        """행정규칙 검색"""
        admin_rules = AdminRules()
        seen_ids = set()
        
        # 1. 법령 체계도에서 직접 연계된 행정규칙 조회
        try:
            result = self.law_client.search(
                target='lsStmd',
                ID=law_id,
                display=100
            )
            
            if result and result.get('totalCnt', 0) > 0:
                for item in result.get('results', []):
                    if item.get('행정규칙명'):
                        self._categorize_admin_rule(item, admin_rules, seen_ids)
                        
        except Exception as e:
            logger.error(f"체계도 조회 오류: {e}")
        
        # 2. 소관부처 기반 검색
        if department:
            dept_code = self.name_processor.get_department_code(department)
            if dept_code:
                self._search_admin_rules_by_department(
                    keywords, dept_code, admin_rules, seen_ids
                )
        
        # 3. 키워드 기반 포괄적 검색
        self._search_admin_rules_by_keywords(
            keywords, admin_rules, seen_ids
        )
        
        # 4. 법령 ID 직접 참조 검색
        self._search_admin_rules_by_law_id(
            law_id, admin_rules, seen_ids
        )
        
        return admin_rules
    
    def _categorize_admin_rule(self, rule: Dict, admin_rules: AdminRules, seen_ids: Set):
        """행정규칙 분류"""
        rule_name = rule.get('행정규칙명', '')
        rule_id = rule.get('행정규칙ID')
        
        if rule_id in seen_ids:
            return
        
        seen_ids.add(rule_id)
        
        if '훈령' in rule_name:
            admin_rules.directive.append(rule)
        elif '예규' in rule_name:
            admin_rules.regulation.append(rule)
        elif '고시' in rule_name:
            admin_rules.notice.append(rule)
        elif '지침' in rule_name:
            admin_rules.guideline.append(rule)
        elif '규정' in rule_name:
            admin_rules.rule.append(rule)
        else:
            admin_rules.etc.append(rule)
    
    def _search_admin_rules_by_department(self, keywords: List[str], dept_code: str,
                                         admin_rules: AdminRules, seen_ids: Set):
        """부처별 행정규칙 검색"""
        for keyword in keywords[:5]:
            try:
                result = self.law_client.search(
                    target='admrul',
                    query=keyword,
                    org=dept_code,
                    display=100
                )
                
                if result.get('totalCnt', 0) > 0:
                    for rule in result.get('results', []):
                        rule_name = rule.get('행정규칙명', '')
                        if any(k in rule_name for k in keywords[:3]):
                            self._categorize_admin_rule(rule, admin_rules, seen_ids)
                            
            except Exception as e:
                logger.error(f"부처별 행정규칙 검색 오류: {e}")
    
    def _search_admin_rules_by_keywords(self, keywords: List[str],
                                       admin_rules: AdminRules, seen_ids: Set):
        """키워드 기반 행정규칙 검색"""
        rule_types = [
            ('directive', '훈령'),
            ('regulation', '예규'),
            ('notice', '고시'),
            ('guideline', '지침'),
            ('rule', '규정')
        ]
        
        for category_key, type_name in rule_types:
            for keyword in keywords[:3]:
                search_patterns = [
                    f"{keyword} {type_name}",
                    f"{keyword}{type_name}",
                    keyword
                ]
                
                for pattern in search_patterns:
                    try:
                        result = self.law_client.search(
                            target='admrul',
                            query=pattern,
                            display=50
                        )
                        
                        if result.get('totalCnt', 0) > 0:
                            for rule in result.get('results', []):
                                rule_name = rule.get('행정규칙명', '')
                                if type_name in rule_name and any(k in rule_name for k in keywords[:3]):
                                    self._categorize_admin_rule(rule, admin_rules, seen_ids)
                                    
                    except Exception as e:
                        logger.error(f"행정규칙 검색 오류: {e}")
    
    def _search_admin_rules_by_law_id(self, law_id: str,
                                     admin_rules: AdminRules, seen_ids: Set):
        """법령 ID로 행정규칙 검색"""
        try:
            result = self.law_client.search(
                target='admrul',
                query=law_id,
                display=100
            )
            
            if result.get('totalCnt', 0) > 0:
                for rule in result.get('results', []):
                    self._categorize_admin_rule(rule, admin_rules, seen_ids)
                    
        except Exception as e:
            logger.error(f"법령 ID 참조 검색 오류: {e}")
    
    def _search_attachments(self, law_id: str, law_name: str, 
                          keywords: List[str]) -> List[Dict]:
        """법령 별표서식 검색"""
        attachments = []
        seen_ids = set()
        
        # 1. 법령 ID로 직접 검색
        try:
            result = self.law_client.search(
                target='licbyl',
                query=law_id,
                search=2,  # 해당법령검색
                display=100
            )
            
            if result.get('totalCnt', 0) > 0:
                for attach in result.get('results', []):
                    attach_id = attach.get('별표서식ID')
                    if attach_id and attach_id not in seen_ids:
                        attachments.append(attach)
                        seen_ids.add(attach_id)
                        
        except Exception as e:
            logger.error(f"법령 ID 별표서식 검색 오류: {e}")
        
        # 2. 법령명으로 검색
        for keyword in keywords[:5]:
            try:
                result = self.law_client.search(
                    target='licbyl',
                    query=keyword,
                    search=2,
                    display=50
                )
                
                if result.get('totalCnt', 0) > 0:
                    for attach in result.get('results', []):
                        attach_id = attach.get('별표서식ID')
                        attach_law = attach.get('해당법령명', '')
                        
                        if (attach_id and attach_id not in seen_ids and
                            any(k in attach_law for k in keywords[:3])):
                            attachments.append(attach)
                            seen_ids.add(attach_id)
                            
            except Exception as e:
                logger.error(f"별표서식 검색 오류: {e}")
        
        return attachments
    
    def _search_admin_attachments(self, admin_rules: AdminRules) -> List[Dict]:
        """행정규칙 별표서식 검색"""
        attachments = []
        seen_ids = set()
        
        for rule in admin_rules.get_all():
            rule_name = rule.get('행정규칙명', '')
            rule_id = rule.get('행정규칙ID')
            
            if rule_id:
                try:
                    result = self.law_client.search(
                        target='admbyl',
                        query=rule_name,
                        search=2,
                        display=30
                    )
                    
                    if result.get('totalCnt', 0) > 0:
                        for attach in result.get('results', []):
                            attach_id = attach.get('별표서식ID')
                            if attach_id and attach_id not in seen_ids:
                                attachments.append(attach)
                                seen_ids.add(attach_id)
                                
                except Exception as e:
                    logger.error(f"행정규칙 별표서식 검색 오류: {e}")
        
        return attachments
    
    def _search_local_laws(self, law_name: str, keywords: List[str],
                         admin_rules: AdminRules) -> List[Dict]:
        """자치법규 검색"""
        local_laws = []
        seen_ids = set()
        
        # 1. 법령명 기반 검색
        for keyword in keywords[:5]:
            try:
                result = self.law_client.search(
                    target='ordin',
                    query=keyword,
                    display=100
                )
                
                if result.get('totalCnt', 0) > 0:
                    for law in result.get('results', []):
                        law_id = law.get('자치법규ID')
                        if law_id and law_id not in seen_ids:
                            local_laws.append(law)
                            seen_ids.add(law_id)
                            
            except Exception as e:
                logger.error(f"자치법규 검색 오류: {e}")
        
        # 2. 행정규칙과 연계된 자치법규 검색
        for rule in admin_rules.get_all()[:10]:  # 상위 10개만
            rule_name = rule.get('행정규칙명', '')
            if rule_name:
                try:
                    base_name = self.name_processor.extract_base_name(rule_name)
                    result = self.law_client.search(
                        target='ordin',
                        query=base_name,
                        display=20
                    )
                    
                    if result.get('totalCnt', 0) > 0:
                        for law in result.get('results', []):
                            law_id = law.get('자치법규ID')
                            if law_id and law_id not in seen_ids:
                                local_laws.append(law)
                                seen_ids.add(law_id)
                                
                except Exception as e:
                    logger.error(f"자치법규 검색 오류: {e}")
        
        return local_laws

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
            md_content += f"- **위임법령:** {stats['delegated']}개\n\n"
        
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
            for idx, law in enumerate(hierarchy.local_laws[:10], 1):
                content += f"##### {idx}. {law.get('자치법규명', 'N/A')}\n"
                content += f"- **지자체:** {law.get('지자체명', 'N/A')}\n"
                content += f"- **발령일자:** {law.get('발령일자', 'N/A')}\n\n"
        
        return content
    
    def _format_law_info(self, law: Dict) -> str:
        """법령 정보 포맷팅"""
        info = ""
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
                for idx, rule in enumerate(rules[:5], 1):
                    content += f"{idx}. {rule.get('행정규칙명', 'N/A')}\n"
                    if rule.get('발령일자'):
                        content += f"   - 발령일자: {rule.get('발령일자')}\n"
                    if rule.get('소관부처명'):
                        content += f"   - 소관부처: {rule.get('소관부처명')}\n"
                if len(rules) > 5:
                    content += f"   ... 외 {len(rules)-5}개\n"
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
        
        return folders
    
    def _create_file_content(self, law: Dict, format_type: str) -> str:
        """파일 내용 생성"""
        law_name = (law.get('법령명한글') or law.get('행정규칙명') or 
                   law.get('자치법규명') or law.get('별표서식명') or 
                   law.get('별표명', 'N/A'))
        
        if format_type == "markdown":
            content = f"# {law_name}\n\n"
            content += self._format_law_info(law)
        elif format_type == "json":
            content = json.dumps(law, ensure_ascii=False, indent=2)
        else:  # text
            content = f"{law_name}\n"
            content += "=" * 50 + "\n"
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
            'local': 0, 'attachment': 0, 'delegated': 0
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
            'local': 0, 'attachment': 0, 'delegated': 0
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
