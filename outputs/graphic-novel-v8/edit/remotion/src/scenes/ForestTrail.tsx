import React from 'react';
import {AbsoluteFill, CanvasImage, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Audio} from '@remotion/media';

export const ForestTrail: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: '#080c12', overflow: 'hidden'}}>
      <CanvasImage name="041 — Chloe close-up" src={staticFile('assets/shot-041.png')}
        from={0} durationInFrames={125} width={1920} height={1080} fit="cover"
        style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, scale: 1}} />
      <CanvasImage name="042 — Entering the trail" src={staticFile('assets/shot-042.png')}
        from={125} durationInFrames={390} width={1920} height={1080} fit="cover"
        style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080,
          scale: interpolate(frame, [125, 514], [1, 1.025], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />
      <CanvasImage name="043 — Closed canopy" src={staticFile('assets/shot-043.png')}
        from={515} durationInFrames={266} width={1920} height={1080} fit="cover"
        style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080,
          scale: 1.025,
          translate: interpolate(frame, [515, 780], ['0px 8px', '0px -8px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />
      <CanvasImage name="044 — Dark forest corridor" src={staticFile('assets/shot-044.png')}
        from={781} durationInFrames={365} width={1920} height={1080} fit="cover"
        style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080,
          scale: interpolate(frame, [781, 1145], [1, 1.025], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />
      <Audio name="Original v6 mix — beat 15" src={staticFile('sound/pilot-master-pcm24.wav')}
        from={0} durationInFrames={1146} trimBefore={981} volume={1} />
    </AbsoluteFill>
  );
};
