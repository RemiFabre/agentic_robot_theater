#!/bin/zsh
# Two music cues under the dialogue: cue A from 0 until PIVOT (sharp 0.25 s fade), silence gap, cue B from B_START (offset B_OFF inside the file) to the end.
# Usage: mix_two_cues.sh in.mp4 cueA.mp3 cueB.mp3 out.mp4 PIVOT B_START B_OFF [end_seconds] [music_db=-12] [b_db=music_db]
set -e
IN="$1"; A="$2"; B="$3"; OUT="$4"; PIV="$5"; BST="$6"; BOFF="$7"; END="${8:-}"; DB="${9:--12}"; BDB="${10:-$DB}"; THR="${THR:-0.02}"
if [ -z "$END" ]; then END=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN"); fi
FADE_AT=$(python3 -c "print(max(0,$END-0.6))"); MFADE=$(python3 -c "print(max(0,$END-1.0))")
AFADE=$(python3 -c "print($PIV-0.25)"); BDELAY=$(python3 -c "print(int($BST*1000))")
ffmpeg -y -loglevel error -i "$IN" -i "$A" -ss "$BOFF" -i "$B" -filter_complex "
[0:v]trim=0:$END,setpts=PTS-STARTPTS,fade=t=out:st=$FADE_AT:d=0.6[vout];
[0:a]atrim=0:$END,asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,afade=t=out:st=$FADE_AT:d=0.6,asplit=2[dlg][key];
[1:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:$PIV,volume=${DB}dB,afade=t=in:st=0:d=1.5,afade=t=out:st=$AFADE:d=0.25,apad=whole_dur=${END}[ma];
[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=${BDB}dB,afade=t=in:st=0:d=0.12,adelay=${BDELAY}|${BDELAY},atrim=0:$END,afade=t=out:st=$MFADE:d=1.0[mb];
[ma][mb]amix=inputs=2:normalize=0:duration=first[mus];
[mus][key]sidechaincompress=threshold=${THR}:ratio=5:attack=40:release=700:makeup=1[ducked];
[dlg][ducked]amix=inputs=2:normalize=0:duration=first[aout]" \
 -map "[vout]" -map "[aout]" -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -movflags +faststart "$OUT"
echo "wrote $OUT"
