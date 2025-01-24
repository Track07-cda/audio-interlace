# Audio Interlace

[中文 README](README_CN.md)

A sophisticated audio processing tool for interlacing stereo channels with intelligent silence-based segmentation and crossfading.

## Features

- 🎚️ Independent channel processing
- 🔇 Adaptive silence detection
- ✂️ Context-aware audio segmentation
- 🔀 Intelligent channel interlacing
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

| Segment | Start   | End     | Duration |
|---------|---------|---------|----------|
| L1      | 00:00.0 | 00:12.5 | 12.5s    |
| L2      | 00:12.5 | 00:25.8 | 13.3s    |
| L3      | 00:25.8 | 00:38.2 | 12.4s    |

#### Right Channel Segments

| Segment | Start   | End     | Duration |
|---------|---------|---------|----------|
| R1      | 00:00.0 | 00:15.2 | 15.2s    |
| R2      | 00:15.2 | 00:32.0 | 16.8s    |

### 2. Interlaced Output Sequence

| Order | Channel | Segment | Time Span      | Faded Duration |
|-------|---------|---------|----------------|----------------|
| 1     | Left    | L1      | 00:00-00:12.5  | 12.5s (+300ms) |
| 2     | Right   | R1      | 00:00-00:15.2  | 15.2s (+300ms) |
| 3     | Left    | L2      | 00:12.5-00:25.8| 13.3s (+300ms) |
| 4     | Right   | R2      | 00:15.2-00:32.0| 16.8s (+300ms) |
| 5     | Left    | L3      | 00:25.8-00:38.2| 12.4s (+300ms) |

**Key Characteristics**:

- Total Output Duration: 70.2s (2× original 35.1s)
- Automatic crossfade between segments
- Unbalanced channels handled through sequential alternation
- Time references maintain original audio context

## Parameter Reference

| Option            | Default | Description                          |
|-------------------|---------|--------------------------------------|
| `-i/--input`      | Required| Source WAV file path                 |
| `-o/--output`     | Required| Target WAV output path               |
| `--fade`          | 500     | Crossfade duration (milliseconds)    |
| `--min-segment`   | 1.0     | Minimum valid segment (seconds)      |
| `--min-silence`   | 0.5     | Silence detection threshold (seconds)|
| `--noise-level`   | -30     | Noise floor for silence (dB)         |
| `--temp-dir`      | temp    | Custom temporary directory           |
| `--keep-temp`     | False   | Retain intermediate files            |

## Processing Pipeline

1. **Channel Isolation**  
   - Split stereo WAV input to discrete mono tracks
   - Preserve original PCM characteristics

2. **Adaptive Segmentation**  
   - Detect natural pause points
   - Apply minimum duration constraints
   - Generate segment metadata

3. **Segment Processing**  
   - Apply configured fade effects
   - Maintain original WAV parameters
   - Store processed segments

4. **Interleaving Composition**  
   - Alternate channel segments (L-R-L-R pattern)
   - Handle unbalanced segment counts
   - Generate final concatenation list

5. **Output Generation**  
   - Assemble final WAV output using FFmpeg
   - Clean temporary resources

## License

MIT License - See [LICENSE](LICENSE) for full text
