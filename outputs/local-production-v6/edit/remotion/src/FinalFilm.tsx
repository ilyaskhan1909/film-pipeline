import React from 'react';
import {AbsoluteFill, staticFile} from 'remotion';
import {Audio} from '@remotion/media';
import {Film, FILM_FRAMES} from './Film';
import {NarrationContext} from './DryNarration';

export const FinalFilm: React.FC = () => (
  <NarrationContext.Provider value={false}>
    <AbsoluteFill>
      <Film />
      <Audio name="48k stereo final master" src={staticFile('sound/master.wav')} from={0} durationInFrames={FILM_FRAMES} volume={1} />
    </AbsoluteFill>
  </NarrationContext.Provider>
);
