import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat23: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-060 — 35mm restrained crowd reveal"} from={0} durationInFrames={503}>
      <CinematicShot image="assets/shot-060.png" frames={503} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-064 — 24mm surrounded forest view"} from={503} durationInFrames={168}>
      <CinematicShot image="assets/shot-064.png" frames={168} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-063 — 100mm obscured effigy head"} from={671} durationInFrames={528}>
      <CinematicShot image="assets/shot-063.png" frames={528} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-062 — 100mm wooden hand and ONE doll"} from={1199} durationInFrames={256}>
      <CinematicShot image="assets/shot-062.png" frames={256} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 23" file="assets/s0023.wav" frames={1433} />
  </AbsoluteFill>
);
