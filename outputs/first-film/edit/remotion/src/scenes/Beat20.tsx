import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat20: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-054 — 100mm blue-fabric macro"} from={0} durationInFrames={310}>
      <CinematicShot image="assets/shot-054.png" frames={310} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 20" file="assets/s0020.wav" frames={288} />
  </AbsoluteFill>
);
