import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat04: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-014 — 100mm ember insert"} from={0} durationInFrames={331}>
      <CinematicShot image="assets/shot-014.png" frames={331} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-036 — 85mm forest gap"} from={331} durationInFrames={50}>
      <CinematicShot image="assets/shot-036.png" frames={50} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-033 — 65mm empty forest entrance"} from={381} durationInFrames={294}>
      <CinematicShot image="assets/shot-033.png" frames={294} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 04" file="assets/s0004.wav" frames={657} />
  </AbsoluteFill>
);
