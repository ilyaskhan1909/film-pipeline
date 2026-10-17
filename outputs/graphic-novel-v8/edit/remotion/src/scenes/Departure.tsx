import React from 'react';
import {AbsoluteFill, CanvasImage, staticFile} from 'remotion';
import {Audio} from '@remotion/media';

export const Departure: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#080c12', overflow: 'hidden'}}>
    <CanvasImage name="039 — Chloe left, Jess right" src={staticFile('assets/shot-039-r2.png')}
      from={0} durationInFrames={357} width={1920} height={1080} fit="cover"
      style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, scale: 1}} />
    <CanvasImage name="040 — Empty camp cutaway" src={staticFile('assets/shot-040.png')}
      from={357} durationInFrames={249} width={1920} height={1080} fit="cover"
      style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, scale: 1}} />
    <Audio name="Original v6 mix — beat 14" src={staticFile('sound/pilot-master-pcm24.wav')}
      from={0} durationInFrames={606} trimBefore={375} volume={1} />
  </AbsoluteFill>
);
