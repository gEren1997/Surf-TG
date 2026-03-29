import os
import re
import time
import requests
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from bot.config import Telegram

class TMDBIntegration:
    def __init__(self, db=None):
        self.api_key = Telegram.TMDB_API_KEY
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p/w500"
        self.backdrop_base_url = "https://image.tmdb.org/t/p/original"
        self.enabled = bool(self.api_key and self.api_key.strip())
        self.db = db
        self.cache_ttl = timedelta(days=Telegram.TMDB_CACHE_DAYS)
        self.request_cache = {}
        self.last_request_time = 0
        self.min_request_interval = 0.25  # 4 requests per second max
    
    def extract_title(self, filename: str) -> Optional[str]:
        """Extract movie/show title from filename"""
        if not filename:
            return None
            
        name = os.path.splitext(filename)[0]
        
        # Remove quality tags
        name = re.sub(r'\d{3,4}p', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\d{3,4}x\d{3,4}', '', name, flags=re.IGNORECASE)
        
        # Remove common release tags
        tags = ['bluray', 'web-dl', 'webdl', 'hdtv', 'x264', 'x265', 'hevc', 
                'aac', 'mp4', 'mkv', 'avi', 'hdr', 'dv', 'atmos', 'truehd',
                'webrip', 'hdrip', 'dvdrip', 'bdrip', 'hdcam', 'ts', 'tc',
                'cam', 'scr', 'screener', 'remux', 'proper', 'repack']
        for tag in tags:
            name = re.sub(rf'\b{tag}\b', '', name, flags=re.IGNORECASE)
        
        # Remove year in brackets/parentheses
        name = re.sub(r'[\[\(]\d{4}[\]\)]', '', name)
        
        # Remove episode patterns (S01E02, S1E2, etc)
        name = re.sub(r'[Ss]\d{1,2}[Ee]\d{1,2}', '', name)
        name = re.sub(r'[Ss]\d{1,2}\s*[Ee]\d{1,2}', '', name)
        name = re.sub(r'Episode\s*\d+', '', name, flags=re.IGNORECASE)
        name = re.sub(r'Ep\s*\d+', '', name, flags=re.IGNORECASE)
        
        # Remove random dots/underscores but keep spaces
        name = re.sub(r'[._]', ' ', name)
        
        # Remove multiple spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name if len(name) > 2 else None
    
    def _rate_limit(self):
        """Simple rate limiting to avoid TMDB limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def search_movie(self, title: str) -> Optional[Dict]:
        """Search TMDB for movie"""
        if not self.enabled:
            return None
        
        cache_key = f"movie:{title.lower()}"
        if cache_key in self.request_cache:
            cached_time, data = self.request_cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                return data
        
        try:
            self._rate_limit()
            url = f"{self.base_url}/search/movie"
            params = {
                "api_key": self.api_key,
                "query": title,
                "language": "en-US",
                "page": 1
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("results"):
                movie_data = self._format_movie(data["results"][0])
                self.request_cache[cache_key] = (datetime.now(), movie_data)
                return movie_data
        except Exception as e:
            print(f"TMDB Movie Search Error: {e}")
        return None
    
    def search_tv(self, title: str) -> Optional[Dict]:
        """Search TMDB for TV show"""
        if not self.enabled:
            return None
        
        cache_key = f"tv:{title.lower()}"
        if cache_key in self.request_cache:
            cached_time, data = self.request_cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                return data
        
        try:
            self._rate_limit()
            url = f"{self.base_url}/search/tv"
            params = {
                "api_key": self.api_key,
                "query": title,
                "language": "en-US",
                "page": 1
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("results"):
                tv_data = self._format_tv(data["results"][0])
                self.request_cache[cache_key] = (datetime.now(), tv_data)
                return tv_data
        except Exception as e:
            print(f"TMDB TV Search Error: {e}")
        return None
    
    def _format_movie(self, item: Dict) -> Dict:
        return {
            "title": item.get("title"),
            "original_title": item.get("original_title"),
            "overview": item.get("overview"),
            "poster": f"{self.image_base_url}{item.get('poster_path')}" if item.get('poster_path') else None,
            "backdrop": f"{self.backdrop_base_url}{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
            "rating": item.get("vote_average"),
            "votes": item.get("vote_count"),
            "year": item.get("release_date", "")[:4] if item.get("release_date") else None,
            "genre_ids": item.get("genre_ids", []),
            "type": "movie",
            "tmdb_id": item.get("id")
        }
    
    def _format_tv(self, item: Dict) -> Dict:
        return {
            "title": item.get("name"),
            "original_title": item.get("original_name"),
            "overview": item.get("overview"),
            "poster": f"{self.image_base_url}{item.get('poster_path')}" if item.get('poster_path') else None,
            "backdrop": f"{self.backdrop_base_url}{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
            "rating": item.get("vote_average"),
            "votes": item.get("vote_count"),
            "year": item.get("first_air_date", "")[:4] if item.get("first_air_date") else None,
            "genre_ids": item.get("genre_ids", []),
            "type": "tv",
            "tmdb_id": item.get("id")
        }
    
    async def get_metadata(self, filename: str, file_hash: str = None) -> Optional[Dict]:
        """
        Get metadata for a file with caching:
        1. Check MongoDB cache
        2. Check in-memory cache
        3. Fetch from TMDB API
        4. Store in MongoDB
        """
        if not self.enabled:
            return None
        
        # Check MongoDB cache
        if self.db and file_hash:
            try:
                cached = await self.db.get_tmdb_metadata(file_hash)
                if cached:
                    updated_at = cached.get('updated_at')
                    if updated_at:
                        if isinstance(updated_at, str):
                            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        if datetime.now(updated_at.tzinfo if updated_at.tzinfo else None) - updated_at < self.cache_ttl:
                            return cached
            except Exception as e:
                print(f"Cache read error: {e}")
        
        # Extract title and search
        title = self.extract_title(filename)
        if not title:
            return None
        
        # Try movie first, then TV
        metadata = self.search_movie(title)
        if not metadata:
            metadata = self.search_tv(title)
        
        # Store in MongoDB cache
        if metadata and self.db and file_hash:
            try:
                await self.db.update_tmdb_metadata(file_hash, metadata)
            except Exception as e:
                print(f"Cache write error: {e}")
        
        return metadata
    
    async def enrich_posts(self, posts: List[Dict]) -> List[Dict]:
        """Enrich list of posts with TMDB metadata"""
        if not self.enabled or not posts:
            return posts
        
        for post in posts:
            if post.get('hash') and post.get('title'):
                post['tmdb_data'] = await self.get_metadata(post['title'], post['hash'])
        
        return posts
    
    def clear_cache(self):
        """Clear in-memory cache"""
        self.request_cache.clear()
