from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from ..providers.registry import registry
from ..models.schemas import SearchResponse
from ..models.domain import Album, Track

search_router = APIRouter(prefix="/api", tags=["Search & Discovery"])

@search_router.get("/search", response_model=SearchResponse)
async def search_music(
    q: str = Query("", description="Search term for movie, album, artist, composer, or song"),
    provider: Optional[str] = Query(None, description="Optional specific provider ID")
):
    results = await registry.unified_search(query=q, provider_id=provider)
    return SearchResponse(
        query=q,
        total_results=len(results),
        results=results
    )

@search_router.get("/albums/{provider_id}/{album_id}", response_model=Album)
async def get_album(provider_id: str, album_id: str):
    prov = registry.get(provider_id)
    if not prov:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    
    album = await prov.get_album(album_id)
    if not album:
        raise HTTPException(status_code=404, detail=f"Album '{album_id}' not found on provider '{provider_id}'")
    
    return album

@search_router.get("/tracks/{provider_id}/{track_id}", response_model=Track)
async def get_track(provider_id: str, track_id: str):
    prov = registry.get(provider_id)
    if not prov:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    
    track = await prov.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Track '{track_id}' not found")
        
    return track
