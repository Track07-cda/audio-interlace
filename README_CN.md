# 音频交错处理器

专业的立体声音频处理工具，支持基于静音检测的智能分段和交叉淡入淡出处理。

## 功能特性

- ⏱️ 时间轴排序合并
- 🎚️ 独立声道处理
- 🔇 自适应静音检测
- ✂️ 上下文感知音频分段
- 🎛️ 原生WAV格式保持
- ⏳ 处理进度可视化
- 🧹 自动资源清理

## 系统要求

- Python 3.8+
- FFmpeg 4.3+
- 存储空间：输入文件大小的3倍（用于临时处理）

## 安装说明

1. 克隆仓库：

    ```bash
    git clone https://github.com/Track07-cda/audio-interlace.git
    cd audio-interlace
    ```

2. 安装依赖项：

    ```bash
    pip install -r requirements.txt
    ```

3. 验证FFmpeg安装：

    ```bash
    ffmpeg -version
    ```

## 基础用法

### 命令模板

```bash
python audio_interlace.py -i 输入文件.wav -o 输出文件.wav [选项]
```

### 示例执行

```bash
python audio_interlace.py \
  -i 输入音频.wav \
  -o 处理结果.wav \
  --fade 300 \
  --min-segment 0.8 \
  --min-silence 0.4
```

## 格式支持说明

**FLAC输出注意事项**：

- 自动处理浮点格式转换（32-bit浮点 → 32-bit整型）
- 支持原生整型格式（16/24/32-bit）
- 要求FFmpeg 4.3+ 并启用FLAC编码支持

**验证FFmpeg配置**：

```bash
ffmpeg -encoders | grep flac
# 应显示：FLAC (flac) 
```

## 处理流程示例

### 1. 声道分段结果

#### 左声道片段

| 片段 | 起始时间 | 结束时间 | 时长   | 原始时间位置       |
|-----|----------|----------|--------|--------------------|
| L1  | 00:00.0  | 00:12.5  | 12.5秒 | 00:00.0-00:12.5   |
| L2  | 00:15.0  | 00:25.8  | 10.8秒 | 00:15.0-00:25.8   |
| L3  | 00:28.0  | 00:38.2  | 10.2秒 | 00:28.0-00:38.2   |

#### 右声道片段

| 片段 | 起始时间 | 结束时间 | 时长   | 原始时间位置       |
|-----|----------|----------|--------|--------------------|
| R1  | 00:05.0  | 00:18.2  | 13.2秒 | 00:05.0-00:18.2   |
| R2  | 00:20.5  | 00:35.0  | 14.5秒 | 00:20.5-00:35.0   |

### 2. 时间轴合并结果

| 顺序 | 声道  | 片段 | 时间范围        | 全局时间轴位置      |
|-----|-------|-----|-----------------|---------------------|
| 1   | 左声道 | L1  | 00:00-00:12.5   | 00:00.0-00:12.5    |
| 2   | 右声道 | R1  | 00:05-00:18.2   | 00:12.5-00:25.7    |
| 3   | 左声道 | L2  | 00:15-00:25.8   | 00:25.7-00:36.5    |
| 4   | 右声道 | R2  | 00:20.5-00:35.0 | 00:36.5-00:51.0    |
| 5   | 左声道 | L3  | 00:28-00:38.2   | 00:51.0-01:01.2    |

**核心特性**：

- 智能时间轴排序：按全局起始时间合并
- 自动过渡处理：重叠区域添加淡入淡出
- 跨声道连续性：保留原始时间上下文
- 总输出时长：121.2秒（组合时间轴长度）

## 参数参考

| 选项              | 默认值  | 描述                       |
|-------------------|---------|----------------------------|
| `-i/--input`      | 必填    | 输入WAV文件路径            |
| `-o/--output`     | 必填    | 输出WAV文件路径            |
| `--fade`          | 500     | 淡入淡出时长（毫秒）       |
| `--min-segment`   | 1.0     | 最小有效片段时长（秒）     |
| `--min-silence`   | 0.5     | 静音检测阈值时长（秒）     |
| `--noise-level`   | -30     | 静音噪声阈值（dB）         |
| `--temp-dir`      | temp    | 自定义临时目录路径         |
| `--keep-temp`     | False   | 保留中间处理文件           |

## 处理流程

1. **声道分离**  
   - 将立体声输入分离为独立单声道
   - 保持原始PCM参数

2. **自适应分段**  
   - 检测自然停顿点
   - 应用最小时长限制
   - 生成带时间戳的片段元数据

3. **全局时间排序**  

   ```mermaid
   graph TD
       A[左声道片段] --> C[时间轴排序池]
       B[右声道片段] --> C
       C --> D{时间排序}
       D --> E[创建合并后的时间线]
       E --> F[应用交叉淡化]
   ```

4. **最终合成**  
   - 按时间顺序拼接所有片段
   - 自动处理片段衔接过渡
   - 生成标准WAV输出文件

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

## 致谢

本项目开发过程中使用了深度求索（DeepSeek-R1）大模型进行技术方案设计和代码优化。  
[深度求索人工智能研究](https://www.deepseek.com)
