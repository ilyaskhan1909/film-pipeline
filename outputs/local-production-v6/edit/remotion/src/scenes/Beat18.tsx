import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat18: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-050 — 85mm partial discovery"} from={0} durationInFrames={272}>
      <CinematicShot image="assets/shot-050.png" frames={272} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 18" file="assets/s0018.wav" frames={260} />
  </AbsoluteFill>
);
