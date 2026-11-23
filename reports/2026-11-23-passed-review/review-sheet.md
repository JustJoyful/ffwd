# Review sheet: 50 random passed outputs

For each: does the output do what the **request** asks? Fill `verdict` (ok / problem), `problem` (what is wrong) and `notes` in `review-sheet.csv`.

## 1. `ti-a30fc7c331-verbo` (test-iid)
**Request:** so I recorded this clip and I need to make this video silent and compress it to under 3 MB and crop it to a 1080x1080 square
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Sound: removed | File size: at most 3 MB
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: removed | File size: at most 3 MB
**Command (1 run(s)):** `ffmpeg -i {in:tos_base} -vf crop=800:800,scale=1080:1080 -c:v libx264 -crf 28 -preset veryfast -pix_fmt yuv420p -an {out:out1}`
**Output:** 10.75 s; 1080x1080 h264 24.0 fps; 1.74 MB; mp4; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-a30fc7c331-verbo/run1/out/out1.mp4`

## 2. `ti-0eaecbb45e-sympt` (test-iid)
**Request:** this video is upside down, fix it, and cut it down to the final 4 seconds
**Gold spec means:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture turned upside down (180 degrees) | Start at 0:06 and keep the rest
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture turned upside down (180 degrees) | Frame rate: 25 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:06 to 0:10
**Command (1 run(s)):** `ffmpeg -ss 6 -i {in:h264_25fps_720p} -t 4 -vf vflip,hflip -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 4.00 s; 1280x720 h264 25.0 fps; 1.25 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-0eaecbb45e-sympt/run1/out/out1.mp4`

## 3. `tp-0293962bea-indir` (test-phrasing)
**Request:** before I send this to a friend, rotate this video 90 degrees clockwise
**Gold spec means:** Result: a video (MP4) | Picture size: 800 x 1920 pixels | Rotation: picture turned 90 degrees to the right (clockwise)
**Model said:** Result: a video | Picture size: 800 x 1920 pixels | Rotation: picture turned 90 degrees to the right (clockwise) | Video codec: H.264 | Sound: kept | Audio codec: AAC
**Command (1 run(s)):** `ffmpeg -i {in:tos_quiet} -vf transpose=1 -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 10.75 s; 800x1920 h264 24.0 fps; 9.59 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-0293962bea-indir/run1/out/out1.mp4`

## 4. `tc-3a501a2937-sympt` (test-compositional)
**Request:** the first 2 seconds of this video are junk, get rid of them, and turn it into a GIF, 240 pixels wide
**Gold spec means:** Result: a GIF (GIF) | Picture width: 240 pixels | Start at 0:02 and keep the rest
**Model said:** Result: a GIF | Picture size: 240 x 135 pixels | Keep from 0:02 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 2 -i {in:h264_noisy} -vf scale=240:-2 -an {out:out1}`
**Output:** 2.01 s; 240x136 gif 30.0 fps; 0.17 MB; gif; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-3a501a2937-sympt/run1/out/out1.gif`

## 5. `tc-8469bc1f4b-casua` (test-compositional)
**Request:** shrink the file size to less than 1 mb and remove the sound
**Gold spec means:** Result: a video (MP4) | Sound: removed | File size: at most 1 MB
**Model said:** Result: a video (MP4) | Picture size: 1920 x 800 pixels | Rotation: picture not rotated | Frame rate: 24 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: removed | File size: at most 1 MB
**Command (3 run(s)):** `ffmpeg -i {in:tos_quiet} -c:v libx264 -preset veryfast -crf 34 -pix_fmt yuv420p -an -b:v 128k {out:out1}`
**Output:** 10.75 s; 1920x800 h264 24.0 fps; 1.00 MB; mp4; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-8469bc1f4b-casua/run3/out/out1.mp4`

## 6. `tc-4c3656f637-casua` (test-compositional)
**Request:** put this mkv video in an mp4 container, then make it 320 pixels wide
**Gold spec means:** Result: a video (MP4) | Picture size: 320 x 134 pixels | Video codec: H.264 | Pixel format: yuv420p | Audio codec: AAC
**Model said:** Result: a video (MP4) | Picture size: 320 x 134 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept
**Command (1 run(s)):** `ffmpeg -i {in:tos_multiaud} -vf scale=320:-2 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 10.71 s; 320x134 h264 24.0 fps; 0.47 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-4c3656f637-casua/run1/out/out1.mp4`

## 7. `tc-035af884bb-verbo` (test-compositional)
**Request:** so I recorded this clip and I need to make this play 1.5 times faster, then rotate it 90 degrees counterclockwise
**Gold spec means:** Result: a video (MP4) | Picture size: 720 x 1280 pixels | Rotation: picture turned 90 degrees to the left (counterclockwise) | Length: about 6.667 seconds
**Model said:** Result: a video (MP4) | Picture size: 720 x 1280 pixels | Rotation: picture turned 90 degrees to the left (counterclockwise) | Frame rate: 40 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:07
**Command (1 run(s)):** `ffmpeg -i {in:h264_25fps_720p} -vf setpts=PTS/1.5,transpose=2 -af atempo=1.5 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 6.76 s; 720x1280 h264 25.0 fps; 2.14 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-035af884bb-verbo/run1/out/out1.mp4`

## 8. `tc-e52c03d50e-verbo` (test-compositional)
**Request:** so I recorded this clip and I need to cut the first 1 second off this video and then turn it into a GIF, 320 pixels wide, it's for a school project.
**Gold spec means:** Result: a GIF (GIF) | Picture width: 320 pixels | Start at 0:01 and keep the rest
**Model said:** Result: a GIF | Picture size: 320 x 180 pixels | Keep from 0:01 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 1 -i {in:h264_mono_44k} -vf scale=320:-2 -an {out:out1}`
**Output:** 3.01 s; 320x180 gif 30.0 fps; 0.36 MB; gif; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-e52c03d50e-verbo/run1/out/out1.gif`

## 9. `tp-b7c50f4967-indir` (test-phrasing)
**Request:** I'm posting this online later, so keep only the last 1 second of this clip and make it vertical, 1080 by 1920
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels | Start at 0:04 and keep the rest
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:04 to 0:05
**Command (1 run(s)):** `ffmpeg -ss 4.0 -i {in:h264_4x3} -t 1.0 -vf scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 1.00 s; 1080x1920 h264 30.0 fps; 0.28 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-b7c50f4967-indir/run1/out/out1.mp4`

## 10. `ti-5b099ade28-polit` (test-iid)
**Request:** could you please cut this down to its first 2 seconds and normalize the audio to -14 LUFS?
**Gold spec means:** Result: a video (MP4) | Loudness: about -14 LUFS | Keep from 0:00 to 0:02
**Model said:** Result: a video (MP4) | Picture size: 640 x 480 pixels | Rotation: picture not rotated | Frame rate: 30 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Loudness: about -14 LUFS | Keep from 0:00 to 0:02
**Command (1 run(s)):** `ffmpeg -ss 0 -t 2 -i {in:h264_4x3} -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -c:a aac -af loudnorm=I=-14 {out:out1}`
**Output:** 2.00 s; 640x480 h264 30.0 fps; 0.34 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-5b099ade28-polit/run1/out/out1.mp4`

## 11. `ti-c009193e5e-verbo` (test-iid)
**Request:** I've got a file here and I'd like to join these two videos together in order, then make it vertical, 1080 by 1920, then make it playable on a TV, that's all I need.
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels | Video codec: H.264 | Pixel format: yuv420p | Audio codec: AAC
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels | Rotation: picture not rotated | Frame rate: 30 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:23
**Command (1 run(s)):** `ffmpeg -i {in:h264_long} -i {in:clip_b} -filter_complex [0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0];[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];[0:a][1:a]concat=n=2:v=0:a=1[a];[v0][v1]concat=n=2:v=1:a=0[v] -map [v] -map [a] -c:v libx264 -crf 23 -preset veryfast -pix_fmt yuv420p -c:a aac -movflags +faststart {out:out1}`
**Output:** 23.02 s; 1080x1920 h264 30.0 fps; 3.79 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-c009193e5e-verbo/run1/out/out1.mp4`

## 12. `ti-6184fb5336-terse` (test-iid)
**Request:** play this at 0.5x speed and make it a square, 1080 x 1080
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Length: about 21.342 seconds
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Keep from 0:00 to 0:21
**Command (1 run(s)):** `ffmpeg -i {in:tos_cine} -vf setpts=PTS/0.5,scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080 -af atempo=0.5 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 21.33 s; 1080x1080 h264 24.0 fps; 4.00 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-6184fb5336-terse/run1/out/out1.mp4`

## 13. `tc-3635334d44-polit` (test-compositional)
**Request:** please trim off the first 1 second of this clip and then turn it into a GIF, 240 pixels wide
**Gold spec means:** Result: a GIF (GIF) | Picture width: 240 pixels | Start at 0:01 and keep the rest
**Model said:** Result: a GIF | Picture size: 240 x 135 pixels | Keep from 0:01 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 1 -i {in:h264_quiet} -vf scale=240:-2 -an {out:out1}`
**Output:** 3.01 s; 240x136 gif 30.0 fps; 0.24 MB; gif; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-3635334d44-polit/run1/out/out1.gif`

## 14. `tc-3a3ae24118-verbo` (test-compositional)
**Request:** I have a video on my laptop and I want to compress this to less than 1 MB without changing the resolution (720p) and then strip the audio out, that's all I need.
**Gold spec means:** Result: a video (MP4) | Picture height: 720 pixels | Sound: removed | File size: at most 1 MB
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: removed | File size: at most 1 MB
**Command (1 run(s)):** `ffmpeg -i {in:h264_mono_44k} -vf scale=1280:720 -c:v libx264 -crf 28 -preset veryfast -pix_fmt yuv420p -an {out:out1}`
**Output:** 4.00 s; 1280x720 h264 30.0 fps; 0.66 MB; mp4; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-3a3ae24118-verbo/run1/out/out1.mp4`

## 15. `tc-a1016dde15-verbo` (test-compositional)
**Request:** so I recorded this clip and I need to keep just the first 2 seconds of this video and turn it into a GIF, 240 pixels wide, that's all I need.
**Gold spec means:** Result: a GIF (GIF) | Picture width: 240 pixels | Keep from 0:00 to 0:02
**Model said:** Result: a GIF | Picture size: 240 x 135 pixels | Keep from 0:00 to 0:02
**Command (1 run(s)):** `ffmpeg -ss 0 -t 2 -i {in:h264_mkv} -vf scale=240:-2 -an {out:out1}`
**Output:** 2.00 s; 240x136 gif 30.0 fps; 0.15 MB; gif; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-a1016dde15-verbo/run1/out/out1.gif`

## 16. `tc-bb68dd8499-verbo` (test-compositional)
**Request:** I've got a file here and I'd like to compress this to less than 1 MB without changing the resolution (800p), then strip the audio out, thanks!
**Gold spec means:** Result: a video (MP4) | Picture height: 800 pixels | Sound: removed | File size: at most 1 MB
**Model said:** Result: a video (MP4) | Picture size: 1920 x 800 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: removed | File size: at most 1 MB
**Command (1 run(s)):** `ffmpeg -i {in:tos_mrg_a} -vf scale=1920:800 -c:v libx264 -crf 28 -preset veryfast -pix_fmt yuv420p -an {out:out1}`
**Output:** 7.54 s; 1920x800 h264 24.0 fps; 0.66 MB; mp4; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-bb68dd8499-verbo/run1/out/out1.mp4`

## 17. `ti-f390447cfb-terse` (test-iid)
**Request:** reformat this for a phone screen, 1080x1920
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept
**Command (1 run(s)):** `ffmpeg -i {in:tos_land} -vf scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 12.75 s; 1080x1920 h264 24.0 fps; 2.23 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-f390447cfb-terse/run1/out/out1.mp4`

## 18. `tp-d3a2beb303-indir` (test-phrasing)
**Request:** I'm posting this online later, so speed this video up 1.5x and make this video 640 pixels wide and keep the aspect ratio and keep only the part from 0:00 to 0:03
**Gold spec means:** Result: a video (MP4) | Picture size: 640 x 266 pixels | Length: about 2 seconds
**Model said:** Result: a video (MP4) | Picture size: 640 x 266 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Keep from 0:00 to 0:02
**Command (1 run(s)):** `ffmpeg -ss 0 -t 3 -i {in:tos_mrg_a} -vf setpts=PTS/1.5,scale=640:-2 -af atempo=1.5 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 2.12 s; 640x266 h264 24.0 fps; 0.11 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-d3a2beb303-indir/run1/out/out1.mp4`

## 19. `ti-68cd772e39-terse` (test-iid)
**Request:** trim off the first 3 seconds of this clip and then make it 320 pixels wide
**Gold spec means:** Result: a video (MP4) | Picture size: 320 x 134 pixels | Start at 0:03 and keep the rest
**Model said:** Result: a video (MP4) | Picture size: 320 x 134 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Keep from 0:03 to 0:11
**Command (1 run(s)):** `ffmpeg -ss 3.0 -i {in:tos_base} -vf scale=320:-2 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 7.75 s; 320x134 h264 24.0 fps; 0.33 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-68cd772e39-terse/run1/out/out1.mp4`

## 20. `tc-64a98cb4cd-polit` (test-compositional)
**Request:** I'd like you to make this video 640 pixels wide and keep the aspect ratio, then normalize the audio to -16 LUFS, thanks
**Gold spec means:** Result: a video (MP4) | Picture size: 640 x 266 pixels | Loudness: about -16 LUFS
**Model said:** Result: a video | Picture size: 640 x 267 pixels | Sound: kept | Loudness: about -16 LUFS
**Command (1 run(s)):** `ffmpeg -i {in:tos_mrg_a} -vf scale=640:-2 -af loudnorm=I=-16 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 7.54 s; 640x266 h264 24.0 fps; 0.37 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-64a98cb4cd-polit/run1/out/out1.mp4`

## 21. `ti-38bc7f9567-polit` (test-iid)
**Request:** could you please make this video silent and cut the first 2 seconds off and shrink it to 360p?
**Gold spec means:** Result: a video (MP4) | Picture size: 864 x 360 pixels | Sound: removed | Start at 0:02 and keep the rest
**Model said:** Result: a video (MP4) | Picture size: 864 x 360 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: removed | Keep from 0:02 to 0:11
**Command (1 run(s)):** `ffmpeg -ss 2 -i {in:tos_quiet} -vf scale=-2:360 -c:v libx264 -preset veryfast -pix_fmt yuv420p -an {out:out1}`
**Output:** 8.75 s; 864x360 h264 24.0 fps; 0.80 MB; mp4; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-38bc7f9567-polit/run1/out/out1.mp4`

## 22. `ti-1d6ae1868d-sympt` (test-iid)
**Request:** I only need the audio from this video, as an MP3, and cut it down to the final 2 seconds
**Gold spec means:** Result: an audio file (MP3) | Audio codec: MP3 | Start at 0:06 and keep the rest
**Model said:** Result: an audio file (MP3) | Sound: kept | Audio codec: MP3 | Keep from 0:06 to 0:08
**Command (1 run(s)):** `ffmpeg -ss 5.709478 -i {in:tos_mrg_c} -vn -c:a libmp3lame {out:out1}`
**Output:** 2.01 s; 0.03 MB; mp3; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-1d6ae1868d-sympt/run1/out/out1.mp3`

## 23. `ti-83f23b4282-casua` (test-iid)
**Request:** play this at 0.5x speed and make it a square, 1080 x 1080
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Length: about 21.374 seconds
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Keep from 0:00 to 0:21
**Command (1 run(s)):** `ffmpeg -i {in:tos_multiaud} -vf setpts=PTS/0.5,scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080 -af atempo=0.5 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 21.38 s; 1080x1080 h264 24.0 fps; 5.18 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-83f23b4282-casua/run1/out/out1.mp4`

## 24. `tp-3947935739-indir` (test-phrasing)
**Request:** I'm posting this online later, so speed this video up 2x and keep only the part from 0:01 to 0:04
**Gold spec means:** Result: a video (MP4) | Length: about 1.5 seconds
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture not rotated | Frame rate: 25 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:01 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 1 -t 3 -i {in:h264_25fps_720p} -vf setpts=PTS/2 -af atempo=2 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 1.60 s; 1280x720 h264 25.0 fps; 0.64 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-3947935739-indir/run1/out/out1.mp4`

## 25. `tc-1baee3134d-casua` (test-compositional)
**Request:** make this vieo silent, then make it 2x fster
**Gold spec means:** Result: a video (MP4) | Sound: removed | Length: about 5.381 seconds
**Model said:** Result: a video (MP4) | Picture size: 1920 x 800 pixels | Rotation: picture not rotated | Frame rate: 48 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: removed | Keep from 0:00 to 0:05
**Command (1 run(s)):** `ffmpeg -i {in:tos_quiet} -vf setpts=PTS/2,fps=48 -an -c:v libx264 -preset veryfast -pix_fmt yuv420p {out:out1}`
**Output:** 5.38 s; 1920x800 h264 48.0 fps; 3.36 MB; mp4; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-1baee3134d-casua/run1/out/out1.mp4`

## 26. `ti-64f65e1eb0-terse` (test-iid)
**Request:** turn this into a square clip at 1080 by 1080 and put it in an MP4 container and cut it to the first 1 second
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Audio codec: AAC | Keep from 0:00 to 0:01
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:01
**Command (1 run(s)):** `ffmpeg -ss 0 -t 1 -i {in:h264_mkv} -vf scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 1.03 s; 1080x1080 h264 30.0 fps; 0.33 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-64f65e1eb0-terse/run1/out/out1.mp4`

## 27. `ti-52be3f28e6-terse` (test-iid)
**Request:** keep seconds 5 to 15 and cut the rest
**Gold spec means:** Result: a video (MP4) | Keep from 0:05 to 0:15
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture not rotated | Frame rate: 30 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:05 to 0:15
**Command (1 run(s)):** `ffmpeg -ss 5 -i {in:h264_long} -t 10 -c copy {out:out1}`
**Output:** 10.02 s; 1280x720 h264 30.0 fps; 14.19 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-52be3f28e6-terse/run1/out/out1.mp4`

## 28. `ti-2e2c0e795d-terse` (test-iid)
**Request:** keep just the first 1 second of this video and then change the frame rate to 25 fps
**Gold spec means:** Result: a video (MP4) | Frame rate: 25 frames per second | Keep from 0:00 to 0:01
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture not rotated | Frame rate: 25 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:01
**Command (1 run(s)):** `ffmpeg -ss 0 -t 1 -i {in:h264_quiet} -vf fps=25 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 1.00 s; 1280x720 h264 25.0 fps; 0.30 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-2e2c0e795d-terse/run1/out/out1.mp4`

## 29. `tp-61e4d93ff3-indir` (test-phrasing)
**Request:** I'm posting this online later, so make this video 480 pixels wide and keep the aspect ratio
**Gold spec means:** Result: a video (MP4) | Picture size: 480 x 270 pixels
**Model said:** Result: a video | Picture size: 480 x 270 pixels | Sound: kept
**Command (1 run(s)):** `ffmpeg -i {in:h264_quiet} -vf scale=480:-2 -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 4.01 s; 480x270 h264 30.0 fps; 0.23 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-61e4d93ff3-indir/run1/out/out1.mp4`

## 30. `tp-20a84d7dc0-indir` (test-phrasing)
**Request:** I'm posting this online later, so make this video smaller than 2 MB and make it a square video, 1080 x 1080
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | File size: at most 2 MB
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | File size: at most 2 MB
**Command (1 run(s)):** `ffmpeg -i {in:tos_mrg_a} -vf scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080 -c:v libx264 -crf 28 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 96k {out:out1}`
**Output:** 7.54 s; 1080x1080 h264 24.0 fps; 0.60 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-20a84d7dc0-indir/run1/out/out1.mp4`

## 31. `ti-59cae88bd4-verbo` (test-iid)
**Request:** I have a video on my laptop and I want to convert this video, thanks!
**Gold spec means:** (no gold spec)
**Model said:** (none)
**Command (0 run(s)):** ``
**Output:** output file not found (job dir deleted?)  
``

## 32. `tp-353b729880-conte` (test-phrasing)
**Request:** the college portal keeps rejecting my upload and the volume on this video is all over the place, normalize it to -16 LUFS
**Gold spec means:** Result: a video (MP4) | Loudness: about -16 LUFS
**Model said:** Result: a video | Sound: kept | Audio codec: AAC | Loudness: about -16 LUFS
**Command (1 run(s)):** `ffmpeg -i {in:tos_mrg_b} -c:v copy -af loudnorm=I=-16 -c:a aac {out:out1}`
**Output:** 7.60 s; 1920x800 h264 24.0 fps; 6.35 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-353b729880-conte/run1/out/out1.mp4`

## 33. `tc-dfc4d71743-terse` (test-compositional)
**Request:** remove the first 1 second and make it 480 pixels wide and compress it to under 2 MB
**Gold spec means:** Result: a video (MP4) | Picture size: 480 x 200 pixels | Start at 0:01 and keep the rest | File size: at most 2 MB
**Model said:** Result: a video (MP4) | Picture size: 480 x 200 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:01 to 0:10 | File size: at most 2 MB
**Command (1 run(s)):** `ffmpeg -ss 1 -i {in:tos_720_mrg} -vf scale=480:-2 -c:v libx264 -crf 28 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 96k {out:out1}`
**Output:** 9.42 s; 480x200 h264 24.0 fps; 0.21 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-dfc4d71743-terse/run1/out/out1.mp4`

## 34. `tc-a07bc55412-verbo` (test-compositional)
**Request:** so I recorded this clip and I need to turn this mkv file into an mp4 without losing quality and crop it to a 1080x1080 square
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Audio codec: AAC
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | No re-encoding: the picture quality is untouched
**Command (1 run(s)):** `ffmpeg -i {in:tos_multiaud} -vf crop=800:800,scale=1080:1080 -c:v libx264 -crf 23 -preset veryfast -pix_fmt yuv420p -c:a aac -metadata:s:v:0 rotate=180 {out:out1}`
**Output:** 10.71 s; 1080x1080 h264 24.0 fps; 4.27 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-a07bc55412-verbo/run1/out/out1.mp4`

## 35. `tc-4030ae500c-casua` (test-compositional)
**Request:** trim off the frist 2 seocnds of this clip and turn it into a gif, 240 pxels wide
**Gold spec means:** Result: a GIF (GIF) | Picture width: 240 pixels | Start at 0:02 and keep the rest
**Model said:** Result: a GIF | Picture size: 240 x 135 pixels | Keep from 0:02 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 2 -i {in:h264_mono_44k} -vf scale=240:-2 -an {out:out1}`
**Output:** 2.01 s; 240x136 gif 30.0 fps; 0.17 MB; gif; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-4030ae500c-casua/run1/out/out1.gif`

## 36. `ti-b6b41568df-terse` (test-iid)
**Request:** turn this WebM into a regular MP4, then cut the first 1 second off, then make it play at 0.5x speed
**Gold spec means:** Result: a video (MP4) | Video codec: H.264 | Pixel format: yuv420p | Audio codec: AAC | Length: about 6.016 seconds
**Model said:** Result: a video (MP4) | Picture size: 640 x 360 pixels | Rotation: picture not rotated | Frame rate: 30 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:01 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 1 -i {in:vp9_opus_webm} -vf setpts=PTS/0.5 -af atempo=0.5 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 6.00 s; 640x360 h264 30.0 fps; 0.41 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-b6b41568df-terse/run1/out/out1.mp4`

## 37. `ti-b7b50643d1-polit` (test-iid)
**Request:** could you please shrink this video to 480p and make it smaller than 1 MB?
**Gold spec means:** Result: a video (MP4) | Picture size: 1152 x 480 pixels | File size: at most 1 MB
**Model said:** Result: a video (MP4) | Picture size: 1152 x 480 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | File size: at most 1 MB
**Command (1 run(s)):** `ffmpeg -i {in:tos_base} -vf scale=-2:480 -c:v libx264 -crf 28 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 96k {out:out1}`
**Output:** 10.75 s; 1152x480 h264 24.0 fps; 0.85 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-b7b50643d1-polit/run1/out/out1.mp4`

## 38. `tc-9a4d1f0d99-verbo` (test-compositional)
**Request:** I've got a file here and I'd like to turn this AVI file into a modern MP4 and make it a square, 1080 x 1080, it's for a school project.
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Audio codec: AAC
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC
**Command (1 run(s)):** `ffmpeg -i {in:mpeg4_avi} -vf scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 4.04 s; 1080x1080 h264 25.0 fps; 0.98 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-compositional/tc-9a4d1f0d99-verbo/run1/out/out1.mp4`

## 39. `ti-4ae1891f91-sympt` (test-iid)
**Request:** I only want the first 1 second of this clip, and flip it the right way up, and convert it to 25 fps
**Gold spec means:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture turned upside down (180 degrees) | Frame rate: 25 frames per second | Keep from 0:00 to 0:01
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture turned upside down (180 degrees) | Frame rate: 25 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:01
**Command (1 run(s)):** `ffmpeg -ss 0 -t 1 -i {in:h264_quiet} -vf vflip,hflip,fps=25 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 1.00 s; 1280x720 h264 25.0 fps; 0.30 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-4ae1891f91-sympt/run1/out/out1.mp4`

## 40. `ti-c4dc6c04ad-terse` (test-iid)
**Request:** keep only the part from 0:00 to 0:02 and then make it vertical, 1080 by 1920
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels | Keep from 0:00 to 0:02
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1920 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:02
**Command (1 run(s)):** `ffmpeg -ss 0 -t 2 -i {in:h264_4x3} -vf scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 2.00 s; 1080x1920 h264 30.0 fps; 0.55 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-c4dc6c04ad-terse/run1/out/out1.mp4`

## 41. `ti-f9886404ec-terse` (test-iid)
**Request:** make this video silent, then slow it down to 0.5x speed, then rotate it 180 degrees
**Gold spec means:** Result: a video (MP4) | Picture size: 1280 x 534 pixels | Rotation: picture turned upside down (180 degrees) | Sound: removed | Length: about 20.853 seconds
**Model said:** Result: a video (MP4) | Picture size: 1280 x 534 pixels | Rotation: picture turned upside down (180 degrees) | Frame rate: 24 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: removed | Keep from 0:00 to 0:21
**Command (1 run(s)):** `ffmpeg -i {in:tos_720_mrg} -vf setpts=PTS/0.5,hflip,vflip -an -c:v libx264 -preset veryfast -pix_fmt yuv420p {out:out1}`
**Output:** 20.83 s; 1280x534 h264 24.0 fps; 1.44 MB; mp4; no audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-f9886404ec-terse/run1/out/out1.mp4`

## 42. `ti-c547926d7d-polit` (test-iid)
**Request:** could you please normalize the audio to -23 LUFS?
**Gold spec means:** Result: a video (MP4) | Loudness: about -23 LUFS
**Model said:** Result: a video | Sound: kept | Audio codec: AAC | Loudness: about -23 LUFS
**Command (1 run(s)):** `ffmpeg -i {in:h264_long} -c:v copy -af loudnorm=I=-23 -c:a aac {out:out1}`
**Output:** 20.01 s; 1280x720 h264 30.0 fps; 18.91 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-c547926d7d-polit/run1/out/out1.mp4`

## 43. `ti-60b6f8b188-verbo` (test-iid)
**Request:** so I recorded this clip and I need to colour grade this to look like a movie, thanks!
**Gold spec means:** (no gold spec)
**Model said:** (none)
**Command (0 run(s)):** ``
**Output:** output file not found (job dir deleted?)  
``

## 44. `tp-649fc5b9c0-indir` (test-phrasing)
**Request:** I'm posting this online later, so put these clips back to back in a single MP4, same size as the originals and convert this HEVC iPhone video so it plays everywhere
**Gold spec means:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Video codec: H.264 | Pixel format: yuv420p | Audio codec: AAC
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture not rotated | Frame rate: 30 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:26
**Command (1 run(s)):** `ffmpeg -i {in:clip_a} -i {in:clip_b} -i {in:h264_long} -filter_complex [0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a] -map [v] -map [a] -c:v libx264 -crf 23 -preset veryfast -pix_fmt yuv420p -c:a aac -movflags +faststart {out:out1}`
**Output:** 26.03 s; 1280x720 h264 30.0 fps; 8.84 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-649fc5b9c0-indir/run1/out/out1.mp4`

## 45. `ti-1b7ca31bec-sympt` (test-iid)
**Request:** this video is upside down, fix it, and convert it to 24 fps, and trim it to 0 through 2 seconds
**Gold spec means:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture turned upside down (180 degrees) | Frame rate: 24 frames per second | Keep from 0:00 to 0:02
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture turned upside down (180 degrees) | Frame rate: 24 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:00 to 0:02
**Command (1 run(s)):** `ffmpeg -ss 0 -t 2 -i {in:h264_noisy} -vf vflip,hflip,fps=24 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 2.00 s; 1280x720 h264 24.0 fps; 0.60 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-1b7ca31bec-sympt/run1/out/out1.mp4`

## 46. `tp-bc995fe9cd-indir` (test-phrasing)
**Request:** for my presentation tomorrow, cut the first 1 second off this video
**Gold spec means:** Result: a video (MP4) | Start at 0:01 and keep the rest
**Model said:** Result: a video (MP4) | Picture size: 1280 x 720 pixels | Rotation: picture not rotated | Frame rate: 30 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Keep from 0:01 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 1 -i {in:h264_noisy} -c copy {out:out1}`
**Output:** 3.00 s; 1280x720 h264 30.0 fps; 3.80 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-bc995fe9cd-indir/run1/out/out1.mp4`

## 47. `ti-e50cafe806-verbo` (test-iid)
**Request:** so I recorded this clip and I need to delay the audio by 500 ms
**Gold spec means:** Result: a video (MP4) | Sound starts 500 ms later than the picture
**Model said:** Result: a video | Sound: kept | Audio codec: AAC | Sound starts 500 ms later than the picture
**Command (1 run(s)):** `ffmpeg -i {in:clip_a} -itsoffset 0.5 -i {in:clip_a} -map 0:v:0 -map 1:a:0 -c copy {out:out1}`
**Output:** 3.50 s; 1280x720 h264 30.0 fps; 2.83 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-e50cafe806-verbo/run1/out/out1.mp4`

## 48. `ti-07124fc79f-verbo` (test-iid)
**Request:** I have a video on my laptop and I want to extract the audio from this video as an mp3 and keep only 0:00 to 0:05, thanks!
**Gold spec means:** Result: an audio file (MP3) | Audio codec: MP3 | Keep from 0:00 to 0:05
**Model said:** Result: an audio file (MP3) | Sound: kept | Audio codec: MP3 | Keep from 0:00 to 0:05
**Command (1 run(s)):** `ffmpeg -ss 0 -t 5 -i {in:tos_land} -vn -c:a libmp3lame {out:out1}`
**Output:** 5.04 s; 0.08 MB; mp3; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-07124fc79f-verbo/run1/out/out1.mp3`

## 49. `ti-c232318234-sympt` (test-iid)
**Request:** this needs to be 60 fps for my editor
**Gold spec means:** Result: a video (MP4) | Frame rate: 60 frames per second
**Model said:** Result: a video | Picture size: 1920 x 800 pixels | Rotation: picture not rotated | Frame rate: 60 frames per second | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC
**Command (1 run(s)):** `ffmpeg -i {in:tos_mrg_a} -vf fps=60 -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -c:a aac {out:out1}`
**Output:** 7.55 s; 1920x800 h264 60.0 fps; 3.73 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-iid/ti-c232318234-sympt/run1/out/out1.mp4`

## 50. `tp-713d20f7c7-indir` (test-phrasing)
**Request:** before I send this to a friend, make it a square video, 1080 x 1080 and normalize the audio to -14 LUFS and keep just the first 4 seconds of this video
**Gold spec means:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Loudness: about -14 LUFS | Keep from 0:00 to 0:04
**Model said:** Result: a video (MP4) | Picture size: 1080 x 1080 pixels | Video codec: H.264 | Pixel format: yuv420p | Sound: kept | Audio codec: AAC | Loudness: about -14 LUFS | Keep from 0:00 to 0:04
**Command (1 run(s)):** `ffmpeg -ss 0 -t 4 -i {in:tos_720_mrg} -vf scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080 -c:v libx264 -preset veryfast -pix_fmt yuv420p -af loudnorm=I=-14 -c:a aac {out:out1}`
**Output:** 4.04 s; 1080x1080 h264 24.0 fps; 0.69 MB; mp4; audio  
`/home/joydeep/Projects/ffmpeg-agent/data/jobs/M3-test-phrasing/tp-713d20f7c7-indir/run1/out/out1.mp4`

