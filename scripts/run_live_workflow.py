import asyncio
from pathlib import Path
from app.providers.pagalnew_provider import PagalnewMusicProvider
from app.services.download_manager import download_manager
from app.database import db
from mutagen.id3 import ID3

async def test_live_workflow():
    prov = PagalnewMusicProvider()
    print("1. Searching for 'Awarapan' on PagalNew...")
    results = await prov.search("Awarapan")
    assert len(results) > 0, "No search results returned"
    
    alb_item = next((r for r in results if r.item_type == "album" and "awarapan-2" in r.id), None)
    assert alb_item is not None, "Album awarapan-2 not found in search"
    print(f"   Found album: {alb_item.title} (ID: {alb_item.id})")

    print("2. Fetching album metadata & tracklist...")
    album = await prov.get_album(alb_item.id)
    assert album is not None, "Could not fetch album"
    print(f"   Album: {album.title} ({album.year}) - {len(album.tracks)} tracks")
    assert len(album.tracks) > 0, "Tracklist is empty"

    track = next((t for t in album.tracks if "yeh-awarapan" in t.id), album.tracks[0])
    print(f"3. Selected track: {track.title} by {track.artists}")
    print(f"   Available bitrates: {[q.bitrate_kbps for q in track.qualities]}")

    print("4. Enqueuing download with 320 kbps...")
    task = await download_manager.enqueue_track(track, album, preferred_bitrate=320, strict_320k=False)
    print(f"   Task ID: {task.task_id}")
    print(f"   Target Path: {task.target_file_path}")

    print("5. Waiting for download & metadata tagging to complete...")
    for _ in range(60):
        await asyncio.sleep(1.0)
        t = db.get_task(task.task_id)
        if t and t.status in ("COMPLETED", "FAILED"):
            print(f"   Status: {t.status} ({t.downloaded_bytes} bytes downloaded)")
            if t.status == "FAILED":
                print(f"   Error: {t.error_message}")
            break
        elif t:
            print(f"   Downloading... {t.downloaded_bytes}/{t.total_bytes} bytes ({t.progress_pct}%)")

    final_file = Path(task.target_file_path)
    assert final_file.exists(), f"File does not exist: {final_file}"
    assert final_file.stat().st_size > 0, "Downloaded file is 0 bytes"

    print("6. Inspecting embedded ID3 tags using Mutagen...")
    tags = ID3(str(final_file))
    print(f"   ID3 Version: 2.{tags.version[1]}")
    print(f"   TIT2 (Title): {tags.get('TIT2')}")
    print(f"   TPE1 (Artist): {tags.get('TPE1')}")
    print(f"   TALB (Album): {tags.get('TALB')}")
    print(f"   TPE2 (Album Artist): {tags.get('TPE2')}")
    print(f"   TRCK (Track #): {tags.get('TRCK')}")
    print(f"   TDRC (Year): {tags.get('TDRC')}")
    apic = tags.getall("APIC")
    print(f"   APIC (Cover Art): {len(apic)} frame(s) present, size: {len(apic[0].data) if apic else 0} bytes")

    print("\nSUCCESS: Live search-to-album-to-download with ID3 tagging verified!")

if __name__ == "__main__":
    asyncio.run(test_live_workflow())
