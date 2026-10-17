import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat11: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-030 — 65mm medium detail"} from={0} durationInFrames={479}>
      <CinematicShot image="assets/shot-030.png" frames={479} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-032 — 85mm distant rear view"} from={479} durationInFrames={116}>
      <CinematicShot image="assets/shot-032.png" frames={116} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-033 — 65mm empty forest entrance"} from={595} durationInFrames={83}>
      <CinematicShot image="assets/shot-033.png" frames={83} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 11" file="assets/s0011.wav" frames={659} />
  </AbsoluteFill>
);
