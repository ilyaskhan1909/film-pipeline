import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat22: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-059 — 100mm first tiny eye-glints"} from={0} durationInFrames={187}>
      <CinematicShot image="assets/shot-059.png" frames={187} motion="pan-left" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 22" file="assets/s0022.wav" frames={171} />
  </AbsoluteFill>
);
