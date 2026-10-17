import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat06: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-017 — 85mm candid close-up"} from={0} durationInFrames={284}>
      <CinematicShot image="assets/shot-017.png" frames={284} motion="pan-right" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-018 — 35mm lakeside point of view"} from={284} durationInFrames={268}>
      <CinematicShot image="assets/shot-018.png" frames={268} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-019 — 65mm restrained reaction close-up"} from={552} durationInFrames={580}>
      <CinematicShot image="assets/shot-019.png" frames={580} motion="pan-left" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 06" file="assets/s0006.wav" frames={1116} />
  </AbsoluteFill>
);
