import React from 'react';
import {AbsoluteFill} from 'remotion';
import {CinematicShot} from './CinematicShot';
import {FilmTitle} from './FilmTitle';

export const TitlePreview: React.FC = () => (
  <AbsoluteFill>
    <CinematicShot image="assets/shot-000.png" frames={144} motion="push-in" />
    <FilmTitle />
  </AbsoluteFill>
);
