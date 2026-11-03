"""Minimal, dependency-free reader for Apple iWork .iwa archives (Keynote, Pages,
Numbers). An .iwa file is a sequence of Snappy-compressed chunks (no CRC); the
decompressed stream is a sequence of (ArchiveInfo, payloads) records.

    objs = read_iwa(path)       # {object_id: [(type_id, payload_bytes), ...]}
    fields = decode(payload)    # [(field_number, wire_type, value), ...]

Only what keynote_extract.py needs is implemented; field meanings are reverse-
engineered and documented there.
"""
from __future__ import annotations


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def snappy_decompress(data: bytes) -> bytes:
    """Decompress one raw Snappy block."""
    length, i = _varint(data, 0)
    out = bytearray()
    while i < len(data):
        tag = data[i]
        i += 1
        kind = tag & 3
        if kind == 0:  # literal
            n = tag >> 2
            if n >= 60:
                extra = n - 59
                n = int.from_bytes(data[i:i + extra], "little")
                i += extra
            n += 1
            out += data[i:i + n]
            i += n
            continue
        if kind == 1:
            n = ((tag >> 2) & 7) + 4
            off = ((tag >> 5) << 8) | data[i]
            i += 1
        elif kind == 2:
            n = (tag >> 2) + 1
            off = int.from_bytes(data[i:i + 2], "little")
            i += 2
        else:
            n = (tag >> 2) + 1
            off = int.from_bytes(data[i:i + 4], "little")
            i += 4
        start = len(out) - off
        for k in range(n):  # copies may overlap
            out.append(out[start + k])
    if len(out) != length:
        raise ValueError("snappy length mismatch")
    return bytes(out)


def iwa_stream(raw: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] != 0:
            raise ValueError("unexpected iwa chunk header")
        n = int.from_bytes(raw[i + 1:i + 4], "little")
        out += snappy_decompress(raw[i + 4:i + 4 + n])
        i += 4 + n
    return bytes(out)


def decode(buf: bytes) -> list[tuple[int, int, object]]:
    """Decode one protobuf message into (field, wire_type, value) triples.
    Length-delimited values stay bytes; varints are ints; fixed are bytes."""
    out = []
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        field, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(buf, i)
        elif wt == 1:
            v, i = buf[i:i + 8], i + 8
        elif wt == 2:
            n, i = _varint(buf, i)
            v, i = buf[i:i + n], i + n
        elif wt == 5:
            v, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        out.append((field, wt, v))
    return out


def read_iwa(path) -> dict[int, list[tuple[int, bytes]]]:
    data = iwa_stream(open(path, "rb").read())
    objs: dict[int, list[tuple[int, bytes]]] = {}
    i = 0
    while i < len(data):
        n, i = _varint(data, i)
        info = decode(data[i:i + n])
        i += n
        ident = next(v for f, _, v in info if f == 1)
        entry = []
        for f, _, mi in info:
            if f != 2:
                continue
            m = decode(mi)
            mtype = next(v for g, _, v in m if g == 1)
            mlen = next(v for g, _, v in m if g == 3)
            entry.append((mtype, data[i:i + mlen]))
            i += mlen
        objs[ident] = entry
    return objs
