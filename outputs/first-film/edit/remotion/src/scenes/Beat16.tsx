import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat16: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-046 — 85mm empty search frame"} from={0} durationInFrames={37}>
      <CinematicShot image="assets/shot-046.png" frames={37} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-045 — 65mm footsteps insert"} from={37} durationInFrames={130}>
      <CinematicShot image="assets/shot-045.png" frames={130} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 16" file="assets/s0016.wav" frames={150} />
  </AbsoluteFill>
);
