import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat13: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-037 — 65mm medium side close-up"} from={0} durationInFrames={217}>
      <CinematicShot image="assets/shot-037.png" frames={217} motion="pan-right" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-038 — 85mm close-up"} from={217} durationInFrames={158}>
      <CinematicShot image="assets/shot-038.png" frames={158} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 13" file="assets/s0013.wav" frames={363} />
  </AbsoluteFill>
);
