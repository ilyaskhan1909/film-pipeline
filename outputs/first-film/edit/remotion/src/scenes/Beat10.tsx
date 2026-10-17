import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat10: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-028 — 100mm beer-can insert"} from={0} durationInFrames={162}>
      <CinematicShot image="assets/shot-028.png" frames={162} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-029 — 50mm medium side view"} from={162} durationInFrames={177}>
      <CinematicShot image="assets/shot-029.png" frames={177} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 10" file="assets/s0010.wav" frames={329} />
  </AbsoluteFill>
);
