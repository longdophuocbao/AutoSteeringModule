#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Công cụ tổng hợp file WAV thành file header C++ (audio_data.h) cho ESP32
=============================================================================
- Quét toàn bộ file .wav trong thư mục nguồn (mặc định ./audio)
- Trích xuất dữ liệu nhị phân thành mảng PROGMEM trong bộ nhớ Flash của ESP32
- Tự động tạo comment chi tiết ở đầu file: danh sách bài âm thanh, thông số kỹ thuật,
  thời lượng, kích thước bộ nhớ và hướng dẫn code mẫu để gọi phát âm thanh.
=============================================================================
"""

import sys
import os
import glob
import struct
import argparse
from datetime import datetime

# Đảm bảo console Windows in tiếng Việt không bị lỗi cp1252
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
DEFAULT_OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "include", "audio_data.h")

def parse_wav_info(data: bytes):
    """
    Trích xuất thông số kỹ thuật từ header chuẩn của file WAV.
    """
    if len(data) < 44 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        return None
    
    try:
        # Đọc cấu trúc fmt subchunk
        channels = struct.unpack_from('<H', data, 22)[0]
        sample_rate = struct.unpack_from('<I', data, 24)[0]
        bits_per_sample = struct.unpack_from('<H', data, 34)[0]
        
        # Tìm vị trí chunk 'data'
        data_pos = data.find(b'data', 36)
        if data_pos != -1:
            data_size = struct.unpack_from('<I', data, data_pos + 4)[0]
        else:
            data_size = len(data) - 44
            
        byte_rate = sample_rate * channels * (bits_per_sample // 8)
        duration = data_size / byte_rate if byte_rate > 0 else 0
        
        return {
            "channels": channels,
            "sample_rate": sample_rate,
            "bits_per_sample": bits_per_sample,
            "duration": duration,
            "size": len(data)
        }
    except Exception:
        return None

def sanitize_var_name(filename: str) -> str:
    """
    Chuyển tên file thành tên biến C hợp lệ (chỉ gồm a-z, 0-9, _)
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    clean = "".join(c if c.isalnum() else "_" for c in base)
    if clean and clean[0].isdigit():
        clean = "_" + clean
    return clean.lower()

def generate_header(input_dir: str, output_file: str):
    """
    Quét toàn bộ file .wav trong input_dir và ghi file header output_file.
    """
    wav_files = sorted(glob.glob(os.path.join(input_dir, "*.wav")))
    if not wav_files:
        print(f"[CẢNH BÁO] Không tìm thấy file .wav nào trong thư mục: {input_dir}")
        return False

    print(f"Tìm thấy {len(wav_files)} file .wav. Đang xử lý...")
    
    tracks_info = []
    arrays_code = []
    total_bytes = 0

    for wav_path in wav_files:
        filename = os.path.basename(wav_path)
        var_name = f"sound_{sanitize_var_name(filename)}"
        
        with open(wav_path, "rb") as f:
            data = f.read()

        info = parse_wav_info(data)
        if not info:
            info = {
                "channels": 1,
                "sample_rate": 16000,
                "bits_per_sample": 16,
                "duration": len(data) / 32000,
                "size": len(data)
            }
        
        tracks_info.append({
            "filename": filename,
            "var_name": var_name,
            "len_name": f"{var_name}_len",
            "info": info
        })
        total_bytes += len(data)

        # Chuyển đổi dữ liệu nhị phân thành mảng C (12 byte mỗi dòng)
        lines = [f"// File: {filename} ({len(data):,} bytes, ~{info['duration']:.2f}s)"]
        lines.append(f"const uint8_t {var_name}[] PROGMEM = {{")
        for i in range(0, len(data), 12):
            chunk = data[i:i+12]
            hex_str = ", ".join(f"0x{b:02X}" for b in chunk)
            lines.append(f"    {hex_str},")
        lines.append("};")
        lines.append(f"const uint32_t {var_name}_len = {len(data)};\n")
        
        arrays_code.append("\n".join(lines))
        print(f" -> {filename:<20} | Mảng: {var_name:<18} | Size: {len(data):>6,} B | Thời lượng: ~{info['duration']:.2f}s")

    # Tạo bảng danh mục cho phần Comment đầu file
    table_lines = [
        "// +----+----------------------+--------------------+-----------+------------+--------+----------+------------+",
        "// | STT| Tên file WAV         | Tên mảng dữ liệu   | Kích thước| Tần số mẫu | Kênh   | Số bit   | Thời lượng |",
        "// +----+----------------------+--------------------+-----------+------------+--------+----------+------------+",
    ]
    for idx, t in enumerate(tracks_info, 1):
        inf = t["info"]
        table_lines.append(
            f"// | {idx:<2} | {t['filename']:<20} | {t['var_name']:<18} | {inf['size']:>7,} B | {inf['sample_rate']:>6} Hz  | "
            f"{'Mono' if inf['channels']==1 else 'Stereo':<6} | {inf['bits_per_sample']:>2}-bit   | ~{inf['duration']:>4.2f}s   |"
        )
    table_lines.append("// +----+----------------------+--------------------+-----------+------------+--------+----------+------------+")

    table_comment = "\n".join(table_lines)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Xây dựng nội dung file header hoàn chỉnh
    header_template = f"""// =============================================================================
// FILE: audio_data.h
// TỰ ĐỘNG TẠO BỞI: wav_to_header.py
// THỜI GIAN TẠO: {now_str}
// =============================================================================
//
// DANH MỤC CÁC FILE ÂM THANH TRONG BỘ NHỚ FLASH (PROGMEM):
//
{table_comment}
//
// Tổng dung lượng Flash sử dụng: {total_bytes:,} bytes (~{total_bytes / 1024:.1f} KB)
//
// -----------------------------------------------------------------------------
// HƯỚNG DẪN SỬ DỤNG TRONG CODE C++ (ARDUINO / PLATFORMIO):
// -----------------------------------------------------------------------------
// 1. Thêm thư viện vào mã nguồn:
//    #include "audio_data.h"
//
// 2. Gọi hàm phát âm thanh mẫu:
//    void playAudio(const uint8_t *data, uint32_t len) {{
//        stopAudio();
//        file = new AudioFileSourcePROGMEM(data, len);
//        wav = new AudioGeneratorWAV();
//        wav->begin(file, out);
//    }}
//
// 3. Ví dụ phát từng câu:
//    playAudio(sound_manual, sound_manual_len); // Phát âm thanh MANUAL
//    playAudio(sound_auto, sound_auto_len);     // Phát âm thanh AUTO
//    playAudio(sound_cancel, sound_cancel_len); // Phát âm thanh CANCEL
// =============================================================================

#ifndef AUDIO_DATA_H
#define AUDIO_DATA_H

#include <Arduino.h>

{chr(10).join(arrays_code)}
#endif // AUDIO_DATA_H
"""

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header_template)

    print("-" * 65)
    print(f" [THÀNH CÔNG] Đã ghi file header: {output_file}")
    print(f" Tổng số file âm thanh : {len(tracks_info)}")
    print(f" Tổng dung lượng bộ nhớ: {total_bytes:,} bytes (~{total_bytes / 1024:.1f} KB)")
    print("=" * 65)
    return True

def main():
    parser = argparse.ArgumentParser(description="Tổng hợp file WAV thành file header C++ audio_data.h")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_INPUT_DIR, help="Thư mục chứa các file .wav")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_FILE, help="Đường dẫn file header .h đầu ra")
    args = parser.parse_args()

    print("=" * 65)
    print(" CÔNG CỤ TỔNG HỢP FILE WAV -> AUDIO_DATA.H")
    print(f" Thư mục nguồn: {args.input}")
    print(f" File xuất ra : {args.output}")
    print("=" * 65)

    generate_header(args.input, args.output)

if __name__ == "__main__":
    main()
