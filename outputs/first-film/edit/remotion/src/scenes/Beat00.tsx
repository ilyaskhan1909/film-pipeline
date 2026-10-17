import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat00: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-000 — 24mm wide establishing shot"} from={0} durationInFrames={407}>
      <CinematicShot image="assets/shot-000.png" frames={407} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-001 — 35mm water-level landscape"} from={407} durationInFrames={253}>
      <CinematicShot image="assets/shot-001.png" frames={253} motion="pan-right" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-003 — 85mm long shot from shore"} from={660} durationInFrames={48}>
      <CinematicShot image="assets/shot-003.png" frames={48} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-004 — 85mm grill insert"} from={708} durationInFrames={117}>
      <CinematicShot image="assets/shot-004.png" frames={117} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-005 — 85mm fire insert"} from={825} durationInFrames={328}>
      <CinematicShot image="assets/shot-005.png" frames={328} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 00" file="assets/s0000.wav" frames={1137} />
  </AbsoluteFill>
);
