"""Native-size sample plates for restrained-motion review, not automated acceptance."""
from pathlib import Path

from PIL import Image, ImageDraw

from comparison import decoded_frames

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'work/animation-pilot/evidence-v3/animation-c0125ade55b122d0'
OUTPUT = ROOT/'outputs/animation-pilot/review'
FFMPEG = ROOT/'work/ffmpeg-full/ffmpeg.exe'

source = Image.open(RUN/'source/shot-001.png').convert('RGB').resize((512,288),Image.Resampling.LANCZOS)
plates = [('Original checkpoint',source)]
for index,frame in enumerate(decoded_frames(RUN/'clips/shot-001-seed-20261005.mp4',512,288,FFMPEG)):
    if index in (0,18,36,54,72):
        plates.append((f'Wan I2V frame {index}',Image.fromarray(frame)))
canvas = Image.new('RGB',(1536,640),'#151515')
draw = ImageDraw.Draw(canvas)
for index,(label,image) in enumerate(plates):
    x,y=(index%3)*512,(index//3)*320
    draw.text((x+8,y+8),label,fill='white')
    canvas.paste(image,(x,y+32))
canvas.save(OUTPUT/'lake-native-review.jpg',quality=97)
