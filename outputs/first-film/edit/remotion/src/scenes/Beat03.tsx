import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat03: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-011 — 85mm distant tree-line detail"} from={0} durationInFrames={77}>
      <CinematicShot image="assets/shot-011.png" frames={77} motion="pan-left" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 03" file="assets/s0003.wav" frames={60} />
  </AbsoluteFill>
);
