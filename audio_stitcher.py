import argparse
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_nonsilent
from tqdm import tqdm
import os

def validate_threshold(value):
    """验证静音阈值有效性"""
    value = int(value)
    if not -50 <= value <= -20:
        raise argparse.ArgumentTypeError("静音阈值必须在-50到-20之间")
    return value

def validate_silence_duration(value):
    """验证静音时长有效性"""
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("静音时长必须大于0")
    return value

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="音频自动分割处理工具",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # 必需参数
    parser.add_argument("input", 
                      help="输入音频文件路径")
    parser.add_argument("-o", "--output",
                      required=True,
                      help="输出文件路径（必须指定）")

    # 处理参数
    parser.add_argument("-t", "--threshold",
                      type=validate_threshold,
                      default=-40,
                      help="静音检测阈值（dBFS，越小越敏感）")
    parser.add_argument("-d", "--min-silence-duration",
                      type=validate_silence_duration,
                      default=500,
                      metavar="MILLISECONDS",
                      help="视为有效停顿的最小静音时长（毫秒）")
    
    # 可选参数
    parser.add_argument("--no-progress",
                      action="store_true",
                      help="禁用进度条显示")
    parser.add_argument("-f", "--force",
                      action="store_true",
                      help="强制覆盖已存在的输出文件")

    return parser.parse_args()

def trim_global_silence(audio, silence_thresh, min_silence_len, show_progress=True):
    """全局静音修剪（带进度控制）"""
    progress = tqdm(total=4, desc="全局静音处理", disable=not show_progress)
    
    left, right = audio.split_to_mono()
    progress.update(1)
    
    def get_active_ranges(channel):
        nonsilent = detect_nonsilent(channel, 
                                   min_silence_len=min_silence_len,
                                   silence_thresh=silence_thresh)
        return nonsilent[0][0], nonsilent[-1][1] if nonsilent else (0, 0)
    
    left_start, left_end = get_active_ranges(left)
    right_start, right_end = get_active_ranges(right)
    progress.update(1)
    
    global_start = min(left_start, right_start)
    global_end = max(left_end, right_end)
    progress.update(1)
    
    trimmed = audio[global_start:global_end]
    progress.update(1)
    progress.close()
    return trimmed

def process_audio(args):
    """主处理流程"""
    # 验证输出文件
    if os.path.exists(args.output) and not args.force:
        raise FileExistsError(f"输出文件已存在：{args.output}（使用-f强制覆盖）")
    
    # 加载音频
    audio = AudioSegment.from_file(args.input)
    
    # 全局修剪
    trimmed_audio = trim_global_silence(audio, 
                                      args.threshold,
                                      args.min_silence_duration,
                                      not args.no_progress)
    
    # 分割处理
    left, right = trimmed_audio.split_to_mono()
    
    def process_channel(channel, name):
        chunks = split_on_silence(
            channel,
            min_silence_len=args.min_silence_duration,
            silence_thresh=args.threshold,
            keep_silence=0
        )
        if not args.no_progress:
            print(f"{name}声道分割完成，共{len(chunks)}段")
        return chunks
    
    left_chunks = process_channel(left, "左")
    right_chunks = process_channel(right, "右")
    
    # 合成输出
    output = AudioSegment.empty()
    total = max(len(left_chunks), len(right_chunks))
    iterable = range(total)
    
    if not args.no_progress:
        iterable = tqdm(iterable, desc="合成处理", unit="段")
    
    for i in iterable:
        if i < len(left_chunks):
            output += left_chunks[i].pan(-1)
        if i < len(right_chunks):
            output += right_chunks[i].pan(1)
    
    # 导出结果
    output.export(args.output, format="wav")
    print(f"\n处理完成！输出文件已保存至：{args.output}")

if __name__ == "__main__":
    try:
        args = parse_arguments()
        process_audio(args)
    except Exception as e:
        print(f"\n错误发生：{str(e)}")
        exit(1)