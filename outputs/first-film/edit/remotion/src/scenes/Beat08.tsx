import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat08: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-022 — 50mm seated lake view"} from={0} durationInFrames={258}>
      <CinematicShot image="assets/shot-022.png" frames={258} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-023 — 85mm reaction close-up"} from={258} durationInFrames={82}>
      <CinematicShot image="assets/shot-023.png" frames={82} motion="pan-left" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 08" file="assets/s0008.wav" frames={327} />
  </AbsoluteFill>
);
