#!/bin/zsh
# Mix a music bed under the dialogue with sidechain ducking; optionally end the video early with a fade.
# Usage: video/mix_music.sh in.mp4 music.mp3 out.mp4 [end_seconds] [music_db=-12]
set -e
IN="$1"; MUS="$2"; OUT="$3"; END="${4:-}"; DB="${5:--12}"
if [ -z "$END" ]; then END=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN"); fi
FADE_AT=$(python3 -c "print(max(0,$END-0.6))"); MFADE=$(python3 -c "print(max(0,$END-1.0))")
ffmpeg -y -loglevel error -i "$IN" -i "$MUS" -filter_complex "
[0:v]trim=0:$END,setpts=PTS-STARTPTS,fade=t=out:st=$FADE_AT:d=0.6[vout];
[0:a]atrim=0:$END,asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,afade=t=out:st=$FADE_AT:d=0.6,asplit=2[dlg][key];
[1:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:$END,volume=${DB}dB,afade=t=in:st=0:d=1.5,afade=t=out:st=$MFADE:d=1.0[mus];
[mus][key]sidechaincompress=threshold=0.02:ratio=5:attack=40:release=700:makeup=1[ducked];
[dlg][ducked]amix=inputs=2:normalize=0:duration=first[aout]" \
 -map "[vout]" -map "[aout]" -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -movflags +faststart "$OUT"
echo "wrote $OUT"
