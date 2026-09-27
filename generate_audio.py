#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Công cụ tạo file âm thanh WAV bằng Text-to-Speech (TTS) trên Windows
=============================================================================
- Sử dụng giọng đọc tích hợp sẵn của Windows (System.Speech.Synthesis)
- Xuất chuẩn âm thanh: 16000 Hz, 16-bit, Mono (Tương thích tốt với MAX98357A & ESP32)
- Hướng dẫn chạy:
    python generate_audio.py                 # Tạo toàn bộ file mẫu (manual, auto, cancel)
    python generate_audio.py "Hello World"   # Tạo file âm thanh tùy chỉnh
=============================================================================
"""

import sys
import os
import argparse
import subprocess
import base64

# Đảm bảo console Windows in tiếng Việt không bị lỗi font/mã hóa cp1252
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thư mục mặc định để chứa các file .wav
DEFAULT_AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")

# Danh sách các câu thoại mặc định của dự án AutoSteering
DEFAULT_TRACKS = {
    "manual": "Manual",
    "auto": "Auto",
    "cancel": "Cancel",
}

def generate_wav(text: str, output_path: str, sample_rate: int = 16000, voice_name: str = None) -> bool:
    """
    Sinh file WAV từ văn bản sử dụng Windows SpeechSynthesizer qua PowerShell.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Kịch bản PowerShell để tạo WAV chuẩn 16-bit PCM Mono
    voice_select = f"$synth.SelectVoice('{voice_name}')" if voice_name else ""
    
    ps_code = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
{voice_select}
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo({sample_rate}, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$synth.SetOutputToWaveFile('{os.path.abspath(output_path)}', $format)
$synth.Speak('{text}')
$synth.Dispose()
"""
    # Mã hóa Base64 UTF-16LE để tránh lỗi escape ký tự đặc biệt
    encoded_cmd = base64.b64encode(ps_code.encode("utf-16le")).decode("ascii")
    
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_cmd],
            capture_output=True,
            text=True
        )
        if res.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            # Tính thời lượng tương đối: 16000 mẫu/giây * 2 byte/mẫu = 32000 byte/giây
            duration = (file_size - 44) / (sample_rate * 2) if file_size > 44 else 0
            print(f" [OK] '{text}' -> {output_path} ({file_size:,} bytes, ~{duration:.2f}s)")
            return True
        else:
            print(f" [LỖI] Không thể tạo file cho '{text}': {res.stderr.strip()}")
            return False
    except Exception as e:
        print(f" [LỖI NGOẠI LỆ] {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Tạo file WAV giọng đọc chuẩn từ văn bản trên Windows")
    parser.add_argument("--text", "-t", type=str, help="Văn bản cần đọc (nếu chỉ tạo 1 file)")
    parser.add_argument("--name", "-n", type=str, help="Tên file đầu ra (không cần đuôi .wav)")
    parser.add_argument("--dir", "-d", type=str, default=DEFAULT_AUDIO_DIR, help="Thư mục lưu file .wav")
    parser.add_argument("--rate", "-r", type=int, default=16000, help="Tần số lấy mẫu (mặc định 16000 Hz)")
    args = parser.parse_args()

    print("=" * 65)
    print(" CÔNG CỤ TỰ ĐỘNG TẠO FILE ÂM THANH WAV (TEXT-TO-SPEECH)")
    print(f" Thư mục đích: {args.dir}")
    print(f" Tần số mẫu : {args.rate} Hz (16-bit Mono)")
    print("=" * 65)

    if args.text:
        filename = args.name if args.name else "speech"
        if not filename.endswith(".wav"):
            filename += ".wav"
        output_path = os.path.join(args.dir, filename)
        generate_wav(args.text, output_path, sample_rate=args.rate)
    else:
        print(f"Đang sinh {len(DEFAULT_TRACKS)} file âm thanh mặc định...")
        success_count = 0
        for name, text in DEFAULT_TRACKS.items():
            output_path = os.path.join(args.dir, f"{name}.wav")
            if generate_wav(text, output_path, sample_rate=args.rate):
                success_count += 1
        print("-" * 65)
        print(f"Hoàn thành! Đã tạo thành công {success_count}/{len(DEFAULT_TRACKS)} file.")
        print(f"Các file đã được lưu tại: {args.dir}")

if __name__ == "__main__":
    main()
