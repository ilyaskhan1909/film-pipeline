import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat01: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-006 — 35mm twilight horizon"} from={0} durationInFrames={124}>
      <CinematicShot image="assets/shot-006.png" frames={124} motion="hold" dissolve={8} />
    </Sequence>
    <Sequence name={"shot-007 — 65mm empty-chair detail"} from={124} durationInFrames={253}>
      <CinematicShot image="assets/shot-007.png" frames={253} motion="pan-left" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 01" file="assets/s0001.wav" frames={358} />
  </AbsoluteFill>
);
