import os
import re
import requests
from typing import Optional, Dict, List
from fuzzywuzzy import fuzz

class TMDBIntegration:
    def __init__(self):
        self.api_key = os.getenv("TMDB_API_KEY")
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p/w500"
        self.enabled = bool(self.api_key)
    
    def extract_title(self, filename: str) -> Optional[str]:
        """Extract movie/show title from filename"""
        # Remove file extension
        name = os.path.splitext(filename)[0]
        # Remove quality tags (1080p, 720p, etc)
        name = re.sub(r'\d{3,4}p', '', name, flags=re.IGNORECASE)
        # Remove common release tags
        tags = ['bluray', 'web-dl', 'webdl', 'hdtv', 'x264', 'x265', 'hevc', 
                'aac', 'mp4', 'mkv', 'avi', 'hdr', 'dv', 'atmos', 'truehd']
        for tag in tags:
            name = re.sub(rf'\b{tag}\b', '', name, flags=re.IGNORECASE)
        # Remove year in brackets/parentheses
        name = re.sub(r'[\[\(]\d{4}[\]\)]', '', name)
        # Remove episode patterns (S01E02, S1E2, etc)
        name = re.sub(r'[Ss]\d{1,2}[Ee]\d{1,2}', '', name)
        # Clean up
        name = re.sub(r'[._\-]', ' ', name).strip()
        return name if len(name) > 2 else None
    
    def search_movie(self, title: str) -> Optional[Dict]:
        """Search TMDB for movie"""
        if not self.enabled:
            return None
        try:
            url = f"{self.base_url}/search/movie"
            params = {
                "api_key": self.api_key,
                "query": title,
                "language": "en-US",
                "page": 1
            }
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            if data.get("results"):
                return self._format_movie(data["results"][0])
        except Exception as e:
            print(f"TMDB Movie Search Error: {e}")
        return None
    
    def search_tv(self, title: str) -> Optional[Dict]:
        """Search TMDB for TV show"""
        if not self.enabled:
            return None
        try:
            url = f"{self.base_url}/search/tv"
            params = {
                "api_key": self.api_key,
                "query": title,
                "language": "en-US",
                "page": 1
            }
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            if data.get("results"):
                return self._format_tv(data["results"][0])
        except Exception as e:
            print(f"TMDB TV Search Error: {e}")
        return None
    
    def _format_movie(self, item: Dict) -> Dict:
        return {
            "title": item.get("title"),
            "overview": item.get("overview"),
            "poster": f"{self.image_base_url}{item.get('poster_path')}" if item.get('poster_path') else None,
            "backdrop": f"{self.image_base_url}{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
            "rating": item.get("vote_average"),
            "year": item.get("release_date", "")[:4] if item.get("release_date") else None,
            "genre_ids": item.get("genre_ids", []),
            "type": "movie"
        }
    
    def _format_tv(self, item: Dict) -> Dict:
        return {
            "title": item.get("name"),
            "overview": item.get("overview"),
            "poster": f"{self.image_base_url}{item.get('poster_path')}" if item.get('poster_path') else None,
            "backdrop": f"{self.image_base_url}{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
            "rating": item.get("vote_average"),
            "year": item.get("first_air_date", "")[:4] if item.get("first_air_date") else None,
            "genre_ids": item.get("genre_ids", []),
            "type": "tv"
        }
    
    def get_metadata(self, filename: str) -> Optional[Dict]:
        """Get metadata for a file (try movie first, then TV)"""
        title = self.extract_title(filename)
        if not title:
            return None
        
        # Try movie first
        movie = self.search_movie(title)
        if movie:
            return movie
        
        # Try TV
        tv = self.search_tv(title)
        if tv:
            return tv
        
        return None
    
    def get_best_match(self, filename: str, candidates: List[Dict]) -> Optional[Dict]:
        """Find best matching metadata from candidates using fuzzy matching"""
        title = self.extract_title(filename)
        if not title or not candidates:
            return None
        
        best_match = None
        best_score = 0
        
        for candidate in candidates:
            candidate_title = candidate.get("title", candidate.get("name", ""))
            score = fuzz.ratio(title.lower(), candidate_title.lower())
            if score > best_score and score > 70:  # Threshold
                best_score = score
                best_match = candidate
        
        return self._format_movie(best_match) if best_match else None
