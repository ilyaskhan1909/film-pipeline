import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat15: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-041 — 85mm quiet close-up"} from={0} durationInFrames={125}>
      <CinematicShot image="assets/shot-041.png" frames={125} motion="pan-right" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-042 — 35mm flashlight point of view"} from={125} durationInFrames={390}>
      <CinematicShot image="assets/shot-042.png" frames={390} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-043 — 24mm upward canopy"} from={515} durationInFrames={266}>
      <CinematicShot image="assets/shot-043.png" frames={266} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-044 — 50mm empty search trail"} from={781} durationInFrames={365}>
      <CinematicShot image="assets/shot-044.png" frames={365} motion="push-in" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 15" file="assets/s0015.wav" frames={1129} />
  </AbsoluteFill>
);
