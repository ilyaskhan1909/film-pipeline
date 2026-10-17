import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat21: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-056 — 35mm escape route"} from={0} durationInFrames={202}>
      <CinematicShot image="assets/shot-056.png" frames={202} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-057 — 50mm off-axis forest view"} from={202} durationInFrames={241}>
      <CinematicShot image="assets/shot-057.png" frames={241} motion="pan-right" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-058 — 85mm forest-edge suspense"} from={443} durationInFrames={268}>
      <CinematicShot image="assets/shot-058.png" frames={268} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 21" file="assets/s0021.wav" frames={701} />
  </AbsoluteFill>
);
