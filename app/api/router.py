from fastapi import APIRouter
from .routes_search import search_router
from .routes_downloads import downloads_router
from .routes_settings import settings_router
from .routes_mock_cdn import mock_cdn_router

api_router = APIRouter()
api_router.include_router(search_router)
api_router.include_router(downloads_router)
api_router.include_router(settings_router)
api_router.include_router(mock_cdn_router)
