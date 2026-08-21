from __future__ import annotations

import struct
from pathlib import Path


def write_placeholder_avi(
    output_path: Path,
    *,
    duration_seconds: int,
    seed: int,
    width: int = 320,
    height: int = 180,
    fps: int = 8,
) -> Path:
    """写入标准库可生成的轻量 AVI 假视频。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(duration_seconds) * fps)
    row_stride = ((width * 3 + 3) // 4) * 4
    frame_size = row_stride * height
    frames = [
        _build_frame(width=width, height=height, row_stride=row_stride, frame_index=index, frame_count=frame_count, seed=seed)
        for index in range(frame_count)
    ]

    avih = struct.pack(
        "<IIIIIIIIII4I",
        int(1_000_000 / fps),
        frame_size * fps,
        0,
        0x10,
        frame_count,
        0,
        1,
        frame_size,
        width,
        height,
        0,
        0,
        0,
        0,
    )
    strh = struct.pack(
        "<4s4sIHHIIIIIIIIhhhh",
        b"vids",
        b"DIB ",
        0,
        0,
        0,
        0,
        1,
        fps,
        0,
        frame_count,
        frame_size,
        0xFFFFFFFF,
        0,
        0,
        0,
        width,
        height,
    )
    strf = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height,
        1,
        24,
        0,
        frame_size,
        0,
        0,
        0,
        0,
    )
    hdrl = _list(
        b"hdrl",
        _chunk(b"avih", avih)
        + _list(
            b"strl",
            _chunk(b"strh", strh) + _chunk(b"strf", strf),
        ),
    )

    movi_payload_parts: list[bytes] = []
    idx_entries: list[bytes] = []
    offset = 4
    for frame in frames:
        frame_chunk = _chunk(b"00db", frame)
        movi_payload_parts.append(frame_chunk)
        idx_entries.append(struct.pack("<4sIII", b"00db", 0x10, offset, len(frame)))
        offset += len(frame_chunk)

    movi = _list(b"movi", b"".join(movi_payload_parts))
    idx1 = _chunk(b"idx1", b"".join(idx_entries))
    output_path.write_bytes(_riff(hdrl + movi + idx1))
    return output_path


def _riff(payload: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", len(payload) + 4) + b"AVI " + payload


def _list(list_type: bytes, payload: bytes) -> bytes:
    data = list_type + payload
    return b"LIST" + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) % 2 else b"")


def _chunk(fourcc: bytes, payload: bytes) -> bytes:
    return fourcc + struct.pack("<I", len(payload)) + payload + (b"\x00" if len(payload) % 2 else b"")


def _build_frame(*, width: int, height: int, row_stride: int, frame_index: int, frame_count: int, seed: int) -> bytes:
    base_r, base_g, base_b = _base_color(seed)
    bar_x = int((frame_index / max(1, frame_count - 1)) * (width - 1))
    frame = bytearray(row_stride * height)
    for source_y in range(height - 1, -1, -1):
        target_row = height - 1 - source_y
        row_offset = target_row * row_stride
        shade = int(36 * (source_y / max(1, height - 1)))
        for x in range(width):
            distance = abs(x - bar_x)
            pulse = max(0, 80 - distance * 4)
            index = row_offset + x * 3
            frame[index] = min(255, base_b + shade + pulse)
            frame[index + 1] = min(255, base_g + shade // 2 + pulse // 3)
            frame[index + 2] = min(255, base_r + shade // 3 + pulse // 4)
    return bytes(frame)


def _base_color(seed: int) -> tuple[int, int, int]:
    palette = [
        (32, 58, 74),
        (78, 46, 36),
        (46, 68, 45),
        (77, 37, 54),
        (45, 48, 91),
    ]
    return palette[seed % len(palette)]
