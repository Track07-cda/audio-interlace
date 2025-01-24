import os
import argparse
import subprocess
import json
import shutil
from itertools import zip_longest
from math import isclose

def parse_args():
    parser = argparse.ArgumentParser(description='Audio Splitter and Merger')
    parser.add_argument('-i', '--input', required=True, help='Input audio file')
    parser.add_argument('-o', '--output', required=True, help='Output audio file')
    parser.add_argument('--fade', type=int, default=500, help='Fade duration in milliseconds')
    parser.add_argument('--min-segment', type=float, default=1.0, 
                      help='Minimum segment duration in seconds')
    parser.add_argument('--min-silence', type=float, default=0.5,
                      help='Minimum silence duration to detect as split point (seconds)')
    parser.add_argument('--noise-level', type=float, default=-30.0,
                      help='Noise level threshold for silence detection in dB')
    parser.add_argument('--temp-dir', default='temp', help='Temporary directory')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files')
    return parser.parse_args()

def get_duration(input_file):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'json', input_file]
    result = subprocess.run(cmd, stdout=subprocess.PIPE)
    return float(json.loads(result.stdout)['format']['duration'])

def detect_silence(input_file, min_silence, noise_level):
    cmd = [
        'ffmpeg', '-i', input_file, '-af',
        f'silencedetect=noise={noise_level}dB:d={min_silence}',
        '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    
    silences = []
    for line in result.stderr.split('\n'):
        if 'silence_start' in line:
            start = float(line.split('silence_start: ')[1].split()[0])
        if 'silence_end' in line:
            end = float(line.split('silence_end: ')[1].split()[0])
            silences.append((start, end))
    return silences

def split_and_fade(input_file, output_dir, segments, fade_duration, temp_dir, channel):
    fade_in = fade_duration / 1000
    output_files = []
    
    for idx, (start, end) in enumerate(segments):
        output_file = os.path.abspath(os.path.join(output_dir, f'segment_{idx}.wav'))
        duration = end - start
        
        fade_out_start = max(0, duration - fade_in)
        fade_out_duration = min(fade_in, duration)
        
        # 修正pan滤镜语法
        if channel == "left":
            pan_filter = "pan=stereo|c0=1*c0|c1=0*c0"  # 左声道保留，右声道静音
        else:
            pan_filter = "pan=stereo|c0=0*c0|c1=1*c0"  # 右声道保留，左声道静音
        
        filter_chain = (
            f"afade=in:st=0:d={fade_in},"
            f"afade=out:st={fade_out_start}:d={fade_out_duration},"
            f"{pan_filter}"
        )
        
        cmd = [
            'ffmpeg', '-y', '-ss', str(start), '-to', str(end),
            '-i', input_file, 
            '-filter_complex', filter_chain,  # 使用-filter_complex参数
            '-ac', '2',
            '-loglevel', 'error', output_file
        ]
        subprocess.run(cmd, check=True)
        output_files.append(output_file)
    
    return output_files

def process_channel(input_file, args, channel, duration):
    silences = detect_silence(input_file, args.min_silence, args.noise_level)
    
    split_points = []
    for start, end in silences:
        split_points.append((start + end) / 2)
    
    segments = []
    prev = 0.0
    for point in split_points:
        segments.append((prev, point))
        prev = point
    segments.append((prev, duration))
    
    # Merge short segments
    merged = []
    current_start, current_end = segments[0]
    for seg in segments[1:]:
        if (seg[1] - current_start) < args.min_segment:
            current_end = seg[1]
        else:
            merged.append((current_start, current_end))
            current_start, current_end = seg
    merged.append((current_start, current_end))
    
    return split_and_fade(input_file, os.path.join(args.temp_dir, channel),
                         merged, args.fade, args.temp_dir, channel)

def main():
    args = parse_args()
    
    # Setup temporary directories
    os.makedirs(args.temp_dir, exist_ok=True)
    for d in ['left', 'right', 'segments']:
        os.makedirs(os.path.join(args.temp_dir, d), exist_ok=True)

    try:
        # Split channels
        left_file = os.path.join(args.temp_dir, 'left.wav')
        right_file = os.path.join(args.temp_dir, 'right.wav')
        subprocess.run([
            'ffmpeg', '-y', '-i', args.input,
            '-filter_complex', 'channelsplit=channel_layout=stereo[left][right]',
            '-map', '[left]', left_file,
            '-map', '[right]', right_file,
            '-loglevel', 'error'
        ], check=True)

        # Process channels
        duration = get_duration(args.input)
        left_segments = process_channel(left_file, args, 'left', duration)
        right_segments = process_channel(right_file, args, 'right', duration)

        # Interleave segments
        interleaved = []
        for l, r in zip_longest(left_segments, right_segments):
            if l: interleaved.append(l)
            if r: interleaved.append(r)

        # 创建concat列表时统一使用Linux风格路径
        concat_list = os.path.join(args.temp_dir, 'concat.txt')
        with open(concat_list, 'w') as f:
            for seg in interleaved:
                # 转换为Linux风格路径并确保引号包裹
                linux_path = seg.replace('\\', '/')
                f.write(f"file '{linux_path}'\n")

        # 合并时使用绝对路径执行
        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_list, '-c', 'copy', 
            os.path.abspath(args.output),  # 输出文件也使用绝对路径
            '-loglevel', 'error'
        ], check=True)

    finally:
        if not args.keep_temp:
            shutil.rmtree(args.temp_dir)


if __name__ == '__main__':
    main()