import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat07: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-020 — 85mm intimate side close-up"} from={0} durationInFrames={454}>
      <CinematicShot image="assets/shot-020.png" frames={454} motion="push-in" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 07" file="assets/s0007.wav" frames={442} />
  </AbsoluteFill>
);
