import React from 'react';
import {AbsoluteFill, CanvasImage, Easing, interpolate, staticFile, useCurrentFrame} from 'remotion';

type ShotProps = {
  image: string;
  frames: number;
  motion: 'push-in' | 'pan-left' | 'pan-right' | 'hold';
  dissolve?: number;
};

export const CinematicShot: React.FC<ShotProps> = ({image, frames, motion, dissolve = 0}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        overflow: 'hidden',
        backgroundColor: '#101A17',
        opacity: dissolve > 0 ? interpolate(frame, [0, dissolve], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1,
      }}
    >
      <CanvasImage
        src={staticFile(image)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          scale: motion === 'push-in'
            ? interpolate(frame, [0, Math.max(1, frames - 1)], [1.015, 1.075], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.linear, output: 'perceptual-scale'})
            : motion === 'hold' ? 1.015 : 1.06,
          translate: motion === 'pan-left'
            ? interpolate(frame, [0, Math.max(1, frames - 1)], ['18px 0px', '-18px 0px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
            : motion === 'pan-right'
              ? interpolate(frame, [0, Math.max(1, frames - 1)], ['-18px 0px', '18px 0px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
              : '0px 0px',
        }}
      />
    </AbsoluteFill>
  );
};
