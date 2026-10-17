import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat17: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-046 — 85mm empty search frame"} from={0} durationInFrames={180}>
      <CinematicShot image="assets/shot-046.png" frames={180} motion="hold" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-047 — 50mm discovery shot at ground level"} from={180} durationInFrames={276}>
      <CinematicShot image="assets/shot-047.png" frames={276} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-048 — 35mm old-oak establishing"} from={456} durationInFrames={60}>
      <CinematicShot image="assets/shot-048.png" frames={60} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-049 — 85mm absence insert"} from={516} durationInFrames={243}>
      <CinematicShot image="assets/shot-049.png" frames={243} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 17" file="assets/s0017.wav" frames={740} />
  </AbsoluteFill>
);
