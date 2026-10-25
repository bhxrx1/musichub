from typing import Dict, List, Optional
from .base import BaseMusicProvider
from .mock_provider import MockMusicProvider
from .pagalnew_provider import PagalnewMusicProvider
from ..models.domain import ProviderInfo, SearchResultItem

class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, BaseMusicProvider] = {}
        # Register both PagalNew real provider and Mock provider
        self.register(PagalnewMusicProvider())
        self.register(MockMusicProvider())

    def register(self, provider: BaseMusicProvider) -> None:
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> Optional[BaseMusicProvider]:
        return self._providers.get(provider_id)

    def list_providers(self) -> List[ProviderInfo]:
        return [
            ProviderInfo(
                id=p.provider_id,
                name=p.provider_name,
                enabled=True,
                supports_batch_download=p.supports_batch_download,
                description=f"Audio provider adapter for {p.provider_name}"
            )
            for p in self._providers.values()
        ]

    async def unified_search(self, query: str, provider_id: Optional[str] = None) -> List[SearchResultItem]:
        results: List[SearchResultItem] = []
        if provider_id and provider_id in self._providers:
            providers = [self._providers[provider_id]]
        else:
            # Query active providers; PagalNew first, then others
            providers = list(self._providers.values())

        for p in providers:
            try:
                res = await p.search(query)
                results.extend(res)
            except Exception as e:
                print(f"[Registry] Error querying provider {p.provider_id}: {e}")

        return results

registry = ProviderRegistry()
