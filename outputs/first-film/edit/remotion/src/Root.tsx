import React from 'react';
import {Composition, Folder} from 'remotion';
import {Film} from './Film';
import {FinalFilm} from './FinalFilm';
import {Beat00} from './scenes/Beat00';
import {Beat01} from './scenes/Beat01';
import {Beat02} from './scenes/Beat02';
import {Beat03} from './scenes/Beat03';
import {Beat04} from './scenes/Beat04';
import {Beat05} from './scenes/Beat05';
import {Beat06} from './scenes/Beat06';
import {Beat07} from './scenes/Beat07';
import {Beat08} from './scenes/Beat08';
import {Beat09} from './scenes/Beat09';
import {Beat10} from './scenes/Beat10';
import {Beat11} from './scenes/Beat11';
import {Beat12} from './scenes/Beat12';
import {Beat13} from './scenes/Beat13';
import {Beat14} from './scenes/Beat14';
import {Beat15} from './scenes/Beat15';
import {Beat16} from './scenes/Beat16';
import {Beat17} from './scenes/Beat17';
import {Beat18} from './scenes/Beat18';
import {Beat19} from './scenes/Beat19';
import {Beat20} from './scenes/Beat20';
import {Beat21} from './scenes/Beat21';
import {Beat22} from './scenes/Beat22';
import {Beat23} from './scenes/Beat23';
import {Beat24} from './scenes/Beat24';
import {Beat25} from './scenes/Beat25';
export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Film" component={FinalFilm} durationInFrames={16762} fps={24} width={1920} height={1080} />
    <Composition id="Dry-Film" component={Film} durationInFrames={16762} fps={24} width={1920} height={1080} />
    <Folder name="Story-beats">
      <Composition id="Beat00" component={Beat00} durationInFrames={1153} fps={24} width={1920} height={1080} />
      <Composition id="Beat01" component={Beat01} durationInFrames={377} fps={24} width={1920} height={1080} />
      <Composition id="Beat02" component={Beat02} durationInFrames={755} fps={24} width={1920} height={1080} />
      <Composition id="Beat03" component={Beat03} durationInFrames={77} fps={24} width={1920} height={1080} />
      <Composition id="Beat04" component={Beat04} durationInFrames={675} fps={24} width={1920} height={1080} />
      <Composition id="Beat05" component={Beat05} durationInFrames={358} fps={24} width={1920} height={1080} />
      <Composition id="Beat06" component={Beat06} durationInFrames={1132} fps={24} width={1920} height={1080} />
      <Composition id="Beat07" component={Beat07} durationInFrames={454} fps={24} width={1920} height={1080} />
      <Composition id="Beat08" component={Beat08} durationInFrames={340} fps={24} width={1920} height={1080} />
      <Composition id="Beat09" component={Beat09} durationInFrames={1268} fps={24} width={1920} height={1080} />
      <Composition id="Beat10" component={Beat10} durationInFrames={339} fps={24} width={1920} height={1080} />
      <Composition id="Beat11" component={Beat11} durationInFrames={678} fps={24} width={1920} height={1080} />
      <Composition id="Beat12" component={Beat12} durationInFrames={610} fps={24} width={1920} height={1080} />
      <Composition id="Beat13" component={Beat13} durationInFrames={375} fps={24} width={1920} height={1080} />
      <Composition id="Beat14" component={Beat14} durationInFrames={606} fps={24} width={1920} height={1080} />
      <Composition id="Beat15" component={Beat15} durationInFrames={1146} fps={24} width={1920} height={1080} />
      <Composition id="Beat16" component={Beat16} durationInFrames={167} fps={24} width={1920} height={1080} />
      <Composition id="Beat17" component={Beat17} durationInFrames={759} fps={24} width={1920} height={1080} />
      <Composition id="Beat18" component={Beat18} durationInFrames={272} fps={24} width={1920} height={1080} />
      <Composition id="Beat19" component={Beat19} durationInFrames={940} fps={24} width={1920} height={1080} />
      <Composition id="Beat20" component={Beat20} durationInFrames={310} fps={24} width={1920} height={1080} />
      <Composition id="Beat21" component={Beat21} durationInFrames={711} fps={24} width={1920} height={1080} />
      <Composition id="Beat22" component={Beat22} durationInFrames={187} fps={24} width={1920} height={1080} />
      <Composition id="Beat23" component={Beat23} durationInFrames={1455} fps={24} width={1920} height={1080} />
      <Composition id="Beat24" component={Beat24} durationInFrames={922} fps={24} width={1920} height={1080} />
      <Composition id="Beat25" component={Beat25} durationInFrames={660} fps={24} width={1920} height={1080} />
    </Folder>
  </>
);
