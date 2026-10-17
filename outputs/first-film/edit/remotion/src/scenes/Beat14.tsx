import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat14: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-039 — 50mm first-person medium two-shot"} from={0} durationInFrames={357}>
      <CinematicShot image="assets/shot-039.png" frames={357} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-040 — 35mm environmental cutaway"} from={357} durationInFrames={249}>
      <CinematicShot image="assets/shot-040.png" frames={249} motion="push-in" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 14" file="assets/s0014.wav" frames={594} />
  </AbsoluteFill>
);
