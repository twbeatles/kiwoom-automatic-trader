"""
키움증권 REST API OAuth2 인증 모듈

토큰 발급, 갱신 및 자격증명 관리를 담당합니다.
"""

import os
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


class KiwoomAuth:
    """OAuth2 토큰 기반 인증 관리 클래스"""
    
    # 키움 REST API 엔드포인트
    BASE_URL = "https://api.kiwoom.com"
    TOKEN_ENDPOINT = "/oauth2/token"
    
    # 토큰 캐시 파일
    TOKEN_CACHE_FILE = "kiwoom_token_cache.json"
    
    def __init__(self, app_key: str = "", secret_key: str = "", 
                 is_mock: bool = False, cache_dir: Optional[str] = None):
        """
        Args:
            app_key: 키움 REST API App Key
            secret_key: 키움 REST API Secret Key
            is_mock: 모의투자 여부 (True: 모의투자, False: 실거래)
            cache_dir: 토큰 캐시 저장 디렉토리 (기본: 현재 디렉토리)
        """
        self.app_key = app_key
        self.secret_key = secret_key
        self.is_mock = is_mock
        
        # 로거 설정
        self.logger = logging.getLogger('KiwoomAuth')
        
        # 토큰 저장소
        self._access_token: Optional[str] = None
        self._token_type: str = "bearer"
        self._expires_at: float = 0  # Unix timestamp
        
        # 캐시 디렉토리 설정
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd()
        self.cache_path = self.cache_dir / self.TOKEN_CACHE_FILE
        
        # 캐시된 토큰 로드 시도
        self._load_cached_token()
    
    def set_credentials(self, app_key: str, secret_key: str, is_mock: bool = False):
        """자격증명 설정/업데이트"""
        self.app_key = app_key
        self.secret_key = secret_key
        self.is_mock = is_mock
        # 자격증명 변경 시 토큰 초기화
        self._access_token = None
        self._expires_at = 0
    
    def get_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        유효한 액세스 토큰을 반환합니다.
        만료된 경우 자동으로 갱신합니다.
        
        Args:
            force_refresh: True면 강제로 새 토큰 발급
            
        Returns:
            액세스 토큰 문자열, 실패 시 None
        """
        # 토큰이 유효한지 확인 (만료 5분 전에 갱신)
        if not force_refresh and self._access_token and time.time() < (self._expires_at - 300):
            return self._access_token
        
        # 새 토큰 발급
        return self._request_new_token()
    
    def _request_new_token(self) -> Optional[str]:
        """새 액세스 토큰을 요청합니다."""
        if not self.app_key or not self.secret_key:
            self.logger.error("App Key 또는 Secret Key가 설정되지 않았습니다.")
            return None
        
        try:
            url = f"{self.BASE_URL}{self.TOKEN_ENDPOINT}"
            
            payload = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.secret_key
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            self.logger.info("토큰 발급 요청 중...")
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # 응답 형식:
                # {
                #   "token": "...",
                #   "token_type": "bearer",
                #   "expires_dt": "20261108083713",
                #   "return_code": 0,
                #   "return_msg": "정상적으로 처리되었습니다"
                # }
                
                if data.get("return_code") == 0:
                    self._access_token = data.get("token")
                    self._token_type = data.get("token_type", "bearer")
                    
                    # 만료 시간 파싱 (YYYYMMDDHHMMSS 형식)
                    expires_dt = data.get("expires_dt", "")
                    if expires_dt:
                        try:
                            dt = datetime.strptime(expires_dt, "%Y%m%d%H%M%S")
                            self._expires_at = dt.timestamp()
                        except ValueError:
                            # 파싱 실패 시 24시간 후로 설정
                            self._expires_at = time.time() + 86400
                    
                    # 캐시에 저장
                    self._save_token_cache()
                    
                    self.logger.info(f"토큰 발급 성공 (만료: {expires_dt})")
                    return self._access_token
                else:
                    error_msg = data.get("return_msg", "알 수 없는 오류")
                    self.logger.error(f"토큰 발급 실패: {error_msg}")
                    return None
            else:
                self.logger.error(f"토큰 요청 HTTP 오류: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"토큰 요청 네트워크 오류: {e}")
            return None
        except Exception as e:
            self.logger.error(f"토큰 요청 예외: {e}")
            return None
    
    def get_auth_header(self) -> Dict[str, str]:
        """
        API 요청에 사용할 인증 헤더를 반환합니다.
        
        Returns:
            {"Authorization": "bearer TOKEN"} 형태의 딕셔너리
        """
        token = self.get_token()
        if token:
            return {"Authorization": f"{self._token_type} {token}"}
        return {}
    
    def is_authenticated(self) -> bool:
        """현재 유효한 토큰이 있는지 확인합니다."""
        return self._access_token is not None and time.time() < self._expires_at
    
    def invalidate_token(self):
        """현재 토큰을 무효화합니다 (로그아웃)."""
        self._access_token = None
        self._expires_at = 0
        
        # 캐시 파일 삭제
        if self.cache_path.exists():
            try:
                self.cache_path.unlink()
            except OSError:
                pass
    
    def _save_token_cache(self):
        """토큰을 캐시 파일에 저장합니다."""
        try:
            cache_data = {
                "access_token": self._access_token,
                "token_type": self._token_type,
                "expires_at": self._expires_at,
                "app_key_hash": hash(self.app_key)  # 키 변경 감지용
            }
            
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
                
        except Exception as e:
            self.logger.warning(f"토큰 캐시 저장 실패: {e}")
    
    def _load_cached_token(self):
        """캐시된 토큰을 로드합니다."""
        if not self.cache_path.exists():
            return
        
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 동일한 App Key로 발급된 토큰인지 확인
            if cache_data.get("app_key_hash") != hash(self.app_key):
                self.logger.info("App Key가 변경되어 캐시된 토큰 무효화")
                return
            
            # 토큰이 아직 유효한지 확인
            expires_at = cache_data.get("expires_at", 0)
            if time.time() < expires_at - 300:  # 5분 여유
                self._access_token = cache_data.get("access_token")
                self._token_type = cache_data.get("token_type", "bearer")
                self._expires_at = expires_at
                self.logger.info("캐시된 토큰 로드 완료")
                
        except Exception as e:
            self.logger.warning(f"토큰 캐시 로드 실패: {e}")
    
    def test_connection(self) -> Dict[str, Any]:
        """
        연결 테스트를 수행합니다.
        
        Returns:
            {
                "success": bool,
                "message": str,
                "token_expires": str (만료 시간)
            }
        """
        token = self.get_token(force_refresh=True)
        
        if token:
            expires_str = datetime.fromtimestamp(self._expires_at).strftime("%Y-%m-%d %H:%M:%S")
            return {
                "success": True,
                "message": "토큰 발급 성공",
                "token_expires": expires_str
            }
        else:
            return {
                "success": False,
                "message": "토큰 발급 실패 - App Key/Secret Key를 확인해주세요.",
                "token_expires": None
            }
