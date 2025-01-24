import os
import argparse
import subprocess
import json
import shutil
import logging
from itertools import zip_longest
from tqdm import tqdm

class AudioProcessor:
    """音频处理核心类，负责声道分离、静音检测、片段处理等"""
    
    def __init__(self, args):
        self.args = args
        self.logger = self._setup_logger()
        self.temp_dir = os.path.abspath(args.temp_dir)
        self._prepare_directories()

    def _setup_logger(self):
        """配置日志记录器"""
        logger = logging.getLogger('AudioProcessor')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        return logger

    def _prepare_directories(self):
        """创建必要的临时目录"""
        os.makedirs(self.temp_dir, exist_ok=True)
        for d in ['left', 'right']:
            os.makedirs(os.path.join(self.temp_dir, d), exist_ok=True)

    def process(self):
        """主处理流程"""
        try:
            left, right = self._split_channels()
            left_segments = self._process_channel(left, 'left')
            right_segments = self._process_channel(right, 'right')
            self._merge_segments(left_segments, right_segments)
        finally:
            if not self.args.keep_temp:
                self._cleanup()

    def _split_channels(self):
        """分离左右声道"""
        self.logger.info("Splitting stereo channels...")
        left = os.path.join(self.temp_dir, 'left.wav')
        right = os.path.join(self.temp_dir, 'right.wav')

        subprocess.run([
            'ffmpeg', '-y', '-i', self.args.input,
            '-filter_complex', 'channelsplit=channel_layout=stereo[left][right]',
            '-map', '[left]', left,
            '-map', '[right]', right,
            '-loglevel', 'error'
        ], check=True)
        return left, right

    def _process_channel(self, input_file, channel):
        """处理单个声道"""
        self.logger.info(f"Processing {channel} channel...")
        duration = self._get_duration(input_file)
        silences = self._detect_silence(input_file)
        segments = self._calculate_segments(silences, duration)
        return self._split_and_fade(input_file, segments, channel)

    def _get_duration(self, input_file):
        """获取音频时长"""
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'json', input_file]
        result = subprocess.run(cmd, stdout=subprocess.PIPE)
        return float(json.loads(result.stdout)['format']['duration'])

    def _detect_silence(self, input_file):
        """检测静音区间"""
        self.logger.info(f"Detecting silence in {os.path.basename(input_file)}...")
        cmd = [
            'ffmpeg', '-i', input_file, '-af',
            f'silencedetect=noise={self.args.noise_level}dB:d={self.args.min_silence}',
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        return self._parse_silence(result.stderr)

    def _parse_silence(self, output):
        """解析静音检测输出"""
        silences = []
        for line in output.split('\n'):
            if 'silence_start' in line:
                start = float(line.split('silence_start: ')[1].split()[0])
            if 'silence_end' in line:
                end = float(line.split('silence_end: ')[1].split()[0])
                silences.append((start, end))
        return silences

    def _calculate_segments(self, silences, duration):
        """计算有效片段"""
        split_points = [(s + e) / 2 for s, e in silences]
        segments = []
        prev = 0.0
        for point in split_points:
            segments.append((prev, point))
            prev = point
        segments.append((prev, duration))
        return self._merge_short_segments(segments)

    def _merge_short_segments(self, segments):
        """合并过短片段"""
        merged = []
        current = segments[0]
        for seg in segments[1:]:
            if seg[1] - current[0] < self.args.min_segment:
                current = (current[0], seg[1])
            else:
                merged.append(current)
                current = seg
        merged.append(current)
        return merged

    def _split_and_fade(self, input_file, segments, channel):
        """分割音频并添加淡入淡出效果"""
        output_dir = os.path.join(self.temp_dir, channel)
        fade_duration = self.args.fade / 1000
        outputs = []

        with tqdm(segments, desc=f"Processing {channel} segments") as pbar:
            for idx, (start, end) in enumerate(pbar):
                output = self._process_segment(
                    input_file, output_dir, idx, 
                    start, end, fade_duration, channel
                )
                outputs.append(output)
                pbar.set_postfix({"current": f"{end:.2f}s"})
        return outputs

    def _process_segment(self, input_file, output_dir, idx, start, end, fade_duration, channel):
        """处理单个音频片段"""
        output_file = os.path.abspath(os.path.join(output_dir, f'segment_{idx}.wav'))
        duration = end - start
        fade_out_start = max(0, duration - fade_duration)

        # 构建滤镜链
        filters = [
            f"afade=in:st=0:d={fade_duration}",
            f"afade=out:st={fade_out_start}:d={fade_duration}",
            self._get_pan_filter(channel)
        ]
        filter_chain = ",".join(filters)

        subprocess.run([
            'ffmpeg', '-y',
            '-ss', str(start),
            '-to', str(end),
            '-i', input_file,
            '-filter_complex', filter_chain,
            '-ac', '2',
            '-loglevel', 'error',
            output_file
        ], check=True)
        return output_file

    def _get_pan_filter(self, channel):
        """生成声道控制滤镜"""
        return {
            'left': 'pan=stereo|c0=1*c0|c1=0*c0',
            'right': 'pan=stereo|c0=0*c0|c1=1*c0'
        }[channel]

    def _merge_segments(self, left, right):
        """合并交错片段"""
        self.logger.info("Merging final audio...")
        concat_list = self._generate_concat_list(left, right)
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0',
            '-i', concat_list,
            '-c', 'copy',
            os.path.abspath(self.args.output),
            '-loglevel', 'error'
        ], check=True)

    def _generate_concat_list(self, left, right):
        """生成合并列表文件"""
        concat_path = os.path.join(self.temp_dir, 'concat.txt')
        with open(concat_path, 'w') as f:
            for l, r in zip_longest(left, right):
                if l: f.write(f"file '{l.replace('\\', '/')}'\n")
                if r: f.write(f"file '{r.replace('\\', '/')}'\n")
        return concat_path

    def _cleanup(self):
        """清理临时文件"""
        self.logger.info("Cleaning temporary files...")
        shutil.rmtree(self.temp_dir)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='立体声音频交错处理器')
    parser.add_argument('-i', '--input', required=True, help='输入音频文件')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    parser.add_argument('--fade', type=int, default=500, 
                       help='淡入淡出时长（毫秒）')
    parser.add_argument('--min-segment', type=float, default=1.0,
                       help='最小有效片段时长（秒）')
    parser.add_argument('--min-silence', type=float, default=0.5,
                       help='静音检测阈值时长（秒）')
    parser.add_argument('--noise-level', type=float, default=-30.0,
                       help='静音检测噪声阈值（dB）')
    parser.add_argument('--temp-dir', default='temp', 
                       help='临时文件目录')
    parser.add_argument('--keep-temp', action='store_true',
                       help='保留临时文件')
    return parser.parse_args()

if __name__ == '__main__':
    processor = AudioProcessor(parse_args())
    processor.process()
    print("处理完成！输出文件：", processor.args.output)