# Audio Interlace

[中文 README](README_CN.md)

A sophisticated audio processing tool for timeline-based merging of stereo channels with intelligent segmentation.

## Features

- ⏱️ Timeline-sorted merging
- 🎚️ Independent channel processing
- 🔇 Adaptive silence detection
- ✂️ Context-aware audio segmentation
- 🎛️ Native WAV format preservation
- ⏳ Processing progress visualization
- 🧹 Automatic resource cleanup

## Requirements

- Python 3.8+
- FFmpeg 4.3+
- Storage: 3× input file size (for temporary processing)

## Installation

1. Clone repository:

    ```bash
    git clone https://github.com/Track07-cda/audio-interlace.git
    cd audio-interlace
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Verify FFmpeg installation:

    ```bash
    ffmpeg -version
    ```

## Basic Usage

### Command Template

```bash
python audio_interlace.py -i INPUT.wav -o OUTPUT.wav [OPTIONS]
```

### Example Execution

```bash
python audio_interlace.py \
  -i input_audio.wav \
  -o processed_output.wav \
  --fade 300 \
  --min-segment 0.8 \
  --min-silence 0.4
```

## Format Support Notice

**Currently supports WAV format exclusively**  

- Input files must be standard WAV format
- Output will be generated as WAV file
- Preserves original PCM characteristics:
  - Sample rate (44.1k-384kHz)
  - Bit depth (16/24/32-bit)
  - Channel configuration

## Workflow Example

### 1. Channel Segmentation Results

#### Left Channel Segments

| Segment | Start   | End     | Duration | Original Position |
|---------|---------|---------|----------|-------------------|
| L1      | 00:00.0 | 00:12.5 | 12.5s    | 00:00-00:12.5     |
| L2      | 00:15.0 | 00:25.8 | 10.8s    | 00:15-00:25.8     |
| L3      | 00:28.0 | 00:38.2 | 10.2s    | 00:28-00:38.2     |

#### Right Channel Segments

| Segment | Start   | End     | Duration | Original Position |
|---------|---------|---------|----------|-------------------|
| R1      | 00:05.0 | 00:18.2 | 13.2s    | 00:05-00:18.2     |
| R2      | 00:20.5 | 00:35.0 | 14.5s    | 00:20.5-00:35.0   |

### 2. Timeline-Merged Output Sequence

| Order | Channel | Segment | Time Span      | Global Timeline Position |
|-------|---------|---------|----------------|--------------------------|
| 1     | Left    | L1      | 00:00-00:12.5  | 00:00.0-00:12.5          |
| 2     | Right   | R1      | 00:05-00:18.2  | 00:12.5-00:25.7          |
| 3     | Left    | L2      | 00:15-00:25.8  | 00:25.7-00:36.5          |
| 4     | Right   | R2      | 00:20.5-00:35.0| 00:36.5-00:51.0          |
| 5     | Left    | L3      | 00:28-00:38.2  | 00:51.0-01:01.2          |

**Key Characteristics**:

- Chronological merging preserves original temporal context
- Automatic gap filling with crossfades
- Total duration: 121.2s (Combined timeline length)
- Smart overlap resolution using fade effects

## Parameter Reference

| Option            | Default | Description                           |
|-------------------|---------|---------------------------------------|
| `-i/--input`      | Required| Source WAV file path                  |
| `-o/--output`     | Required| Target WAV output path                |
| `--fade`          | 500     | Crossfade duration (milliseconds)     |
| `--min-segment`   | 1.0     | Minimum valid segment length (seconds)|
| `--min-silence`   | 0.5     | Silence detection threshold (seconds) |
| `--noise-level`   | -30     | Noise floor for silence (dB)          |
| `--temp-dir`      | temp    | Custom temporary directory            |
| `--keep-temp`     | False   | Retain intermediate files             |

## Processing Pipeline

1. **Channel Isolation**  
   - Split stereo input to discrete mono tracks
   - Preserve original PCM characteristics

2. **Adaptive Segmentation**  
   - Detect natural pause points
   - Generate timestamped segments

3. **Global Timeline Assembly**  

   ```mermaid
   graph TD
       A[Left Segments] --> C[Time-Ordered Pool]
       B[Right Segments] --> C
       C --> D{Sort by Start Time}
       D --> E[Create Merged Timeline]
       E --> F[Apply Crossfades]
   ```

4. **Final Output Generation**  
   - Render timeline with original audio quality
   - Maintain WAV specifications

## License

MIT License - See [LICENSE](LICENSE) for full text

## Acknowledgments

This project was developed with the assistance of the DeepSeek-R1 large language model for technical solution design and code optimization.  
[DeepSeek Artificial Intelligence Research](https://www.deepseek.com)
