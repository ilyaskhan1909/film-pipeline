import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat05: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-015 — 50mm medium side view"} from={0} durationInFrames={160}>
      <CinematicShot image="assets/shot-015.png" frames={160} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-016 — 85mm insert at fire level"} from={160} durationInFrames={198}>
      <CinematicShot image="assets/shot-016.png" frames={198} motion="push-in" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 05" file="assets/s0005.wav" frames={346} />
  </AbsoluteFill>
);
