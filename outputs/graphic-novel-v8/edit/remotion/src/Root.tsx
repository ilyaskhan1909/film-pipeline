import React from 'react';
import {Composition, Folder} from 'remotion';
import {InkPilot} from './InkPilot';
import {CampConversation} from './scenes/CampConversation';
import {Departure} from './scenes/Departure';
import {ForestTrail} from './scenes/ForestTrail';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="InkPilot" component={InkPilot} durationInFrames={2127} fps={24} width={1920} height={1080} />
    <Folder name="Ink-scenes">
      <Composition id="CampConversation" component={CampConversation} durationInFrames={375} fps={24} width={1920} height={1080} />
      <Composition id="Departure" component={Departure} durationInFrames={606} fps={24} width={1920} height={1080} />
      <Composition id="ForestTrail" component={ForestTrail} durationInFrames={1146} fps={24} width={1920} height={1080} />
    </Folder>
  </>
);
