from fastapi import APIRouter, Header, Response, HTTPException
import math

mock_cdn_router = APIRouter(prefix="/mock-cdn", tags=["Mock CDN"])

# Standard simulated file sizes
SIZES = {
    128: 4 * 1024 * 1024,   # 4 MB
    320: 10 * 1024 * 1024,  # 10 MB
}

# Standard MP3 ID3 header prefix
ID3_HEADER = b"ID3\x04\x00\x00\x00\x02\x2b\x46" + (b"\x00" * 200)

@mock_cdn_router.get("/stream/{track_id}/{bitrate}")
async def stream_mock_audio(track_id: str, bitrate: int, range: str = Header(None)):
    """Simulates an audio CDN supporting HTTP Range requests and returning valid MP3 bytes."""
    total_size = SIZES.get(bitrate, 5 * 1024 * 1024)

    # Generate synthetic chunk data
    def get_byte_slice(start: int, length: int) -> bytes:
        slice_data = bytearray()
        if start < len(ID3_HEADER):
            hdr_chunk = ID3_HEADER[start:min(start + length, len(ID3_HEADER))]
            slice_data.extend(hdr_chunk)
            remaining = length - len(hdr_chunk)
            if remaining > 0:
                # Fill remaining with dummy audio payload
                slice_data.extend(b"\xff\xfb\x90\x64" * (remaining // 4 + 1))
        else:
            slice_data.extend(b"\xff\xfb\x90\x64" * (length // 4 + 1))
        return bytes(slice_data[:length])

    if not range:
        # Full content response (200 OK)
        data = get_byte_slice(0, total_size)
        return Response(
            content=data,
            status_code=200,
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(total_size),
                "Content-Disposition": f'attachment; filename="{track_id}_{bitrate}k.mp3"'
            }
        )

    # Range request handling (bytes=start-end)
    try:
        range_spec = range.strip().replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else total_size - 1

        if start >= total_size:
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{total_size}"}
            )

        end = min(end, total_size - 1)
        length = end - start + 1
        data = get_byte_slice(start, length)

        return Response(
            content=data,
            status_code=206,
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Length": str(length),
                "Content-Disposition": f'attachment; filename="{track_id}_{bitrate}k.mp3"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Range Header: {str(e)}")
