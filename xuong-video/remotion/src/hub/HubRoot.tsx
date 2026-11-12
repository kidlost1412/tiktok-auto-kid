import React from 'react';
import {Composition} from 'remotion';
import {HubOverlay, HubProps} from './HubVideo';
import hubSample from './sample-props.json';

export const HubRoot: React.FC = () => (
  <Composition id="HubOverlay" component={HubOverlay} defaultProps={hubSample as unknown as HubProps} durationInFrames={30} fps={30} width={1080} height={1920}
    calculateMetadata={({props}) => ({durationInFrames: props.duration_f})}/>
);
