### 1. tr-0284be5a24-casua (widened)
request: make this video 2x faster, then stip the audio out, then resize it to a width of 320

- x4 spec_acc=0.84 passed=True runs=[1] | outputs.out1.time.start_s: emitted=0.0 gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x3 spec_acc=0.74 passed=True runs=[1] | outputs.out1.time.start_s: emitted=0.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.2; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x1 spec_acc=0.78 passed=True runs=[1] | outputs.out1.time.start_s: emitted=0.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
  run args: ['-i', '{in:h264_mono_44k}', '-vf', 'setpts=PTS/2,scale=320:-2', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '{out:out1}']

### 2. tr-09e0026e55-sympt (widened)
request: I only want the first 5 seconds of this clip, and speed it up 1.5x, and reformat it to 1080x1920

- x7 spec_acc=0.70 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=36 gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
- x1 spec_acc=0.67 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=36 gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
  run args: ['-ss', '0', '-t', '5', '-i', '{in:tos_multiaud}', '-vf', 'setpts=PTS/1.5,scale=1080:1920,fps=36', '-af', 'atempo=1.5', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 3. tr-1ada5e5192-verbo (widened)
request: so I recorded this clip and I need to trim this to 0s through 2s and then make it a square, 1080 x 1080 and then make it 2x faster, thanks!

- x4 spec_acc=0.48 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=2 gold=1.0; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.2; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=60 gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
- x3 spec_acc=0.53 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=2 gold=1.0; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.2; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x1 spec_acc=0.63 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=2 gold=1.0; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
  run args: ['-ss', '0', '-t', '2', '-i', '{in:h264_noisy}', '-vf', 'setpts=PTS/2,scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080', '-af', 'atempo=2', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 4. tr-2b196cf0b7-terse (widened)
request: flip this video upside down the right way up and change the frame rate to 60 fps and cut it to the first 1 second

- x5 spec_acc=0.50 passed=True runs=[1] | family: emitted='["F1", "F5", "F12"]' gold='["F5", "F12", "F1"]'; outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.height: emitted=1920 gold=800; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=800 gold=1920
- x2 spec_acc=0.45 passed=True runs=[1] | family: emitted='["F1", "F5", "F12"]' gold='["F5", "F12", "F1"]'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.container: emitted='matroska' gold='mp4'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.height: emitted=1920 gold=800; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=800 gold=1920
- x1 spec_acc=0.43 passed=True runs=[1] | family: emitted='["F1", "F5", "F12"]' gold='["F5", "F12", "F1"]'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.container: emitted='matroska' gold='mp4'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.height: emitted=1920 gold=800; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=800 gold=1920
  run args: ['-ss', '0', '-t', '1', '-i', '{in:tos_multiaud}', '-vf', 'vflip,hflip,fps=60', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 5. tr-2c4bbe8fc8-verbo (widened)
request: I have a video on my laptop and I want to make this video silent and keep just the first 1 second and resize it to a width of 320, thanks!

- x4 spec_acc=0.74 passed=True runs=[1] | family: emitted='["F1", "F4", "F9"]' gold='["F9", "F1", "F4"]'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x4 spec_acc=0.89 passed=True runs=[1] | family: emitted='["F1", "F4", "F9"]' gold='["F9", "F1", "F4"]'
  run args: ['-ss', '0', '-t', '1', '-i', '{in:h264_quiet}', '-vf', 'scale=320:-2', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', '-an', '{out:out1}']

### 6. tr-34d9e19875-terse (t18)
request: make this webm video playable on my TV and slow it down to 0.5x speed and make it vertical, 1080 by 1920

- x5 spec_acc=0.86 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.start_s: emitted=0.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2
- x3 spec_acc=0.78 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.5 gold=0.2; outputs.out1.video.fps: emitted=60 gold='<absent>'
  run args: ['-i', '{in:bbb_4k}', '-vf', 'setpts=PTS/0.5,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=60', '-af', 'atempo=0.5', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 7. tr-34e344a91d-polit (widened)
request: can you trim off the first 5 seconds of this clip and strip the audio out and crop it to a 1080x1080 square and make it 1.5x faster?

- x6 spec_acc=0.67 passed=True runs=[1] | family: emitted='["F1", "F4", "F5", "F9", "F12"]' gold='["F1", "F9", "F4", "F12"]'; outputs.out1.time.start_s: emitted=5.0 gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=45 gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
- x1 spec_acc=0.57 passed=True runs=[1] | family: emitted='["F1", "F4", "F5", "F9", "F12"]' gold='["F1", "F9", "F4", "F12"]'; outputs.out1.time.end_s: emitted=12.0 gold=10.0; outputs.out1.time.start_s: emitted=5.0 gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=45 gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
- x1 spec_acc=0.50 passed=True runs=[1] | family: emitted='["F1", "F4", "F5", "F9", "F12"]' gold='["F1", "F9", "F4", "F12"]'; outputs.out1.time.end_s: emitted=12.0 gold=10.0; outputs.out1.time.start_s: emitted=5.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=45 gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
  run args: ['-ss', '5', '-i', '{in:h264_long}', '-vf', 'crop=720:720,scale=1080:1080,setpts=PTS/1.5,fps=45', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '{out:out1}']

### 8. tr-34ed49f0f1-polit (t18)
request: please extract the audio from this video as an mp3 and boost the volume by 6 dB and cut it down to the final 2 seconds

- x5 spec_acc=0.67 passed=True runs=[1] | outputs.out1.audio.loudness_lufs: emitted='<absent>' gold=-19.4; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=4.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.2
- x2 spec_acc=0.67 passed=True runs=[1] | outputs.out1.audio.loudness_lufs: emitted='<absent>' gold=-19.4; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=4.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.2
- x1 spec_acc=0.71 passed=True runs=[1] | outputs.out1.audio.loudness_lufs: emitted='<absent>' gold=-19.4; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=4.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2
  run args: ['-ss', '2', '-t', '2', '-i', '{in:h264_noisy}', '-vn', '-af', 'volume=6dB', '-c:a', 'libmp3lame', '{out:out1}']

### 9. tr-386d3a73d4-polit (widened)
request: can you turn this video 90 degrees to the left and remove the sound?

- x5 spec_acc=0.59 passed=True runs=[1] | outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=30.0 gold='<absent>'; outputs.out1.video.height: emitted=720 gold=1280; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=1280 gold=720
- x2 spec_acc=0.56 passed=True runs=[1] | outputs.out1.lossless: emitted=True gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=30.0 gold='<absent>'; outputs.out1.video.height: emitted=720 gold=1280; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=1280 gold=720
- x1 spec_acc=0.59 passed=True runs=[1] | outputs.out1.time.end_s: emitted=2.0 gold='<absent>'; outputs.out1.time.start_s: emitted=0.0 gold='<absent>'; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.height: emitted=720 gold=1280; outputs.out1.video.width: emitted=1280 gold=720
  run args: ['-i', '{in:h264_2s}', '-vf', 'transpose=2', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-an', '{out:out1}']

### 10. tr-4368bf81c7-casua (t18)
request: cut this down to its frst 3 seconds and rotte it 90 dgerees counterclockwise withotu re-encoding

- x5 spec_acc=0.50 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.lossless: emitted='<absent>' gold=True; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=24.0 gold='<absent>'; outputs.out1.video.height: emitted=800 gold=1920; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=1920 gold=800
- x2 spec_acc=0.70 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.lossless: emitted='<absent>' gold=True; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x1 spec_acc=0.56 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=24.0 gold='<absent>'; outputs.out1.video.height: emitted=800 gold=1920; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=1920 gold=800
  run args: ['-ss', '0', '-t', '3', '-i', '{in:tos_base}', '-c', 'copy', '-metadata:s:v:0', 'rotate=90', '{out:out1}']

### 11. tr-6a9353d7d6-polit (widened)
request: I'd like you to resize this clip to a width of 640, then keep just the first 3 seconds, then speed it up 2x, thanks

- x5 spec_acc=0.56 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.2; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.height: emitted=267 gold=266; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x3 spec_acc=0.67 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.2; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
  run args: ['-ss', '0', '-t', '3', '-i', '{in:tos_mrg_b}', '-vf', 'scale=640:-2,setpts=PTS/2', '-af', 'atempo=2', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 12. tr-6b2e4250fe-terse (t18)
request: remove the first 2 seconds

- x7 spec_acc=0.42 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=4.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.fps: emitted=30.0 gold='<absent>'; outputs.out1.video.height: emitted=720 gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'; outputs.out1.video.width: emitted=1280 gold='<absent>'
- x1 spec_acc=1.00 passed=True runs=[1] | identical to gold
  run args: ['-ss', '2', '-i', '{in:h264_quiet}', '-c', 'copy', '{out:out1}']

### 13. tr-6cac188978-casua (t18)
request: trim off the first 5 seconds of this clip and make it vertical, 1080 by 1920 and strpi the audio out

- x5 spec_acc=0.62 passed=True runs=[1] | outputs.out1.container: emitted='matroska' gold='mp4'; outputs.out1.time.start_s: emitted='<absent>' gold=5; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x3 spec_acc=0.78 passed=True runs=[1] | outputs.out1.time.end_s: emitted=10.687 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
  run args: ['-ss', '5', '-i', '{in:tos_multiaud}', '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '{out:out1}']

### 14. tr-79d985b8a9-casua (t18)
request: cut out the setcion bteween 0 and 2 seconds, then make it vertical, 1080 by 1920

- x6 spec_acc=0.78 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
- x2 spec_acc=0.53 passed=True runs=[1] | outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=4.0 gold=2; outputs.out1.time.start_s: emitted=2.0 gold=0; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'
  run args: ['-ss', '0', '-t', '2', '-i', '{in:h264_mono_44k}', '-vf', 'scale=1080:1920', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 15. tr-79f43d170e-polit (widened)
request: can you remove the sound from this video and then make it 640 pixels wide and then cut the first 1 second off and then slow it down to 0.5x speed?

- x3 spec_acc=0.57 passed=True runs=[1] | outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.time.end_s: emitted=20.852546 gold=18.853; outputs.out1.time.start_s: emitted=1.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2; outputs.out1.video.height: emitted='<absent>' gold=268
- x2 spec_acc=0.53 passed=True runs=[1] | outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.lossless: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=20.852544 gold=18.853; outputs.out1.time.start_s: emitted=1.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2; outputs.out1.video.height: emitted='<absent>' gold=268
- x2 spec_acc=0.57 passed=True runs=[1] | outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.time.end_s: emitted=20.85254 gold=18.853; outputs.out1.time.start_s: emitted=1.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2; outputs.out1.video.height: emitted='<absent>' gold=268
- x1 spec_acc=0.46 passed=True runs=[1] | outputs.out1.audio.present: emitted='<absent>' gold=False; outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.time.end_s: emitted=10.42627 gold=18.853; outputs.out1.time.start_s: emitted=1.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.2; outputs.out1.video.height: emitted='<absent>' gold=268
  run args: ['-ss', '1', '-i', '{in:tos_720_mrg}', '-vf', 'scale=640:-2,setpts=PTS/0.5', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '{out:out1}']

### 16. tr-817f192daa-verbo (widened)
request: I have a video on my laptop and I want to make this webm video playable on my TV, then cut it to the first 5 seconds, then shrink it to 360p, it's for a school project.

- x5 spec_acc=0.70 passed=True runs=[2] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.2 gold=0.15; outputs.out1.video.height: emitted=480 gold=360; outputs.out1.video.width: emitted=854 gold=864
- x2 spec_acc=0.91 passed=True runs=[2] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15
- x1 spec_acc=0.73 passed=True runs=[2] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.height: emitted=480 gold=360; outputs.out1.video.width: emitted=854 gold=864
  run args: ['-ss', '0', '-t', '5', '-i', '{in:tos_webm}', '-vf', 'scale=-2:360', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 17. tr-85ea025afa-verbo (widened)
request: I have a video on my laptop and I want to drop the first 2 seconds and then change the frame rate to 24 fps and then scale it down to 360p and then strip the audio out

- x5 spec_acc=0.76 passed=True runs=[1] | outputs.out1.time.end_s: emitted=4.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
- x3 spec_acc=0.67 passed=True runs=[1] | family: emitted='["F1", "F4", "F12", "F9"]' gold='["F1", "F12", "F4", "F9"]'; outputs.out1.time.end_s: emitted=4.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'
  run args: ['-ss', '2', '-i', '{in:h264_quiet}', '-vf', 'fps=24,scale=640:360', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '{out:out1}']

### 18. tr-86622192ff-verbo (widened)
request: I've got a file here and I'd like to trim the clip to the first 2 seconds and convert it to 60 fps and strip the audio out and turn it to the right, it's for a school project.

- x7 spec_acc=0.61 passed=True runs=[1] | outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.time.tolerance_s: emitted=0.1 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.height: emitted=720 gold=1280; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=1280 gold=720
- x1 spec_acc=0.64 passed=True runs=[1] | outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.height: emitted=720 gold=1280; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.width: emitted=1280 gold=720
  run args: ['-ss', '0', '-t', '2', '-i', '{in:h264_quiet}', '-vf', 'fps=60,transpose=1', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '{out:out1}']

### 19. tr-8683697e0f-terse (widened)
request: join these three videos together in order and then convert it to a normal MP4

- x5 spec_acc=0.71 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.video.fps: emitted=30.0 gold='<absent>'; outputs.out1.video.height: emitted=720 gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'; outputs.out1.video.width: emitted=1280 gold='<absent>'
- x2 spec_acc=0.60 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=10.0 gold='<absent>'; outputs.out1.time.start_s: emitted=0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.5 gold='<absent>'; outputs.out1.video.fps: emitted=30 gold='<absent>'; outputs.out1.video.height: emitted=720 gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'; outputs.out1.video.width: emitted=1280 gold='<absent>'
- x1 spec_acc=0.60 passed=True runs=[1] | outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.time.end_s: emitted=10.0 gold='<absent>'; outputs.out1.time.start_s: emitted=0.0 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.5 gold='<absent>'; outputs.out1.video.fps: emitted=30.0 gold='<absent>'; outputs.out1.video.height: emitted=720 gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'; outputs.out1.video.width: emitted=1280 gold='<absent>'
  run args: ['-i', '{in:clip_b}', '-i', '{in:h264_noisy}', '-i', '{in:clip_a}', '-filter_complex', '[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]', '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

### 20. tr-980416099b-sympt (widened)
request: the first 5 seconds of this video are junk, get rid of them, and convert it to 30 fps, and shrink it to 480p

- x4 spec_acc=0.38 passed=True runs=[1] | family: emitted='["F1", "F3", "F4", "F12"]' gold='["F1", "F12", "F4"]'; outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.time.end_s: emitted=10.76254 gold='<absent>'; outputs.out1.time.tolerance_s: emitted=0.2 gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'; outputs.out1.video.width: emitted=854 gold=1152
- x4 spec_acc=0.40 passed=True runs=[1] | family: emitted='["F1", "F3", "F4", "F12"]' gold='["F1", "F12", "F4"]'; outputs.out1.audio.codec: emitted='aac' gold='<absent>'; outputs.out1.audio.present: emitted=True gold='<absent>'; outputs.out1.container: emitted='<absent>' gold='mp4'; outputs.out1.time.end_s: emitted=10.76254 gold='<absent>'; outputs.out1.time.tolerance_s: emitted='<absent>' gold=0.15; outputs.out1.video.codec: emitted='h264' gold='<absent>'; outputs.out1.video.pix_fmt: emitted='yuv420p' gold='<absent>'; outputs.out1.video.rotation: emitted=0 gold='<absent>'; outputs.out1.video.width: emitted=854 gold=1152
  run args: ['-ss', '5', '-i', '{in:tos_base}', '-vf', 'fps=30,scale=-2:480', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '{out:out1}']

