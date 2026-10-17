import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {DryNarration} from '../DryNarration';
import {CinematicShot} from '../CinematicShot';
export const Beat09: React.FC = () => (
  <AbsoluteFill>
    <Sequence name={"shot-027 — 35mm low wide campsite"} from={0} durationInFrames={200}>
      <CinematicShot image="assets/shot-027.png" frames={200} motion="pan-left" dissolve={8} />
    </Sequence>
    <Sequence name={"shot-039 — 50mm first-person medium two-shot"} from={200} durationInFrames={795}>
      <CinematicShot image="assets/shot-039.png" frames={795} motion="pan-left" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-024 — 85mm northern shoreline"} from={995} durationInFrames={96}>
      <CinematicShot image="assets/shot-024.png" frames={96} motion="push-in" dissolve={0} />
    </Sequence>
    <Sequence name={"shot-025 — 65mm eastern shoreline"} from={1091} durationInFrames={177}>
      <CinematicShot image="assets/shot-025.png" frames={177} motion="pan-right" dissolve={0} />
    </Sequence>
    <DryNarration name="Dry narration 09" file="assets/s0009.wav" frames={1250} />
  </AbsoluteFill>
);
