import asyncio
from app.providers.pagalnew_provider import PagalnewMusicProvider

async def main():
    print("=== PagalNew Live Pagination & Album Verification ===")
    provider = PagalnewMusicProvider()

    # 1. Browse Category Page 1
    print("\n1. Fetching 'bollywood-2026' Page 1...")
    res_page_1 = await provider.browse_category("bollywood-2026", page=1)
    print(f"   Page 1 items count: {len(res_page_1.items)}")
    print(f"   Current page: {res_page_1.current_page}, has_prev: {res_page_1.has_prev}, has_next: {res_page_1.has_next}, total_pages: {res_page_1.total_pages}")
    page_1_titles = [item.title for item in res_page_1.items]
    print(f"   First 3 albums on Page 1: {page_1_titles[:3]}")
    assert len(res_page_1.items) > 0, "Page 1 returned no items"
    assert res_page_1.current_page == 1
    assert res_page_1.has_next is True

    # 2. Browse Category Page 2
    print("\n2. Fetching 'bollywood-2026' Page 2...")
    res_page_2 = await provider.browse_category("bollywood-2026", page=2)
    print(f"   Page 2 items count: {len(res_page_2.items)}")
    print(f"   Current page: {res_page_2.current_page}, has_prev: {res_page_2.has_prev}, has_next: {res_page_2.has_next}, total_pages: {res_page_2.total_pages}")
    page_2_titles = [item.title for item in res_page_2.items]
    print(f"   First 3 albums on Page 2: {page_2_titles[:3]}")
    assert len(res_page_2.items) > 0, "Page 2 returned no items"
    assert res_page_2.current_page == 2
    assert res_page_2.has_prev is True

    # 3. Verify page 1 and page 2 return different albums
    overlap = set(page_1_titles).intersection(set(page_2_titles))
    print(f"\n3. Checking page uniqueness: overlap count = {len(overlap)}")
    assert len(overlap) < len(page_1_titles), "Page 1 and Page 2 should not have identical albums"
    print("   Verified: Page 1 and Page 2 return distinct albums!")

    # 4. Open an album from page 2 and verify full tracklist
    target_album_item = res_page_2.items[0]
    print(f"\n4. Opening full album details for: '{target_album_item.title}' (ID: {target_album_item.id})...")
    full_album = await provider.get_album(target_album_item.id)
    assert full_album is not None, f"Could not load album '{target_album_item.id}'"
    print(f"   Album Title: {full_album.title}")
    print(f"   Year: {full_album.year}")
    print(f"   Artists: {', '.join(full_album.artists)}")
    print(f"   Starcast: {', '.join(full_album.starcast)}")
    print(f"   Track Count: {len(full_album.tracks)}")
    assert len(full_album.tracks) > 0, "Album has no tracks"
    for idx, trk in enumerate(full_album.tracks[:3], 1):
        print(f"     Track {idx}: {trk.title} (Singers: {', '.join(trk.artists)})")

    # 5. Verify Indipop Category Page 1 vs Page 2
    print("\n5. Testing Indipop Category Page 1 vs Page 2...")
    indipop_1 = await provider.browse_category("indipop", page=1)
    indipop_2 = await provider.browse_category("indipop", page=2)
    print(f"   Indipop P1 count: {len(indipop_1.items)} (has_next={indipop_1.has_next})")
    print(f"   Indipop P2 count: {len(indipop_2.items)} (has_prev={indipop_2.has_prev})")
    assert len(indipop_1.items) > 0
    assert len(indipop_2.items) > 0
    assert indipop_1.items[0].title != indipop_2.items[0].title
    print(f"   Indipop P1 first: '{indipop_1.items[0].title}' vs P2 first: '{indipop_2.items[0].title}'")

    print("\nSUCCESS: Real PagalNew pagination and album tracklist inspection fully verified!")

if __name__ == "__main__":
    asyncio.run(main())
