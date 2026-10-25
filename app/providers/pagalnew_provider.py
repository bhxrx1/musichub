import asyncio
import re
import time
import urllib.parse
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from .base import BaseMusicProvider
from ..models.domain import Album, Track, QualityOption, SearchResultItem
from ..models.schemas import ProviderDiagnosticResponse, CategoryBrowseResponse
from ..database import db
from ..config import settings

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 MusicHub/1.2"
)

def get_category_path(category_key: str, page: int = 1) -> str:
    """Builds PagalNew category listing URL path based on observed real-world site routes."""
    page = max(1, page)
    if category_key == "bollywood-2026":
        return f"/category/bollywood-mp3-songs/{page}/2026"
    elif category_key == "bollywood-2025":
        return f"/category/bollywood-mp3-songs/{page}/2025"
    elif category_key in ("bollywood-tracks", "bollywood"):
        return f"/category/bollywood-mp3-songs/{page}"
    elif category_key in ("indipop", "indipop-mp3-tracks"):
        return f"/category/indipop-mp3-songs/{page}"
    elif category_key in ("punjabi", "punjabi-mp3-tracks"):
        return f"/category/punjabi-mp3-songs/{page}"
    elif category_key in ("haryanvi", "haryanvi-mp3-tracks"):
        return f"/category/haryanvi-mp3-songs/{page}"
    elif category_key in ("bhojpuri", "bhojpuri-mp3-tracks"):
        return f"/category/bhojpuri-mp3-songs/{page}"
    else:
        clean_cat = category_key.replace("-tracks", "-songs")
        return f"/category/{clean_cat}/{page}"

def parse_pagination_info(html: str, current_page: int) -> dict:
    """Parses real PagalNew pagination bar elements from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    pag_div = soup.find(class_="pagination")

    has_prev = current_page > 1
    has_next = False
    total_pages = None
    page_numbers = []

    if pag_div:
        active_el = pag_div.find(class_=re.compile(r"currentactive|active", re.I))
        if active_el and active_el.get_text(strip=True).isdigit():
            current_page = int(active_el.get_text(strip=True))

        for a in pag_div.find_all("a"):
            text = a.get_text(strip=True)
            href = a.get("href", "")

            if ">>" in text:
                has_next = True
                m = re.search(r"/(\d+)(?:/\d+)?$", href)
                if m:
                    total_pages = int(m.group(1))
            elif text.isdigit():
                num = int(text)
                page_numbers.append(num)
                if num > current_page:
                    has_next = True

        if not total_pages and page_numbers:
            total_pages = max(page_numbers)
            if current_page >= total_pages and not any(">>" in a.get_text() for a in pag_div.find_all("a")):
                has_next = False
    else:
        has_next = False
        has_prev = current_page > 1
        total_pages = 1

    return {
        "current_page": current_page,
        "has_next": has_next,
        "has_prev": has_prev,
        "total_pages": total_pages
    }

class PagalnewMusicProvider(BaseMusicProvider):
    def __init__(self, base_url: Optional[str] = None, http_client: Optional[httpx.AsyncClient] = None):
        self._base_url = (base_url or settings.pagalnew_base_url).rstrip("/")
        self._client = http_client
        self._track_fetch_semaphore = asyncio.Semaphore(5)

    @property
    def provider_id(self) -> str:
        return "pagalnew"

    @property
    def provider_name(self) -> str:
        return "PagalNew"

    @property
    def supports_batch_download(self) -> bool:
        return True

    def _get_client(self) -> httpx.AsyncClient:
        if self._client:
            return self._client
        return httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=15.0
        )

    def _extract_b_field(self, soup: BeautifulSoup, label: str) -> Optional[str]:
        for b in soup.find_all("b"):
            if label.lower() in b.get_text().lower():
                val = b.next_sibling
                if val and isinstance(val, str) and val.strip():
                    return val.strip()
        return None

    def _extract_slug(self, href: str, prefix: str) -> str:
        clean = href.split("?")[0]
        pattern = rf"{prefix}/([^/]+?)(?:\.html)?$"
        m = re.search(pattern, clean)
        if m:
            return m.group(1)
        return clean.strip("/").split("/")[-1].replace(".html", "")

    async def browse_category(self, category_key: str = "bollywood-2026", page: int = 1) -> CategoryBrowseResponse:
        """Fetch and parse a category listing page with real pagination controls."""
        path = get_category_path(category_key, page)
        url = f"{self._base_url}{path}"
        client = self._get_client()
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                return CategoryBrowseResponse(
                    category=category_key,
                    current_page=page,
                    has_next=False,
                    has_prev=page > 1,
                    total_pages=None,
                    items=[]
                )
            if resp.status_code != 200:
                return CategoryBrowseResponse(
                    category=category_key,
                    current_page=page,
                    has_next=False,
                    has_prev=page > 1,
                    total_pages=None,
                    items=[]
                )

            items = self.parse_search_html(resp.text)
            pag_info = parse_pagination_info(resp.text, current_page=page)

            if not items:
                pag_info["has_next"] = False

            return CategoryBrowseResponse(
                category=category_key,
                current_page=pag_info["current_page"],
                has_next=pag_info["has_next"],
                has_prev=pag_info["has_prev"],
                total_pages=pag_info["total_pages"],
                items=items
            )
        except Exception as e:
            print(f"[PagalNew] Category browse error for '{category_key}' page {page}: {e}")
            return CategoryBrowseResponse(
                category=category_key,
                current_page=page,
                has_next=False,
                has_prev=page > 1,
                total_pages=None,
                items=[]
            )
        finally:
            if not self._client:
                await client.aclose()

    async def search(self, query: str, search_type: str = "all") -> List[SearchResultItem]:
        q = query.strip()
        if not q:
            # Query trending/default Bollywood if search query is empty
            search_url = f"{self._base_url}/category/bollywood-tracks"
        else:
            search_url = f"{self._base_url}/search.php?find={urllib.parse.quote_plus(q)}"

        client = self._get_client()
        try:
            resp = await client.get(search_url)
            if resp.status_code != 200:
                return []
            return self.parse_search_html(resp.text)
        except Exception as e:
            print(f"[PagalNew] Search error for query '{q}': {e}")
            return []
        finally:
            if not self._client:
                await client.aclose()

    def parse_search_html(self, html: str) -> List[SearchResultItem]:
        soup = BeautifulSoup(html, "html.parser")
        results: List[SearchResultItem] = []
        seen_ids = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            
            # 1. Album Result
            if "/album/" in href:
                slug = self._extract_slug(href, "/album")
                if slug in seen_ids:
                    continue
                seen_ids.add(slug)

                txt = a.get_text(separator=" | ", strip=True)
                title = txt.split("|")[0].replace("Mp3 Songs", "").strip()
                
                # Image
                img = a.find("img")
                artwork = None
                if img:
                    src = img.get("data-src") or img.get("src")
                    if src and not src.endswith(".gif") and not src.endswith(".svg"):
                        artwork = urllib.parse.urljoin(self._base_url, src)

                # Year heuristic
                year_m = re.search(r"\b(19\d\d|20\d\d)\b", slug) or re.search(r"\b(19\d\d|20\d\d)\b", title)
                year = int(year_m.group(0)) if year_m else None

                results.append(SearchResultItem(
                    id=slug,
                    provider=self.provider_id,
                    item_type="album",
                    title=title or slug,
                    album_title=title or slug,
                    year=year,
                    artists=[],
                    artwork_url=artwork,
                    album_id=slug
                ))

            # 2. Song Result
            elif "/songs/" in href or "/song/" in href:
                slug = self._extract_slug(href, r"/songs?")
                if slug in seen_ids:
                    continue
                seen_ids.add(slug)

                txt = a.get_text(separator=" | ", strip=True)
                parts = [p.strip() for p in txt.split("|") if p.strip()]
                title_artist = parts[0] if parts else slug
                
                if " - " in title_artist:
                    raw_title, raw_artists = title_artist.split(" - ", 1)
                else:
                    raw_title, raw_artists = title_artist, ""

                song_title = re.sub(r"\s*-\s*.*?(?:Mp3\s*Song)?$", "", raw_title, flags=re.IGNORECASE).strip()
                artists = [art.strip() for art in re.split(r"[-–,]", raw_artists) if art.strip()]
                album_name = parts[1] if len(parts) > 1 else None

                img = a.find("img")
                artwork = None
                if img:
                    src = img.get("data-src") or img.get("src")
                    if src and not src.endswith(".gif") and not src.endswith(".svg"):
                        artwork = urllib.parse.urljoin(self._base_url, src)

                results.append(SearchResultItem(
                    id=slug,
                    provider=self.provider_id,
                    item_type="track",
                    title=song_title or slug,
                    album_title=album_name,
                    artists=artists,
                    artwork_url=artwork,
                    album_id=None
                ))

        return results

    async def get_album(self, album_id: str) -> Optional[Album]:
        # 1. Check local cache
        cached = db.get_cached_album(self.provider_id, album_id)
        if cached:
            return cached

        clean_slug = album_id.replace(".html", "").strip("/")
        album_url = f"{self._base_url}/album/{clean_slug}.html"

        client = self._get_client()
        try:
            resp = await client.get(album_url)
            if resp.status_code != 200:
                return None
            
            album = self.parse_album_html(clean_slug, resp.text)
            if not album:
                return None

            # Fetch track qualities in parallel with bounded concurrency
            await self._enrich_album_tracks(album, client)

            # Cache the fully resolved album
            db.cache_album(album)
            return album
        except Exception as e:
            print(f"[PagalNew] Error fetching album {album_id}: {e}")
            return None
        finally:
            if not self._client:
                await client.aclose()

    def parse_album_html(self, slug: str, html: str) -> Optional[Album]:
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        raw_title = self._extract_b_field(soup, "Album:")
        if not raw_title:
            h1 = soup.find("h1")
            raw_title = h1.get_text(strip=True) if h1 else slug
        clean_title = re.sub(r"\s*Mp3\s*Songs(?:\s*Download\s*Pagalnew)?.*$", "", raw_title, flags=re.IGNORECASE).strip()

        # Artists
        artists_str = self._extract_b_field(soup, "Artists:") or ""
        artists = [a.strip() for a in re.split(r"[-–,]", artists_str) if a.strip()]

        # Starcast
        starcast_str = self._extract_b_field(soup, "Starcast:") or ""
        starcast = [s.strip() for s in re.split(r"[-–,]", starcast_str) if s.strip()]

        # Composer
        composer_str = self._extract_b_field(soup, "Composed by:")
        composer = ", ".join([c.strip() for c in re.split(r"[\t\n,]+", composer_str) if c.strip()]) if composer_str else None

        # Year
        year_str = self._extract_b_field(soup, "Year:")
        year = None
        if year_str and year_str.isdigit():
            year = int(year_str)
        else:
            year_m = re.search(r"\b(19\d\d|20\d\d)\b", slug) or re.search(r"\b(19\d\d|20\d\d)\b", clean_title)
            if year_m:
                year = int(year_m.group(0))

        # Cover Image
        cover_img = soup.find("img", alt=lambda a: a and "cover" in a.lower())
        artwork = None
        if cover_img:
            src = cover_img.get("data-src") or cover_img.get("src")
            if src and not src.endswith(".gif") and not src.endswith(".svg"):
                artwork = urllib.parse.urljoin(self._base_url, src)

        # Track links
        tracks: List[Track] = []
        track_links = soup.find_all("a", href=re.compile(r"/songs?/.*\.html"))
        seen_track_ids = set()

        for idx, a in enumerate(track_links, 1):
            track_slug = self._extract_slug(a["href"], r"/songs?")
            if track_slug in seen_track_ids:
                continue
            seen_track_ids.add(track_slug)

            txt_div = a.find("div", class_="main_page_category_music_txt")
            if txt_div:
                parts = [p.strip() for p in txt_div.get_text(separator="|", strip=True).split("|") if p.strip()]
                raw_t = parts[0] if parts else track_slug
                clean_t = re.sub(r"\s*-\s*.*?(?:Mp3\s*Song)?$", "", raw_t, flags=re.IGNORECASE).strip()
                trk_artists = [art.strip() for art in re.split(r"[-–,]", parts[1]) if art.strip()] if len(parts) > 1 else artists
            else:
                clean_t = track_slug.replace("-", " ").title()
                trk_artists = artists

            # Track artwork
            trk_img = a.find("img")
            trk_art = None
            if trk_img:
                src = trk_img.get("data-src") or trk_img.get("src")
                if src and not src.endswith(".gif") and not src.endswith(".svg"):
                    trk_art = urllib.parse.urljoin(self._base_url, src)

            tracks.append(Track(
                id=track_slug,
                album_id=slug,
                provider=self.provider_id,
                title=clean_t,
                artists=trk_artists,
                composer=composer,
                artwork_url=trk_art or artwork,
                track_number=idx,
                qualities=[]
            ))

        return Album(
            id=slug,
            provider=self.provider_id,
            title=clean_title or slug,
            year=year,
            artists=artists,
            composer=composer,
            starcast=starcast,
            artwork_url=artwork,
            tracks=tracks
        )

    async def _enrich_album_tracks(self, album: Album, client: httpx.AsyncClient) -> None:
        """Concurrently fetch track pages to populate download quality options."""
        async def fetch_track_qualities(track: Track):
            async with self._track_fetch_semaphore:
                try:
                    song_url = f"{self._base_url}/songs/{track.id}.html"
                    r = await client.get(song_url)
                    if r.status_code == 200:
                        parsed_track = self.parse_track_html(track.id, r.text)
                        if parsed_track and parsed_track.qualities:
                            track.qualities = parsed_track.qualities
                            if not track.composer and parsed_track.composer:
                                track.composer = parsed_track.composer
                except Exception as e:
                    print(f"[PagalNew] Failed to fetch quality for {track.id}: {e}")

        tasks = [fetch_track_qualities(t) for t in album.tracks]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def get_track(self, track_id: str) -> Optional[Track]:
        clean_slug = track_id.replace(".html", "").strip("/")
        song_url = f"{self._base_url}/songs/{clean_slug}.html"

        client = self._get_client()
        try:
            resp = await client.get(song_url)
            if resp.status_code != 200:
                return None
            return self.parse_track_html(clean_slug, resp.text)
        except Exception as e:
            print(f"[PagalNew] Error fetching track {track_id}: {e}")
            return None
        finally:
            if not self._client:
                await client.aclose()

    def parse_track_html(self, slug: str, html: str) -> Optional[Track]:
        soup = BeautifulSoup(html, "html.parser")
        
        # Song Title
        raw_title = self._extract_b_field(soup, "Song Name:")
        if not raw_title:
            h1 = soup.find("h1")
            raw_title = h1.get_text(strip=True) if h1 else slug
        clean_title = re.sub(r"\s*Song\s*-\s*.*$", "", raw_title, flags=re.IGNORECASE).strip()

        # Singers
        singers_str = self._extract_b_field(soup, "Singer(s):") or ""
        singers = [s.strip() for s in re.split(r"[-–,]", singers_str) if s.strip()]

        # Music Composer
        composer = self._extract_b_field(soup, "Music Composer:")

        # Album link & id
        album_id = "unknown"
        album_link = soup.find("a", href=re.compile(r"/album/.*\.html"))
        if album_link:
            album_id = self._extract_slug(album_link["href"], "/album")

        # Artwork
        img = soup.find("img", alt=lambda a: a and "cover" in a.lower()) or soup.find("img", class_="b-lazy")
        artwork = None
        if img:
            src = img.get("data-src") or img.get("src")
            if src and not src.endswith(".gif") and not src.endswith(".svg"):
                artwork = urllib.parse.urljoin(self._base_url, src)

        # Download qualities from <div class="downloaddiv">
        qualities: List[QualityOption] = []
        ddiv = soup.find("div", class_="downloaddiv")
        if ddiv:
            for a in ddiv.find_all("a", href=True):
                btn_text = a.get_text(strip=True)
                m = re.search(r"(\d+)\s*KBPS", btn_text, re.IGNORECASE)
                if m:
                    bitrate = int(m.group(1))
                    is_320 = (bitrate >= 320)
                    dl_url = urllib.parse.urljoin(self._base_url, a["href"])
                    qualities.append(QualityOption(
                        bitrate_kbps=bitrate,
                        format="mp3",
                        download_url=dl_url,
                        is_confirmed_320k=is_320
                    ))

        # Sort qualities descending by bitrate (highest first)
        qualities.sort(key=lambda q: q.bitrate_kbps, reverse=True)

        return Track(
            id=slug,
            album_id=album_id,
            provider=self.provider_id,
            title=clean_title or slug,
            artists=singers,
            composer=composer,
            artwork_url=artwork,
            qualities=qualities
        )

    async def test_connection(self) -> ProviderDiagnosticResponse:
        client = self._get_client()
        start = time.perf_counter()
        try:
            r = await client.get(self._base_url, timeout=10.0)
            latency = (time.perf_counter() - start) * 1000
            if r.status_code == 200:
                return ProviderDiagnosticResponse(
                    provider_id=self.provider_id,
                    provider_name=self.provider_name,
                    healthy=True,
                    latency_ms=round(latency, 1),
                    message="PagalNew is online and responding."
                )
            return ProviderDiagnosticResponse(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                healthy=False,
                latency_ms=round(latency, 1),
                message=f"PagalNew returned HTTP {r.status_code}."
            )
        except Exception as e:
            return ProviderDiagnosticResponse(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                healthy=False,
                message=f"Connection failed: {str(e)}"
            )
        finally:
            if not self._client:
                await client.aclose()
