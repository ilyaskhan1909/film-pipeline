import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat19: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-051 — 65mm full doll close-up"} from={0} durationInFrames={401}>
      <CinematicShot image="assets/shot-051.png" frames={401} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-052 — 100mm doll-face macro"} from={401} durationInFrames={164}>
      <CinematicShot image="assets/shot-052.png" frames={164} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-053 — 100mm hands and cloth insert"} from={565} durationInFrames={375}>
      <CinematicShot image="assets/shot-053.png" frames={375} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 19" file="assets/s0019.wav" frames={926} />
  </AbsoluteFill>
);
