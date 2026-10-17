import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CampConversation} from './scenes/CampConversation';
import {Departure} from './scenes/Departure';
import {ForestTrail} from './scenes/ForestTrail';

// Original beats 13–15, frames 8252–10378. This is a style pilot, not a full-film remake.
export const InkPilot: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#080c12', overflow: 'hidden'}}>
    <Sequence name="13 — Camp conversation" from={0} durationInFrames={375}>
      <CampConversation />
    </Sequence>
    <Sequence name="14 — Departure" from={375} durationInFrames={606}>
      <Departure />
    </Sequence>
    <Sequence name="15 — Forest trail" from={981} durationInFrames={1146}>
      <ForestTrail />
    </Sequence>
  </AbsoluteFill>
);
