import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat12: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-034 — 65mm absent camper chair"} from={0} durationInFrames={163}>
      <CinematicShot image="assets/shot-034.png" frames={163} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-035 — 50mm prolonged lake stillness"} from={163} durationInFrames={309}>
      <CinematicShot image="assets/shot-035.png" frames={309} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-036 — 85mm forest gap"} from={472} durationInFrames={138}>
      <CinematicShot image="assets/shot-036.png" frames={138} motion="push-in" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 12" file="assets/s0012.wav" frames={586} />
  </AbsoluteFill>
);
