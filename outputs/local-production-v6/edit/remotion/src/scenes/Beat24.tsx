import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat24: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-063 — 100mm obscured effigy head"} from={0} durationInFrames={399}>
      <CinematicShot image="assets/shot-063.png" frames={399} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-064 — 24mm surrounded forest view"} from={399} durationInFrames={348}>
      <CinematicShot image="assets/shot-064.png" frames={348} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-066 — 100mm far campsite glow"} from={747} durationInFrames={175}>
      <CinematicShot image="assets/shot-066.png" frames={175} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 24" file="assets/s0024.wav" frames={903} />
  </AbsoluteFill>
);
