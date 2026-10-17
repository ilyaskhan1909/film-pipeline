import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

export const FilmEnding: React.FC<{frames: number}> = ({frames}) => {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{
    backgroundColor: '#000',
    opacity: interpolate(frame, [frames - 36, frames - 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    pointerEvents: 'none',
  }} />;
};
