import React from 'react';
import {Video} from '@remotion/media';
import {AbsoluteFill, staticFile} from 'remotion';

// This alpha-preserving overlay is authored in the sibling HyperFrames project.
export const FilmTitle: React.FC = () => (
  <AbsoluteFill style={{zIndex: 1}}>
    <Video
    name="The Last Firework title"
    src={staticFile('title.webm')}
    from={0}
    trimBefore={0}
    durationInFrames={144}
    muted
    style={{width: '100%', height: '100%'}}
    />
  </AbsoluteFill>
);
