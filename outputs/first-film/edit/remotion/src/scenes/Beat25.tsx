import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat25: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-068 — 85mm remote camp view"} from={0} durationInFrames={265}>
      <CinematicShot image="assets/shot-068.png" frames={265} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-069 — 50mm final empty chairs"} from={265} durationInFrames={153}>
      <CinematicShot image="assets/shot-069.png" frames={153} motion="pan-right" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-070 — 85mm closing-water texture"} from={418} durationInFrames={242}>
      <CinematicShot image="assets/shot-070.png" frames={242} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 25" file="assets/s0025.wav" frames={588} />
  </AbsoluteFill>
);
