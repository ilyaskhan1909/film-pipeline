import gzip, requests, shutil
from pathlib import Path
root=Path(__file__).resolve().parent
target=root/'ffmpeg-full'; target.mkdir(exist_ok=True)
binary=target/'ffmpeg.exe'
archive=target/'ffmpeg-win32-x64.gz'
if not binary.exists():
    if not archive.exists():
        url='https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-win32-x64.gz'
        with requests.get(url,stream=True,timeout=(20,30)) as response:
            response.raise_for_status()
            count=0
            with open(archive.with_suffix('.partial'),'wb') as out:
                for block in response.iter_content(1024*1024):
                    out.write(block); count+=len(block); print(f'{count//1024**2} MiB',flush=True)
        archive.with_suffix('.partial').replace(archive)
    with gzip.open(archive,'rb') as inp,open(binary,'wb') as out: shutil.copyfileobj(inp,out)
print('FFmpeg full test binaries ready')
