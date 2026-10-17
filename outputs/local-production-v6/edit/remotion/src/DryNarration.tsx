import React, {createContext, useContext} from 'react';
import {staticFile} from 'remotion';
import {Audio} from '@remotion/media';

export const NarrationContext = createContext(true);

export const DryNarration: React.FC<{file: string; frames: number; name: string}> = ({file, frames, name}) => {
  const enabled = useContext(NarrationContext);
  if (!enabled) return null;
  return <Audio name={name} src={staticFile(file)} from={0} durationInFrames={frames} volume={1} />;
};
