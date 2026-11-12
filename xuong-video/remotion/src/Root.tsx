import {Composition} from 'remotion';
import {DosageBackground, DosagePreview} from './Composition';
import {KitElement,KitProps} from './kit/KitElement';
import kitSample from './kit/sample-props.json';
import {V6Preview,PreviewProps} from './preview/V6Preview';
import {FrameStyle,FrameStyleProps} from './frame-styles/FrameStyle';
import {Asset,AssetProps} from './assets/Asset';

const frameStyleDefault:FrameStyleProps={style:'clean',params:{border_px:8,color:'#FFFFFF'},canvas:[1080,1920],frames:1,enter_f:12,animated:false,
  boxes:[{box:[60,300,520,900],radius:40},{box:[560,300,1020,900],radius:40,label:{text:'NGƯỜI DÙNG THẬT',corner:'tl'}}]};
const previewDefault:PreviewProps={duration_f:30,main:{src:'main.mp4',w:1080,h:1920},main_moves:[],broll:[],graphics:[],mattes:[],subs:[],
  sub:{font_px:42,center_y:1425,color:'#FFFFFF',active:'#FFE14D',bg:'#000000',bg_alpha:0.55,pad_x:18,pad_y:8,radius:14,line_h:54}};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="KitElement" component={KitElement} defaultProps={kitSample as unknown as KitProps} durationInFrames={kitSample.frames} fps={30} width={1080} height={1920}
        calculateMetadata={({props})=>({durationInFrames:props.frames})}/>
      <Composition id="FrameStyle" component={FrameStyle} defaultProps={frameStyleDefault} durationInFrames={1} fps={30} width={1080} height={1920}
        calculateMetadata={({props})=>({durationInFrames:props.frames,width:props.canvas[0],height:props.canvas[1]})}/>
      <Composition id="Asset" component={Asset} defaultProps={{kind:'tick',width:52,height:52,params:{fill:'#1F9E46',mark:'#FFFFFF'}} as AssetProps} durationInFrames={1} fps={30} width={52} height={52}
        calculateMetadata={({props})=>({width:props.width,height:props.height})}/>
      <Composition id="V6Preview" component={V6Preview} defaultProps={previewDefault} durationInFrames={30} fps={30} width={1080} height={1920}
        calculateMetadata={({props})=>({durationInFrames:props.duration_f})}/>
      <Composition id="TC01-Dosage-Preview" component={DosagePreview} durationInFrames={38} fps={30} width={1080} height={1920}/>
      <Composition id="TC01-Dosage-Background" component={DosageBackground} durationInFrames={38} fps={30} width={1080} height={1920}/>
    </>
  );
};
