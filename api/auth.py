"""
?ㅼ?利앷텒 REST API OAuth2 ?몄쬆 紐⑤뱢

?좏겙 諛쒓툒, 媛깆떊 諛??먭꺽利앸챸 愿由щ? ?대떦?⑸땲??
"""

import os
import json
import time
import hashlib
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from config import Config


class KiwoomAuth:
    """OAuth2 토큰 기반 인증 관리 클래스"""
    
    # ?ㅼ? REST API ?붾뱶?ъ씤??
    BASE_URL = "https://api.kiwoom.com"
    TOKEN_ENDPOINT = "/oauth2/token"
    
    # ?좏겙 罹먯떆 ?뚯씪
    TOKEN_CACHE_FILE = "kiwoom_token_cache.json"
    
    def __init__(self, app_key: str = "", secret_key: str = "", 
                 is_mock: bool = False, cache_dir: Optional[str] = None):
        """
        Args:
            app_key: ?ㅼ? REST API App Key
            secret_key: ?ㅼ? REST API Secret Key
            is_mock: 紐⑥쓽?ъ옄 ?щ? (True: 紐⑥쓽?ъ옄, False: ?ㅺ굅??
            cache_dir: ?좏겙 罹먯떆 ????붾젆?좊━ (湲곕낯: ?꾩옱 ?붾젆?좊━)
        """
        self.app_key = app_key
        self.secret_key = secret_key
        self.is_mock = is_mock
        
        # 濡쒓굅 ?ㅼ젙
        self.logger = logging.getLogger('KiwoomAuth')
        
        # ?좏겙 ??μ냼
        self._access_token: Optional[str] = None
        self._token_type: str = "bearer"
        self._expires_at: float = 0  # Unix timestamp
        
        # 罹먯떆 ?붾젆?좊━ ?ㅼ젙
        base_dir = Path(getattr(Config, "BASE_DIR", Path.cwd()))
        self.cache_dir = Path(cache_dir) if cache_dir else base_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / self.TOKEN_CACHE_FILE
        
        # 罹먯떆???좏겙 濡쒕뱶 ?쒕룄
        self._load_cached_token()
    
    def set_credentials(self, app_key: str, secret_key: str, is_mock: bool = False):
        """?먭꺽利앸챸 ?ㅼ젙/?낅뜲?댄듃"""
        self.app_key = app_key
        self.secret_key = secret_key
        self.is_mock = is_mock
        # ?먭꺽利앸챸 蹂寃????좏겙 珥덇린??
        self._access_token = None
        self._expires_at = 0
    
    def get_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        ?좏슚???≪꽭???좏겙??諛섑솚?⑸땲??
        留뚮즺??寃쎌슦 ?먮룞?쇰줈 媛깆떊?⑸땲??
        
        Args:
            force_refresh: True硫?媛뺤젣濡????좏겙 諛쒓툒
            
        Returns:
            ?≪꽭???좏겙 臾몄옄?? ?ㅽ뙣 ??None
        """
        # ?좏겙???좏슚?쒖? ?뺤씤 (留뚮즺 5遺??꾩뿉 媛깆떊)
        if not force_refresh and self._access_token and time.time() < (self._expires_at - 300):
            return self._access_token
        
        # ???좏겙 諛쒓툒
        return self._request_new_token()
    
    def _request_new_token(self) -> Optional[str]:
        """???≪꽭???좏겙???붿껌?⑸땲??"""
        if not self.app_key or not self.secret_key:
            self.logger.error("App Key ?먮뒗 Secret Key媛 ?ㅼ젙?섏? ?딆븯?듬땲??")
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
            
            self.logger.info("?좏겙 諛쒓툒 ?붿껌 以?..")
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # ?묐떟 ?뺤떇:
                # {
                #   "token": "...",
                #   "token_type": "bearer",
                #   "expires_dt": "20261108083713",
                #   "return_code": 0,
                #   "return_msg": "?뺤긽?곸쑝濡?泥섎━?섏뿀?듬땲??
                # }
                
                if data.get("return_code") == 0:
                    self._access_token = data.get("token")
                    self._token_type = data.get("token_type", "bearer")
                    
                    # 留뚮즺 ?쒓컙 ?뚯떛 (YYYYMMDDHHMMSS ?뺤떇)
                    expires_dt = data.get("expires_dt", "")
                    if expires_dt:
                        try:
                            dt = datetime.strptime(expires_dt, "%Y%m%d%H%M%S")
                            self._expires_at = dt.timestamp()
                        except ValueError:
                            # ?뚯떛 ?ㅽ뙣 ??24?쒓컙 ?꾨줈 ?ㅼ젙
                            self._expires_at = time.time() + 86400
                    
                    # 罹먯떆?????
                    self._save_token_cache()
                    
                    self.logger.info(f"?좏겙 諛쒓툒 ?깃났 (留뚮즺: {expires_dt})")
                    return self._access_token
                else:
                    error_msg = data.get("return_msg", "?????녿뒗 ?ㅻ쪟")
                    self.logger.error(f"?좏겙 諛쒓툒 ?ㅽ뙣: {error_msg}")
                    return None
            else:
                self.logger.error(f"?좏겙 ?붿껌 HTTP ?ㅻ쪟: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"?좏겙 ?붿껌 ?ㅽ듃?뚰겕 ?ㅻ쪟: {e}")
            return None
        except Exception as e:
            self.logger.error(f"?좏겙 ?붿껌 ?덉쇅: {e}")
            return None
    
    def get_auth_header(self) -> Dict[str, str]:
        """
        API ?붿껌???ъ슜???몄쬆 ?ㅻ뜑瑜?諛섑솚?⑸땲??
        
        Returns:
            {"Authorization": "bearer TOKEN"} ?뺥깭???뺤뀛?덈━
        """
        token = self.get_token()
        if token:
            return {"Authorization": f"{self._token_type} {token}"}
        return {}
    
    def is_authenticated(self) -> bool:
        """?꾩옱 ?좏슚???좏겙???덈뒗吏 ?뺤씤?⑸땲??"""
        return self._access_token is not None and time.time() < self._expires_at
    
    def invalidate_token(self):
        """?꾩옱 ?좏겙??臾댄슚?뷀빀?덈떎 (濡쒓렇?꾩썐)."""
        self._access_token = None
        self._expires_at = 0
        
        # 罹먯떆 ?뚯씪 ??젣
        if self.cache_path.exists():
            try:
                self.cache_path.unlink()
            except OSError:
                pass
    
    def _save_token_cache(self):
        """?좏겙??罹먯떆 ?뚯씪????ν빀?덈떎."""
        try:
            cache_data = {
                "access_token": self._access_token,
                "token_type": self._token_type,
                "expires_at": self._expires_at,
                "app_key_hash": self._app_key_hash()  # ??蹂寃?媛먯???
            }
            
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
                
        except Exception as e:
            self.logger.warning(f"?좏겙 罹먯떆 ????ㅽ뙣: {e}")
    
    def _load_cached_token(self):
        """罹먯떆???좏겙??濡쒕뱶?⑸땲??"""
        if not self.cache_path.exists():
            return
        
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # ?숈씪??App Key濡?諛쒓툒???좏겙?몄? ?뺤씤
            if cache_data.get("app_key_hash") != self._app_key_hash():
                self.logger.info("App Key changed, cached token invalidated")
                return
            
            # ?좏겙???꾩쭅 ?좏슚?쒖? ?뺤씤
            expires_at = cache_data.get("expires_at", 0)
            if time.time() < expires_at - 300:  # 5遺??ъ쑀
                self._access_token = cache_data.get("access_token")
                self._token_type = cache_data.get("token_type", "bearer")
                self._expires_at = expires_at
                self.logger.info("罹먯떆???좏겙 濡쒕뱶 ?꾨즺")
                
        except Exception as e:
            self.logger.warning(f"?좏겙 罹먯떆 濡쒕뱶 ?ㅽ뙣: {e}")

    def _app_key_hash(self) -> str:
        """App Key 식별자"""
        return hashlib.sha256(self.app_key.encode('utf-8')).hexdigest()

    def test_connection(self) -> Dict[str, Any]:
        """
        ?곌껐 ?뚯뒪?몃? ?섑뻾?⑸땲??
        
        Returns:
            {
                "success": bool,
                "message": str,
                "token_expires": str (留뚮즺 ?쒓컙)
            }
        """
        token = self.get_token(force_refresh=True)
        
        if token:
            expires_str = datetime.fromtimestamp(self._expires_at).strftime("%Y-%m-%d %H:%M:%S")
            return {
                "success": True,
                "message": "?좏겙 諛쒓툒 ?깃났",
                "token_expires": expires_str
            }
        else:
            return {
                "success": False,
                "message": "?좏겙 諛쒓툒 ?ㅽ뙣 - App Key/Secret Key瑜??뺤씤?댁＜?몄슂.",
                "token_expires": None
            }

