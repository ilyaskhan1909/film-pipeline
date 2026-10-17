import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat02: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-008 — 70mm twilight landscape"} from={0} durationInFrames={206}>
      <CinematicShot image="assets/shot-008.png" frames={206} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-009 — 24mm wide shore view"} from={206} durationInFrames={213}>
      <CinematicShot image="assets/shot-009.png" frames={213} motion="pan-right" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-010 — 85mm compressed lake detail"} from={419} durationInFrames={336}>
      <CinematicShot image="assets/shot-010.png" frames={336} motion="hold" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 02" file="assets/s0002.wav" frames={736} />
  </AbsoluteFill>
);
