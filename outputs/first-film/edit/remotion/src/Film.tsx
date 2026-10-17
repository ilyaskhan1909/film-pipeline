import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CinematicShot} from './CinematicShot';
import {FilmTitle} from './FilmTitle';
import {FilmEnding} from './FilmEnding';
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
export const FILM_FRAMES = 16762;
export const Film: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: "#101A17"}}> 
    <Sequence name="Opening breath" from={0} durationInFrames={36}><CinematicShot image="assets/shot-000.png" frames={36} motion="hold" /></Sequence>
    <Sequence name="Time transition 01" from={1189} durationInFrames={8}><CinematicShot image="assets/shot-005.png" frames={8} motion="hold" /></Sequence>
    <Sequence name="Time transition 09" from={5357} durationInFrames={8}><CinematicShot image="assets/shot-023.png" frames={8} motion="hold" /></Sequence>
    <Sequence name="Beat 00" from={36} durationInFrames={1153}><Beat00 /></Sequence>
    <Sequence name="Beat 01" from={1189} durationInFrames={377}><Beat01 /></Sequence>
    <Sequence name="Beat 02" from={1566} durationInFrames={755}><Beat02 /></Sequence>
    <Sequence name="Beat 03" from={2321} durationInFrames={77}><Beat03 /></Sequence>
    <Sequence name="Beat 04" from={2398} durationInFrames={675}><Beat04 /></Sequence>
    <Sequence name="Beat 05" from={3073} durationInFrames={358}><Beat05 /></Sequence>
    <Sequence name="Beat 06" from={3431} durationInFrames={1132}><Beat06 /></Sequence>
    <Sequence name="Beat 07" from={4563} durationInFrames={454}><Beat07 /></Sequence>
    <Sequence name="Beat 08" from={5017} durationInFrames={340}><Beat08 /></Sequence>
    <Sequence name="Beat 09" from={5357} durationInFrames={1268}><Beat09 /></Sequence>
    <Sequence name="Beat 10" from={6625} durationInFrames={339}><Beat10 /></Sequence>
    <Sequence name="Beat 11" from={6964} durationInFrames={678}><Beat11 /></Sequence>
    <Sequence name="Beat 12" from={7642} durationInFrames={610}><Beat12 /></Sequence>
    <Sequence name="Beat 13" from={8252} durationInFrames={375}><Beat13 /></Sequence>
    <Sequence name="Beat 14" from={8627} durationInFrames={606}><Beat14 /></Sequence>
    <Sequence name="Beat 15" from={9233} durationInFrames={1146}><Beat15 /></Sequence>
    <Sequence name="Beat 16" from={10379} durationInFrames={167}><Beat16 /></Sequence>
    <Sequence name="Beat 17" from={10546} durationInFrames={759}><Beat17 /></Sequence>
    <Sequence name="Beat 18" from={11305} durationInFrames={272}><Beat18 /></Sequence>
    <Sequence name="Beat 19" from={11577} durationInFrames={940}><Beat19 /></Sequence>
    <Sequence name="Beat 20" from={12517} durationInFrames={310}><Beat20 /></Sequence>
    <Sequence name="Beat 21" from={12827} durationInFrames={711}><Beat21 /></Sequence>
    <Sequence name="Beat 22" from={13538} durationInFrames={187}><Beat22 /></Sequence>
    <Sequence name="Beat 23" from={13725} durationInFrames={1455}><Beat23 /></Sequence>
    <Sequence name="Beat 24" from={15180} durationInFrames={922}><Beat24 /></Sequence>
    <Sequence name="Beat 25" from={16102} durationInFrames={660}><Beat25 /></Sequence>
    <Sequence name="HyperFrames film title" from={0} durationInFrames={144}><FilmTitle /></Sequence>
    <FilmEnding frames={16762} />
  </AbsoluteFill>
);
