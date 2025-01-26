import os
import argparse
import subprocess
import json
import shutil
import logging
from tqdm import tqdm


class AudioProcessor:
    """Core audio processing class for channel splitting, silence detection and segment processing"""

    ENCODER_MAPPING = {
        'flt': ('pcm_f32le', 32),    # 32-bit floating-point little-endian
        'fltp': ('pcm_f32le', 32),   # Planar 32-bit float
        's32': ('pcm_s32le', 32),    # 32-bit signed integer little-endian
        's16': ('pcm_s16le', 16),    # 16-bit signed integer little-endian
        's16p': ('pcm_s16le', 16),   # Planar 16-bit signed integer
        'u8': ('pcm_u8', 8),         # 8-bit unsigned integer
        'u8p': ('pcm_u8', 8),        # Planar 8-bit unsigned
        'flac_s32': ('s32', 32),     # FLAC compatible 32-bit integer
        'flac_s16': ('s16', 16)      # FLAC compatible 16-bit integer
    }

    def __init__(self, args):
        """Initialize audio processor with configuration parameters
        
        Args:
            args: Command line arguments parsed by argparse
        """
        self.args = args
        self.logger = self._setup_logger()
        self.temp_dir = os.path.abspath(args.temp_dir)
        self.audio_params = self._get_audio_params(args.input)
        self.output_format = os.path.splitext(args.output)[1].lower().lstrip('.')
        if self.output_format not in ['wav', 'flac']:
            raise ValueError("Only support WAV/FLAC output formats")
        self._prepare_directories()
        self.logger.info(f"Input audio params: {self.audio_params}")

    def _setup_logger(self):
        """Initialize and configure logger instance
        
        Returns:
            Configured logger object
        """
        logger = logging.getLogger('AudioProcessor')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(handler)
        return logger

    def _prepare_directories(self):
        """Create temporary directories structure for processing"""
        os.makedirs(self.temp_dir, exist_ok=True)
        for channel in ['left', 'right']:
            os.makedirs(os.path.join(self.temp_dir, channel), exist_ok=True)

    def process(self):
        """Main processing workflow controller"""
        try:
            left, right = self._split_channels()
            left_segments = self._process_channel(left, 'left')
            right_segments = self._process_channel(right, 'right')
            self._merge_segments(left_segments, right_segments)
        finally:
            if not self.args.keep_temp:
                self._cleanup()

    def _split_channels(self):
        """Split stereo input into separate mono channel files
        
        Returns:
            tuple: (left_channel_path, right_channel_path)
        """
        self.logger.info("Splitting stereo channels...")
        left_path = os.path.join(self.temp_dir, 'left.wav')
        right_path = os.path.join(self.temp_dir, 'right.wav')

        subprocess.run([
            'ffmpeg', '-y', '-i', self.args.input,
            '-filter_complex', 'channelsplit=channel_layout=stereo[left][right]',
            '-map', '[left]', left_path,
            '-map', '[right]', right_path,
            '-loglevel', 'error'
        ], check=True)
        return left_path, right_path

    def _process_channel(self, input_file, channel):
        """Process single audio channel through full pipeline
        
        Args:
            input_file: Path to input audio file
            channel: Channel identifier ('left' or 'right')
        
        Returns:
            list: Processed segment metadata
        """
        self.logger.info(f"Processing {channel} channel...")
        duration = self._get_duration(input_file)
        silences = self._detect_silence(input_file)
        segments = self._calculate_segments(silences, duration)
        return self._split_and_fade(input_file, segments, channel)

    def _get_duration(self, input_file):
        """Get audio duration in seconds using FFprobe
        
        Args:
            input_file: Path to audio file
        
        Returns:
            float: Duration in seconds
        """
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json', input_file
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE)
        return float(json.loads(result.stdout)['format']['duration'])

    def _detect_silence(self, input_file):
        """Detect silence intervals using FFmpeg's silencedetect filter
        
        Args:
            input_file: Path to audio file
        
        Returns:
            list: Silence intervals as (start, end) tuples
        """
        self.logger.info(f"Detecting silence in {os.path.basename(input_file)}...")
        cmd = [
            'ffmpeg', '-i', input_file, '-af',
            f'silencedetect=noise={self.args.noise_level}dB:d={self.args.min_silence}',
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        return self._parse_silence(result.stderr)

    def _parse_silence(self, output):
        """Parse FFmpeg's silencedetect output into time intervals
        
        Args:
            output: FFmpeg's stderr output
        
        Returns:
            list: Silence intervals as (start, end) tuples
        """
        silences = []
        current_silence = {}
        for line in output.split('\n'):
            if 'silence_start' in line:
                current_silence['start'] = float(line.split('silence_start: ')[1].split()[0])
            if 'silence_end' in line:
                current_silence['end'] = float(line.split('silence_end: ')[1].split()[0])
                silences.append((current_silence['start'], current_silence['end']))
                current_silence = {}
        return silences

    def _calculate_segments(self, silences, duration):
        """Calculate valid audio segments between silence intervals
        
        Args:
            silences: List of silence intervals
            duration: Total audio duration
        
        Returns:
            list: Valid audio segments as (start, end) tuples
        """
        split_points = [(start + end) / 2 for start, end in silences]
        segments = []
        prev_point = 0.0
        
        for point in split_points:
            segments.append((prev_point, point))
            prev_point = point
        segments.append((prev_point, duration))
        
        return self._merge_short_segments(segments)

    def _merge_short_segments(self, segments):
        """Merge segments shorter than minimum allowed duration
        
        Args:
            segments: List of audio segments
        
        Returns:
            list: Merged segments meeting duration requirements
        """
        merged = []
        current_start, current_end = segments[0]
        
        for seg in segments[1:]:
            if (seg[1] - current_start) < self.args.min_segment:
                current_end = seg[1]
            else:
                merged.append((current_start, current_end))
                current_start, current_end = seg
        merged.append((current_start, current_end))
        
        return merged

    def _split_and_fade(self, input_file, segments, channel):
        """Split audio into segments with crossfade effects
        
        Args:
            input_file: Path to input audio
            segments: List of segments to process
            channel: Channel identifier
        
        Returns:
            list: Metadata for processed segments
        """
        output_dir = os.path.join(self.temp_dir, channel)
        fade_duration = self.args.fade / 1000  # Convert ms to seconds
        outputs = []

        with tqdm(segments, desc=f"Processing {channel} segments") as pbar:
            for idx, (start, end) in enumerate(pbar):
                output = self._process_segment(
                    input_file, output_dir, idx,
                    start, end, fade_duration, channel
                )
                outputs.append({
                    'start': start,
                    'end': end,
                    'path': output,
                    'channel': channel
                })
                pbar.set_postfix({"current": f"{end:.2f}s"})
        return outputs

    def _get_audio_params(self, input_file):
        """Extract audio format parameters using FFprobe
        
        Args:
            input_file: Path to audio file
        
        Returns:
            dict: Audio parameters including sample rate, format, etc.
        """
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=sample_rate,sample_fmt,channels,bits_per_sample',
            '-of', 'json', input_file
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
        info = json.loads(result.stdout)['streams'][0]
        
        return {
            'sample_rate': int(info['sample_rate']),
            'sample_fmt': info['sample_fmt'],
            'bits_per_sample': int(info.get('bits_per_sample', 16)),
            'channels': int(info['channels'])
        }

    def _process_segment(self, input_file, output_dir, idx, start, end, fade_duration, channel):
        """Process individual audio segment with fade effects
        
        Args:
            input_file: Source audio file
            output_dir: Directory for processed segments
            idx: Segment index
            start: Segment start time
            end: Segment end time
            fade_duration: Fade duration in seconds
            channel: Channel identifier
        
        Returns:
            str: Path to processed segment file
        """
        output_file = os.path.abspath(os.path.join(output_dir, f'segment_{idx}.wav'))
        duration = end - start
        fade_out_start = max(0, duration - fade_duration)

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
            '-ar', str(self.audio_params['sample_rate']),
            '-sample_fmt', self.audio_params['sample_fmt'],
            '-c:a', self._get_encoder(for_final=False),
            '-loglevel', 'error',
            output_file
        ], check=True)
        return output_file

    def _get_encoder(self, for_final=False):
        """Get appropriate audio encoder configuration
        
        Args:
            for_final: Whether to get encoder for final output
        
        Returns:
            str: Encoder name for FFmpeg
        """
        if not for_final:
            # Intermediate processing always uses WAV
            sample_fmt = self.audio_params['sample_fmt']
            if sample_fmt not in self.ENCODER_MAPPING:
                raise ValueError(f"Unsupported sample format: {sample_fmt}")
            return self.ENCODER_MAPPING[sample_fmt][0]
        
        # Final output configuration
        if self.output_format == 'flac':
            return 'flac'  # FFmpeg's FLAC encoder name
        else:
            return self._get_encoder(for_final=False)

    def _get_pan_filter(self, channel):
        """Generate FFmpeg pan filter for channel isolation
        
        Args:
            channel: Target channel ('left' or 'right')
        
        Returns:
            str: FFmpeg filter configuration
        """
        return {
            'left': 'pan=stereo|c0=1*c0|c1=0*c0',
            'right': 'pan=stereo|c0=0*c0|c1=1*c0'
        }[channel]

    def _merge_segments(self, left_segments, right_segments):
        """Merge processed segments into final output
        
        Args:
            left_segments: Processed left channel segments
            right_segments: Processed right channel segments
        """
        all_segments = left_segments + right_segments
        
        # Sort by start time, left channel first for same start time
        sorted_segments = sorted(
            all_segments,
            key=lambda x: (x['start'], x['channel'] == 'right')
        )
        
        self.logger.info("Final segment order:")
        for seg in sorted_segments:
            self.logger.info(f"{seg['channel'].upper()} {seg['start']:.2f}s-{seg['end']:.2f}s")
        
        self._generate_final_output(sorted_segments)

    def _generate_final_output(self, sorted_segments):
        """Generate final output file from sorted segments
        
        Args:
            sorted_segments: Chronologically ordered segments
        """
        concat_list = os.path.join(self.temp_dir, 'concat.txt')
        
        with open(concat_list, 'w') as f:
            for seg in sorted_segments:
                linux_path = seg['path'].replace('\\', '/')
                f.write(f"file '{linux_path}'\n")

        # Configure output parameters based on format
        output_args = []
        if self.output_format == 'flac':
            original_fmt = self.audio_params['sample_fmt']
            target_fmt = 's32' if original_fmt in ['flt', 'fltp'] else original_fmt
            
            if target_fmt != original_fmt:
                self.logger.warning(f"Converting {original_fmt} to {target_fmt} for FLAC output")
                
            output_args = [
                '-compression_level', '8',
                '-sample_fmt', target_fmt
            ]
        else:
            output_args = [
                '-sample_fmt', self.audio_params['sample_fmt']
            ]

        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'concat', 
            '-safe', '0',
            '-i', concat_list,
            '-c:a', self._get_encoder(for_final=True),
            '-ar', str(self.audio_params['sample_rate']),
            *output_args,
            os.path.abspath(self.args.output),
            '-loglevel', 'error'
        ], check=True)

    def _cleanup(self):
        """Clean up temporary processing files"""
        self.logger.info("Cleaning temporary files...")
        shutil.rmtree(self.temp_dir)


def parse_args():
    """Parse and validate command line arguments
    
    Returns:
        Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description='Stereo Audio Interlacing Processor')
    parser.add_argument('-i', '--input', required=True, help='Input audio file path')
    parser.add_argument(
        '-o', '--output', required=True,
        help='Output file path (WAV/FLAC formats supported)'
    )
    parser.add_argument(
        '--fade', type=int, default=500,
        help='Crossfade duration in milliseconds (default: 500)'
    )
    parser.add_argument(
        '--min-segment', type=float, default=1.0,
        help='Minimum valid segment duration in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--min-silence', type=float, default=0.5,
        help='Minimum silence duration for splitting (seconds, default: 0.5)'
    )
    parser.add_argument(
        '--noise-level', type=float, default=-30.0,
        help='Noise threshold for silence detection in dB (default: -30)'
    )
    parser.add_argument(
        '--temp-dir', default='temp',
        help='Temporary directory path (default: temp)'
    )
    parser.add_argument(
        '--keep-temp', action='store_true',
        help='Retain intermediate processing files'
    )
    return parser.parse_args()


if __name__ == '__main__':
    processor = AudioProcessor(parse_args())
    processor.process()
    print("Processing completed! Output file:", processor.args.output)
