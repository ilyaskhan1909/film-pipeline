import React from 'react';
import {AbsoluteFill, CanvasImage, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Audio} from '@remotion/media';

export const CampConversation: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: '#080c12', overflow: 'hidden'}}>
      <CanvasImage name="037 — Jess by the fire" src={staticFile('assets/shot-037.png')}
        from={0} durationInFrames={217} width={1920} height={1080} fit="cover"
        style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080,
          scale: 1.025,
          translate: interpolate(frame, [0, 216], ['-10px 0px', '10px 0px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />
      <CanvasImage name="038 — Jess close-up" src={staticFile('assets/shot-038.png')}
        from={217} durationInFrames={158} width={1920} height={1080} fit="cover"
        style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, scale: 1}} />
      <Audio name="Original v6 mix — beat 13" src={staticFile('sound/pilot-master-pcm24.wav')}
        from={0} durationInFrames={375} trimBefore={0} volume={1} />
    </AbsoluteFill>
  );
};
