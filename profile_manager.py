"""
Profile Manager for Kiwoom Pro Algo-Trader
다중 프로필 관리 시스템
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ProfileManager:
    """설정 프로필 관리 클래스"""
    
    PROFILES_FILE = "kiwoom_profiles.json"
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_path = self.data_dir / self.PROFILES_FILE
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.current_profile: Optional[str] = None
        self._load_profiles()
    
    def _load_profiles(self):
        """프로필 파일 로드"""
        try:
            if self.profiles_path.exists():
                with open(self.profiles_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.profiles = data.get('profiles', {})
                    self.current_profile = data.get('current', None)
        except (json.JSONDecodeError, OSError):
            self.profiles = {}
            self.current_profile = None
    
    def _save_profiles(self):
        """프로필 파일 저장"""
        try:
            data = {
                'profiles': self.profiles,
                'current': self.current_profile,
                'updated': datetime.now().isoformat()
            }
            with open(self.profiles_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False
    
    def get_profile_names(self) -> List[str]:
        """모든 프로필 이름 반환"""
        return list(self.profiles.keys())
    
    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """특정 프로필 반환"""
        return self.profiles.get(name)
    
    def get_current_profile(self) -> Optional[Dict[str, Any]]:
        """현재 프로필 반환"""
        if self.current_profile:
            return self.profiles.get(self.current_profile)
        return None
    
    def get_current_profile_name(self) -> Optional[str]:
        """현재 프로필 이름 반환"""
        return self.current_profile
    
    def save_profile(self, name: str, settings: Dict[str, Any], 
                     description: str = "") -> bool:
        """프로필 저장
        
        Args:
            name: 프로필 이름
            settings: 설정 딕셔너리
            description: 프로필 설명
        
        Returns:
            성공 여부
        """
        self.profiles[name] = {
            'name': name,
            'description': description,
            'settings': settings,
            'created': self.profiles.get(name, {}).get('created', datetime.now().isoformat()),
            'updated': datetime.now().isoformat()
        }
        return self._save_profiles()
    
    def load_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """프로필 불러오기 및 현재 프로필로 설정
        
        Args:
            name: 프로필 이름
        
        Returns:
            설정 딕셔너리 또는 None
        """
        profile = self.profiles.get(name)
        if profile:
            self.current_profile = name
            self._save_profiles()
            return profile.get('settings', {})
        return None
    
    def delete_profile(self, name: str) -> bool:
        """프로필 삭제
        
        Args:
            name: 프로필 이름
        
        Returns:
            성공 여부
        """
        if name in self.profiles:
            del self.profiles[name]
            if self.current_profile == name:
                self.current_profile = None
            return self._save_profiles()
        return False
    
    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """프로필 이름 변경
        
        Args:
            old_name: 기존 이름
            new_name: 새 이름
        
        Returns:
            성공 여부
        """
        if old_name in self.profiles and new_name not in self.profiles:
            self.profiles[new_name] = self.profiles.pop(old_name)
            self.profiles[new_name]['name'] = new_name
            self.profiles[new_name]['updated'] = datetime.now().isoformat()
            if self.current_profile == old_name:
                self.current_profile = new_name
            return self._save_profiles()
        return False
    
    def duplicate_profile(self, source_name: str, new_name: str) -> bool:
        """프로필 복제
        
        Args:
            source_name: 원본 프로필 이름
            new_name: 새 프로필 이름
        
        Returns:
            성공 여부
        """
        if source_name in self.profiles and new_name not in self.profiles:
            source = self.profiles[source_name]
            self.profiles[new_name] = {
                'name': new_name,
                'description': f"Copy of {source_name}",
                'settings': source.get('settings', {}).copy(),
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }
            return self._save_profiles()
        return False
    
    def export_profile(self, name: str, filepath: str) -> bool:
        """프로필 내보내기
        
        Args:
            name: 프로필 이름
            filepath: 저장 경로
        
        Returns:
            성공 여부
        """
        profile = self.profiles.get(name)
        if profile:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(profile, f, ensure_ascii=False, indent=2)
                return True
            except OSError:
                pass
        return False
    
    def import_profile(self, filepath: str, new_name: Optional[str] = None) -> bool:
        """프로필 가져오기
        
        Args:
            filepath: 파일 경로
            new_name: 새 프로필 이름 (None이면 파일의 이름 사용)
        
        Returns:
            성공 여부
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                profile = json.load(f)
            
            name = new_name or profile.get('name', 'Imported')
            # 중복 이름 처리
            base_name = name
            counter = 1
            while name in self.profiles:
                name = f"{base_name} ({counter})"
                counter += 1
            
            profile['name'] = name
            profile['updated'] = datetime.now().isoformat()
            self.profiles[name] = profile
            return self._save_profiles()
        except (json.JSONDecodeError, OSError):
            return False
    
    def get_profile_info(self, name: str) -> Optional[Dict[str, str]]:
        """프로필 메타정보 반환"""
        profile = self.profiles.get(name)
        if profile:
            return {
                'name': profile.get('name', name),
                'description': profile.get('description', ''),
                'created': profile.get('created', ''),
                'updated': profile.get('updated', '')
            }
        return None
